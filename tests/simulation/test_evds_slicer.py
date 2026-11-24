"""Tests for the EVDS snapshot slicer."""

from datetime import date, timedelta

import pytest

from src.simulation.evds_slicer import (
    get_lag_days,
    parse_observation_date,
    slice_for_dt,
)


def make_result():
    """Return a small deposit_rates snapshot (weekly, lag 6 days)."""
    result = {
        "source": "evds",
        "group": "deposit_rates",
        "series_codes": ["TP.TRY.MT06"],
        "start_date": "2026-08-24",
        "end_date": "2026-11-21",
        "items": [
            {"Tarih": "28-08-2026", "TP_TRY_MT06": "44.76"},
            {"Tarih": "04-09-2026", "TP_TRY_MT06": "44.37"},
        ],
    }
    return result


def test_parse_daily_date():
    assert parse_observation_date("28-08-2026") == date(2026, 8, 28)


def test_parse_monthly_date_is_last_day_of_month():
    assert parse_observation_date("2026-10") == date(2026, 10, 31)
    assert parse_observation_date("2026-2") == date(2026, 2, 28)


def test_unknown_group_raises_error():
    with pytest.raises(ValueError):
        get_lag_days("unknown_group")


def test_item_is_hidden_one_day_before_lag_ends():
    # 28-08 + 6 gün = 03-09. 02-09'da görünmez.
    envelope = slice_for_dt(make_result(), date(2026, 9, 2))
    assert len(envelope["items"]) == 0


def test_item_is_visible_on_lag_end_day():
    envelope = slice_for_dt(make_result(), date(2026, 9, 3))
    assert len(envelope["items"]) == 1


def test_slice_grows_and_never_shrinks():
    result = make_result()
    previous_count = 0
    dt = date(2026, 8, 25)
    while dt <= date(2026, 9, 20):
        count = len(slice_for_dt(result, dt)["items"])
        assert count >= previous_count
        previous_count = count
        dt = dt + timedelta(days=1)
    assert previous_count == 2


def test_empty_slice_keeps_full_envelope():
    dt = date(2026, 8, 24)
    envelope = slice_for_dt(make_result(), dt)
    assert envelope["items"] == []
    assert envelope["end_date"] == "2026-08-24"
    assert envelope["start_date"] == "2026-08-24"
    assert envelope["fallback_reason"] is None
    assert envelope["group"] == "deposit_rates"


def test_slice_does_not_change_the_snapshot_result():
    result = make_result()
    slice_for_dt(result, date(2026, 9, 10))
    assert len(result["items"]) == 2
    assert result["end_date"] == "2026-11-21"
