"""Тесты `DamiaProvider` через respx (мокинг httpx)."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx

from mcp_fssp.config import Config
from mcp_fssp.constants import DAMIA_BASE_URL
from mcp_fssp.errors import (
    AuthFailedError,
    ParseError,
    ProviderUnavailableError,
    RateLimitedError,
    ValidationError,
)
from mcp_fssp.providers.damia import DamiaProvider


def _make_provider(config: Config) -> DamiaProvider:
    return DamiaProvider(config)


class TestInit:
    def test_no_key_raises(self, clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        monkeypatch.setenv("MCP_FSSP_PROVIDER", "damia")
        monkeypatch.setenv("MCP_FSSP_AUDIT_DB", str(tmp_path / "audit.sqlite"))
        config = Config.from_env()
        with pytest.raises(AuthFailedError):
            DamiaProvider(config)


class TestCheckIndividual:
    @pytest.mark.asyncio
    async def test_happy_path(self, damia_config: Config) -> None:
        provider = _make_provider(damia_config)
        with respx.mock(assert_all_called=False) as mock:
            route = mock.get(DAMIA_BASE_URL).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "Иванов Иван": {
                            "ip": [
                                {
                                    "nomer": "12345/22/74033-ИП",
                                    "predmet": "Алименты",
                                    "summa": "100000",
                                    "isporg": "Тверской РОСП",
                                }
                            ]
                        }
                    },
                )
            )
            resp = await provider.check_individual(
                fio="Иванов Иван", birth_date=date(1990, 1, 15)
            )
            assert resp.found == 1
            assert resp.proceedings[0].subject_type == "alimony"
            assert route.called
            req = route.calls.last.request
            assert "fio=" in str(req.url)
            assert "dataR=15.01.1990" in str(req.url)
            assert "key=test-damia-token" in str(req.url)

    @pytest.mark.asyncio
    async def test_empty_response(self, damia_config: Config) -> None:
        provider = _make_provider(damia_config)
        with respx.mock(assert_all_called=False) as mock:
            mock.get(DAMIA_BASE_URL).mock(
                return_value=httpx.Response(
                    200, json={"status": "Ничего не найдено"}
                )
            )
            resp = await provider.check_individual(
                fio="Иванов Иван", birth_date=date(1990, 1, 15)
            )
            assert resp.found == 0
            assert resp.not_found is True

    @pytest.mark.asyncio
    async def test_401_auth_failed(self, damia_config: Config) -> None:
        provider = _make_provider(damia_config)
        with respx.mock(assert_all_called=False) as mock:
            mock.get(DAMIA_BASE_URL).mock(
                return_value=httpx.Response(401, text="Unauthorized")
            )
            with pytest.raises(AuthFailedError):
                await provider.check_individual(
                    fio="Иванов Иван", birth_date=date(1990, 1, 15)
                )

    @pytest.mark.asyncio
    async def test_429_rate_limited(self, damia_config: Config) -> None:
        provider = _make_provider(damia_config)
        with respx.mock(assert_all_called=False) as mock:
            mock.get(DAMIA_BASE_URL).mock(
                return_value=httpx.Response(429, text="Too Many Requests")
            )
            with pytest.raises(RateLimitedError):
                await provider.check_individual(
                    fio="Иванов Иван", birth_date=date(1990, 1, 15)
                )

    @pytest.mark.asyncio
    async def test_500_provider_unavailable(self, damia_config: Config) -> None:
        provider = _make_provider(damia_config)
        with respx.mock(assert_all_called=False) as mock:
            mock.get(DAMIA_BASE_URL).mock(
                return_value=httpx.Response(500, text="Server Error")
            )
            with pytest.raises(ProviderUnavailableError):
                await provider.check_individual(
                    fio="Иванов Иван", birth_date=date(1990, 1, 15)
                )

    @pytest.mark.asyncio
    async def test_timeout(self, damia_config: Config) -> None:
        provider = _make_provider(damia_config)
        with respx.mock(assert_all_called=False) as mock:
            mock.get(DAMIA_BASE_URL).mock(side_effect=httpx.TimeoutException("timed out"))
            with pytest.raises(ProviderUnavailableError):
                await provider.check_individual(
                    fio="Иванов Иван", birth_date=date(1990, 1, 15)
                )

    @pytest.mark.asyncio
    async def test_invalid_json(self, damia_config: Config) -> None:
        provider = _make_provider(damia_config)
        with respx.mock(assert_all_called=False) as mock:
            mock.get(DAMIA_BASE_URL).mock(
                return_value=httpx.Response(200, text="<html>nope</html>")
            )
            with pytest.raises(ParseError):
                await provider.check_individual(
                    fio="Иванов Иван", birth_date=date(1990, 1, 15)
                )

    @pytest.mark.asyncio
    async def test_invalid_fio_no_http(self, damia_config: Config) -> None:
        """Невалидный ФИО — ошибка ДО HTTP-вызова."""
        provider = _make_provider(damia_config)
        with respx.mock(assert_all_called=False) as mock:
            route = mock.get(DAMIA_BASE_URL).mock(
                return_value=httpx.Response(200, json={"ip": []})
            )
            with pytest.raises(ValidationError):
                await provider.check_individual(
                    fio="X", birth_date=date(1990, 1, 15)
                )
            assert not route.called


class TestCheckLegalEntity:
    @pytest.mark.asyncio
    async def test_inn(self, damia_config: Config) -> None:
        provider = _make_provider(damia_config)
        with respx.mock(assert_all_called=False) as mock:
            route = mock.get(DAMIA_BASE_URL).mock(
                return_value=httpx.Response(200, json={"7707083893": {"ip": []}})
            )
            resp = await provider.check_legal_entity(inn="7707083893")
            assert resp.found == 0
            assert "inn=7707083893" in str(route.calls.last.request.url)

    @pytest.mark.asyncio
    async def test_ogrn(self, damia_config: Config) -> None:
        provider = _make_provider(damia_config)
        with respx.mock(assert_all_called=False) as mock:
            route = mock.get(DAMIA_BASE_URL).mock(
                return_value=httpx.Response(200, json={"ip": []})
            )
            resp = await provider.check_legal_entity(ogrn="1027700132195")
            assert resp.found == 0
            assert "ogrn=1027700132195" in str(route.calls.last.request.url)

    @pytest.mark.asyncio
    async def test_neither_param(self, damia_config: Config) -> None:
        provider = _make_provider(damia_config)
        with pytest.raises(ValidationError):
            await provider.check_legal_entity()

    @pytest.mark.asyncio
    async def test_invalid_inn(self, damia_config: Config) -> None:
        provider = _make_provider(damia_config)
        with pytest.raises(ValidationError):
            await provider.check_legal_entity(inn="123")


class TestGetProceeding:
    @pytest.mark.asyncio
    async def test_happy(self, damia_config: Config) -> None:
        provider = _make_provider(damia_config)
        with respx.mock(assert_all_called=False) as mock:
            mock.get(DAMIA_BASE_URL).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "12345/22/74033-ИП": {
                            "ip": [
                                {
                                    "nomer": "12345/22/74033-ИП",
                                    "predmet": "Кредит",
                                    "summa": "50000",
                                    "isporg": "x",
                                    "ispdoc": "Решение",
                                }
                            ]
                        }
                    },
                )
            )
            resp = await provider.get_proceeding("12345/22/74033-ИП")
            assert resp.proceeding.id == "12345/22/74033-ИП"
            assert resp.proceeding.case_basis == "Решение"

    @pytest.mark.asyncio
    async def test_empty_id(self, damia_config: Config) -> None:
        provider = _make_provider(damia_config)
        with pytest.raises(ValidationError):
            await provider.get_proceeding("")
