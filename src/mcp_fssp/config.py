"""Чтение переменных окружения в типизированную структуру `Config`.

Единая точка, где пакет обращается к `os.environ`. Все остальные модули
работают через `Config` или через `ServiceContext` (см. context.py).

Ошибка парсинга числового env-значения — НЕ silent fallback на дефолт.
Мы поднимаем `ValidationError` с точным указанием переменной и значения,
чтобы `mcp-fssp` не стартовал с «молча исправленной» конфигурацией.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .constants import (
    ALL_PROVIDERS,
    DEFAULT_AUDIT_DB_FILENAME,
    DEFAULT_BYOK_DAILY_LIMIT,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_PROVIDER,
    DEFAULT_RPS,
    DEFAULT_USER_AGENT,
    ENV_API_CLOUD_KEY,
    ENV_AUDIT_DB,
    ENV_BYOK_DAILY_LIMIT,
    ENV_CHECKO_KEY,
    ENV_DAMIA_KEY,
    ENV_HOSTED_API_BASE,
    ENV_HOSTED_API_BASE_LEGACY,
    ENV_HOSTED_API_KEY,
    ENV_HOSTED_API_KEY_LEGACY,
    ENV_HTTP_TIMEOUT,
    ENV_LOG_LEVEL,
    ENV_NEWDB_KEY,
    ENV_PROVIDER,
    ENV_RPS,
    ENV_USER_AGENT,
    HOSTED_API_BASE_DEFAULT,
    PROVIDER_ATOMNO_PRO,
    PROVIDER_DAMIA,
    PROVIDER_SELF_PARSER,
)
from .errors import ValidationError


@dataclass(frozen=True)
class Config:
    """Типизированный снимок env на момент старта сервера."""

    provider: str
    damia_key: str | None
    checko_key: str | None
    newdb_key: str | None
    api_cloud_key: str | None
    hosted_api_key: str | None
    hosted_api_base: str
    http_timeout_seconds: float
    rps: int
    user_agent: str
    audit_db_path: Path
    log_level: str
    byok_daily_limit: int

    @property
    def hosted_mode_enabled(self) -> bool:
        """Если пользователь задал Atomno API-ключ и провайдер `atomno_pro`."""
        return (
            self.provider == PROVIDER_ATOMNO_PRO
            and self.hosted_api_key is not None
            and self.hosted_api_key != ""
        )

    @property
    def provider_configured(self) -> bool:
        """Есть ли валидный токен под выбранный провайдер.

        Для self-parser токен не требуется (но капча требует доп.настройки —
        проверяется в самом провайдере).
        """
        if self.provider == PROVIDER_DAMIA:
            return bool(self.damia_key)
        if self.provider == "checko":
            return bool(self.checko_key)
        if self.provider == "newdb":
            return bool(self.newdb_key)
        if self.provider == "api_cloud":
            return bool(self.api_cloud_key)
        if self.provider == PROVIDER_SELF_PARSER:
            return True
        if self.provider == PROVIDER_ATOMNO_PRO:
            return bool(self.hosted_api_key)
        return False

    @classmethod
    def from_env(cls) -> Config:
        provider = (os.environ.get(ENV_PROVIDER) or DEFAULT_PROVIDER).strip().lower()
        if provider not in ALL_PROVIDERS:
            raise ValidationError(
                f"Неизвестный провайдер '{provider}' в {ENV_PROVIDER}.",
                hint=f"Допустимые значения: {', '.join(ALL_PROVIDERS)}.",
                details={"env_var": ENV_PROVIDER, "value": provider},
            )

        cwd = Path.cwd()
        audit_db = Path(
            os.environ.get(ENV_AUDIT_DB) or str(cwd / DEFAULT_AUDIT_DB_FILENAME)
        )
        timeout = _parse_float_env(ENV_HTTP_TIMEOUT, DEFAULT_HTTP_TIMEOUT_SECONDS)
        rps = _parse_int_env(ENV_RPS, DEFAULT_RPS)
        user_agent = os.environ.get(ENV_USER_AGENT) or DEFAULT_USER_AGENT
        log_level = (os.environ.get(ENV_LOG_LEVEL) or "INFO").upper()
        hosted_base = (
            os.environ.get(ENV_HOSTED_API_BASE)
            or os.environ.get(ENV_HOSTED_API_BASE_LEGACY)
            or HOSTED_API_BASE_DEFAULT
        )
        hosted_key = _clean_optional(os.environ.get(ENV_HOSTED_API_KEY)) or _clean_optional(
            os.environ.get(ENV_HOSTED_API_KEY_LEGACY)
        )
        byok_limit = _parse_int_env(ENV_BYOK_DAILY_LIMIT, DEFAULT_BYOK_DAILY_LIMIT)

        return cls(
            provider=provider,
            damia_key=_clean_optional(os.environ.get(ENV_DAMIA_KEY)),
            checko_key=_clean_optional(os.environ.get(ENV_CHECKO_KEY)),
            newdb_key=_clean_optional(os.environ.get(ENV_NEWDB_KEY)),
            api_cloud_key=_clean_optional(os.environ.get(ENV_API_CLOUD_KEY)),
            hosted_api_key=hosted_key,
            hosted_api_base=hosted_base,
            http_timeout_seconds=timeout,
            rps=rps,
            user_agent=user_agent,
            audit_db_path=audit_db,
            log_level=log_level,
            byok_daily_limit=byok_limit,
        )


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _parse_float_env(var_name: str, default: float) -> float:
    raw = os.environ.get(var_name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            (
                f"Переменная окружения {var_name}='{raw}' — невалидное "
                f"число с плавающей точкой."
            ),
            hint=f"Ожидается положительное число секунд, например '{default}'.",
            details={"env_var": var_name, "value": raw},
        ) from exc
    if value <= 0:
        raise ValidationError(
            f"Переменная окружения {var_name}={raw} должна быть > 0.",
            hint=f"Значение по умолчанию: {default} секунд.",
            details={"env_var": var_name, "value": raw},
        )
    return value


def _parse_int_env(var_name: str, default: int) -> int:
    raw = os.environ.get(var_name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"Переменная окружения {var_name}='{raw}' — невалидное целое число.",
            hint=f"Значение по умолчанию: {default}.",
            details={"env_var": var_name, "value": raw},
        ) from exc
    if value <= 0:
        raise ValidationError(
            f"Переменная окружения {var_name}={raw} должна быть > 0.",
            details={"env_var": var_name, "value": raw},
        )
    return value
