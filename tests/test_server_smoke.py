"""Smoke-тесты на уровне FastMCP `mcp` объекта.

Проверяем что:
  * сервер импортируется без ошибок;
  * зарегистрированы все 4 тулза;
  * `ping` возвращает структурированный ответ при валидной конфигурации;
  * ошибка тулза превращается в dict с полем `error: True`, а не traceback.
"""

from __future__ import annotations

import httpx
import pytest
import respx


def test_server_imports() -> None:
    from mcp_fssp import server

    assert server.mcp is not None
    assert server.mcp.name == "mcp-fssp"


@pytest.mark.asyncio
async def test_tools_registered() -> None:
    from mcp_fssp.server import mcp

    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert "ping" in names
    assert "check_individual_debts" in names
    assert "check_legal_entity_debts" in names
    assert "get_proceeding_details" in names


@pytest.mark.asyncio
async def test_ping_returns_dict(damia_config) -> None:
    """Через прямой вызов impl-функции тулза (минуем FastMCP-роутер)."""
    import mcp_fssp.server as srv

    # Заменяем глобальный _ctx чтобы не пересоздавать.
    from mcp_fssp.audit_db import AuditDb
    from mcp_fssp.context import ServiceContext
    from mcp_fssp.providers.damia import DamiaProvider

    audit = AuditDb(damia_config.audit_db_path)
    await audit.init()
    provider = DamiaProvider(damia_config)
    srv._ctx = ServiceContext(config=damia_config, audit=audit, provider=provider)
    try:
        result = await srv.ping()
        assert isinstance(result, dict)
        assert result.get("ok") is True
        assert result["service"] == "mcp-fssp"
        assert result["provider"] == "damia"
        assert result["provider_configured"] is True
    finally:
        await audit.close()
        srv._ctx = None


@pytest.mark.asyncio
async def test_check_individual_debts_returns_error_dict_on_failure(
    damia_config,
) -> None:
    """При ошибке тулз должен вернуть dict со структурой ошибки, не traceback."""
    import mcp_fssp.server as srv
    from mcp_fssp.audit_db import AuditDb
    from mcp_fssp.constants import DAMIA_BASE_URL
    from mcp_fssp.context import ServiceContext
    from mcp_fssp.providers.damia import DamiaProvider

    audit = AuditDb(damia_config.audit_db_path)
    await audit.init()
    provider = DamiaProvider(damia_config)
    srv._ctx = ServiceContext(config=damia_config, audit=audit, provider=provider)
    try:
        with respx.mock(assert_all_called=False) as mock:
            mock.get(DAMIA_BASE_URL).mock(
                return_value=httpx.Response(401, text="bad token")
            )
            result = await srv.check_individual_debts(
                fio="Иванов Иван", birth_date="1990-01-15"
            )
        assert isinstance(result, dict)
        assert result.get("error") is True
        assert result.get("code") == "auth_failed"
    finally:
        await audit.close()
        srv._ctx = None


@pytest.mark.asyncio
async def test_check_individual_debts_validation_error(damia_config) -> None:
    """Валидационная ошибка тоже → dict, не raise."""
    import mcp_fssp.server as srv
    from mcp_fssp.audit_db import AuditDb
    from mcp_fssp.context import ServiceContext
    from mcp_fssp.providers.damia import DamiaProvider

    audit = AuditDb(damia_config.audit_db_path)
    await audit.init()
    provider = DamiaProvider(damia_config)
    srv._ctx = ServiceContext(config=damia_config, audit=audit, provider=provider)
    try:
        result = await srv.check_individual_debts(
            fio="X",  # слишком короткое
            birth_date="1990-01-15",
        )
        assert isinstance(result, dict)
        assert result.get("error") is True
        assert result.get("code") == "invalid_input"
    finally:
        await audit.close()
        srv._ctx = None
