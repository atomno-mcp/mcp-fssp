"""Тулз `check_legal_entity_debts` — поиск ИП по юр.лицу или ИП-предпринимателю.

См. SPEC §5.2. Phase 1 минимально-достаточный: реализован для Damia,
для остальных провайдеров фабрика вернёт NotImplementedInPhase.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ..byok_limit import enforce_byok_daily_limit
from ..constants import ERROR_CODE_INTERNAL, PROVIDER_DAMIA
from ..errors import McpFsspError, ValidationError
from ..normalize import (
    assert_valid_inn,
    assert_valid_ogrn,
    hash_inn,
    hash_ogrn,
)
from ..schemas import CheckDebtsResponse

if TYPE_CHECKING:
    from ..context import ServiceContext


async def check_legal_entity_debts(
    ctx: "ServiceContext",
    *,
    inn: str | None = None,
    ogrn: str | None = None,
) -> CheckDebtsResponse:
    """Проверить ИП по юр.лицу (ИНН-10/ОГРН-13) или ИП-предпринимателю
    (ИНН-12/ОГРНИП-15)."""
    if not inn and not ogrn:
        raise ValidationError(
            "Нужен один из параметров: inn или ogrn.",
            hint="Передайте `inn` (10 или 12 цифр) либо `ogrn` (13 или 15 цифр).",
        )

    if inn:
        validated_inn = assert_valid_inn(inn)
        query_hash = hash_inn(validated_inn)
    else:
        assert ogrn is not None
        validated_ogrn = assert_valid_ogrn(ogrn)
        query_hash = hash_ogrn(validated_ogrn)

    started = time.perf_counter()
    try:
        await enforce_byok_daily_limit(ctx.audit, ctx.config)
        response = await ctx.provider.check_legal_entity(
            inn=inn if inn else None,
            ogrn=ogrn if ogrn else None,
        )
    except McpFsspError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        await ctx.audit.log(
            tool_name="check_legal_entity_debts",
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
            tool_name="check_legal_entity_debts",
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
        tool_name="check_legal_entity_debts",
        query_hash=query_hash,
        provider=ctx.provider.name,
        status="ok",
        found_count=response.found,
        latency_ms=latency_ms,
    )
    return response
