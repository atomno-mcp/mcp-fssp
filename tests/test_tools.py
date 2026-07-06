"""Интеграционные тесты на уровне tools (`tools/*.py`).

Прогоняют end-to-end: tool → ServiceContext → DamiaProvider → respx-мок.
Проверяют что в audit-DB пишется правильный лог.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from mcp_fssp.audit_db import AuditDb
from mcp_fssp.constants import DAMIA_BASE_URL
from mcp_fssp.context import ServiceContext
from mcp_fssp.errors import AuthFailedError, ValidationError
from mcp_fssp.providers.damia import DamiaProvider
from mcp_fssp.tools import (
    check_individual_debts,
    check_legal_entity_debts,
    get_proceeding_details,
)


@pytest.fixture
def damia_ctx(damia_config, audit_db: AuditDb) -> ServiceContext:
    provider = DamiaProvider(damia_config)
    return ServiceContext(config=damia_config, audit=audit_db, provider=provider)


class TestCheckIndividualDebts:
    @pytest.mark.asyncio
    async def test_happy_path_logs_to_audit(self, damia_ctx: ServiceContext) -> None:
        with respx.mock(assert_all_called=False) as mock:
            mock.get(DAMIA_BASE_URL).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "Петров Пётр": {
                            "ip": [
                                {
                                    "nomer": "9/9/9-ИП",
                                    "predmet": "Алименты",
                                    "summa": "1000",
                                    "isporg": "x",
                                }
                            ]
                        }
                    },
                )
            )
            r = await check_individual_debts(
                damia_ctx, fio="Петров Пётр", birth_date="1990-01-15"
            )
            assert r.found == 1
            count = await damia_ctx.audit.count()
            assert count == 1

    @pytest.mark.asyncio
    async def test_validation_error_logs_too(self, damia_ctx: ServiceContext) -> None:
        # Невалидный ФИО — должен бросить ДО HTTP. Но проверим что ошибка
        # пробрасывается. Лога не будет, потому что ошибка ДО старта таймера.
        with pytest.raises(ValidationError):
            await check_individual_debts(
                damia_ctx, fio="X", birth_date="1990-01-15"
            )

    @pytest.mark.asyncio
    async def test_provider_error_logs(self, damia_ctx: ServiceContext) -> None:
        with respx.mock(assert_all_called=False) as mock:
            mock.get(DAMIA_BASE_URL).mock(
                return_value=httpx.Response(401, text="bad token")
            )
            with pytest.raises(AuthFailedError):
                await check_individual_debts(
                    damia_ctx, fio="Петров Пётр", birth_date="1990-01-15"
                )
            count = await damia_ctx.audit.count()
            assert count == 1


class TestCheckLegalEntityDebts:
    @pytest.mark.asyncio
    async def test_inn(self, damia_ctx: ServiceContext) -> None:
        with respx.mock(assert_all_called=False) as mock:
            mock.get(DAMIA_BASE_URL).mock(
                return_value=httpx.Response(200, json={"ip": []})
            )
            r = await check_legal_entity_debts(damia_ctx, inn="7707083893")
            assert r.found == 0
            assert r.query.inn == "7707083893"

    @pytest.mark.asyncio
    async def test_ogrn(self, damia_ctx: ServiceContext) -> None:
        with respx.mock(assert_all_called=False) as mock:
            mock.get(DAMIA_BASE_URL).mock(
                return_value=httpx.Response(200, json={"ip": []})
            )
            r = await check_legal_entity_debts(damia_ctx, ogrn="1027700132195")
            assert r.query.ogrn == "1027700132195"

    @pytest.mark.asyncio
    async def test_neither(self, damia_ctx: ServiceContext) -> None:
        with pytest.raises(ValidationError):
            await check_legal_entity_debts(damia_ctx)

    @pytest.mark.asyncio
    async def test_invalid_inn(self, damia_ctx: ServiceContext) -> None:
        with pytest.raises(ValidationError):
            await check_legal_entity_debts(damia_ctx, inn="123")


class TestGetProceedingDetails:
    @pytest.mark.asyncio
    async def test_happy(self, damia_ctx: ServiceContext) -> None:
        with respx.mock(assert_all_called=False) as mock:
            mock.get(DAMIA_BASE_URL).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "1/1/1-ИП": {
                            "ip": [
                                {
                                    "nomer": "1/1/1-ИП",
                                    "predmet": "x",
                                    "summa": "100",
                                    "isporg": "x",
                                }
                            ]
                        }
                    },
                )
            )
            r = await get_proceeding_details(damia_ctx, proceeding_id="1/1/1-ИП")
            assert r.proceeding.id == "1/1/1-ИП"

    @pytest.mark.asyncio
    async def test_invalid_format(self, damia_ctx: ServiceContext) -> None:
        with pytest.raises(ValidationError):
            await get_proceeding_details(damia_ctx, proceeding_id="not-a-valid-id")
