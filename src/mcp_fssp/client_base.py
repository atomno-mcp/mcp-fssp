"""Абстрактный базовый класс провайдеров и общие HTTP-утилиты.

Все провайдеры (Damia / Checko / NewDB / api-cloud / self-parser /
atomno-pro) наследуются от `AbstractProviderClient`. Это даёт единую
точку для:

  * перевода HTTP-ошибок провайдера в наши `McpFsspError`-подклассы;
  * учёта таймаутов, retry-логики (TBD в Phase 3);
  * мокинга в тестах (через `pytest-respx`).
"""

from __future__ import annotations

import abc
from datetime import date

import httpx

from .config import Config
from .errors import (
    AuthFailedError,
    ProviderUnavailableError,
    RateLimitedError,
)
from .schemas import CheckDebtsResponse, ProceedingDetails


class AbstractProviderClient(abc.ABC):
    """Контракт для всех провайдеров FSSP-данных.

    Реализации обязаны:
      * корректно нормализовать вход (через `normalize.py`);
      * парсить ответ провайдера в `Proceeding[]` (через `parsers/{name}.py`);
      * мапить HTTP-ошибки на McpFsspError-исключения через `_map_http_error`.
    """

    name: str = "abstract"
    requires_token: bool = True

    def __init__(self, config: Config) -> None:
        self._config = config

    @property
    def config(self) -> Config:
        return self._config

    @abc.abstractmethod
    async def check_individual(
        self,
        *,
        fio: str,
        birth_date: date,
        region: str | None = None,
    ) -> CheckDebtsResponse:
        """Запросить ИП по физ.лицу."""

    @abc.abstractmethod
    async def check_legal_entity(
        self,
        *,
        inn: str | None = None,
        ogrn: str | None = None,
    ) -> CheckDebtsResponse:
        """Запросить ИП по юр.лицу или ИП-предпринимателю."""

    @abc.abstractmethod
    async def get_proceeding(self, proceeding_id: str) -> ProceedingDetails:
        """Получить расширенную карточку ИП по номеру."""

    # ------------------------------------------------------------------
    # Общие утилиты — HTTP-клиент и маппинг ошибок.
    # ------------------------------------------------------------------

    def make_httpx_client(self) -> httpx.AsyncClient:
        """Создать httpx-клиент с конфигом таймаута и User-Agent.

        Каждый вызов тулза создаёт **новый** клиент: stdio-MCP всё равно
        не bench-сценарий, а изоляция упрощает тестирование (respx).
        """
        return httpx.AsyncClient(
            timeout=self._config.http_timeout_seconds,
            headers={"User-Agent": self._config.user_agent},
        )

    def map_http_error(
        self, exc: BaseException, *, provider_name: str
    ) -> Exception:
        """Преобразовать httpx/Timeout-ошибки в наши McpFsspError-исключения."""
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            if status in (401, 403):
                return AuthFailedError(
                    f"Провайдер {provider_name} отверг запрос (HTTP {status}).",
                    hint=(
                        "Проверьте, что токен задан в .env и не истёк. "
                        "На стороне провайдера зайдите в личный кабинет и "
                        "сверьте баланс/лимиты."
                    ),
                    details={"http_status": status, "provider": provider_name},
                )
            if status == 429:
                return RateLimitedError(
                    f"Провайдер {provider_name} вернул 429 (rate-limit).",
                    hint=(
                        "Подождите минуту и повторите запрос либо снизьте "
                        "MCP_FSSP_RPS в конфиге."
                    ),
                    details={"http_status": 429, "provider": provider_name},
                )
            if 500 <= status < 600:
                return ProviderUnavailableError(
                    f"Провайдер {provider_name} вернул HTTP {status}.",
                    hint="Это временная ошибка на стороне провайдера. Повторите позже.",
                    details={"http_status": status, "provider": provider_name},
                )
            return ProviderUnavailableError(
                f"Провайдер {provider_name} ответил неожиданным HTTP {status}.",
                details={"http_status": status, "provider": provider_name},
            )

        if isinstance(exc, httpx.TimeoutException):
            return ProviderUnavailableError(
                f"Таймаут запроса к {provider_name} "
                f"(>{self._config.http_timeout_seconds} сек).",
                hint="Увеличьте MCP_FSSP_HTTP_TIMEOUT или повторите запрос.",
                details={"provider": provider_name, "timeout": True},
            )

        if isinstance(exc, httpx.RequestError):
            return ProviderUnavailableError(
                f"Сетевая ошибка при запросе к {provider_name}: {exc.__class__.__name__}.",
                details={"provider": provider_name, "error_class": exc.__class__.__name__},
            )

        return exc
