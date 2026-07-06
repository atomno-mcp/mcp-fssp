"""FastMCP entrypoint для mcp-fssp.

Регистрирует тулзы:
    * `ping`                     — диагностика готовности.
    * `check_individual_debts`   — SPEC §5.1.
    * `check_legal_entity_debts` — SPEC §5.2.
    * `get_proceeding_details`   — SPEC §5.3.

`ServiceContext` создаётся лениво на первом вызове и переиспользуется
на весь процесс. Закрытие audit-DB — через `atexit`-хук.

Все ошибки тулзов обрабатываются ТОЛЬКО через `McpFsspError.to_dict()` —
никаких silent fallback или null-возвратов.
"""

from __future__ import annotations

import argparse
import asyncio
import atexit
import logging
import os
import sys
from typing import Any

from fastmcp import FastMCP

from . import __version__
from .constants import ENV_LOG_LEVEL
from .context import ServiceContext
from .errors import McpFsspError, ValidationError
from .schemas import PingResponse
from .tools import (
    check_individual_debts as _check_individual_impl,
)
from .tools import (
    check_legal_entity_debts as _check_legal_impl,
)
from .tools import (
    get_proceeding_details as _get_details_impl,
)

logger = logging.getLogger("mcp_fssp")

mcp: FastMCP = FastMCP(
    name="mcp-fssp",
    instructions=(
        "MCP-сервер для проверки задолженностей через ФССП РФ. "
        "Три тулза: check_individual_debts (физ.лицо по ФИО+ДР), "
        "check_legal_entity_debts (юр.лицо/ИП по ИНН/ОГРН), "
        "get_proceeding_details (карточка одного ИП). "
        "Текущая фаза — Phase 1, поддерживается провайдер Damia API-ФССП. "
        "Источник данных: api-fssp.damia.ru. Требуется MCP_FSSP_DAMIA_KEY."
    ),
)

_ctx: ServiceContext | None = None
_ctx_lock = asyncio.Lock()


async def _get_ctx() -> ServiceContext:
    global _ctx
    if _ctx is not None:
        return _ctx
    async with _ctx_lock:
        if _ctx is None:
            ctx = ServiceContext.from_env()
            await ctx.__aenter__()
            _ctx = ctx
            atexit.register(_close_ctx_atexit)
    assert _ctx is not None
    return _ctx


def _close_ctx_atexit() -> None:
    if _ctx is None:
        return
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_ctx.__aexit__(None, None, None))
        loop.close()
    except Exception:  # pragma: no cover - best-effort cleanup
        pass


def _err(exc: McpFsspError) -> dict[str, Any]:
    return exc.to_dict()


# ---------------------------------------------------------------------------
# Тулзы MCP.
# ---------------------------------------------------------------------------


@mcp.tool()
async def ping() -> dict[str, Any]:
    """Диагностика: сервер жив, сообщает версию и текущий провайдер."""
    try:
        ctx = await _get_ctx()
    except McpFsspError as exc:
        return _err(exc)

    response = PingResponse(
        version=__version__,
        provider=ctx.config.provider,  # type: ignore[arg-type]
        provider_configured=ctx.config.provider_configured,
        hosted_mode_enabled=ctx.config.hosted_mode_enabled,
    )
    return response.model_dump(mode="json")


@mcp.tool()
async def check_individual_debts(
    fio: str,
    birth_date: str,
    region: str | None = None,
) -> dict[str, Any]:
    """Проверить открытые исполнительные производства на физ.лицо.

    Запрос содержит ПДн — используйте только в законных целях (due-diligence,
    скоринг по согласию субъекта) с соблюдением 152-ФЗ.

    Args:
        fio: ФИО полностью на кириллице. Пример: "Иванов Иван Иванович".
        birth_date: Дата рождения в формате "YYYY-MM-DD" или "dd.mm.yyyy".
        region: Опционально — код или название субъекта РФ для ускорения поиска.

    Returns:
        Объект с полями `query`, `found`, `not_found`, `proceedings`,
        `fetched_at`, `source`. См. SPEC §5.1 для полной схемы.
    """
    try:
        ctx = await _get_ctx()
        response = await _check_individual_impl(
            ctx, fio=fio, birth_date=birth_date, region=region
        )
        return response.model_dump(mode="json")
    except McpFsspError as exc:
        return _err(exc)


@mcp.tool()
async def check_legal_entity_debts(
    inn: str | None = None,
    ogrn: str | None = None,
) -> dict[str, Any]:
    """Проверить открытые исполнительные производства на юр.лицо или ИП-предпринимателя.

    Args:
        inn: ИНН (10 цифр для юр.лица или 12 для ИП-предпринимателя).
        ogrn: ОГРН (13 цифр) или ОГРНИП (15 цифр). Хотя бы один из двух
            параметров должен быть передан.

    Returns:
        Объект с тем же контрактом, что и `check_individual_debts`.
        В `query` отражается `inn` или `ogrn`. См. SPEC §5.2.
    """
    try:
        ctx = await _get_ctx()
        response = await _check_legal_impl(ctx, inn=inn, ogrn=ogrn)
        return response.model_dump(mode="json")
    except McpFsspError as exc:
        return _err(exc)


@mcp.tool()
async def get_proceeding_details(proceeding_id: str) -> dict[str, Any]:
    """Получить детальную карточку конкретного ИП по его номеру.

    Args:
        proceeding_id: Номер ИП в формате "12345/22/74033-ИП".

    Returns:
        Объект `ProceedingDetails`: расширенная карточка с полями
        `bailiff_full_name`, `bailiff_email`, `case_basis`, `documents`.
        См. SPEC §5.3.
    """
    try:
        ctx = await _get_ctx()
        response = await _get_details_impl(ctx, proceeding_id=proceeding_id)
        return response.model_dump(mode="json")
    except McpFsspError as exc:
        return _err(exc)


# ---------------------------------------------------------------------------
# Точка входа CLI.
# ---------------------------------------------------------------------------

_SUPPORTED_TRANSPORTS = ("stdio", "http", "sse", "streamable-http")
_DEFAULT_TRANSPORT = "stdio"
_DEFAULT_HTTP_HOST = "127.0.0.1"
_DEFAULT_HTTP_PORT = 8000
_VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

_CLI_DESCRIPTION = (
    "MCP-сервер для проверки задолженностей в ФССП РФ "
    "(физ.лица по ФИО+ДР, юр.лица/ИП по ИНН/ОГРН). "
    "По умолчанию запускается по MCP stdio-транспорту для интеграции с Cursor, "
    "Claude Desktop, Claude Code и другими MCP-клиентами."
)

_CLI_EPILOG = (
    "Примеры:\n"
    "  atomno-mcp-fssp                              # stdio для MCP-клиента\n"
    "  atomno-mcp-fssp --transport http --port 8000\n"
    "  atomno-mcp-fssp --check-config\n"
    "\n"
    "Переменные окружения:\n"
    "  MCP_FSSP_PROVIDER   — провайдер данных (по умолчанию damia).\n"
    "  MCP_FSSP_DAMIA_KEY  — токен Damia API-ФССП.\n"
    "  MCP_FSSP_LOG_LEVEL  — уровень логирования (перекрывается --log-level).\n"
    "\n"
    "Документация: https://github.com/atomno-mcp/mcp-fssp"
)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atomno-mcp-fssp",
        description=_CLI_DESCRIPTION,
        epilog=_CLI_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"atomno-mcp-fssp {__version__}",
        help="показать версию пакета и выйти",
    )
    parser.add_argument(
        "--transport",
        "-t",
        choices=_SUPPORTED_TRANSPORTS,
        default=_DEFAULT_TRANSPORT,
        help=(
            f"MCP-транспорт (по умолчанию: {_DEFAULT_TRANSPORT}). "
            "stdio — для локальных MCP-клиентов; http/sse/streamable-http — для сетевых."
        ),
    )
    parser.add_argument(
        "--host",
        default=_DEFAULT_HTTP_HOST,
        help=(
            f"Хост для http/sse/streamable-http транспортов (по умолчанию: {_DEFAULT_HTTP_HOST}). "
            "Игнорируется для stdio."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_DEFAULT_HTTP_PORT,
        help=(
            f"Порт для http/sse/streamable-http транспортов (по умолчанию: {_DEFAULT_HTTP_PORT}). "
            "Игнорируется для stdio."
        ),
    )
    parser.add_argument(
        "--log-level",
        "-l",
        choices=_VALID_LOG_LEVELS,
        default=None,
        help=(
            "Уровень логирования; перекрывает переменную MCP_FSSP_LOG_LEVEL. "
            "По умолчанию INFO."
        ),
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Проверить конфигурацию (env vars, наличие токена) и выйти.",
    )
    return parser


def _resolve_log_level(cli_value: str | None) -> str:
    """CLI-флаг имеет приоритет над env; фолбэк — INFO."""
    if cli_value is not None:
        return cli_value
    env_raw = os.environ.get(ENV_LOG_LEVEL)
    if env_raw is None:
        return "INFO"
    env_norm = env_raw.strip().upper()
    if env_norm in _VALID_LOG_LEVELS:
        return env_norm
    raise ValueError(
        f"{ENV_LOG_LEVEL}={env_raw!r} — недопустимое значение. "
        f"Допустимые: {', '.join(_VALID_LOG_LEVELS)}."
    )


def main(argv: list[str] | None = None) -> int:
    """Точка входа CLI.

    Returns:
        0 — штатное завершение; 2 — ошибка конфигурации.
    """
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    try:
        log_level = _resolve_log_level(args.log_level)
    except ValueError as exc:
        parser.error(str(exc))
        return 2  # pragma: no cover - parser.error вызывает SystemExit(2)

    try:
        ctx_template = ServiceContext.from_env()
    except McpFsspError as exc:
        logging.basicConfig(level="INFO", format="%(message)s")
        logger.error("atomno-mcp-fssp: %s", exc.message_ru)
        if exc.hint:
            logger.error("Подсказка: %s", exc.hint)
        raise SystemExit(2) from exc
    except ValidationError as exc:
        logging.basicConfig(level="INFO")
        logger.error("atomno-mcp-fssp: невалидная конфигурация — %s", exc.message_ru)
        raise SystemExit(2) from exc

    if args.check_config:
        sys.stdout.write(
            f"atomno-mcp-fssp {__version__}\n"
            f"  provider:            {ctx_template.config.provider}\n"
            f"  provider_configured: {ctx_template.config.provider_configured}\n"
            f"  hosted_mode:         {ctx_template.config.hosted_mode_enabled}\n"
            f"  audit_db:            {ctx_template.config.audit_db_path}\n"
            f"  http_timeout:        {ctx_template.config.http_timeout_seconds}s\n"
            f"  log_level:           {log_level}\n"
            "OK: конфигурация валидна.\n"
        )
        return 0

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info(
        "atomno-mcp-fssp %s starting (transport=%s, provider=%s, hosted=%s)",
        __version__,
        args.transport,
        ctx_template.config.provider,
        ctx_template.config.hosted_mode_enabled,
    )

    run_kwargs: dict[str, Any] = {"transport": args.transport}
    if args.transport in {"http", "sse", "streamable-http"}:
        run_kwargs["host"] = args.host
        run_kwargs["port"] = args.port
    mcp.run(**run_kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
