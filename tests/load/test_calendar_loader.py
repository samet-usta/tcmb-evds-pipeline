"""Tests for calendar_loader. DB connection is mocked; no network."""
from datetime import date
from unittest.mock import MagicMock, patch

from src.load.calendar_loader import build_calendar_rows, load_calendar


def test_build_calendar_rows_one_row_per_day():
    rows = build_calendar_rows(date(2026, 11, 26), date(2026, 11, 29))
    assert len(rows) == 4
    assert rows[0] == {"dt": date(2026, 11, 26), "is_business_day": True}
    assert rows[2] == {"dt": date(2026, 11, 28), "is_business_day": False}


def test_build_calendar_rows_marks_public_holiday():
    rows = build_calendar_rows(date(2026, 10, 29), date(2026, 10, 29))
    assert rows[0]["is_business_day"] is False


def test_load_calendar_upserts_rows_and_closes_connection():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value

    with patch("src.load.calendar_loader.get_connection", return_value=mock_conn):
        row_count = load_calendar(date(2026, 11, 26), date(2026, 11, 29))

    assert row_count == 4
    args = mock_cursor.executemany.call_args.args
    assert len(args[1]) == 4
    mock_conn.close.assert_called_once()
