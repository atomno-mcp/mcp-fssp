"""Типизированные исключения пакета mcp-fssp.

Иерархия (см. SPEC §4.1 FR-008 и §5.1):

    McpFsspError                — корень
        ValidationError         — невалидный вход (ФИО/ИНН/ОГРН/дата)
        NotFoundError           — данных по запросу нет
        ProviderUnavailableError — провайдер вернул 5xx / таймаут
        AuthFailedError         — провайдер вернул 401/403 (неверный токен)
        RateLimitedError        — превышен RPS у провайдера (429)
        CaptchaFailedError      — для self-parser, не смогли решить капчу
        ParseError              — провайдер изменил формат ответа
        ProRequiredError        — Pro-only фича на open-режиме
        NotImplementedInPhase   — намеренно не сделано в текущей фазе

Каждое исключение несёт:
    * `message_ru` — человекочитаемое сообщение для AI-агента;
    * `hint`      — подсказка, что пользователю сделать дальше (необязательно);
    * `details`   — произвольная структурированная диагностика.
"""

from __future__ import annotations

from typing import Any

from .constants import (
    ERROR_CODE_AUTH_FAILED,
    ERROR_CODE_CAPTCHA_FAILED,
    ERROR_CODE_INTERNAL,
    ERROR_CODE_NOT_FOUND,
    ERROR_CODE_NOT_IMPLEMENTED,
    ERROR_CODE_PARSE_ERROR,
    ERROR_CODE_PRO_REQUIRED,
    ERROR_CODE_PROVIDER_UNAVAILABLE,
    ERROR_CODE_RATE_LIMITED,
    ERROR_CODE_VALIDATION,
)


class McpFsspError(Exception):
    """Базовое исключение пакета.

    Имеет стабильный `code` (см. `constants.ERROR_CODE_*`) — клиенты MCP
    разбирают ответы по нему, а не по тексту сообщения.
    """

    code: str = ERROR_CODE_INTERNAL

    def __init__(
        self,
        message_ru: str,
        *,
        hint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message_ru = message_ru
        self.hint = hint
        self.details = details or {}
        super().__init__(message_ru)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": True,
            "code": self.code,
            "message": self.message_ru,
        }
        if self.hint is not None:
            payload["hint"] = self.hint
        if self.details:
            payload["details"] = self.details
        return payload


class ValidationError(McpFsspError):
    code = ERROR_CODE_VALIDATION


class NotFoundError(McpFsspError):
    code = ERROR_CODE_NOT_FOUND


class ProviderUnavailableError(McpFsspError):
    """Внешний провайдер недоступен (5xx / таймаут / DNS).

    Не должно молча фолбэчить на пустой результат — пользователь должен
    знать, что данные не получены, чтобы при необходимости повторить
    или сменить провайдера в конфиге.
    """

    code = ERROR_CODE_PROVIDER_UNAVAILABLE


class AuthFailedError(McpFsspError):
    """Провайдер отверг запрос из-за аутентификации (401 / 403).

    Типовые причины: токен не задан, отозван, истёк, опечатка.
    """

    code = ERROR_CODE_AUTH_FAILED


class RateLimitedError(McpFsspError):
    """Провайдер вернул 429 либо локальный rate-limit сработал."""

    code = ERROR_CODE_RATE_LIMITED


class CaptchaFailedError(McpFsspError):
    """Self-parser не смог решить капчу за N попыток."""

    code = ERROR_CODE_CAPTCHA_FAILED


class ParseError(McpFsspError):
    """Ответ провайдера не соответствует ожидаемой структуре.

    Чаще всего — провайдер изменил формат API. Это сигнал к ревизии
    `parsers/<provider>.py`.
    """

    code = ERROR_CODE_PARSE_ERROR


class ProRequiredError(McpFsspError):
    """Pro-only фича вызвана без `ATOMNO_API_KEY`."""

    code = ERROR_CODE_PRO_REQUIRED


class NotImplementedInPhase(McpFsspError):
    """Функциональность намеренно не реализована в текущей фазе.

    Используется вместо голого `NotImplementedError`, чтобы:
      1. Ответ MCP-тулза был валидным JSON-объектом с понятным `code` и
         `message` — а не внутренней traceback-ошибкой.
      2. В логах однозначно читалось «это не баг, это Phase 0/1 граница» —
         без silent fallback на мусор.
    """

    code = ERROR_CODE_NOT_IMPLEMENTED
