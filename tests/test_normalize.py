"""Тесты для `normalize.py`."""

from __future__ import annotations

from datetime import date

import pytest

from mcp_fssp.errors import ValidationError
from mcp_fssp.normalize import (
    assert_valid_inn,
    assert_valid_ogrn,
    fio_parts,
    format_birth_date_damia,
    hash_inn,
    hash_ogrn,
    hash_person,
    is_valid_inn,
    is_valid_ogrn,
    normalize_fio,
    parse_birth_date,
)


# ---------------------------------------------------------------------------
# ФИО.
# ---------------------------------------------------------------------------


class TestNormalizeFio:
    def test_basic(self) -> None:
        assert normalize_fio("Иванов Иван Иванович") == "Иванов Иван Иванович"

    def test_strips_extra_spaces(self) -> None:
        assert normalize_fio("  Иванов   Иван  ") == "Иванов Иван"

    def test_handles_dash(self) -> None:
        assert normalize_fio("Петрова-Сидорова Анна") == "Петрова-Сидорова Анна"

    def test_handles_yo(self) -> None:
        assert normalize_fio("Зёмин Иван") == "Зёмин Иван"

    def test_too_short(self) -> None:
        with pytest.raises(ValidationError):
            normalize_fio("Иван")

    def test_too_long(self) -> None:
        with pytest.raises(ValidationError):
            normalize_fio("Иван " * 50)

    def test_latin_rejected(self) -> None:
        with pytest.raises(ValidationError):
            normalize_fio("Ivanov Ivan")

    def test_digits_rejected(self) -> None:
        with pytest.raises(ValidationError):
            normalize_fio("Иванов И1ван")

    def test_non_string_rejected(self) -> None:
        with pytest.raises(ValidationError):
            normalize_fio(12345)  # type: ignore[arg-type]

    def test_fio_parts_two(self) -> None:
        assert fio_parts("Иванов Иван") == ("Иванов", "Иван", None)

    def test_fio_parts_three(self) -> None:
        assert fio_parts("Иванов Иван Иванович") == ("Иванов", "Иван", "Иванович")

    def test_fio_parts_too_few(self) -> None:
        with pytest.raises(ValidationError):
            fio_parts("Иванов")


# ---------------------------------------------------------------------------
# Дата рождения.
# ---------------------------------------------------------------------------


class TestParseBirthDate:
    def test_iso(self) -> None:
        assert parse_birth_date("1990-01-15") == date(1990, 1, 15)

    def test_dot_format(self) -> None:
        assert parse_birth_date("15.01.1990") == date(1990, 1, 15)

    def test_slash_format(self) -> None:
        assert parse_birth_date("15/01/1990") == date(1990, 1, 15)

    def test_already_date(self) -> None:
        d = date(1990, 1, 15)
        assert parse_birth_date(d) == d

    def test_invalid_string(self) -> None:
        with pytest.raises(ValidationError):
            parse_birth_date("not-a-date")

    def test_future_date(self) -> None:
        with pytest.raises(ValidationError):
            parse_birth_date("2099-01-01")

    def test_pre_1900(self) -> None:
        with pytest.raises(ValidationError):
            parse_birth_date("1850-01-01")

    def test_non_string(self) -> None:
        with pytest.raises(ValidationError):
            parse_birth_date(123)  # type: ignore[arg-type]

    def test_format_for_damia(self) -> None:
        assert format_birth_date_damia(date(1990, 1, 15)) == "15.01.1990"


# ---------------------------------------------------------------------------
# ИНН (валидные тестовые ИНН с правильной контрольной цифрой).
# ---------------------------------------------------------------------------


# Валидный ИНН 10 для тестов: ИНН Сбербанка 7707083893
VALID_INN_10 = "7707083893"
# Валидный ИНН 12 для тестов (Тестовое физлицо)
VALID_INN_12 = "500100732259"


class TestInn:
    def test_valid_10(self) -> None:
        assert is_valid_inn(VALID_INN_10) is True
        assert assert_valid_inn(VALID_INN_10) == VALID_INN_10

    def test_valid_12(self) -> None:
        assert is_valid_inn(VALID_INN_12) is True

    def test_wrong_checksum_10(self) -> None:
        assert is_valid_inn("7707083890") is False

    def test_wrong_length(self) -> None:
        assert is_valid_inn("12345") is False

    def test_letters(self) -> None:
        assert is_valid_inn("770708389a") is False

    def test_non_string(self) -> None:
        assert is_valid_inn(7707083893) is False  # type: ignore[arg-type]

    def test_assert_raises_on_invalid(self) -> None:
        with pytest.raises(ValidationError):
            assert_valid_inn("12345")

    def test_assert_hint_when_ogrn_passed(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            assert_valid_inn("1037739010891")  # 13 цифр
        assert exc_info.value.hint is not None
        assert "ОГРН" in exc_info.value.hint


# ---------------------------------------------------------------------------
# ОГРН.
# ---------------------------------------------------------------------------


# Валидный ОГРН 13 для тестов (Сбербанк): 1027700132195
VALID_OGRN_13 = "1027700132195"


class TestOgrn:
    def test_valid_13(self) -> None:
        assert is_valid_ogrn(VALID_OGRN_13) is True
        assert assert_valid_ogrn(VALID_OGRN_13) == VALID_OGRN_13

    def test_invalid_checksum(self) -> None:
        assert is_valid_ogrn("1027700132190") is False

    def test_wrong_length(self) -> None:
        assert is_valid_ogrn("12345") is False

    def test_non_string(self) -> None:
        assert is_valid_ogrn(None) is False  # type: ignore[arg-type]

    def test_assert_raises(self) -> None:
        with pytest.raises(ValidationError):
            assert_valid_ogrn("12345")

    def test_assert_hint_when_inn_passed(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            assert_valid_ogrn(VALID_INN_10)
        assert exc_info.value.hint is not None
        assert "ИНН" in exc_info.value.hint


# ---------------------------------------------------------------------------
# Хэширование.
# ---------------------------------------------------------------------------


class TestHashing:
    def test_hash_person_stable(self) -> None:
        h1 = hash_person("Иванов Иван", date(1990, 1, 15))
        h2 = hash_person("Иванов Иван", date(1990, 1, 15))
        assert h1 == h2

    def test_hash_person_case_insensitive(self) -> None:
        h1 = hash_person("Иванов Иван", date(1990, 1, 15))
        h2 = hash_person("ИВАНОВ ИВАН", date(1990, 1, 15))
        assert h1 == h2

    def test_hash_person_different_dates(self) -> None:
        h1 = hash_person("Иванов Иван", date(1990, 1, 15))
        h2 = hash_person("Иванов Иван", date(1990, 1, 16))
        assert h1 != h2

    def test_hash_person_length(self) -> None:
        h = hash_person("Иванов Иван", date(1990, 1, 15))
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_inn_and_ogrn(self) -> None:
        assert len(hash_inn(VALID_INN_10)) == 64
        assert len(hash_ogrn(VALID_OGRN_13)) == 64
        assert hash_inn(VALID_INN_10) != hash_ogrn(VALID_OGRN_13)
