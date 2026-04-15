# 0004 — Updates em lote reais via `batch_update`

**Prioridade:** P1  **Breaking:** Não

## Contexto

Em `app/services/sheets.py`:

- `update_row` (linhas 401-448) chama `worksheet.update_cell(actual_row_number, i + 1, data[header])` **uma vez por coluna alterada**.
- `update_rows_bulk` (linhas 488-524) aninha esse laço: `O(N_linhas × M_colunas)` chamadas HTTP à API do Google por request.
- `create_row` (linhas 450-486) chama `worksheet.append_row` (1 call), mas depois executa `_get_all_records_safe(worksheet)` só para devolver a última linha — outra leitura completa do sheet.

## Problema

- "Bulk update" de 100 linhas × 10 colunas = 1000 chamadas sequenciais ao Google. Latência proibitiva e fácil estourar quotas (`RESOURCE_EXHAUSTED` da Sheets API).
- `create_row` re-lê o sheet inteiro a cada inserção — custo O(n) de leitura por insert.
- O nome "bulk" da rota é enganoso: não há bulk nenhum internamente.

## Proposta

### 4.1. `update_row` com um único range

```python
actual_row_number = row_id + 2
headers = await _run_sync(self._get_safe_headers, worksheet)
row_values = [data.get(h, "") for h in headers]  # preserva vazios para células não alteradas? NÃO — ler a linha antes
```

**Cuidado**: o contrato atual é *patch* (só atualiza campos presentes em `data`), não *replace*. Para preservar isso com uma única chamada, precisamos:

1. Ler a linha atual: `current = await self.get_row(worksheet, row_id)`.
2. Mesclar: `merged = {**current, **data}`.
3. Escrever a linha inteira num único range:

```python
range_a1 = f"A{actual_row_number}:{_col_index_to_letter(len(headers))}{actual_row_number}"
new_values = [merged.get(h, "") for h in headers]
await _run_sync(worksheet.update, range_a1, [new_values])
return merged
```

Resultado: **2 chamadas** (read + write) em vez de N.

### 4.2. `update_rows_bulk` com `batch_update`

Substituir o laço por uma única chamada:

```python
headers = await _run_sync(self._get_safe_headers, worksheet)
last_col = _col_index_to_letter(len(headers))

# Ler o range existente para preservar campos não alterados
start_row = start_row_id + 2
end_row = start_row + len(data) - 1
read_range = f"A{start_row}:{last_col}{end_row}"
existing = await _run_sync(worksheet.get, read_range)

# Mesclar por linha
merged_rows = []
for i, patch in enumerate(data):
    current = dict(zip(headers, existing[i] if i < len(existing) else []))
    merged = {**current, **patch}
    merged_rows.append([merged.get(h, "") for h in headers])

await _run_sync(worksheet.update, read_range, merged_rows)
return len(data)
```

Resultado: **2 chamadas**, independente de N×M.

### 4.3. `create_row` sem releitura

Eliminar o `_get_all_records_safe` final. `append_row` já devolve a resposta da API com o range inserido — usar isso para retornar a linha criada sem ler o sheet inteiro:

```python
response = await _run_sync(worksheet.append_row, row_data, value_input_option="USER_ENTERED")
# response.updates.updatedRange tem o range; a linha inserida é o que acabamos de enviar
return dict(zip(headers, row_data))
```

Aceitar que o retorno é o que foi enviado, não uma releitura pós-fato do Google.

### 4.4. `create_rows_bulk` — já usa `append_rows`, OK

Verificar apenas que o método é envolvido em `_run_sync` (spec 0001) e que o retorno não depende de releitura.

## Critérios de aceitação

- `update_row` faz no máximo 2 chamadas ao Google (medido via mock).
- `update_rows_bulk` faz no máximo 2 chamadas ao Google, independente de N e M.
- `create_row` faz no máximo 1 chamada ao Google.
- Testes cobrem: patch preserva campos não enviados, range A1 correto em update_rows_bulk, retorno da linha criada casa com o input.
- Contratos HTTP dos endpoints permanecem idênticos (payloads, status codes).

## Fora de escopo

- Validação de tipo por coluna (números, datas) — fora do escopo desta spec.
- Opção `value_input_option` configurável pelo cliente — abrir spec separada.
- Transações ACID — a Sheets API não garante atomicidade de batch_update; documentar.

## Riscos / impacto

- `value_input_option="USER_ENTERED"` vs `"RAW"` muda o parsing de datas/números pelo Google. O comportamento atual com `update_cell` é `USER_ENTERED` por default — manter.
- Se dois patches no mesmo `update_rows_bulk` afetam a mesma linha, o último ganha. Igual ao comportamento atual.
- Mesclagem read-then-write não é atômica: mudanças concorrentes ao mesmo range entre o read e o write são perdidas. Documentar como limitação conhecida.
