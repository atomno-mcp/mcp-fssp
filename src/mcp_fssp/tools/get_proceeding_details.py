"""Тулз `get_proceeding_details` — расширенная карточка одного ИП.

См. SPEC §5.3.
"""

from __future__ import annotations

import hashlib
import re
import time
from typing import TYPE_CHECKING

from ..constants import ERROR_CODE_INTERNAL, PROCEEDING_ID_PATTERN
from ..errors import McpFsspError, ValidationError
from ..schemas import ProceedingDetails

if TYPE_CHECKING:
    from ..context import ServiceContext


_PROCEEDING_ID_RE = re.compile(PROCEEDING_ID_PATTERN)


async def get_proceeding_details(
    ctx: "ServiceContext",
    *,
    proceeding_id: str,
) -> ProceedingDetails:
    """Получить расширенную карточку конкретного ИП по номеру."""
    if not isinstance(proceeding_id, str) or not proceeding_id.strip():
        raise ValidationError(
            "proceeding_id должен быть непустой строкой.",
            details={"input": proceeding_id},
        )

    cleaned = proceeding_id.strip()
    if not _PROCEEDING_ID_RE.match(cleaned):
        raise ValidationError(
            f"Невалидный номер ИП: '{proceeding_id}'. Ожидается формат "
            f"'NNNNN/YY/SSSSS-ИП', например '12345/22/74033-ИП'.",
            details={"input": proceeding_id},
        )

    query_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

    started = time.perf_counter()
    try:
        response = await ctx.provider.get_proceeding(cleaned)
    except McpFsspError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        await ctx.audit.log(
            tool_name="get_proceeding_details",
            query_hash=query_hash,
            provider=ctx.provider.name,
            status="error",
            latency_ms=latency_ms,
            error_code=exc.code,
            error_message=exc.message_ru,
        )
        raise
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        await ctx.audit.log(
            tool_name="get_proceeding_details",
            query_hash=query_hash,
            provider=ctx.provider.name,
            status="error",
            latency_ms=latency_ms,
            error_code=ERROR_CODE_INTERNAL,
            error_message=str(exc),
        )
        raise

    latency_ms = int((time.perf_counter() - started) * 1000)
    await ctx.audit.log(
        tool_name="get_proceeding_details",
        query_hash=query_hash,
        provider=ctx.provider.name,
        status="ok",
        found_count=1,
        latency_ms=latency_ms,
    )
    return response
