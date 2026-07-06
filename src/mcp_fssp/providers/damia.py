"""Провайдер Damia API-ФССП.

Документация (источник [5] SPEC): https://api-fssp.damia.ru
Endpoints (по состоянию на 2026-04):

  * GET https://api-fssp.damia.ru/api?fio=...&dataR=dd.mm.yyyy&key=TOKEN
        — поиск по физ.лицу.
  * GET https://api-fssp.damia.ru/api?inn=...&key=TOKEN
        — поиск по ИНН (юр.лицо или ИП-предприниматель).
  * GET https://api-fssp.damia.ru/api?ogrn=...&key=TOKEN
        — поиск по ОГРН.
  * GET https://api-fssp.damia.ru/api?nomer=...&key=TOKEN&proizv=1
        — детальная карточка по номеру ИП.

Ответ — JSON. Точный формат описан в `parsers/damia.py`.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx

from ..client_base import AbstractProviderClient
from ..constants import DAMIA_BASE_URL, PROVIDER_DAMIA
from ..errors import (
    AuthFailedError,
    ParseError,
    ValidationError,
)
from ..normalize import (
    assert_valid_inn,
    assert_valid_ogrn,
    format_birth_date_damia,
    normalize_fio,
)
from ..schemas import CheckDebtsResponse, ProceedingDetails
from ..parsers.damia import (
    parse_check_response,
    parse_details_response,
)

logger = logging.getLogger("mcp_fssp.providers.damia")


class DamiaProvider(AbstractProviderClient):
    """Клиент Damia API-ФССП."""

    name = PROVIDER_DAMIA
    requires_token = True

    def __init__(self, config: Any) -> None:  # type: ignore[override]
        super().__init__(config)
        if not config.damia_key:
            raise AuthFailedError(
                "Для провайдера damia не задан токен в MCP_FSSP_DAMIA_KEY.",
                hint=(
                    "Зарегистрируйтесь на https://api-fssp.damia.ru, получите "
                    "ключ и пропишите его в .env как MCP_FSSP_DAMIA_KEY=..."
                ),
                details={"env_var": "MCP_FSSP_DAMIA_KEY"},
            )

    async def check_individual(
        self,
        *,
        fio: str,
        birth_date: date,
        region: str | None = None,
    ) -> CheckDebtsResponse:
        normalized_fio = normalize_fio(fio)
        params: dict[str, str] = {
            "fio": normalized_fio,
            "dataR": format_birth_date_damia(birth_date),
            "key": self._config.damia_key or "",
        }
        if region:
            params["region"] = region.strip()

        payload = await self._get(params)
        return parse_check_response(
            payload,
            query={
                "fio": normalized_fio,
                "birth_date": birth_date,
                "region": region,
            },
        )

    async def check_legal_entity(
        self,
        *,
        inn: str | None = None,
        ogrn: str | None = None,
    ) -> CheckDebtsResponse:
        if not inn and not ogrn:
            raise ValidationError(
                "check_legal_entity_debts требует один из параметров: inn или ogrn.",
            )
        params: dict[str, str] = {"key": self._config.damia_key or ""}
        query_echo: dict[str, Any] = {}
        if inn:
            params["inn"] = assert_valid_inn(inn)
            query_echo["inn"] = inn
        elif ogrn:
            params["ogrn"] = assert_valid_ogrn(ogrn)
            query_echo["ogrn"] = ogrn

        payload = await self._get(params)
        return parse_check_response(payload, query=query_echo)

    async def get_proceeding(self, proceeding_id: str) -> ProceedingDetails:
        if not proceeding_id or not isinstance(proceeding_id, str):
            raise ValidationError(
                "proceeding_id должен быть непустой строкой.",
                details={"input": proceeding_id},
            )
        params = {
            "nomer": proceeding_id.strip(),
            "key": self._config.damia_key or "",
            "proizv": "1",
        }
        payload = await self._get(params)
        return parse_details_response(payload, proceeding_id=proceeding_id)

    # ------------------------------------------------------------------
    # HTTP-уровень.
    # ------------------------------------------------------------------

    async def _get(self, params: dict[str, str]) -> dict[str, Any]:
        async with self.make_httpx_client() as client:
            try:
                response = await client.get(DAMIA_BASE_URL, params=params)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise self.map_http_error(exc, provider_name=self.name) from exc
            except httpx.RequestError as exc:
                raise self.map_http_error(exc, provider_name=self.name) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise ParseError(
                "Damia API вернул невалидный JSON.",
                hint="Возможно, провайдер отдал HTML-страницу с ошибкой. "
                "Проверьте токен и обратитесь в поддержку Damia.",
                details={"body_preview": response.text[:200]},
            ) from exc

        if not isinstance(data, dict):
            raise ParseError(
                "Damia API вернул JSON неожиданного типа (ожидался object).",
                details={"got_type": type(data).__name__},
            )

        return data
