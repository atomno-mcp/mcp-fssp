"""Сервисный контекст: инкапсулирует Config + AuditDb + Provider.

Создаётся один раз на процесс, переиспользуется во всех тулзах.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .audit_db import AuditDb
from .config import Config
from .providers import make_provider

if TYPE_CHECKING:
    from .client_base import AbstractProviderClient


class ServiceContext:
    """Контейнер для долгоживущих ресурсов.

    Использование как async-context-manager:

        async with ServiceContext.from_env() as ctx:
            await tool(ctx, ...)
    """

    def __init__(
        self,
        *,
        config: Config,
        audit: AuditDb,
        provider: "AbstractProviderClient",
    ) -> None:
        self.config = config
        self.audit = audit
        self.provider = provider

    @classmethod
    def from_env(cls) -> "ServiceContext":
        config = Config.from_env()
        audit = AuditDb(config.audit_db_path)
        provider = make_provider(config)
        return cls(config=config, audit=audit, provider=provider)

    async def __aenter__(self) -> "ServiceContext":
        await self.audit.init()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.audit.close()
