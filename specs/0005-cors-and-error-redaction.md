# 0005 — CORS configurável e redação de erros

**Prioridade:** P1  **Breaking:** Sim (CORS default muda)

## Contexto

**CORS** em `app/config.py:35` e `app/main.py:49-55`:

```python
ALLOWED_ORIGINS: list = ["*"]  # Configure this for production

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Erros** em `app/api/sheets.py`, repetido em todos os handlers:

```python
except Exception as e:
    logger.error(f"Error getting rows: {str(e)}")
    raise HTTPException(
        status_code=500,
        detail=f"Internal server error: {str(e)}"
    )
```

E em `app/services/sheets.py`:

```python
raise HTTPException(
    status_code=400,
    detail=f"Cannot access Google document '{document_id}': {str(e)}"
)
```

## Problema

**CORS**:
- A combinação `allow_origins=["*"]` + `allow_credentials=True` é inválida pela spec de CORS (MDN, RFC). Navegadores modernos rejeitam silenciosamente o `Access-Control-Allow-Origin` quando credenciais estão habilitadas — o middleware do Starlette tenta mitigar ecoando o Origin, mas isso anula qualquer defesa real.
- Hardcoded no código, sem override via env.

**Erros**:
- `str(e)` em `HTTPException.detail` vaza: mensagens do Google (que podem conter tokens reduzidos, identificadores internos), paths de arquivos, tracebacks de bibliotecas, etc.
- Cada handler duplica o mesmo try/except. Cinco handlers, cinco blocos idênticos.
- Não há request ID para correlacionar log interno (com o erro verdadeiro) e resposta ao cliente (que deveria receber só um ID opaco).

## Proposta

### 5.1. CORS via env

Em `app/config.py`:

```python
ALLOWED_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
ALLOW_CREDENTIALS: bool = os.getenv("ALLOW_CREDENTIALS", "false").lower() == "true"
```

Validação em `validate_config`:

```python
if self.ALLOW_CREDENTIALS and "*" in self.ALLOWED_ORIGINS:
    raise ValueError(
        "ALLOWED_ORIGINS=* is incompatible with ALLOW_CREDENTIALS=true"
    )
if not self.ALLOWED_ORIGINS:
    # default seguro: bloquear tudo exceto same-origin
    self.ALLOWED_ORIGINS = []
```

Atualizar `.env.example` com `ALLOWED_ORIGINS=http://localhost:3000` e `ALLOW_CREDENTIALS=false`.

### 5.2. Exception handlers centralizados

Criar `app/api/errors.py`:

```python
import logging
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException

logger = logging.getLogger(__name__)

async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    error_id = str(uuid.uuid4())
    logger.exception("Unhandled error [%s] on %s %s", error_id, request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "message": "Internal server error",
            "status": 500,
            "error_id": error_id,
        },
    )

async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "message": exc.detail if isinstance(exc.detail, str) else "Error",
            "status": exc.status_code,
        },
    )

def register(app: FastAPI) -> None:
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
```

Registrar em `app/main.py:create_app` via `errors.register(app)`.

### 5.3. Remover try/except duplicado dos handlers

Em `app/api/sheets.py`, todos os blocos `try/except HTTPException/Exception` passam a ser só:

```python
document, worksheet = await get_worksheet_from_ids(...)
rows = await sheets_service.get_sheet_rows(worksheet, options)
log_success(...)
return rows
```

Os exception handlers centralizados cuidam do resto.

### 5.4. Sanitizar erros do service

Mensagens como `f"Cannot access Google document '{document_id}': {str(e)}"` devem virar `"Cannot access Google document"` e logar o detalhe separadamente via `logger.error(..., exc_info=True)`.

## Critérios de aceitação

- `.env` com `ALLOWED_ORIGINS=*` + `ALLOW_CREDENTIALS=true` faz o app falhar no boot com mensagem clara.
- Default em dev (sem override) usa `ALLOWED_ORIGINS=[]` e `ALLOW_CREDENTIALS=false`.
- Request que gera exceção inesperada devolve JSON com `error_id` mas **sem** `str(e)`.
- Log interno contém traceback completo associado ao mesmo `error_id`.
- Handlers em `app/api/sheets.py` não têm mais `try/except Exception`.
- Teste verifica que uma rota levantando `RuntimeError` retorna 500 sem vazamento da mensagem.

## Fora de escopo

- Rate limiting.
- Autenticação de aplicação (diferente de repasse do token Google).
- Correlation ID em todos os logs (parcial nesta spec; full é spec 0010).

## Riscos / impacto

- **Breaking change** para qualquer cliente web que hoje depende do CORS aberto. Documentar no CHANGELOG / release notes.
- Mudança no shape do erro: clientes que hoje parseiam `detail` recebem `message`. Aceitável, mas comunicar.
