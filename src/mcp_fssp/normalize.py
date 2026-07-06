"""Утилиты нормализации входных данных и валидации идентификаторов.

Покрывает:
  * Нормализация ФИО (strip, схлопывание пробелов, title-case опционально).
  * Валидация ИНН по контрольной цифре (см. SPEC §0).
  * Валидация ОГРН/ОГРНИП по контрольной цифре.
  * Валидация даты рождения и форматирование под Damia (`dd.mm.yyyy`).
  * Хэш ФИО+ДР для аудит-лога (sha256, без plain-text ПДн).

Алгоритмы контрольных сумм — стандартные ФНС (Приказ МНС N БГ-3-09/178).
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime

from .constants import (
    FIO_MAX_LENGTH,
    FIO_MIN_LENGTH,
    INN_INDIVIDUAL_LENGTH,
    INN_LEGAL_LENGTH,
    OGRN_LEGAL_LENGTH,
    OGRNIP_LENGTH,
)
from .errors import ValidationError

# ---------------------------------------------------------------------------
# ФИО.
# ---------------------------------------------------------------------------

# Кириллица (включая Ё/ё), пробел, дефис, апостроф (для двойных фамилий
# типа О`Брайен — крайне редко, но возможно у иностранных граждан).
_FIO_ALLOWED_CHARS = re.compile(r"^[А-Яа-яЁё\s\-']+$")
_DOUBLE_SPACE = re.compile(r"\s+")


def normalize_fio(value: object) -> str:
    """Нормализовать ФИО: strip, схлопывание пробелов, валидация символов.

    На вход — что угодно, на выход — строка либо `ValidationError`.
    Регистр сохраняется — Damia принимает любые регистры.
    """
    if not isinstance(value, str):
        raise ValidationError(
            f"ФИО должно быть строкой, получено: {type(value).__name__}.",
            details={"input_type": type(value).__name__},
        )

    cleaned = _DOUBLE_SPACE.sub(" ", value.strip())

    if len(cleaned) < FIO_MIN_LENGTH:
        raise ValidationError(
            f"ФИО слишком короткое (минимум {FIO_MIN_LENGTH} символов).",
            hint="Передавайте ФИО полностью: 'Иванов Иван Иванович'.",
            details={"input": value, "length": len(cleaned)},
        )

    if len(cleaned) > FIO_MAX_LENGTH:
        raise ValidationError(
            f"ФИО слишком длинное (максимум {FIO_MAX_LENGTH} символов).",
            details={"input": value, "length": len(cleaned)},
        )

    if not _FIO_ALLOWED_CHARS.match(cleaned):
        raise ValidationError(
            "ФИО содержит недопустимые символы. Разрешены только русские "
            "буквы, пробелы, дефисы и апострофы.",
            hint=(
                "Если ФИО на латинице — большинство провайдеров ФССП их не "
                "обрабатывает. Используйте кириллический вариант."
            ),
            details={"input": value},
        )

    return cleaned


def fio_parts(value: str) -> tuple[str, str, str | None]:
    """Разобрать ФИО на три части (фамилия, имя, отчество).

    Принимает уже нормализованное ФИО. Если отчество отсутствует — третья
    часть None. Если частей <2, бросает `ValidationError` (без имени
    Damia не работает).
    """
    parts = value.split()
    if len(parts) < 2:
        raise ValidationError(
            "ФИО должно содержать как минимум фамилию и имя.",
            hint="Пример валидного входа: 'Иванов Иван' или 'Иванов Иван Иванович'.",
            details={"input": value},
        )
    surname, name = parts[0], parts[1]
    patronymic = " ".join(parts[2:]) if len(parts) > 2 else None
    return surname, name, patronymic


# ---------------------------------------------------------------------------
# Дата рождения.
# ---------------------------------------------------------------------------


def parse_birth_date(value: object) -> date:
    """Распарсить дату рождения (поддерживаем `YYYY-MM-DD` и `dd.mm.yyyy`).

    Возвращает `date`. Любой невалидный вход — `ValidationError`.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    if not isinstance(value, str):
        raise ValidationError(
            f"Дата рождения должна быть строкой или date, получено "
            f"{type(value).__name__}.",
            details={"input_type": type(value).__name__},
        )

    raw = value.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
        else:
            _check_reasonable_birth_date(parsed, raw)
            return parsed

    raise ValidationError(
        f"Дата рождения '{value}' не распознана. "
        f"Ожидается формат 'YYYY-MM-DD' или 'dd.mm.yyyy'.",
        hint="Пример: '1990-01-15' или '15.01.1990'.",
        details={"input": value},
    )


def _check_reasonable_birth_date(parsed: date, raw: str) -> None:
    today = date.today()
    if parsed > today:
        raise ValidationError(
            f"Дата рождения '{raw}' в будущем — скорее всего опечатка.",
            details={"input": raw, "parsed": parsed.isoformat()},
        )
    if parsed.year < 1900:
        raise ValidationError(
            f"Дата рождения '{raw}' раньше 1900 года — скорее всего опечатка.",
            details={"input": raw, "parsed": parsed.isoformat()},
        )


def format_birth_date_damia(value: date) -> str:
    """Damia API ожидает дату в формате `dd.mm.yyyy` (см. SPEC §5.1)."""
    return value.strftime("%d.%m.%Y")


# ---------------------------------------------------------------------------
# ИНН / ОГРН (контрольные суммы по официальным алгоритмам ФНС).
# ---------------------------------------------------------------------------

_INN_10_WEIGHTS: tuple[int, ...] = (2, 4, 10, 3, 5, 9, 4, 6, 8, 0)
_INN_12_WEIGHTS_1: tuple[int, ...] = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8, 0, 0)
_INN_12_WEIGHTS_2: tuple[int, ...] = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8, 0)


def _checksum_inn(digits: tuple[int, ...], weights: tuple[int, ...]) -> int:
    return sum(d * w for d, w in zip(digits, weights, strict=False)) % 11 % 10


def is_valid_inn(value: object) -> bool:
    """Проверить валидность ИНН (длина 10/12 + контрольная цифра)."""
    if not isinstance(value, str) or not value.isdigit():
        return False
    length = len(value)
    if length not in (INN_LEGAL_LENGTH, INN_INDIVIDUAL_LENGTH):
        return False

    digits = tuple(int(c) for c in value)

    if length == INN_LEGAL_LENGTH:
        return _checksum_inn(digits[:INN_LEGAL_LENGTH], _INN_10_WEIGHTS) == digits[9]

    check1 = _checksum_inn(digits[:11] + (0,), _INN_12_WEIGHTS_1)
    check2 = _checksum_inn(digits[:INN_INDIVIDUAL_LENGTH], _INN_12_WEIGHTS_2)
    return check1 == digits[10] and check2 == digits[11]


def assert_valid_inn(value: str) -> str:
    """Бросает `ValidationError` если ИНН невалиден; иначе возвращает значение."""
    if is_valid_inn(value):
        return value

    hint: str | None = None
    if isinstance(value, str) and value.isdigit():
        length = len(value)
        if length == OGRN_LEGAL_LENGTH:
            hint = "Похоже, что передан ОГРН (13 цифр). Используйте параметр `ogrn`."
        elif length == OGRNIP_LENGTH:
            hint = "Похоже, что передан ОГРНИП (15 цифр). Используйте параметр `ogrn`."

    raise ValidationError(
        (
            f"Невалидный ИНН: '{value}'. Ожидается {INN_LEGAL_LENGTH} цифр "
            f"(юр.лицо) или {INN_INDIVIDUAL_LENGTH} (ИП/физлицо) с корректной "
            f"контрольной цифрой."
        ),
        hint=hint,
        details={
            "input": value,
            "expected_length": [INN_LEGAL_LENGTH, INN_INDIVIDUAL_LENGTH],
        },
    )


def is_valid_ogrn(value: object) -> bool:
    """Проверить валидность ОГРН (13 цифр) или ОГРНИП (15 цифр)."""
    if not isinstance(value, str) or not value.isdigit():
        return False
    length = len(value)
    if length not in (OGRN_LEGAL_LENGTH, OGRNIP_LENGTH):
        return False

    body = value[:-1]
    expected = int(value[-1])
    divisor = 11 if length == OGRN_LEGAL_LENGTH else 13
    return int(body) % divisor % 10 == expected


def assert_valid_ogrn(value: str) -> str:
    """Бросает `ValidationError` если ОГРН невалиден."""
    if is_valid_ogrn(value):
        return value

    hint: str | None = None
    if isinstance(value, str) and value.isdigit():
        length = len(value)
        if length == INN_LEGAL_LENGTH:
            hint = "Похоже, что передан ИНН юр.лица (10 цифр). Используйте параметр `inn`."
        elif length == INN_INDIVIDUAL_LENGTH:
            hint = "Похоже, что передан ИНН ИП/физлица (12 цифр). Используйте параметр `inn`."

    raise ValidationError(
        (
            f"Невалидный ОГРН: '{value}'. Ожидается {OGRN_LEGAL_LENGTH} цифр "
            f"(юр.лицо) или {OGRNIP_LENGTH} (ИП-предприниматель) с корректной "
            f"контрольной цифрой."
        ),
        hint=hint,
        details={
            "input": value,
            "expected_length": [OGRN_LEGAL_LENGTH, OGRNIP_LENGTH],
        },
    )


# ---------------------------------------------------------------------------
# Хэширование ПДн для аудит-лога (без plain-text).
# ---------------------------------------------------------------------------


def hash_person(fio: str, birth_date: date) -> str:
    """`sha256(fio_lower_normalized + birth_date_iso)` — стабильный анонимный ID.

    Вход: уже нормализованное ФИО (см. `normalize_fio`) + распарсенная дата.
    Возвращает hex-строку 64 символа.
    """
    payload = f"{fio.lower()}|{birth_date.isoformat()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def hash_inn(inn: str) -> str:
    """`sha256(inn)` — для аудит-лога юр.лиц. Сам ИНН не secret, но хэшируем
    для единообразия со схемой `query_hash`."""
    return hashlib.sha256(inn.encode("utf-8")).hexdigest()


def hash_ogrn(ogrn: str) -> str:
    """`sha256(ogrn)` — аналогично `hash_inn`."""
    return hashlib.sha256(ogrn.encode("utf-8")).hexdigest()
