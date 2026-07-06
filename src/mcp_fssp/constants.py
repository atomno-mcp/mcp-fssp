"""Все магические числа и enum-строки пакета.

Никакие другие модули НЕ должны вводить числовые константы (длины, лимиты,
коды ошибок, TTL, имена таблиц) на своих уровнях — всё собрано здесь,
чтобы ревью было одноточечным и изменение поведения не размазывалось
по коду.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Форматы официальных идентификаторов (ФНС РФ).
# Источники — SPEC §0 (глоссарий) и §4.1.
# ---------------------------------------------------------------------------

INN_LEGAL_LENGTH: Final[int] = 10
INN_INDIVIDUAL_LENGTH: Final[int] = 12
OGRN_LEGAL_LENGTH: Final[int] = 13
OGRNIP_LENGTH: Final[int] = 15

FIO_MIN_LENGTH: Final[int] = 5
FIO_MAX_LENGTH: Final[int] = 200

REGION_MIN_LENGTH: Final[int] = 2
REGION_MAX_LENGTH: Final[int] = 80

# Регекс для номера ИП (исполнительного производства) формата
# "12345/22/74033-ИП". Допускаем как кириллическую "ИП", так и
# латинскую "IP" — встречается у разных провайдеров.
PROCEEDING_ID_PATTERN: Final[str] = r"^\d+/\d+/\d+-(?:ИП|IP)$"

# ---------------------------------------------------------------------------
# Провайдеры.
# ---------------------------------------------------------------------------

PROVIDER_DAMIA: Final[str] = "damia"
PROVIDER_CHECKO: Final[str] = "checko"
PROVIDER_NEWDB: Final[str] = "newdb"
PROVIDER_API_CLOUD: Final[str] = "api_cloud"
PROVIDER_SELF_PARSER: Final[str] = "self_parser"
PROVIDER_ATOMNO_PRO: Final[str] = "atomno_pro"

ALL_PROVIDERS: Final[tuple[str, ...]] = (
    PROVIDER_DAMIA,
    PROVIDER_CHECKO,
    PROVIDER_NEWDB,
    PROVIDER_API_CLOUD,
    PROVIDER_SELF_PARSER,
    PROVIDER_ATOMNO_PRO,
)

# Провайдеры реализованные в текущей фазе.
IMPLEMENTED_PROVIDERS: Final[tuple[str, ...]] = (PROVIDER_DAMIA, PROVIDER_ATOMNO_PRO)

DEFAULT_PROVIDER: Final[str] = PROVIDER_ATOMNO_PRO
DEFAULT_BYOK_DAILY_LIMIT: Final[int] = 10

# ---------------------------------------------------------------------------
# Типы субъектов.
# ---------------------------------------------------------------------------

SUBJECT_TYPE_INDIVIDUAL: Final[str] = "individual"
SUBJECT_TYPE_LEGAL: Final[str] = "legal_entity"

# ---------------------------------------------------------------------------
# Категории предмета взыскания (см. SPEC §5.4 keyword-классификатор).
# ---------------------------------------------------------------------------

PROCEEDING_CATEGORIES: Final[tuple[str, ...]] = (
    "alimony",
    "tax",
    "fine_traffic",
    "credit",
    "utility",
    "other",
)

# ---------------------------------------------------------------------------
# Статусы исполнительного производства.
# ---------------------------------------------------------------------------

PROCEEDING_STATUSES: Final[tuple[str, ...]] = (
    "active",
    "completed",
    "suspended",
    "unknown",
)

# ---------------------------------------------------------------------------
# Коды ошибок (стабильный контракт для AI-клиентов; см. SPEC §5.1).
# ---------------------------------------------------------------------------

ERROR_CODE_VALIDATION: Final[str] = "invalid_input"
ERROR_CODE_NOT_FOUND: Final[str] = "not_found"
ERROR_CODE_PROVIDER_UNAVAILABLE: Final[str] = "provider_unavailable"
ERROR_CODE_AUTH_FAILED: Final[str] = "auth_failed"
ERROR_CODE_RATE_LIMITED: Final[str] = "rate_limited"
ERROR_CODE_CAPTCHA_FAILED: Final[str] = "captcha_failed"
ERROR_CODE_PARSE_ERROR: Final[str] = "parse_error"
ERROR_CODE_PRO_REQUIRED: Final[str] = "pro_required"
ERROR_CODE_NOT_IMPLEMENTED: Final[str] = "not_implemented"
ERROR_CODE_INTERNAL: Final[str] = "internal"

# ---------------------------------------------------------------------------
# HTTP / лимиты.
# ---------------------------------------------------------------------------

DEFAULT_HTTP_TIMEOUT_SECONDS: Final[float] = 15.0
DEFAULT_RPS: Final[int] = 30
DEFAULT_USER_AGENT: Final[str] = "mcp-fssp/0.1 (+https://github.com/atomno-mcp/mcp-fssp)"

# Максимальное количество запросов в одной batch-сессии (FR-104).
BATCH_MAX_QUERIES: Final[int] = 100

# ---------------------------------------------------------------------------
# Endpoints провайдеров.
# ---------------------------------------------------------------------------

DAMIA_BASE_URL: Final[str] = "https://api-fssp.damia.ru/api"
CHECKO_BASE_URL: Final[str] = "https://api.checko.ru/v2"
NEWDB_BASE_URL: Final[str] = "https://newdb.net/fssp/api"
API_CLOUD_BASE_URL: Final[str] = "https://api-cloud.ru/api/fssp.php"

# ---------------------------------------------------------------------------
# Hosted Pro.
# ---------------------------------------------------------------------------

HOSTED_API_BASE_DEFAULT: Final[str] = "https://api.atomno-mcp.ru/mcp-fssp/v1"

# ---------------------------------------------------------------------------
# SQLite (audit-лог).
# ---------------------------------------------------------------------------

DEFAULT_AUDIT_DB_FILENAME: Final[str] = "audit.sqlite"
TABLE_AUDIT_LOG: Final[str] = "audit_log"

# ---------------------------------------------------------------------------
# Имена env-переменных — в одном месте, чтобы не разъезжались между
# `config.py`, `.env.example` и Dockerfile.
# ---------------------------------------------------------------------------

ENV_PROVIDER: Final[str] = "MCP_FSSP_PROVIDER"
ENV_DAMIA_KEY: Final[str] = "MCP_FSSP_DAMIA_KEY"
ENV_CHECKO_KEY: Final[str] = "MCP_FSSP_CHECKO_KEY"
ENV_NEWDB_KEY: Final[str] = "MCP_FSSP_NEWDB_KEY"
ENV_API_CLOUD_KEY: Final[str] = "MCP_FSSP_API_CLOUD_KEY"
ENV_HOSTED_API_KEY: Final[str] = "MCP_FSSP_ATOMNO_API_KEY"
ENV_HOSTED_API_KEY_LEGACY: Final[str] = "ATOMNO_API_KEY"
ENV_HOSTED_API_BASE: Final[str] = "MCP_FSSP_ATOMNO_API_BASE"
ENV_HOSTED_API_BASE_LEGACY: Final[str] = "ATOMNO_API_BASE"
ENV_BYOK_DAILY_LIMIT: Final[str] = "MCP_FSSP_BYOK_DAILY_LIMIT"
ENV_HTTP_TIMEOUT: Final[str] = "MCP_FSSP_HTTP_TIMEOUT"
ENV_RPS: Final[str] = "MCP_FSSP_RPS"
ENV_USER_AGENT: Final[str] = "MCP_FSSP_USER_AGENT"
ENV_AUDIT_DB: Final[str] = "MCP_FSSP_AUDIT_DB"
ENV_LOG_LEVEL: Final[str] = "MCP_FSSP_LOG_LEVEL"
