"""Тесты для audit_db."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_fssp.audit_db import AuditDb


@pytest.mark.asyncio
async def test_init_creates_db_file(tmp_path: Path) -> None:
    db_path = tmp_path / "subdir" / "audit.sqlite"
    db = AuditDb(db_path)
    await db.init()
    assert db_path.exists()
    await db.close()


@pytest.mark.asyncio
async def test_log_and_count(tmp_path: Path) -> None:
    db = AuditDb(tmp_path / "audit.sqlite")
    await db.init()
    await db.log(
        tool_name="check_individual_debts",
        query_hash="a" * 64,
        provider="damia",
        status="ok",
        found_count=2,
        latency_ms=120,
    )
    await db.log(
        tool_name="check_individual_debts",
        query_hash="b" * 64,
        provider="damia",
        status="error",
        error_code="invalid_input",
        error_message="bad fio",
    )
    assert await db.count() == 2
    await db.close()


@pytest.mark.asyncio
async def test_init_idempotent(tmp_path: Path) -> None:
    db = AuditDb(tmp_path / "audit.sqlite")
    await db.init()
    await db.init()
    await db.close()
