# 0011 — Cache de clientes gspread e documentos por token

**Prioridade:** P2  **Breaking:** Não

## Contexto

`GoogleSheetsService._get_client` em `app/services/sheets.py:91` é chamado **toda vez** que um handler precisa autenticar contra o Google:

```python
def _get_client(self, access_token: Optional[str] = None) -> gspread.Client:
    if access_token:
        credentials = Credentials(token=access_token)
        return gspread.authorize(credentials)
    elif settings.GOOGLE_API_KEY:
        return gspread.api_key(settings.GOOGLE_API_KEY)
```

`_get_document_sync` em `app/services/sheets.py:190` sempre chama `client.open_by_key(document_id)` depois:

```python
client = self._get_client(access_token)
document = client.open_by_key(document_id)
```

`gspread.authorize(Credentials(token=...))` constrói um cliente novo (nova sessão HTTP, nova instância de `http.client`). `client.open_by_key(document_id)` dispara uma chamada à Sheets API para recuperar metadados do documento.

Depois das specs 0003 e 0004, uma leitura paginada chega a custar:
1. Construir `gspread.Client` (setup de HTTPS session, cache TTL de tokens internos do google-auth).
2. `open_by_key` — 1 chamada à Sheets API (~200–400 ms).
3. `_get_safe_headers` — 1 chamada (`row_values(1)`).
4. `worksheet.get(range)` — 1 chamada.

Os passos 1 e 2 **repetem em cada request**, mesmo quando o mesmo cliente chama `GET /{doc}/{sheet}` 100 vezes com o mesmo token.

## Problema

- **Latência**: ~50% do tempo de um endpoint simples é gasto em trabalho redundante de auth + `open_by_key`.
- **Custo de quota Google**: `open_by_key` conta como leitura de metadata.
- **Throughput**: sob carga, cada worker uvicorn sequencialmente abre sessão HTTPS do zero.

Spec 0001 (offloading para thread pool) resolveu o problema de **bloqueio**, mas não o de **trabalho repetido**.

## Proposta

### 11.1. Dois caches TTL, chaveados por hash do token

Adicionar em `app/services/sheets.py` dois `cachetools.TTLCache` (ou equivalente) protegidos por `threading.Lock`:

```python
import hashlib
import threading
from cachetools import TTLCache

_CLIENT_CACHE_TTL_SECONDS = 300   # 5 minutes
_DOCUMENT_CACHE_TTL_SECONDS = 60  # 1 minute
_CLIENT_CACHE_MAXSIZE = 256
_DOCUMENT_CACHE_MAXSIZE = 1024

def _auth_cache_key(access_token: Optional[str]) -> str:
    """
    Produce a stable, non-reversible key for an auth method.

    Never use the raw token as a dict key: we don't want plaintext
    tokens sitting in process memory any longer than necessary, and
    we don't want them appearing in tracebacks / repr output.
    """
    if access_token:
        return "oauth:" + hashlib.sha256(access_token.encode()).hexdigest()
    return "apikey"

_client_cache: "TTLCache[str, gspread.Client]" = TTLCache(
    maxsize=_CLIENT_CACHE_MAXSIZE, ttl=_CLIENT_CACHE_TTL_SECONDS
)
_client_lock = threading.Lock()

_document_cache: "TTLCache[Tuple[str, str], Spreadsheet]" = TTLCache(
    maxsize=_DOCUMENT_CACHE_MAXSIZE, ttl=_DOCUMENT_CACHE_TTL_SECONDS
)
_document_lock = threading.Lock()
```

### 11.2. Cache-aware `_get_client`

```python
def _get_client(self, access_token: Optional[str] = None) -> gspread.Client:
    key = _auth_cache_key(access_token)
    with _client_lock:
        cached = _client_cache.get(key)
        if cached is not None:
            return cached

    # Authenticate outside the lock to avoid serializing all requests.
    client = self._build_client(access_token)

    with _client_lock:
        _client_cache[key] = client
    return client

def _build_client(self, access_token: Optional[str]) -> gspread.Client:
    # The previous body of _get_client — actually performs authorization.
    ...
```

### 11.3. Cache-aware `_get_document_sync`

```python
def _get_document_sync(
    self, document_id: str, access_token: Optional[str] = None
) -> Spreadsheet:
    key = (_auth_cache_key(access_token), document_id)
    with _document_lock:
        cached = _document_cache.get(key)
        if cached is not None:
            return cached

    client = self._get_client(access_token)
    try:
        document = client.open_by_key(document_id)
    except Exception as e:
        # If auth failed, drop the client so the next request rebuilds it.
        logger.error(f"Error accessing document {document_id}: {str(e)}")
        self._invalidate_client(access_token)
        raise HTTPException(
            status_code=400,
            detail=f"Cannot access Google document '{document_id}'",
        )

    with _document_lock:
        _document_cache[key] = document
    return document

def _invalidate_client(self, access_token: Optional[str]) -> None:
    key = _auth_cache_key(access_token)
    with _client_lock:
        _client_cache.pop(key, None)
    # Drop every cached document that used this auth as well.
    prefix = key
    with _document_lock:
        stale = [k for k in _document_cache if k[0] == prefix]
        for k in stale:
            _document_cache.pop(k, None)
```

### 11.4. Invalidação em 401

`_get_safe_headers`, `_get_all_records_safe`, `get_sheet_rows_paginated`, etc., devem converter falhas de auth em `HTTPException(401)` e limpar o cache do cliente antes de propagar, para que o próximo request reautentique com um token fresco.

Um decorator helper mantém isso DRY:

```python
def _with_auth_invalidation(func):
    """Wrap a sync method so that Google auth failures drop the cache."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except google.auth.exceptions.RefreshError:
            # Access token expired/revoked. Drop cache and surface 401.
            ...
    return wrapper
```

Fora do escopo desta spec se ficar muito grande — o caminho simples é invalidação explícita em `_get_document_sync` cobrindo 90% dos casos.

### 11.5. Dependência

Adicionar `cachetools==5.*` ao `requirements.txt`. Mantém a implementação simples e evita escrever uma TTLCache manual com expiração lazy.

### 11.6. Métrica / observabilidade

Emitir um `logger.debug` em hit vs miss para cada cache. Opcionalmente expor contadores via `/ready` ou um endpoint `/internal/cache` se a spec 0010 for estendida. Fora do escopo desta spec.

## Critérios de aceitação

- Duas chamadas consecutivas a `GET /{doc}/{sheet}` com o mesmo `x-google-access-token` disparam **no máximo 1** `gspread.authorize` + 1 `open_by_key` (medido via mock).
- `_get_client` chamado concorrentemente por N threads com o mesmo token produz **no máximo 1** construção de cliente (proteção com lock testada).
- Mock de `open_by_key` lançando `RefreshError` na primeira chamada: a chamada seguinte com o mesmo token tenta reautenticar do zero (não reusa cache).
- Cache expira após `_CLIENT_CACHE_TTL_SECONDS` (teste usando `freezegun` ou `time.monotonic` monkeypatch).
- Nenhum token aparece em chave de cache, repr de objeto, ou log — apenas o SHA-256 prefixado por `oauth:`.
- `ci-test` continua verde.

## Fora de escopo

- **Refresh token automático**: a API recebe access tokens Bearer de curto prazo; clientes são responsáveis por renová-los. Não vamos orquestrar refresh.
- **Cache distribuído** (Redis/memcached): desnecessário para um único processo uvicorn; adicionar spec própria se escalar horizontalmente.
- **Cache de worksheets individuais** ou de leituras paginadas: risco alto de stale reads, não vale o ganho. Usuários que precisam de consistência forte não vão querer.
- **Métricas Prometheus** dos caches.

## Riscos / impacto

- **Tokens em memória mais tempo**: o `gspread.Client` retém o token nas credenciais internas. O hash protege a *chave* do dict mas não o valor. Mitigação: TTL curto (5 min) e `_invalidate_client` em erro de auth.
- **Vazamento cross-tenant**: o pior bug possível seria dois usuários distintos compartilharem cliente. O hash SHA-256 full do token como prefixo elimina colisão na prática. Teste explícito garantindo que tokens diferentes produzem chaves diferentes.
- **Stale document metadata**: se alguém renomeia uma aba ou muda permissões, podemos servir metadata antiga por até 60 s. Aceitável para read-heavy APIs; documentar.
- **Memória**: `maxsize=256` clientes + `1024` documentos é teto hard. LRU evict do `cachetools.TTLCache` cobre o resto.
- **Threads e locks**: `asyncio.to_thread` já usa um thread pool, então `threading.Lock` é o primitive certo. Contenção deve ser baixa porque crítica é só 2 dict ops.

## Dependências com outras specs

- **Depende de 0001** (thread pool) — sem ele não faz sentido usar `threading.Lock`.
- **Depende de 0008** (DI) — facilita testes substituindo o service com caches isolados.
- **Interage com 0005** (error redaction) — `_invalidate_client` precisa rodar *antes* que o handler centralizado receba a exceção.
