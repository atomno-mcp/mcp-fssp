"""Общие pytest-фикстуры для mcp-fssp.

Покрывает: создание изолированной audit-DB во временной папке, чистый
конфиг, фабрику минимального ServiceContext без обращения к сети.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio

from mcp_fssp.audit_db import AuditDb
from mcp_fssp.config import Config


@pytest.fixture
def damia_test_key() -> str:
    return "test-damia-token"


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Удалить все MCP_FSSP_* и ATOMNO_* переменные из env на время теста."""
    for key in list(os.environ.keys()):
        if key.startswith("MCP_FSSP_") or key in (
            "ATOMNO_API_KEY",
            "ATOMNO_API_BASE",
            "MCP_FSSP_ATOMNO_API_KEY",
            "MCP_FSSP_ATOMNO_API_BASE",
        ):
            monkeypatch.delenv(key, raising=False)
    yield


@pytest.fixture
def damia_config(
    tmp_path: Path,
    damia_test_key: str,
    clean_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Config:
    monkeypatch.setenv("MCP_FSSP_PROVIDER", "damia")
    monkeypatch.setenv("MCP_FSSP_DAMIA_KEY", damia_test_key)
    monkeypatch.setenv("MCP_FSSP_AUDIT_DB", str(tmp_path / "audit.sqlite"))
    monkeypatch.setenv("MCP_FSSP_HTTP_TIMEOUT", "5")
    return Config.from_env()


@pytest_asyncio.fixture
async def audit_db(tmp_path: Path) -> AsyncIterator[AuditDb]:
    db = AuditDb(tmp_path / "audit.sqlite")
    await db.init()
    try:
        yield db
    finally:
        await db.close()
