"""Unit tests for ``app.config.Settings``."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_accepts_api_key(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "abc")
    monkeypatch.delenv("ALLOW_CREDENTIALS", raising=False)
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    s = Settings(_env_file=None)
    assert s.GOOGLE_API_KEY == "abc"
    assert s.ALLOWED_ORIGINS == []


def test_settings_requires_some_credential(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_rejects_star_origin_with_credentials(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "abc")
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ALLOWED_ORIGINS=["*"],
            ALLOW_CREDENTIALS=True,
        )


def test_settings_rejects_non_integer_port(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "abc")
    monkeypatch.setenv("PORT", "not-an-int")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
