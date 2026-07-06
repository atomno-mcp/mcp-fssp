"""Тесты для парсера ответов Damia (`parsers/damia.py`)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from mcp_fssp.errors import ParseError
from mcp_fssp.parsers.damia import (
    _categorize,
    _extract_ip_list,
    _proceeding_from_damia_item,
    _status_from_damia,
    parse_check_response,
    parse_details_response,
)


class TestCategorize:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Алименты на содержание ребёнка", "alimony"),
            ("Штраф ГИБДД за превышение скорости", "fine_traffic"),
            ("Административный штраф ПДД", "fine_traffic"),
            ("Транспортный налог за 2023 год", "tax"),
            ("НДФЛ за 2022 год", "tax"),
            ("Задолженность по ЖКХ", "utility"),
            ("Электроэнергия неоплаченная", "utility"),
            ("Кредитная задолженность ПАО Сбербанк", "credit"),
            ("Ипотека по договору №1234", "credit"),
            ("Возмещение ущерба", "other"),
            ("", "other"),
        ],
    )
    def test_categories(self, text: str, expected: str) -> None:
        assert _categorize(text) == expected


class TestProceedingFromDamiaItem:
    def test_minimal(self) -> None:
        item = {
            "nomer": "12345/22/74033-ИП",
            "predmet": "Алименты",
            "summa": "150000",
            "isporg": "Курчатовский РОСП",
        }
        p = _proceeding_from_damia_item(item)
        assert p.id == "12345/22/74033-ИП"
        assert p.subject_type == "alimony"
        assert p.amount_rub == Decimal("150000")
        assert p.amount_remaining_rub is None
        assert p.executor_office == "Курчатовский РОСП"
        assert p.source_provider == "damia"
        assert p.status == "active"

    def test_with_remaining_and_dates(self) -> None:
        item = {
            "nomer": "1/1/1-ИП",
            "predmet": "Штраф ГИБДД",
            "summa": "1 234,56",
            "ostatok": "500.00",
            "ddd": "15.03.2022",
            "isporg": "x",
            "prist": {
                "fio": "Иванов И.И.",
                "tel": "+7 900 000-00-00",
                "email": "test@example.com",
            },
        }
        p = _proceeding_from_damia_item(item)
        assert p.amount_rub == Decimal("1234.56")
        assert p.amount_remaining_rub == Decimal("500.00")
        assert p.started_at == date(2022, 3, 15)
        assert p.bailiff_full_name == "Иванов И.И."
        assert p.executor_phone == "+7 900 000-00-00"
        assert p.bailiff_email == "test@example.com"

    def test_missing_nomer_raises(self) -> None:
        with pytest.raises(ParseError):
            _proceeding_from_damia_item({"predmet": "x", "summa": 0, "isporg": "x"})

    def test_non_dict_raises(self) -> None:
        with pytest.raises(ParseError):
            _proceeding_from_damia_item("not a dict")  # type: ignore[arg-type]


class TestStatusFromDamia:
    def test_active_default(self) -> None:
        assert _status_from_damia({}) == "active"

    def test_completed_by_status(self) -> None:
        assert _status_from_damia({"status": "Окончено"}) == "completed"

    def test_completed_by_okonchanie(self) -> None:
        assert _status_from_damia({"okonchanie": "01.01.2024"}) == "completed"

    def test_suspended(self) -> None:
        assert _status_from_damia({"status": "Приостановлено"}) == "suspended"


class TestExtractIpList:
    def test_top_level_ip(self) -> None:
        assert _extract_ip_list({"ip": [{"a": 1}]}) == [{"a": 1}]

    def test_nested_ip(self) -> None:
        payload = {"Иванов Иван": {"ip": [{"a": 1}, {"b": 2}]}}
        assert _extract_ip_list(payload) == [{"a": 1}, {"b": 2}]

    def test_empty_status_not_found(self) -> None:
        assert _extract_ip_list({"status": "Ничего не найдено"}) == []

    def test_error_field_raises(self) -> None:
        with pytest.raises(ParseError):
            _extract_ip_list({"error": "bad token"})

    def test_unknown_structure_raises(self) -> None:
        with pytest.raises(ParseError):
            _extract_ip_list({"weird": [1, 2, 3]})


class TestParseCheckResponse:
    def test_with_proceedings(self) -> None:
        payload = {
            "Иванов Иван": {
                "ip": [
                    {
                        "nomer": "1/1/1-ИП",
                        "predmet": "Алименты",
                        "summa": "100000",
                        "isporg": "x",
                    }
                ]
            }
        }
        r = parse_check_response(
            payload, query={"fio": "Иванов Иван", "birth_date": date(1990, 1, 1)}
        )
        assert r.found == 1
        assert r.not_found is False
        assert r.proceedings[0].id == "1/1/1-ИП"
        assert r.source == "damia"
        assert r.query.fio == "Иванов Иван"
        assert r.query.birth_date == date(1990, 1, 1)

    def test_empty(self) -> None:
        r = parse_check_response(
            {"status": "Ничего не найдено"},
            query={"inn": "7707083893"},
        )
        assert r.found == 0
        assert r.not_found is True
        assert r.proceedings == []


class TestParseDetailsResponse:
    def test_basic(self) -> None:
        payload = {
            "12345/22/74033-ИП": {
                "ip": [
                    {
                        "nomer": "12345/22/74033-ИП",
                        "predmet": "Кредит",
                        "summa": "50000",
                        "isporg": "x",
                        "ispdoc": "Решение №1",
                    }
                ]
            }
        }
        r = parse_details_response(payload, proceeding_id="12345/22/74033-ИП")
        assert r.proceeding.id == "12345/22/74033-ИП"
        assert r.proceeding.case_basis == "Решение №1"
        assert r.source == "damia"
        assert r.query == {"proceeding_id": "12345/22/74033-ИП"}

    def test_flat_object(self) -> None:
        payload = {
            "nomer": "12345/22/74033-ИП",
            "predmet": "x",
            "summa": "100",
            "isporg": "x",
        }
        r = parse_details_response(payload, proceeding_id="12345/22/74033-ИП")
        assert r.proceeding.id == "12345/22/74033-ИП"
