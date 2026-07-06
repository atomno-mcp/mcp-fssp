# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-07-06

### Changed

- Брендинг PyPI и публичной документации: `atomno-labs` → `Atomno` / `atomno-mcp`
  (copyright, контактные URL).

## [0.1.1] - 2026-07-06

### Fixed

- Провайдер по умолчанию — корпоративный endpoint Atomno (`atomno_pro`, `api.atomno-mcp.ru`).
  Требуется `MCP_FSSP_ATOMNO_API_KEY` (алиас: `ATOMNO_API_KEY`).
- Thin-client `AtomnoProProvider`: при недоступности backend — понятное сообщение
  вместо тихого падения (бета, `hello@atomno.ru`).
- Fair-use: дневной лимит **10 запросов** в демо-режиме без корпоративного ключа
  (`MCP_FSSP_BYOK_DAILY_LIMIT`). Собственный ключ Damia — `MCP_FSSP_PROVIDER=damia`.

### Changed

- Документация: production — корпоративный API; Damia BYOK — для разработки и пилотов.

## [0.1.0] - 2026-07-06

### Added

- Phase 1 open-core client `apps/mcp-fssp-client/` with FastMCP server.
- Tools: `ping`, `check_individual_debts`, `check_legal_entity_debts`, `get_proceeding_details`.
- Damia API-ФССП provider with httpx + respx test mocks.
- Argparse CLI: `--help`, `--version`, `--transport`, `--host`, `--port`, `--log-level`, `--check-config`.
- SQLite audit log (hashed PII, no plain-text FIO storage).
- `tests/test_cli.py` (6 groups) + 120+ unit/integration tests.

### Limitations

- Only `damia` provider implemented in Phase 1; other providers raise `not_implemented`.
- Official FSSP API disabled since 2022; direct `fssp.gov.ru` parsing deferred to Phase 2.
- Requires commercial provider API key for live queries.

[0.1.2]: https://github.com/atomno-mcp/mcp-fssp/releases/tag/v0.1.2
[0.1.1]: https://github.com/atomno-mcp/mcp-fssp/releases/tag/v0.1.1
[0.1.0]: https://github.com/atomno-mcp/mcp-fssp/releases/tag/v0.1.0
