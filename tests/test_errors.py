"""Тесты для иерархии исключений."""

from __future__ import annotations

from mcp_fssp.errors import (
    AuthFailedError,
    McpFsspError,
    NotFoundError,
    ProviderUnavailableError,
    RateLimitedError,
    ValidationError,
)


def test_to_dict_minimal() -> None:
    err = ValidationError("Невалидный ИНН")
    d = err.to_dict()
    assert d["error"] is True
    assert d["code"] == "invalid_input"
    assert d["message"] == "Невалидный ИНН"
    assert "hint" not in d
    assert "details" not in d


def test_to_dict_full() -> None:
    err = AuthFailedError(
        "Bad token",
        hint="Проверь .env",
        details={"http_status": 401},
    )
    d = err.to_dict()
    assert d["code"] == "auth_failed"
    assert d["hint"] == "Проверь .env"
    assert d["details"] == {"http_status": 401}


def test_inheritance() -> None:
    assert issubclass(ValidationError, McpFsspError)
    assert issubclass(NotFoundError, McpFsspError)
    assert issubclass(ProviderUnavailableError, McpFsspError)
    assert issubclass(RateLimitedError, McpFsspError)


def test_codes_are_distinct() -> None:
    codes = {
        ValidationError.code,
        NotFoundError.code,
        ProviderUnavailableError.code,
        RateLimitedError.code,
        AuthFailedError.code,
    }
    assert len(codes) == 5
