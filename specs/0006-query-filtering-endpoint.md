# 0006 — Expor filtro `query` no endpoint de leitura

**Prioridade:** P2  **Breaking:** Não

## Contexto

- `SheetGetRowsOptions` em `app/models.py:71-98` define um campo `query: Optional[Dict[str, str]]`.
- `GoogleSheetsService._apply_filters` em `app/services/sheets.py:304-326` implementa igualdade string por chave (AND entre chaves).
- **Nenhuma rota preenche `query`**: em `app/api/sheets.py:64`, o handler cria `SheetGetRowsOptions(offset=offset, limit=limit)` e o `query` nunca é passado.
- O README em `README.md:7` lista "Filtering: Query parameters for filtering data" como feature.

## Problema

Feature documentada e parcialmente implementada no serviço, mas **sem caminho até o cliente**. README está enganoso.

## Proposta

### 6.1. Decisão de API

Duas opções:

**Opção A — Query params genéricos (escolhida)**:

```
GET /{doc}/{sheet}?offset=0&limit=50&filter[status]=active&filter[city]=SP
```

Usa a sintaxe `filter[<coluna>]=<valor>` que a FastAPI pode parsear via `Request.query_params` (não nativamente via `Query`). Simples, sem colisão com `offset`/`limit`.

**Opção B — Um único param `q` em JSON**:

```
GET /{doc}/{sheet}?q={"status":"active"}
```

Mais feio e exige URL-encoding.

**Escolha: A.**

### 6.2. Handler

Adicionar em `app/api/sheets.py:get_rows`:

```python
from fastapi import Request

async def get_rows(
    request: Request,
    document_id: str = Path(...),
    sheet_id: str = Path(...),
    x_google_access_token: Optional[str] = Header(None, alias="x-google-access-token"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    filters = {
        key[len("filter["):-1]: value
        for key, value in request.query_params.multi_items()
        if key.startswith("filter[") and key.endswith("]")
    }
    options = SheetGetRowsOptions(
        offset=offset,
        limit=limit,
        query=filters or None,
    )
    ...
```

### 6.3. Semântica de filtro

Manter exatamente o que `_apply_filters` já faz: igualdade case-sensitive entre `str(record[key])` e `value`, AND entre múltiplas chaves. Documentar explicitamente:

- Sem `LIKE`, sem regex, sem ranges.
- Sem `OR`.
- Filtro em colunas inexistentes nunca casa (retorna lista vazia).

Se alguém quiser mais tarde, abrir spec separada.

### 6.4. Interação com spec 0003 (paginação server-side)

Quando `query` é não-vazio, a rota cai no caminho lento (ler tudo → filtrar → paginar). Isto já está previsto na spec 0003. Documentar no OpenAPI que `filter[...]` implica desabilitar a otimização de range.

### 6.5. Atualizar README

Seção nova em `README.md` "Filtering", com exemplo curl.

## Critérios de aceitação

- `GET /{doc}/{sheet}?filter[name]=John` passa `{"name": "John"}` para `SheetGetRowsOptions.query`.
- Múltiplos filtros são combinados com AND.
- Chaves sem `filter[...]` são ignoradas.
- Teste de integração cobre: sem filtro, um filtro, múltiplos filtros, filtro com chave inexistente.
- Swagger UI documenta o parâmetro `filter` (via `openapi_extra` no handler se necessário — aceitar que `Request` cru não aparece lindo no schema).

## Fora de escopo

- Operadores `>`, `<`, `LIKE`, `IN`.
- Combinação `OR`.
- Filtro via POST body.

## Riscos / impacto

- `Request` cru faz o schema OpenAPI do parâmetro ficar menos bonito — aceitar.
- Se o cliente passa `filter[offset]=...` por engano, vai virar filtro de coluna `offset`. Documentar.
