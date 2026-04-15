# 0002 — Corrigir ferramentas de build e criar suíte de testes mínima

**Prioridade:** P0  **Breaking:** Não

## Contexto

O `Makefile` e `pyproject.toml` referenciam arquivos e diretórios que **não existem** no repositório:

- `Makefile:41-50` — `flake8`, `mypy`, `black`, `isort` aplicados a `app/ main.py server.py dev_utils.py`. `server.py` e `dev_utils.py` não existem.
- `Makefile:53-54` — `make validate` chama `python dev_utils.py validate` — arquivo inexistente.
- `Makefile:78` — `make logs` executa `tail -f logs/django.log` (resquício de Django).
- `pyproject.toml:48` — `[tool.pytest.ini_options] testpaths = ["tests"]` aponta para um diretório que nunca foi criado.
- **Nenhum arquivo de teste existe** em todo o repositório.

`make test` passa trivialmente (pytest não encontra nada) e `make lint` falha com `file not found`.

## Problema

- Desenvolvedores não conseguem rodar `make lint` sem erro, o que significa que ninguém roda.
- Não há rede de segurança para mudanças: qualquer refactor é exploratório.
- A spec 0001 (offloading async) só pode ser validada com confiança se houver pelo menos testes do serviço mockando `gspread`.

## Proposta

### 2.1. Corrigir Makefile

Substituir a lista de paths por `APP_PATHS = app/ main.py`:

```make
APP_PATHS = app/ main.py

lint:
	flake8 $(APP_PATHS)
	mypy $(APP_PATHS)

format:
	black $(APP_PATHS)
	isort $(APP_PATHS)

format-check:
	black --check $(APP_PATHS)
	isort --check-only $(APP_PATHS)
```

- Remover o alvo `validate` (ou implementar de fato se houver demanda — fora de escopo aqui).
- Remover `logs` ou trocar para `tail -f` de um path configurável.

### 2.2. Criar estrutura de testes

```
tests/
├── __init__.py
├── conftest.py          # fixtures compartilhadas
├── unit/
│   ├── __init__.py
│   ├── test_sheets_service.py
│   └── test_models.py
└── integration/
    ├── __init__.py
    └── test_api_sheets.py
```

`conftest.py` deve expor, no mínimo:

- `mock_worksheet` — `MagicMock` configurado com `row_count`, `col_count`, `row_values`, `get_all_records`, `get_all_values`, `update_cell`, `append_row`, `append_rows`.
- `mock_document` — `MagicMock` com `title`, `get_worksheet_by_id`, `get_worksheet`, `worksheet`.
- `api_client` — `TestClient` da FastAPI com o `sheets_service` substituído via `app.dependency_overrides` (depende da spec 0008; enquanto não existir, usar `monkeypatch.setattr("app.services.sheets.sheets_service.get_document", ...)`).

### 2.3. Testes mínimos obrigatórios

**`test_sheets_service.py`:**

- `get_sheet` resolve por ID numérico → por índice → por título, nesta ordem.
- `_get_safe_headers` substitui vazios por `Column_N` e desambigua duplicatas com sufixo `_1`, `_2`.
- `_get_all_records_safe` cai no fallback quando `get_all_records` lança.
- `update_row` calcula `actual_row_number = row_id + 2`.
- `update_row` levanta `HTTPException(404)` quando `row_id >= len(records)`.
- Paginação: `offset` e `limit` são aplicados após filtros.

**`test_models.py`:**

- `SheetGetRowsOptions` rejeita `limit > 1000` e `offset < 0`.
- `SheetInfo` serializa com aliases camelCase.

**`test_api_sheets.py`:**

- `GET /{doc}/{sheet}` devolve 200 e lista (serviço mockado).
- `GET /{doc}/{sheet}/info` devolve o shape correto com `sheetId`, `headerValues`, etc.
- `GET /{doc}/{sheet}/{row_id}` com `row_id` inválido devolve 404.
- `validate_config` falha sem `GOOGLE_API_KEY` nem `GOOGLE_SERVICE_ACCOUNT_KEY`.

### 2.4. CI

Adicionar `.github/workflows/ci.yml` rodando `make ci-test` (que já existe no Makefile) em pushes e PRs para `main`. Python 3.11. Sem deploy.

## Critérios de aceitação

- `make lint`, `make format-check`, `make test` rodam sem erro em branch limpa.
- `make ci-test` passa localmente.
- Cobertura inicial ≥ 60% em `app/services/sheets.py` e ≥ 80% em `app/models.py`.
- CI executa em todo PR.

## Fora de escopo

- Testes de integração reais contra a API do Google (exigem credenciais em CI).
- Benchmark de performance.
- Alvo `make validate` — remover, não reescrever.

## Riscos / impacto

- Adicionar `tests/` ao `.gitignore` por engano — verificar antes.
- CI no GitHub Actions pode exigir ajustes de secrets se testes dependerem de env vars; manter os mocks 100% locais.
