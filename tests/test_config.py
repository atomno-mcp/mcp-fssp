"""Тесты для `config.py`."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_fssp.config import Config
from mcp_fssp.errors import ValidationError


def test_defaults_when_only_provider_set(
    tmp_path: Path,
    clean_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_FSSP_AUDIT_DB", str(tmp_path / "audit.sqlite"))
    config = Config.from_env()
    assert config.provider == "atomno_pro"
    assert config.damia_key is None
    assert config.http_timeout_seconds == 15.0
    assert config.rps == 30
    assert config.log_level == "INFO"
    assert not config.provider_configured


def test_with_damia_key(
    tmp_path: Path,
    clean_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_FSSP_PROVIDER", "damia")
    monkeypatch.setenv("MCP_FSSP_DAMIA_KEY", "tok-123")
    monkeypatch.setenv("MCP_FSSP_AUDIT_DB", str(tmp_path / "audit.sqlite"))
    config = Config.from_env()
    assert config.damia_key == "tok-123"
    assert config.provider_configured is True


def test_unknown_provider_rejected(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MCP_FSSP_PROVIDER", "googleapi")
    with pytest.raises(ValidationError):
        Config.from_env()


def test_invalid_timeout_rejected(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MCP_FSSP_HTTP_TIMEOUT", "not-a-number")
    with pytest.raises(ValidationError):
        Config.from_env()


def test_negative_timeout_rejected(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MCP_FSSP_HTTP_TIMEOUT", "-5")
    with pytest.raises(ValidationError):
        Config.from_env()


def test_invalid_rps_rejected(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MCP_FSSP_RPS", "abc")
    with pytest.raises(ValidationError):
        Config.from_env()


def test_hosted_mode_only_when_provider_atomno_pro(
    tmp_path: Path,
    clean_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_FSSP_PROVIDER", "damia")
    monkeypatch.setenv("MCP_FSSP_ATOMNO_API_KEY", "pro-key")
    monkeypatch.setenv("MCP_FSSP_DAMIA_KEY", "damia-key")
    monkeypatch.setenv("MCP_FSSP_AUDIT_DB", str(tmp_path / "audit.sqlite"))
    config = Config.from_env()
    # Hosted mode требует и провайдер atomno_pro, и ключ.
    assert config.hosted_mode_enabled is False

    monkeypatch.setenv("MCP_FSSP_PROVIDER", "atomno_pro")
    config2 = Config.from_env()
    assert config2.hosted_mode_enabled is True


def test_empty_string_token_treated_as_none(
    tmp_path: Path,
    clean_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_FSSP_PROVIDER", "damia")
    monkeypatch.setenv("MCP_FSSP_DAMIA_KEY", "   ")
    monkeypatch.setenv("MCP_FSSP_AUDIT_DB", str(tmp_path / "audit.sqlite"))
    config = Config.from_env()
    assert config.damia_key is None
    assert config.provider_configured is False
