"""Реализации провайдеров (Damia / Checko / NewDB / api-cloud / self-parser /
atomno-pro). См. SPEC §5 и §7.2.

В Phase 1 реализован только Damia. Остальные провайдеры — Phase 2.
"""

from __future__ import annotations

from ..config import Config
from ..constants import (
    PROVIDER_API_CLOUD,
    PROVIDER_ATOMNO_PRO,
    PROVIDER_CHECKO,
    PROVIDER_DAMIA,
    PROVIDER_NEWDB,
    PROVIDER_SELF_PARSER,
)
from ..errors import NotImplementedInPhase
from ..client_base import AbstractProviderClient
from .damia import DamiaProvider


def make_provider(config: Config) -> AbstractProviderClient:
    """Фабрика провайдера по `config.provider`.

    В Phase 1 поддерживается только `damia`. Для остальных — кидаем
    `NotImplementedInPhase` с понятным сообщением, чтобы агент видел,
    почему конфиг работает не так как ожидается.
    """
    if config.provider == PROVIDER_DAMIA:
        return DamiaProvider(config)

    if config.provider in (
        PROVIDER_CHECKO,
        PROVIDER_NEWDB,
        PROVIDER_API_CLOUD,
        PROVIDER_SELF_PARSER,
        PROVIDER_ATOMNO_PRO,
    ):
        raise NotImplementedInPhase(
            f"Провайдер '{config.provider}' будет реализован в Phase 2 "
            f"(см. SPEC §10 roadmap).",
            hint=(
                "В Phase 1 поддерживается только провайдер 'damia'. "
                "Установите MCP_FSSP_PROVIDER=damia и MCP_FSSP_DAMIA_KEY."
            ),
            details={"provider": config.provider, "phase": 1},
        )

    raise NotImplementedInPhase(
        f"Неизвестный провайдер '{config.provider}'.",
        details={"provider": config.provider},
    )


__all__ = ["DamiaProvider", "make_provider"]
