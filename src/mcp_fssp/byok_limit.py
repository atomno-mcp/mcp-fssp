"""Дневной лимит BYOK Damia без Atomno API-ключа (open-core moat v0.1.1)."""

from __future__ import annotations

from datetime import date

from .audit_db import AuditDb
from .config import Config
from .errors import RateLimitedError

DEFAULT_BYOK_DAILY_LIMIT = 10


async def enforce_byok_daily_limit(
    audit: AuditDb,
    config: Config,
) -> None:
    if config.hosted_mode_enabled or config.provider != "damia":
        return
    limit = config.byok_daily_limit
    if limit <= 0:
        return
    today = date.today().isoformat()
    count = await audit.get_byok_daily_count(today)
    if count >= limit:
        raise RateLimitedError(
            (
                f"Дневной лимит open-клиента без Atomno API-ключа исчерпан "
                f"({limit} запросов/сутки). "
                "Получите MCP_FSSP_ATOMNO_API_KEY на https://atomno-mcp.ru/pricing "
                "или напишите hello@atomno.ru."
            ),
            hint="MCP_FSSP_PROVIDER=atomno_pro + MCP_FSSP_ATOMNO_API_KEY — рекомендуемый путь.",
            details={"limit": limit, "used": count, "date": today},
        )
    await audit.increment_byok_daily_count(today)
