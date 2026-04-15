# 0003 — Paginação server-side nas leituras de sheet

**Prioridade:** P1  **Breaking:** Não

## Contexto

`GoogleSheetsService.get_sheet_rows` em `app/services/sheets.py:255-302`:

```python
all_records = self._get_all_records_safe(worksheet)
# ...
start_index = options.offset
end_index = start_index + options.limit
paginated_records = all_records[start_index:end_index]
```

`_get_all_records_safe` sempre lê o sheet **inteiro** antes de aplicar `offset`/`limit`.

## Problema

- Um sheet com 50k linhas gera um payload de ~50k linhas × N colunas do Google para cada `GET /{doc}/{sheet}?limit=10`.
- Custo de API aumenta linearmente com o tamanho do sheet, independente do `limit` solicitado.
- Latência do endpoint cresce linearmente com o tamanho do sheet, mesmo para requests pequenos.
- Consumo de memória idem.

## Proposta

1. Adicionar ao serviço um método novo (sem quebrar a API pública):

   ```python
   async def get_sheet_rows_paginated(
       self,
       worksheet,
       options: SheetGetRowsOptions,
   ) -> List[Dict[str, Any]]:
       headers = await _run_sync(self._get_safe_headers, worksheet)
       if not headers:
           return []

       start_row = options.offset + 2            # +1 1-indexing, +1 header
       end_row = start_row + options.limit - 1
       last_col_letter = _col_index_to_letter(len(headers))
       range_a1 = f"A{start_row}:{last_col_letter}{end_row}"

       values = await _run_sync(worksheet.get, range_a1)
       return [
           {headers[i]: cell for i, cell in enumerate(row) if i < len(headers)}
           for row in values
       ]
   ```

2. Extrair `_col_index_to_letter(n)` (ex.: `1→A`, `27→AA`) num helper em `app/services/sheets.py`.

3. **Quando `options.query` estiver presente** (ver spec 0006), não é possível paginar no server-side sem rodar o filtro no Google (Sheets API não suporta). Cair no fluxo antigo: ler tudo, filtrar em memória, paginar. Documentar no docstring que `query` desabilita a otimização.

4. Substituir a chamada em `get_sheet_rows` por:

   ```python
   if options.query:
       return self._get_rows_in_memory(worksheet, options)  # caminho antigo
   return await self.get_sheet_rows_paginated(worksheet, options)
   ```

## Critérios de aceitação

- Request `GET /{doc}/{sheet}?offset=0&limit=10` em um sheet com 50k linhas faz no máximo **2** chamadas ao Google (1 para headers, 1 para o range), contabilizadas via mock.
- Teste unitário verifica que o range A1 é calculado corretamente para `offset=0, limit=100` (→ `A2:Z101` com 26 colunas) e para `offset=50, limit=10` (→ `A52:Z61`).
- Fallback em memória é acionado quando `query` é passado.
- Endpoint mantém o mesmo contrato de resposta (lista de dicts com header como chave).

## Fora de escopo

- Paginação por cursor — offset/limit é o contrato existente.
- Cache de headers entre requests — abrir spec separada se necessário.
- Otimização do caminho com `query` — depende de spec 0006 definir semântica.

## Riscos / impacto

- Sheets com headers em linha ≠ 1 quebram o offset. Ver spec 0009 (abstração de indexação).
- Se um sheet tem linhas com número de colunas > número de headers, o caminho otimizado descarta as colunas extras em vez de gerar `Column_N`. Documentar como comportamento conhecido ou replicar o tratamento do fallback.
