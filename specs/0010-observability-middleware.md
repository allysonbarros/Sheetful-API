# 0010 — Middleware de observabilidade

**Prioridade:** P3  **Breaking:** Não

## Contexto

Logging atual:

- Handlers chamam `log_request` / `log_success` (`app/api/utils.py:50-80`) ad-hoc.
- Sem correlation ID, sem tempo de resposta, sem status code nos logs.
- `/health` (`app/api/health.py:38`) é uma liveness pura — não verifica conectividade com Google Sheets.

## Problema

Em produção é difícil:
- Correlacionar um erro reportado pelo cliente (`error_id` da spec 0005) com o log do request.
- Identificar endpoints lentos.
- Distinguir "app caiu" de "Google API está fora" (o health check não sabe).

## Proposta

### 10.1. Middleware de request logging

```python
# app/api/middleware.py
import logging
import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("sheetful.access")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            logger.exception(
                "request_failed id=%s method=%s path=%s elapsed_ms=%.1f",
                request_id, request.method, request.url.path, elapsed,
            )
            raise
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            "request id=%s method=%s path=%s status=%d elapsed_ms=%.1f",
            request_id, request.method, request.url.path, response.status_code, elapsed,
        )
        response.headers["x-request-id"] = request_id
        return response
```

Registrar em `app/main.py:create_app`:

```python
app.add_middleware(RequestLoggingMiddleware)
```

### 10.2. Integrar com spec 0005

O `error_id` do handler de exceção deve reusar `request.state.request_id` em vez de gerar um novo UUID. Assim log de acesso e log de erro compartilham a mesma correlação, visível também no header `x-request-id` da resposta.

### 10.3. Readiness check

Novo endpoint em `app/api/health.py`:

```python
@router.get("/ready")
async def readiness(svc: GoogleSheetsService = Depends(get_sheets_service)):
    try:
        await svc.ping()  # método novo que faz um GET leve ao Google
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail="Google Sheets unreachable")
```

`svc.ping()` pode ser `await _run_sync(gspread.authorize(...).list_spreadsheet_files)` com limit=1 ou qualquer chamada barata. O importante é exercitar auth + conexão.

`/health` continua existindo como liveness (sem I/O externa).

### 10.4. Remover `log_request` / `log_success`

Com o middleware cobrindo request logs, os helpers em `app/api/utils.py` ficam redundantes. Deletar e remover as chamadas em `app/api/sheets.py`.

## Critérios de aceitação

- Todo response carrega `x-request-id` no header.
- Log de acesso emite uma linha por request com method, path, status, elapsed_ms, request_id.
- `/health` responde 200 sempre que o processo estiver vivo.
- `/ready` responde 503 quando o Google está inacessível (testável com mock que levanta).
- `error_id` nas respostas 500 = `request_id` do log de acesso.
- `log_request` / `log_success` removidos e não referenciados.

## Fora de escopo

- Exportação de métricas Prometheus.
- Tracing distribuído (OpenTelemetry).
- Structured logging JSON (trivial de adicionar depois, mas fora daqui).
- Alertas.

## Riscos / impacto

- Spec 0010 depende das specs 0005 e 0008. Implementar por último.
- Readiness com chamada ao Google consome quota — cache curto (ex.: 5 s) se for chamado por load balancer.
