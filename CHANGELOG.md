# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/atomno-mcp/mcp-fssp/releases/tag/v0.1.0
