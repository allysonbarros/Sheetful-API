# 0009 — Abstrair a convenção de indexação de linhas

**Prioridade:** P2  **Breaking:** Não

## Contexto

O mapeamento entre o `row_id` 0-based exposto pela API e o número de linha 1-based do Google Sheets aparece solto no código:

- `app/services/sheets.py:428` — `actual_row_number = row_id + 2  # 1-indexing + header`
- `app/services/sheets.py:509` — `actual_row_number = start_row_id + i + 2`

A constante `+2` assume:

1. Exatamente uma linha de header.
2. Header na linha 1.
3. Sem linhas congeladas extras.
4. Sem merged cells no topo.

## Problema

Repetir `+2` em múltiplos pontos convida inconsistências. Qualquer mudança na convenção (ex.: permitir offset de header configurável) exige caçar todas as ocorrências. A spec 0003 (paginação) e a spec 0004 (batch updates) vão introduzir *mais* pontos com esse cálculo.

## Proposta

### 9.1. Helper único

```python
# app/services/sheets.py
HEADER_ROW_COUNT = 1  # constante nomeada

def _api_row_to_sheet_row(api_row_id: int) -> int:
    """Convert 0-based API row index to 1-based sheet row number."""
    return api_row_id + HEADER_ROW_COUNT + 1

def _sheet_row_to_api_row(sheet_row: int) -> int:
    return sheet_row - HEADER_ROW_COUNT - 1

def _col_index_to_letter(col_index: int) -> str:
    """1-based column index to A1 letter (1→A, 27→AA)."""
    result = ""
    while col_index > 0:
        col_index, remainder = divmod(col_index - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result
```

### 9.2. Substituição mecânica

Em todos os métodos de `GoogleSheetsService`, trocar aritmética solta por chamadas aos helpers. Em especial:

- `update_row` — `actual_row_number = _api_row_to_sheet_row(row_id)`
- `update_rows_bulk` — `actual_row_number = _api_row_to_sheet_row(start_row_id + i)`
- Os helpers novos da spec 0003 e 0004 (paginação e batch) usam os mesmos.

### 9.3. Documentar

Adicionar ao docstring do módulo `app/services/sheets.py`:

> Row indexing convention: the API exposes 0-based indices excluding the header. Internal gspread calls use 1-based indices. Always use `_api_row_to_sheet_row` and `_sheet_row_to_api_row` to convert — never compute `+2` inline.

## Critérios de aceitação

- `grep "+ 2" app/services/sheets.py` retorna zero ocorrências relacionadas a row indexing.
- Testes cobrem `_api_row_to_sheet_row(0) == 2`, `_api_row_to_sheet_row(5) == 7`.
- Testes cobrem `_col_index_to_letter(1) == "A"`, `_col_index_to_letter(26) == "Z"`, `_col_index_to_letter(27) == "AA"`.
- Nenhuma mudança de comportamento observável.

## Fora de escopo

- Suportar headers multi-linha ou em linha ≠ 1 — trocar `HEADER_ROW_COUNT` para um campo configurável seria uma spec nova.
- Detecção automática de header.

## Riscos / impacto

- Refactor puro. Baixo risco.
- Implementar **antes** das specs 0003 e 0004 para evitar duplicação dos mesmos cálculos inline.
