<!-- mcp-name: io.github.atomno-mcp/mcp-fssp -->
# mcp-fssp

[![PyPI](https://img.shields.io/pypi/v/atomno-mcp-fssp.svg)](https://pypi.org/project/atomno-mcp-fssp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-server-blue)](https://modelcontextprotocol.io)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

> Russian FSSP (Federal Bailiff Service) debt lookups via MCP — check enforcement proceedings (исполнительные производства) for individuals and legal entities directly from Cursor, Claude Desktop, Cline, Goose, and any MCP client.

**MCP-сервер для проверки задолженностей в ФССП** (Федеральная служба судебных приставов). Позволяет AI-агентам в Cursor / Claude Desktop / Cline / Goose / Kiro делать запросы в базу долгов ФССП и получать структурированный JSON с открытыми исполнительными производствами (ИП): суммы, статусы, реквизиты приставов, основания взыскания.

Покрывает:

- Физических лиц (по ФИО + дате рождения).
- Юридических лиц (по ИНН-10 / ОГРН-13).
- Индивидуальных предпринимателей (по ИНН-12 / ОГРНИП-15).

Часть семейства MCP-серверов **atomno** для due-diligence по российским контрагентам:
[`mcp-egrul`](https://github.com/atomno-mcp/mcp-egrul) (реквизиты юр.лиц) ·
[`mcp-fns-check`](https://github.com/atomno-mcp/mcp-fns-check) (налоговая благонадёжность) ·
[`mcp-cbr-rates`](https://github.com/atomno-mcp/mcp-cbr-rates) (курсы ЦБ) ·
**`mcp-fssp`** (долги в ФССП).

## Зачем

Официальный API ФССП (`api-ip.fssp.gov.ru`) **отключён с 10 марта 2022 года** и не планируется к восстановлению. Единственная официальная точка — публичный web-сервис `fssp.gov.ru/iss/ip` с CAPTCHA. Это создаёт нишу: MCP-обёртка с поддержкой нескольких коммерческих провайдеров (Damia / Checko / NewDB / api-cloud) и нормализованной моделью данных.

Главные кейсы:

- **AI-агент в Cursor / Claude Desktop** делает due-diligence контрагента в чате за 30 секунд вместо 10 минут на ручной обход сайта ФССП.
- **Юристы / банки / скоринг** интегрируют единый `check_*_debts` вызов в свои Python-скрипты или 1С, не разбирая сырые ответы 3-4 разных провайдеров.
- **Self-host энтузиасты** ставят клиент локально со своим ключом Damia/Checko и работают без зависимости от стороннего SaaS — снимает паранойю об утечке ПДн.

## Quick start

### 1. Установить

```bash
# Через pipx (рекомендуется для CLI):
pipx install atomno-mcp-fssp

# Или через uv (быстрее):
uvx atomno-mcp-fssp

# Или классически через pip:
pip install atomno-mcp-fssp
```

### 2. Получить ключ провайдера

Минимум один из:

- **Damia** (https://api-fssp.damia.ru) — основной кандидат для prod. От 7 000 ₽/год за 1 000 запросов; 100 запросов бесплатно на тест.
- **Checko** (https://api.checko.ru) — до 50 запросов/день бесплатно. Хорош для onboarding.
- **NewDB** (https://newdb.net/fssp/api) — бюджетная альтернатива, 2 ₽/запрос, 100 free.
- **api-cloud** (https://api-cloud.ru/api/fssp.php) — per-request оплата.

### 3. Конфиг

Создай `.env` в рабочей директории (или передай переменные через MCP-конфиг):

```ini
MCP_FSSP_PROVIDER=damia
MCP_FSSP_DAMIA_KEY=ваш_ключ_от_Damia
```

Полный список переменных — см. [`.env.example`](.env.example).

### 4. Подключить к Cursor

Открой `~/.cursor/mcp.json` (или Settings → MCP) и добавь:

```json
{
  "mcpServers": {
    "fssp": {
      "command": "uvx",
      "args": ["atomno-mcp-fssp"],
      "env": {
        "MCP_FSSP_PROVIDER": "damia",
        "MCP_FSSP_DAMIA_KEY": "ваш_ключ"
      }
    }
  }
}
```

Перезапусти Cursor. Теперь AI-агент может вызывать `fssp.check_individual_debts(...)`, `fssp.check_legal_entity_debts(...)` и `fssp.get_proceeding_details(...)`.

### 5. Подключить к Claude Desktop

Открой `claude_desktop_config.json` и добавь:

```json
{
  "mcpServers": {
    "fssp": {
      "command": "uvx",
      "args": ["atomno-mcp-fssp"],
      "env": {
        "MCP_FSSP_PROVIDER": "damia",
        "MCP_FSSP_DAMIA_KEY": "ваш_ключ"
      }
    }
  }
}
```

## Доступные инструменты

| Инструмент | Назначение |
|---|---|
| `ping` | Проверка готовности сервера и текущего провайдера. |
| `check_individual_debts(fio, birth_date, region?)` | Список открытых ИП по физ.лицу. |
| `check_legal_entity_debts(inn?, ogrn?)` | Список открытых ИП по юр.лицу или ИП-предпринимателю. |
| `get_proceeding_details(proceeding_id)` | Детальная карточка одного ИП по номеру. |

В Pro-версии (Phase 3+, требует `ATOMNO_API_KEY`):

- `summarize_debts(...)` — AI-summary долгов с категоризацией и risk-score.
- `monitor_debts_changes(...)` — подписка на изменения с webhook/Telegram-алёртами.

## Переменные окружения

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `MCP_FSSP_PROVIDER` | Провайдер: `damia` / `checko` / `newdb` / `api_cloud` / `self_parser` / `atomno_pro` | `damia` |
| `MCP_FSSP_DAMIA_KEY` | Ключ Damia API-ФССП | — |
| `MCP_FSSP_CHECKO_KEY` | Ключ Checko v2 | — |
| `MCP_FSSP_NEWDB_KEY` | Ключ NewDB | — |
| `MCP_FSSP_API_CLOUD_KEY` | Ключ api-cloud.ru | — |
| `ATOMNO_API_KEY` | Ключ Pro-режима (api.atomno-mcp.ru/fssp/) | — |
| `ATOMNO_API_BASE` | URL Pro-backend | `https://api.atomno-mcp.ru/mcp-fssp/v1` |
| `MCP_FSSP_HTTP_TIMEOUT` | Таймаут одного запроса в секундах | `15` |
| `MCP_FSSP_RPS` | Лимит запросов в минуту со стороны клиента | `30` |
| `MCP_FSSP_USER_AGENT` | User-Agent для запросов | `mcp-fssp/0.1 (...)` |
| `MCP_FSSP_AUDIT_DB` | Путь к SQLite-аудит-логу | `./audit.sqlite` |
| `MCP_FSSP_LOG_LEVEL` | Уровень логов: `DEBUG`/`INFO`/`WARNING`/`ERROR` | `INFO` |

## Безопасность и ПДн

- ПДн (ФИО, дата рождения) **не сохраняются** в plain-text. Audit-лог хранит только `sha256(fio_lower + birth_date)`.
- Согласно [229-ФЗ ст. 6.1](https://www.consultant.ru/document/cons_doc_LAW_71450/), сведения из банка данных исполнительных производств являются **открытыми** и доступны без согласия должника.
- Тем не менее, при использовании в коммерческих целях оператор обязан соблюдать [152-ФЗ](https://www.consultant.ru/document/cons_doc_LAW_61801/). Использование в законных целях (например, due-diligence перед сделкой, скоринг по согласию заёмщика) — на стороне пользователя.

## Disclaimer

Сервис — **агрегатор и удобный интерфейс над публичными данными ФССП** (229-ФЗ ст. 6.1). **Не аффилирован с ФССП России**, Damia, Checko, NewDB, api-cloud и другими провайдерами. Используется на ваш риск.

Информация, возвращаемая инструментами, носит **справочный характер** и не заменяет официальные документы, выдаваемые ФССП. Авторы не отвечают за актуальность, полноту и точность данных провайдеров. Ответственность за законность использования сведений (в т.ч. соблюдение 152-ФЗ при обработке ПДн) — на пользователе.

При принятии юридически значимых решений (например, об отказе в кредите) необходимо запрашивать первичные документы у самого должника или через официальные каналы (запрос в подразделение приставов).

## Roadmap

- **v0.1** (текущая) — Phase 0 scaffold + Damia-провайдер + `check_individual_debts`.
- **v0.2** — multi-provider (+Checko, NewDB, api-cloud), `check_legal_entity_debts`, `get_proceeding_details`, локальный кэш L1.
- **v0.3+** — `self_parser` через CAPTCHA-solver.
- **v0.5** — интеграция с Pro-backend (`api.atomno-mcp.ru/fssp/`): `summarize_debts`, `monitor_debts_changes`, кэш L2 на 30 дней, fallback по 3 провайдерам.

Документация по инструментам и переменным окружения — в этом README и в [CHANGELOG.md](CHANGELOG.md). После публикации — также на GitHub: `atomno-mcp/mcp-fssp`.

## Лицензия

[MIT](LICENSE) © 2026 atomno.

Pro-backend (`atomno-mcp/mcp-fssp-server`) — **запланирован на Phase 2** (приватный hosted-сервис с проприетарной лицензией). Open-клиент полностью функционален без него — пользователь подставляет свой ключ любого из 4 коммерческих провайдеров.

## Ссылки

- Спецификация ФССП API (исторически): [api-ip.fssp.gov.ru](https://api-ip.fssp.gov.ru) (отключён с 10.03.2022).
- Web-сервис ФССП: [fssp.gov.ru/iss/ip](https://fssp.gov.ru/iss/ip).
- Каталог MCP: [glama.ai/mcp/servers](https://glama.ai/mcp/servers).
- MCP-спецификация: [modelcontextprotocol.io](https://modelcontextprotocol.io/spec).
