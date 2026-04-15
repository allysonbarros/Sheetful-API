# 0001 — Offloading do gspread bloqueante para thread pool

**Prioridade:** P0  **Breaking:** Não

## Contexto

Todas as funções públicas de `GoogleSheetsService` em `app/services/sheets.py` são `async def`, assim como os handlers em `app/api/sheets.py`. Porém, `gspread` é uma biblioteca **síncrona e bloqueante** (internamente usa `requests`). Exemplos:

- `app/services/sheets.py:103` — `client.open_by_key(document_id)` é sync.
- `app/services/sheets.py:217` — `worksheet.get_all_records()` é sync.
- `app/services/sheets.py:434` — `worksheet.update_cell(...)` é sync.

Nenhuma chamada está dentro de `await asyncio.to_thread(...)`, `loop.run_in_executor(...)` ou similar.

## Problema

Cada request trava o event loop da FastAPI pela duração inteira da chamada à Google API (tipicamente 500 ms–3 s). Com um único worker uvicorn, isso equivale a throughput serial: um único cliente lento bloqueia *todos* os outros, inclusive `/health`. O `async def` dá a ilusão de concorrência sem entregá-la — na prática o comportamento é **pior** que usar rotas síncronas, pois a FastAPI executaria rotas `def` (não `async def`) em thread pool automaticamente.

## Proposta

1. Criar um helper interno em `app/services/sheets.py`:

   ```python
   import asyncio
   from functools import partial
   from typing import Callable, TypeVar

   T = TypeVar("T")

   async def _run_sync(func: Callable[..., T], *args, **kwargs) -> T:
       return await asyncio.to_thread(partial(func, *args, **kwargs))
   ```

2. Envolver **toda** chamada a `gspread` ou à Google API por `await _run_sync(...)`. Especificamente em `GoogleSheetsService`:
   - `_get_client` (contém `gspread.authorize` / `gspread.api_key`).
   - `get_document` → `client.open_by_key`.
   - `get_sheet` → `get_worksheet_by_id`, `get_worksheet`, `worksheet`.
   - `_get_safe_headers` → `worksheet.row_values`, `worksheet.row_count`.
   - `_get_all_records_safe` → `worksheet.get_all_records`, `worksheet.get_all_values`.
   - `update_row`, `update_rows_bulk` → `worksheet.update_cell`.
   - `create_row`, `create_rows_bulk` → `worksheet.append_row`, `worksheet.append_rows`.
   - `get_sheet_info` → acessos a `.id`, `.title`, `.index`, `.row_count`, `.col_count` (esses são puramente atributos locais e *não* precisam de offload — verificar com o código do gspread).

3. Documentar no docstring do módulo que toda I/O síncrona deve passar por `_run_sync`.

## Critérios de aceitação

- Nenhuma chamada direta a métodos de `gspread` ou `Google*` fora de `_run_sync`, verificável via grep (`gspread\.` e `worksheet\.[a-z_]+(` fora do helper).
- Um teste de carga simples (ex.: `httpx.AsyncClient` disparando 20 requests concorrentes a `/{doc}/{sheet}` com um serviço mockado que dorme 1 s) conclui em ~1 s e não em ~20 s.
- Teste unitário garantindo que `_run_sync` propaga exceções do callable síncrono.

## Fora de escopo

- Migração para `gspread-asyncio` ou chamada direta à Google API — maior e pode ser feita depois, isoladamente.
- Cache de cliente/documento (ver spec 0003/futura spec de caching).
- Pool de thread customizado — o default do `asyncio.to_thread` (via `ThreadPoolExecutor` padrão) basta.

## Riscos / impacto

- `asyncio.to_thread` exige Python 3.9+ (o projeto usa 3.11, OK).
- Aumento marginal de uso de memória pelo pool de threads sob concorrência alta.
- Erros capturados dentro do thread aparecem no caller como a exceção original, sem modificação — não afeta o tratamento de `HTTPException` existente.
