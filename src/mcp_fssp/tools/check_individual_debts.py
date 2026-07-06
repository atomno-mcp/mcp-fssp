"""Тулз `check_individual_debts` — поиск ИП по физ.лицу.

См. SPEC §5.1.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ..byok_limit import enforce_byok_daily_limit
from ..constants import ERROR_CODE_INTERNAL, PROVIDER_DAMIA
from ..errors import McpFsspError
from ..normalize import hash_person, normalize_fio, parse_birth_date
from ..schemas import CheckDebtsResponse

if TYPE_CHECKING:
    from ..context import ServiceContext


async def check_individual_debts(
    ctx: "ServiceContext",
    *,
    fio: str,
    birth_date: str,
    region: str | None = None,
) -> CheckDebtsResponse:
    """Проверить ИП по физ.лицу.

    Args:
        ctx: ServiceContext с готовыми provider+audit_db.
        fio: ФИО полностью, например "Иванов Иван Иванович".
        birth_date: Дата рождения в формате YYYY-MM-DD или dd.mm.yyyy.
        region: Опционально — код субъекта РФ или название.
    """
    normalized_fio = normalize_fio(fio)
    parsed_dob = parse_birth_date(birth_date)
    query_hash = hash_person(normalized_fio, parsed_dob)

    started = time.perf_counter()
    try:
        await enforce_byok_daily_limit(ctx.audit, ctx.config)
        response = await ctx.provider.check_individual(
            fio=normalized_fio,
            birth_date=parsed_dob,
            region=region.strip() if isinstance(region, str) else None,
        )
    except McpFsspError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        await ctx.audit.log(
            tool_name="check_individual_debts",
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
            tool_name="check_individual_debts",
            query_hash=query_hash,
            provider=ctx.provider.name,
            status="error",
            latency_ms=latency_ms,
            error_code=ERROR_CODE_INTERNAL,
            error_message=str(exc),
        )
        raise

    latency_ms = int((time.perf_counter() - started) * 1000)
    if ctx.config.provider == PROVIDER_DAMIA:
        from datetime import date

        await ctx.audit.increment_byok_daily_count(date.today().isoformat())
    await ctx.audit.log(
        tool_name="check_individual_debts",
        query_hash=query_hash,
        provider=ctx.provider.name,
        status="ok",
        found_count=response.found,
        latency_ms=latency_ms,
    )
    return response
