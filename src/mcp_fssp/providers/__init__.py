"""Реализации провайдеров (Damia / Checko / NewDB / api-cloud / self-parser /
atomno-pro). См. SPEC §5 и §7.2.
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
from .atomno_pro import AtomnoProProvider
from .damia import DamiaProvider


def make_provider(config: Config) -> AbstractProviderClient:
    """Фабрика провайдера по `config.provider`."""
    if config.provider == PROVIDER_DAMIA:
        return DamiaProvider(config)

    if config.provider == PROVIDER_ATOMNO_PRO:
        return AtomnoProProvider(config)

    if config.provider in (
        PROVIDER_CHECKO,
        PROVIDER_NEWDB,
        PROVIDER_API_CLOUD,
        PROVIDER_SELF_PARSER,
    ):
        raise NotImplementedInPhase(
            f"Провайдер '{config.provider}' будет реализован в Phase 2 "
            f"(см. SPEC §10 roadmap).",
            hint=(
                "В v0.1.1 рекомендуется MCP_FSSP_PROVIDER=atomno_pro + "
                "MCP_FSSP_ATOMNO_API_KEY. BYOK Damia: MCP_FSSP_PROVIDER=damia."
            ),
            details={"provider": config.provider, "phase": 2},
        )

    raise NotImplementedInPhase(
        f"Неизвестный провайдер '{config.provider}'.",
        details={"provider": config.provider},
    )


__all__ = ["AtomnoProProvider", "DamiaProvider", "make_provider"]
