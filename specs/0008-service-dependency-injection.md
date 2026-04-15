# 0008 — Injetar `GoogleSheetsService` via `Depends`

**Prioridade:** P2  **Breaking:** Não

## Contexto

`app/services/sheets.py:566` define um singleton módulo-level:

```python
sheets_service = GoogleSheetsService()
```

Handlers importam e usam diretamente:

```python
from app.services import sheets_service
...
rows = await sheets_service.get_sheet_rows(worksheet, options)
```

## Problema

- Testes precisam de `monkeypatch.setattr` em atributos do singleton para substituir comportamento. Funciona, mas é frágil — ordem de importação importa e é fácil de vazar estado entre testes.
- Não dá para ter configurações diferentes do service por contexto (ex.: timeouts menores em health checks).
- Ciclo de vida é implícito e ligado ao módulo.

## Proposta

### 8.1. Factory + `Depends`

```python
# app/services/sheets.py
def get_sheets_service() -> GoogleSheetsService:
    return _sheets_service_instance   # ainda um singleton, mas via função

_sheets_service_instance = GoogleSheetsService()
```

### 8.2. Handlers passam a depender

```python
from fastapi import Depends
from app.services.sheets import GoogleSheetsService, get_sheets_service

@router.get("/{document_id}/{sheet_id}")
async def get_rows(
    ...,
    svc: GoogleSheetsService = Depends(get_sheets_service),
):
    document, worksheet = await get_worksheet_from_ids(..., svc=svc)
    rows = await svc.get_sheet_rows(worksheet, options)
```

`app/api/utils.py::get_worksheet_from_ids` recebe o `svc` como parâmetro também.

### 8.3. Testes

```python
def test_get_rows(api_client, mock_service):
    app.dependency_overrides[get_sheets_service] = lambda: mock_service
    response = api_client.get("/doc/0")
    assert response.status_code == 200
```

Depois: `app.dependency_overrides.clear()` em fixture teardown.

## Critérios de aceitação

- Nenhum handler importa `sheets_service` diretamente — sempre via `Depends`.
- Testes usam `app.dependency_overrides` em vez de `monkeypatch`.
- `grep "from app.services import sheets_service"` retorna zero.

## Fora de escopo

- Criar um service novo por request (custo alto sem benefício atual).
- Escopo por request para o gspread client.

## Riscos / impacto

- Mudança mecânica em todos os handlers. Baixo risco.
- Integra limpamente com spec 0002 (testes).
