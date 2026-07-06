"""Pydantic v2 модели входов/выходов тулзов mcp-fssp.

См. SPEC §7.3 для контракта `Proceeding` и §5.* для оборачивающих структур.

Все поля русскоязычной семантики (например, `subject_text`) хранятся в
исходном виде — без транслитерации и нормализации. Категоризация
делается на уровне `subject_type` отдельным энумом.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Литералы (синхронизированы с constants.py).
# ---------------------------------------------------------------------------

SubjectType = Literal["individual", "legal_entity"]
ProceedingCategory = Literal[
    "alimony", "tax", "fine_traffic", "credit", "utility", "other"
]
ProceedingStatus = Literal["active", "completed", "suspended", "unknown"]
ProviderName = Literal[
    "damia",
    "checko",
    "newdb",
    "api_cloud",
    "self_parser",
    "atomno_pro",
    "atomno_pro_cache",
]


# ---------------------------------------------------------------------------
# Базовая модель.
# ---------------------------------------------------------------------------


class _Base(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="ignore",
        populate_by_name=True,
    )


# ---------------------------------------------------------------------------
# Эхо запроса (повторяется в каждом ответе для отладки и логирования).
# ---------------------------------------------------------------------------


class QueryEcho(_Base):
    """Что именно мы отправили на провайдер.

    Хотя бы одно из полей должно быть заполнено. Для ФИО+ДР заполняем
    оба, для юр.лица — `inn` или `ogrn`. Поле `region` опционально.
    """

    fio: str | None = None
    birth_date: date | None = None
    inn: str | None = None
    ogrn: str | None = None
    region: str | None = None


# ---------------------------------------------------------------------------
# Исполнительное производство — нормализованная модель.
# ---------------------------------------------------------------------------


class Proceeding(_Base):
    """Одно открытое или закрытое исполнительное производство.

    Поля минимально гарантированные провайдерами:
      * `id` — номер ИП формата `12345/22/74033-ИП`.
      * `subject_text` — текст предмета взыскания (как пришёл).
      * `amount_rub` — сумма по решению, рубли. Decimal для точности.
      * `executor_office` — структурное подразделение приставов.
      * `source_provider` — кто отдал запись.
      * `fetched_at` — когда мы её получили.

    Опциональные (могут отсутствовать у конкретных провайдеров):
      * `case_number`, `started_at`, `amount_remaining_rub`,
        `executor_phone`, `bailiff_full_name`, `case_basis`.
    """

    id: str = Field(..., description="Номер ИП, например '12345/22/74033-ИП'.")
    case_number: str | None = Field(
        default=None,
        description="Номер судебного дела, ставшего основанием.",
    )
    started_at: date | None = Field(
        default=None, description="Дата возбуждения ИП."
    )
    subject_type: ProceedingCategory = Field(
        default="other",
        description="Категория предмета взыскания (классификатор).",
    )
    subject_text: str = Field(..., description="Предмет взыскания, текстом.")
    amount_rub: Decimal = Field(..., description="Сумма по решению, рубли.")
    amount_remaining_rub: Decimal | None = Field(
        default=None, description="Остаток долга на момент запроса."
    )
    status: ProceedingStatus = Field(
        default="unknown", description="Статус ИП."
    )
    executor_office: str = Field(
        ..., description="Структурное подразделение (отдел) приставов."
    )
    executor_phone: str | None = None
    bailiff_full_name: str | None = None
    bailiff_email: str | None = None
    case_basis: str | None = Field(
        default=None,
        description="Основание (например, 'Решение Тверского районного суда').",
    )
    fetched_at: datetime
    source_provider: ProviderName

    @field_validator("amount_rub", "amount_remaining_rub", mode="before")
    @classmethod
    def _coerce_decimal(cls, v: Any) -> Any:
        if v is None or isinstance(v, Decimal):
            return v
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        if isinstance(v, str):
            cleaned = v.replace(" ", "").replace(",", ".")
            return Decimal(cleaned) if cleaned else Decimal("0")
        return v


# ---------------------------------------------------------------------------
# Ответы тулзов.
# ---------------------------------------------------------------------------


class CheckDebtsResponse(_Base):
    """Ответ `check_individual_debts` / `check_legal_entity_debts`."""

    query: QueryEcho
    found: int = Field(..., description="Сколько ИП найдено.")
    not_found: bool = Field(
        default=False,
        description="True, если провайдер явно сообщил «нет данных».",
    )
    proceedings: list[Proceeding] = Field(default_factory=list)
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    source: ProviderName


class ProceedingDetails(_Base):
    """Ответ `get_proceeding_details` — расширенная карточка."""

    query: dict[str, str]
    proceeding: Proceeding
    documents: list[dict[str, Any]] = Field(default_factory=list)
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    source: ProviderName


# ---------------------------------------------------------------------------
# Ping-ответ.
# ---------------------------------------------------------------------------


class PingResponse(_Base):
    """Диагностика готовности сервера."""

    ok: bool = True
    service: str = "mcp-fssp"
    version: str
    provider: ProviderName
    provider_configured: bool = Field(
        ...,
        description=(
            "True если для текущего провайдера задан токен (или провайдер "
            "не требует токена)."
        ),
    )
    hosted_mode_enabled: bool = False
