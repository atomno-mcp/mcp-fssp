"""SQLite-аудит-лог запросов клиента.

В audit-лог пишутся ТОЛЬКО хэши ПДн (см. SPEC §7.7) и метаданные:
ts, tool_name, query_hash (sha256), provider, status, found_count,
latency_ms, error_code. Никакого ФИО / ИНН / ОГРН в plain-text.

Назначение — локальная диагностика и подсчёт квот, не источник данных.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Final

import aiosqlite

from .constants import TABLE_AUDIT_LOG

_SCHEMA_SQL: Final[str] = f"""
CREATE TABLE IF NOT EXISTS {TABLE_AUDIT_LOG} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    query_hash TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL,
    found_count INTEGER,
    latency_ms INTEGER,
    error_code TEXT,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON {TABLE_AUDIT_LOG}(ts);
CREATE INDEX IF NOT EXISTS idx_audit_provider ON {TABLE_AUDIT_LOG}(provider);

CREATE TABLE IF NOT EXISTS byok_daily_usage (
    usage_date TEXT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0
);
"""


class AuditDb:
    """Async-обёртка над SQLite для записи аудит-лога.

    Использование:

        db = AuditDb(Path("./audit.sqlite"))
        await db.init()
        await db.log(tool_name="check_individual_debts", ...)
        await db.close()
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    @property
    def path(self) -> Path:
        return self._path

    async def init(self) -> None:
        """Открыть коннект и применить схему (идемпотентно)."""
        if self._conn is not None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self._path))
        await self._conn.executescript(_SCHEMA_SQL)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def log(
        self,
        *,
        tool_name: str,
        query_hash: str,
        provider: str,
        status: str,
        found_count: int | None = None,
        latency_ms: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Записать одну строку в аудит-лог."""
        if self._conn is None:
            await self.init()
        assert self._conn is not None
        await self._conn.execute(
            f"""INSERT INTO {TABLE_AUDIT_LOG}
                (ts, tool_name, query_hash, provider, status,
                 found_count, latency_ms, error_code, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(tz=timezone.utc).isoformat(),
                tool_name,
                query_hash,
                provider,
                status,
                found_count,
                latency_ms,
                error_code,
                error_message,
            ),
        )
        await self._conn.commit()

    async def count(self) -> int:
        if self._conn is None:
            await self.init()
        assert self._conn is not None
        async with self._conn.execute(
            f"SELECT COUNT(*) FROM {TABLE_AUDIT_LOG}"
        ) as cur:
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def get_byok_daily_count(self, usage_date: str) -> int:
        if self._conn is None:
            await self.init()
        assert self._conn is not None
        async with self._conn.execute(
            "SELECT count FROM byok_daily_usage WHERE usage_date = ?",
            (usage_date,),
        ) as cur:
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def increment_byok_daily_count(self, usage_date: str) -> int:
        if self._conn is None:
            await self.init()
        assert self._conn is not None
        await self._conn.execute(
            "INSERT INTO byok_daily_usage (usage_date, count) VALUES (?, 1) "
            "ON CONFLICT(usage_date) DO UPDATE SET count = count + 1",
            (usage_date,),
        )
        await self._conn.commit()
        return await self.get_byok_daily_count(usage_date)
