# 0007 — Migrar `Settings` para `pydantic-settings`

**Prioridade:** P2  **Breaking:** Não

## Contexto

`app/config.py` é uma classe manual:

```python
class Settings:
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    PORT: int = int(os.getenv("PORT", 8000))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    ALLOWED_ORIGINS: list = ["*"]
    ...
settings = Settings()
```

O projeto já usa `pydantic==2.5.0` mas **não** depende de `pydantic-settings`. Os valores default são avaliados no momento da importação do módulo — qualquer `monkeypatch.setenv` feito depois de importar `app.config` é ignorado, o que torna testes de configuração frágeis.

## Problema

- Parsing manual de bool (`"false".lower() == "true"`) e int com fallback — erro-prone.
- Sem validação de tipos nos env vars: `PORT="abc"` falha só na hora do `int()`, sem mensagem útil.
- Sem suporte a prefixo (`SHEETFUL_`).
- Valores avaliados na import do módulo — testes de override via `monkeypatch` não funcionam sem reimport.
- Lista `ALLOWED_ORIGINS` não tem parser de string-separada-por-vírgula nativo.
- Não carrega `.env` via API, depende de `load_dotenv()` explícito.

## Proposta

### 7.1. Adicionar dependência

```
pydantic-settings==2.x.x
```

ao `requirements.txt`. Remover `python-dotenv` se pydantic-settings o trouxer transitivamente (verificar); caso contrário manter.

### 7.2. Reescrever `app/config.py`

```python
from typing import Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Google API
    google_api_key: Optional[str] = None
    google_service_account_key: Optional[str] = None

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    log_level: str = "INFO"

    # API metadata
    api_title: str = "Sheetful API"
    api_description: str = "The easiest way to turn your Google Sheet into a RESTful API"
    api_version: str = "0.1.0"

    # CORS (ver spec 0005)
    allowed_origins: list[str] = Field(default_factory=list)
    allow_credentials: bool = False

    @model_validator(mode="after")
    def _validate_auth(self) -> "Settings":
        if not self.google_api_key and not self.google_service_account_key:
            raise ValueError(
                "GOOGLE_API_KEY or GOOGLE_SERVICE_ACCOUNT_KEY must be set"
            )
        if self.allow_credentials and "*" in self.allowed_origins:
            raise ValueError(
                "allowed_origins=* is incompatible with allow_credentials=true"
            )
        return self


def get_settings() -> Settings:
    """Factory so tests can override via dependency_overrides."""
    return Settings()


settings = get_settings()
```

### 7.3. Ajustar referências

Trocar todo `settings.FOO` por `settings.foo` no restante do código (FastAPI é case-sensitive aqui). Arquivos afetados:

- `app/main.py`
- `app/api/health.py`
- `app/services/sheets.py`
- `main.py` (root)

### 7.4. `.env.example` e README

Atualizar chaves para lowercase (ou manter uppercase: pydantic-settings é case-insensitive por default).

## Critérios de aceitação

- `make test` passa.
- `PORT="abc"` no `.env` faz o app falhar no boot com mensagem do Pydantic ("Input should be a valid integer"), não num `ValueError` cru do `int()`.
- Sem `GOOGLE_API_KEY` nem `GOOGLE_SERVICE_ACCOUNT_KEY`, o boot falha com a mensagem do `model_validator`.
- Teste unitário em `tests/unit/test_config.py` cobre: settings válido, settings sem credenciais, settings com `allow_credentials + *`.
- `app.dependency_overrides[get_settings]` funciona em testes.

## Fora de escopo

- Recarga dinâmica de settings em runtime.
- Secrets manager (AWS/GCP) — usar env vars.
- `Settings` como `Depends` injetado em handlers — fora do escopo aqui, abrir spec se necessário.

## Riscos / impacto

- Nomes em lowercase são um refactor mecânico mas tocam vários arquivos. Rodar `grep -rn "settings\." app/ main.py` antes e depois.
- Se `pydantic-settings` não for pinnado, versões futuras podem mudar a API. Pin explícito.
- `ALLOWED_ORIGINS` agora é lista tipada — `.env` com `ALLOWED_ORIGINS=http://a.com,http://b.com` é parseado automaticamente como JSON-list? Não — é CSV. Verificar a doc do `pydantic-settings` e ajustar: pode ser necessário JSON (`["http://a.com", "http://b.com"]`) ou usar um `field_validator` para aceitar CSV.
