"""Парсер ответов Damia API-ФССП.

Формат ответа Damia (наблюдаемый, не задокументирован полностью):

    {
        "Иванов Иван Иванович": {
            "ip": [
                {
                    "nomer": "12345/22/74033-ИП",
                    "ddd": "15.03.2022",                    # дата возбуждения
                    "predmet": "Алименты на содержание...",  # предмет взыскания
                    "summa": "150000.00",
                    "ostatok": "75000.00",                   # опц.
                    "isporg": "Курчатовский РОСП",          # отдел
                    "ispdoc": "Решение мирового судьи №1",   # основание
                    "prist": {                                # пристав
                        "fio": "Сидорова А.А.",
                        "tel": "+7 351 ...",
                        "email": "..."
                    }
                },
                ...
            ]
        }
    }

Для запроса по ИНН/ОГРН ключ верхнего уровня — `inn` или `ogrn`-значение.
Для пустого результата Damia может отдать `{"<key>": {"ip": []}}` либо
`{"status": "Ничего не найдено"}` — обрабатываем оба случая.

Парсер устойчив к пропускам полей: minimum required — `nomer`, `predmet`,
`summa`, `isporg`. Остальные опциональны.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from ..constants import PROVIDER_DAMIA
from ..errors import ParseError
from ..schemas import (
    CheckDebtsResponse,
    Proceeding,
    ProceedingCategory,
    ProceedingDetails,
    QueryEcho,
)


def _categorize(subject_text: str) -> ProceedingCategory:
    """Keyword-классификатор предмета взыскания (см. SPEC §5.4 шаг 2).

    Простой и предсказуемый — сложности оставляем для Pro `summarize_debts`.
    """
    s = subject_text.lower()
    if "алимент" in s:
        return "alimony"
    if "штраф" in s and ("гибдд" in s or "адми" in s or "пдд" in s):
        return "fine_traffic"
    if "налог" in s or "ндс" in s or "ндфл" in s:
        return "tax"
    if "жкх" in s or "коммун" in s or "электроэнерг" in s or "газоснаб" in s:
        return "utility"
    if "кредит" in s or "займ" in s or "ссуд" in s or "ипотек" in s:
        return "credit"
    return "other"


def _parse_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        cleaned = value.replace(" ", "").replace(",", ".").replace("\xa0", "")
        try:
            return Decimal(cleaned)
        except InvalidOperation as exc:
            raise ParseError(
                f"Не могу распарсить сумму '{value}'.",
                details={"value": value},
            ) from exc
    raise ParseError(
        f"Сумма должна быть числом или строкой, получено {type(value).__name__}.",
        details={"value_type": type(value).__name__},
    )


def _parse_optional_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return _parse_decimal(value)


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _proceeding_from_damia_item(item: dict[str, Any]) -> Proceeding:
    if not isinstance(item, dict):
        raise ParseError(
            f"Элемент списка ИП должен быть object, получен {type(item).__name__}.",
            details={"got_type": type(item).__name__},
        )

    nomer = item.get("nomer") or item.get("number")
    if not nomer:
        raise ParseError(
            "В ответе Damia отсутствует поле 'nomer' (номер ИП).",
            details={"item_keys": sorted(item.keys())},
        )

    subject_text = item.get("predmet") or item.get("subject") or ""
    summa = _parse_decimal(item.get("summa") or item.get("amount") or 0)
    ostatok = _parse_optional_decimal(item.get("ostatok") or item.get("remaining"))
    started = _parse_date(item.get("ddd") or item.get("date_start"))
    isporg = item.get("isporg") or item.get("office") or ""

    prist = item.get("prist") or {}
    if not isinstance(prist, dict):
        prist = {}

    return Proceeding(
        id=str(nomer),
        case_number=item.get("docnomer") or item.get("case_number"),
        started_at=started,
        subject_type=_categorize(subject_text),
        subject_text=str(subject_text),
        amount_rub=summa,
        amount_remaining_rub=ostatok,
        status=_status_from_damia(item),
        executor_office=str(isporg),
        executor_phone=prist.get("tel") or prist.get("phone"),
        bailiff_full_name=prist.get("fio") or prist.get("name"),
        bailiff_email=prist.get("email"),
        case_basis=item.get("ispdoc") or item.get("basis"),
        fetched_at=datetime.now(tz=timezone.utc),
        source_provider=PROVIDER_DAMIA,
    )


def _status_from_damia(item: dict[str, Any]) -> str:
    """Damia в одном из ответов отдаёт `status` либо `okonchanie` (дата окончания).

    Если есть дата окончания — производство завершено. Иначе считаем active.
    """
    raw_status = (item.get("status") or "").lower()
    if "оконч" in raw_status or "заверш" in raw_status:
        return "completed"
    if "приост" in raw_status:
        return "suspended"
    if item.get("okonchanie") or item.get("date_end"):
        return "completed"
    return "active"


def _extract_ip_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Достать список ИП из верхнего уровня ответа Damia.

    Damia отдаёт структуру вида `{"<key>": {"ip": [...]}}` — где `<key>`
    это исходный запрос (ФИО, ИНН или ОГРН). Также бывает плоский
    вариант `{"ip": [...]}` либо ответ-ошибка `{"status": "..."}` /
    `{"error": "..."}`.
    """
    if "error" in payload:
        # Сюда не попадаем для 4xx (это ловится в _get), но если Damia
        # вернула 200 с error-полем — считаем provider_unavailable-уровнем.
        raise ParseError(
            f"Damia вернула поле error: {payload.get('error')}.",
            details={"raw_keys": sorted(payload.keys())},
        )

    if "ip" in payload and isinstance(payload["ip"], list):
        return payload["ip"]

    # Не "ip" на верхнем уровне, ищем во вложенных object'ах.
    for value in payload.values():
        if isinstance(value, dict) and "ip" in value and isinstance(value["ip"], list):
            return value["ip"]

    # Если это {"status": "Ничего не найдено"} — нормальный пустой ответ.
    if "status" in payload and isinstance(payload["status"], str):
        status_low = payload["status"].lower()
        if "не найден" in status_low or "ничего" in status_low:
            return []

    # Не нашли ничего похожего — ParseError.
    raise ParseError(
        "В ответе Damia не нашёл поле 'ip' ни на верхнем уровне, ни в "
        "вложенных объектах.",
        details={"top_keys": sorted(payload.keys())},
    )


def parse_check_response(
    payload: dict[str, Any],
    *,
    query: dict[str, Any],
) -> CheckDebtsResponse:
    """Распарсить ответ `check_*_debts` из Damia в `CheckDebtsResponse`."""
    items = _extract_ip_list(payload)
    proceedings = [_proceeding_from_damia_item(item) for item in items]
    return CheckDebtsResponse(
        query=QueryEcho(
            fio=query.get("fio"),
            birth_date=query.get("birth_date"),
            inn=query.get("inn"),
            ogrn=query.get("ogrn"),
            region=query.get("region"),
        ),
        found=len(proceedings),
        not_found=len(proceedings) == 0,
        proceedings=proceedings,
        source=PROVIDER_DAMIA,
    )


def parse_details_response(
    payload: dict[str, Any],
    *,
    proceeding_id: str,
) -> ProceedingDetails:
    """Распарсить детальный ответ Damia (`?nomer=...&proizv=1`).

    Damia в детальном режиме возвращает либо такой же `{"<key>": {"ip": [item]}}`
    с одним элементом, либо плоский объект самого ИП. Поддерживаем оба.
    """
    items = _extract_ip_list(payload) if "ip" in payload or any(
        isinstance(v, dict) and "ip" in v for v in payload.values()
    ) else [payload]

    if not items:
        raise ParseError(
            f"Damia не вернула карточку для ИП {proceeding_id}.",
            details={"proceeding_id": proceeding_id},
        )

    proceeding = _proceeding_from_damia_item(items[0])
    documents_raw = items[0].get("docs") or items[0].get("documents") or []
    documents = documents_raw if isinstance(documents_raw, list) else []

    return ProceedingDetails(
        query={"proceeding_id": proceeding_id},
        proceeding=proceeding,
        documents=documents,
        source=PROVIDER_DAMIA,
    )
