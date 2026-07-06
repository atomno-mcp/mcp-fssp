"""Реализация MCP-тулзов как async-функций.

Тулзы тонкие — вся бизнес-логика в `providers/<name>.py` и `parsers/`.
Здесь делается только:

  * Валидация входов (Pydantic + normalize.py).
  * Вызов provider'а через фабрику (`make_provider`).
  * Запись в audit-лог.
  * Маппинг любых исключений на `McpFsspError` (через `try/except` в server).
"""

from .check_individual_debts import check_individual_debts
from .check_legal_entity_debts import check_legal_entity_debts
from .get_proceeding_details import get_proceeding_details

__all__ = [
    "check_individual_debts",
    "check_legal_entity_debts",
    "get_proceeding_details",
]
