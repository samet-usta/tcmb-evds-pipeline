"""Tests for business_calendar. Pure logic; no network."""
from datetime import date

from src.ingestion.business_calendar import (
    business_days_between,
    is_business_day,
)


def test_weekday_is_business_day():
    # 2026-11-27 is a Friday
    assert is_business_day(date(2026, 11, 27)) is True


def test_saturday_and_sunday_are_closed():
    assert is_business_day(date(2026, 11, 28)) is False
    assert is_business_day(date(2026, 11, 29)) is False


def test_public_holiday_on_weekday_is_closed():
    # 2026-10-29 is Cumhuriyet Bayrami (Thursday)
    assert is_business_day(date(2026, 10, 29)) is False


def test_extra_closed_day_is_closed():
    friday = date(2026, 11, 27)
    assert is_business_day(friday, extra_closed_days={friday}) is False


def test_business_days_between_full_week():
    days = business_days_between(date(2026, 11, 23), date(2026, 11, 29))
    assert len(days) == 5
    assert days[0] == date(2026, 11, 23)
    assert days[-1] == date(2026, 11, 27)


def test_business_days_between_skips_holiday():
    # Mon 26 Oct - Fri 30 Oct, Thursday 29 Oct is a holiday
    days = business_days_between(date(2026, 10, 26), date(2026, 10, 30))
    assert date(2026, 10, 29) not in days
    assert len(days) == 4


# --- extra_closed_days config tests ---
from datetime import date

import pytest

from src.ingestion import business_calendar


@pytest.fixture
def config_path(tmp_path, monkeypatch):
    """Point the module to a temp config file and clear the cache."""
    path = tmp_path / "extra_closed_days.yaml"
    monkeypatch.setattr(business_calendar, "EXTRA_CLOSED_DAYS_PATH", path)
    business_calendar.load_extra_closed_days.cache_clear()
    yield path
    business_calendar.load_extra_closed_days.cache_clear()


def test_config_day_is_not_business_day(config_path):
    config_path.write_text("extra_closed_days: [2024-07-12]\n")
    assert business_calendar.is_business_day(date(2024, 7, 12)) is False
    assert business_calendar.is_business_day(date(2024, 7, 11)) is True


def test_empty_config_changes_nothing(config_path):
    config_path.write_text("extra_closed_days: []\n")
    assert business_calendar.is_business_day(date(2024, 7, 12)) is True


def test_invalid_config_value_raises(config_path):
    config_path.write_text('extra_closed_days: ["not-a-date"]\n')
    with pytest.raises(ValueError):
        business_calendar.load_extra_closed_days()
