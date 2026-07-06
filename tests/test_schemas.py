"""Тесты для Pydantic-моделей."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from mcp_fssp.schemas import (
    CheckDebtsResponse,
    PingResponse,
    Proceeding,
    QueryEcho,
)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class TestProceeding:
    def test_minimal_valid(self) -> None:
        p = Proceeding(
            id="12345/22/74033-ИП",
            subject_text="Алименты",
            amount_rub=Decimal("100"),
            executor_office="Курчатовский РОСП",
            fetched_at=_now(),
            source_provider="damia",
        )
        assert p.id == "12345/22/74033-ИП"
        assert p.amount_rub == Decimal("100")
        assert p.subject_type == "other"  # default

    def test_amount_from_string_with_comma(self) -> None:
        p = Proceeding(
            id="1/1/1-ИП",
            subject_text="x",
            amount_rub="1 234,56",  # type: ignore[arg-type]
            executor_office="x",
            fetched_at=_now(),
            source_provider="damia",
        )
        assert p.amount_rub == Decimal("1234.56")

    def test_amount_from_int(self) -> None:
        p = Proceeding(
            id="1/1/1-ИП",
            subject_text="x",
            amount_rub=1000,  # type: ignore[arg-type]
            executor_office="x",
            fetched_at=_now(),
            source_provider="damia",
        )
        assert p.amount_rub == Decimal("1000")

    def test_optional_remaining_none(self) -> None:
        p = Proceeding(
            id="1/1/1-ИП",
            subject_text="x",
            amount_rub=100,  # type: ignore[arg-type]
            executor_office="x",
            fetched_at=_now(),
            source_provider="damia",
        )
        assert p.amount_remaining_rub is None

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(Exception):
            Proceeding(
                id="1/1/1-ИП",
                subject_text="x",
                amount_rub=100,  # type: ignore[arg-type]
                executor_office="x",
                fetched_at=_now(),
                source_provider="damia",
                status="bogus",  # type: ignore[arg-type]
            )


class TestCheckDebtsResponse:
    def test_empty_proceedings(self) -> None:
        r = CheckDebtsResponse(
            query=QueryEcho(fio="Иванов Иван", birth_date=date(1990, 1, 1)),
            found=0,
            not_found=True,
            source="damia",
        )
        assert r.found == 0
        assert r.not_found is True
        assert r.proceedings == []

    def test_with_proceedings(self) -> None:
        p = Proceeding(
            id="1/1/1-ИП",
            subject_text="штраф ГИБДД",
            amount_rub=500,  # type: ignore[arg-type]
            executor_office="x",
            fetched_at=_now(),
            source_provider="damia",
        )
        r = CheckDebtsResponse(
            query=QueryEcho(inn="7707083893"),
            found=1,
            proceedings=[p],
            source="damia",
        )
        assert r.found == 1
        assert r.not_found is False
        assert r.proceedings[0].id == "1/1/1-ИП"


class TestPingResponse:
    def test_basic(self) -> None:
        r = PingResponse(
            version="0.1.0",
            provider="damia",
            provider_configured=True,
        )
        assert r.ok is True
        assert r.service == "mcp-fssp"
        assert r.provider == "damia"
        assert r.hosted_mode_enabled is False
