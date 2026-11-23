"""Unit tests for the Turkish holidays seed generator."""

from src.tools.generate_tr_holidays_seed import COLUMNS, build_rows


def get_dates(rows):
    dates = []
    for row in rows:
        dates.append(row["holiday_date"])
    return dates


def test_row_keys_match_columns():
    rows = build_rows(2026, 2026)
    for row in rows:
        assert list(row.keys()) == COLUMNS


def test_republic_day_is_holiday():
    dates = get_dates(build_rows(2026, 2026))
    assert "2026-10-29" in dates


def test_half_days_are_not_holidays():
    # Arife (yarım gün) kararı: is_holiday = false
    dates = get_dates(build_rows(2026, 2026))
    assert "2026-03-19" not in dates
    assert "2026-05-26" not in dates


def test_dates_are_unique_and_inside_range():
    dates = get_dates(build_rows(2025, 2026))
    assert len(dates) == len(set(dates))
    assert dates == sorted(dates)
    assert dates[0].startswith("2025-")
    assert dates[-1].startswith("2026-")
