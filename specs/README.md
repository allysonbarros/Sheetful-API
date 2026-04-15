# Specs

Este diretório contém propostas de melhoria para o Sheetful API, derivadas da revisão de código em `claude/add-claude-documentation-P7okU`. Cada spec é independente e pode ser implementada isoladamente, salvo quando explicitamente marcada como dependente.

Cada documento segue este formato:

- **Contexto** — estado atual relevante (com referências a arquivos).
- **Problema** — o que está errado e por quê.
- **Proposta** — o que mudar, em termos concretos.
- **Critérios de aceitação** — como saber que está pronto.
- **Fora de escopo** — o que *não* pertence a esta spec.
- **Riscos / impacto** — efeitos colaterais, breaking changes.

## Índice por prioridade

| # | Spec | Prioridade | Breaking? |
|---|------|------------|-----------|
| 0001 | [Offloading do gspread bloqueante para thread pool](0001-async-gspread-offloading.md) | P0 | Não |
| 0002 | [Corrigir ferramentas de build e criar suíte de testes mínima](0002-fix-tooling-and-test-suite.md) | P0 | Não |
| 0003 | [Paginação server-side nas leituras de sheet](0003-server-side-pagination.md) | P1 | Não |
| 0004 | [Updates em lote reais via `batch_update`](0004-batch-sheet-updates.md) | P1 | Não |
| 0005 | [CORS configurável e redação de erros](0005-cors-and-error-redaction.md) | P1 | Sim (CORS) |
| 0006 | [Expor filtro `query` no endpoint de leitura](0006-query-filtering-endpoint.md) | P2 | Não |
| 0007 | [Migrar `Settings` para `pydantic-settings`](0007-pydantic-settings-migration.md) | P2 | Não |
| 0008 | [Injetar `GoogleSheetsService` via `Depends`](0008-service-dependency-injection.md) | P2 | Não |
| 0009 | [Abstrair a convenção de indexação de linhas](0009-row-index-abstraction.md) | P2 | Não |
| 0010 | [Middleware de observabilidade](0010-observability-middleware.md) | P3 | Não |
| 0011 | [Cache de clientes gspread e documentos por token](0011-gspread-client-and-document-caching.md) | P2 | Não |

**Prioridades**: P0 = bloqueia produção, P1 = alto impacto, P2 = saúde do projeto, P3 = melhorias incrementais.

## Ordem de implementação sugerida

0001 → 0009 (helpers de índice antes de 0003/0004) → 0008 (habilita testes unitários reais do serviço) → 0002 → 0003 + 0004 (reduzem custo Google API) → 0007 → 0005 → 0006 → 0010.

## Dependências entre specs

- **0003, 0004** assumem os helpers de **0009**.
- **0002** é muito mais fácil depois de **0008** (`dependency_overrides` em vez de `monkeypatch`).
- **0005** reusa `model_validator` — mais limpo depois de **0007**.
- **0010** depende de **0005** (reusar `request_id` como `error_id`) e **0008** (injetar o service no `/ready`).
- **0006** depende de **0003** (fallback em memória quando há `query`).
- **0011** depende de **0001** (thread pool + `threading.Lock`), **0008** (DI para teste isolado) e interage com **0005** (invalidação antes do handler central).

## Status de implementação

Specs **0001–0010** estão implementadas na branch `claude/add-claude-documentation-P7okU`. **0011** é a única ainda pendente.
