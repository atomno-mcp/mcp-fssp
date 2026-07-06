"""Hosted Pro-провайдер (api.atomno-mcp.ru/mcp-fssp/v1).

Тонкий HTTP-клиент по образцу mcp-sudact. Пока backend в разработке —
возвращает понятную ошибку «coming soon».
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from ..client_base import AbstractProviderClient
from ..constants import PROVIDER_ATOMNO_PRO
from ..errors import NotImplementedInPhase, ProRequiredError
from ..schemas import CheckDebtsResponse, ProceedingDetails


_COMING_SOON = (
    "Hosted API ФССП ещё в разработке. "
    "Напишите hello@atomno.ru для раннего доступа. "
    "Временно: MCP_FSSP_PROVIDER=damia + MCP_FSSP_DAMIA_KEY (deprecated, лимит 10 req/день)."
)


class AtomnoProProvider(AbstractProviderClient):
    """REST-клиент к api.atomno-mcp.ru/mcp-fssp/v1."""

    name = PROVIDER_ATOMNO_PRO
    requires_token = True

    def __init__(self, config: Any) -> None:
        super().__init__(config)
        headers = {
            "User-Agent": config.user_agent,
            "Accept": "application/json",
        }
        if config.hosted_api_key:
            headers["X-API-Key"] = config.hosted_api_key
        self._client = httpx.AsyncClient(
            base_url=config.hosted_api_base.rstrip("/"),
            timeout=config.http_timeout_seconds,
            headers=headers,
        )

    def _require_key(self) -> None:
        if not self._config.hosted_api_key:
            raise ProRequiredError(
                "Не задан MCP_FSSP_ATOMNO_API_KEY для провайдера atomno_pro.",
                hint="Получите ключ: https://atomno-mcp.ru/pricing или hello@atomno.ru",
                details={"env_var": "MCP_FSSP_ATOMNO_API_KEY"},
            )

    async def check_individual(
        self,
        *,
        fio: str,
        birth_date: date,
        region: str | None = None,
    ) -> CheckDebtsResponse:
        return await self._post_check(
            "/individuals",
            {"fio": fio, "birth_date": birth_date.isoformat(), "region": region},
        )

    async def check_legal_entity(
        self,
        *,
        inn: str | None = None,
        ogrn: str | None = None,
    ) -> CheckDebtsResponse:
        return await self._post_check(
            "/legal-entities",
            {"inn": inn, "ogrn": ogrn},
        )

    async def get_proceeding(self, proceeding_id: str) -> ProceedingDetails:
        data = await self._post_json("/proceedings", {"proceeding_id": proceeding_id})
        return ProceedingDetails.model_validate(data)

    async def _post_check(self, path: str, payload: dict[str, Any]) -> CheckDebtsResponse:
        data = await self._post_json(path, payload)
        return CheckDebtsResponse.model_validate(data)

    async def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_key()
        try:
            resp = await self._client.post(path, json=payload)
        except httpx.HTTPError as exc:
            raise NotImplementedInPhase(
                _COMING_SOON,
                hint="hello@atomno.ru",
                details={"path": path, "reason": type(exc).__name__},
            ) from exc
        if resp.status_code in (404, 501, 502, 503):
            raise NotImplementedInPhase(
                _COMING_SOON,
                hint="hello@atomno.ru",
                details={"path": path, "http_status": resp.status_code},
            )
        if resp.status_code >= 400:
            raise NotImplementedInPhase(
                _COMING_SOON,
                details={"path": path, "http_status": resp.status_code},
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise NotImplementedInPhase(
                _COMING_SOON,
                details={"path": path, "reason": "invalid_json"},
            ) from exc
