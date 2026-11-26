"""Business day calendar for Turkey (TCMB).

Single source of truth: the DAG skip check and the Soda gap rule use it.
Extra closed days (not public holidays) come from config/extra_closed_days.yaml.
"""
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import holidays
import yaml

# This file is src/ingestion/business_calendar.py, so parents[2] is the repo root.
EXTRA_CLOSED_DAYS_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "extra_closed_days.yaml"
)


@lru_cache(maxsize=None)
def get_tr_holidays(year):
    """Return Turkish public holidays for one year (cached)."""
    return holidays.country_holidays("TR", years=year)


@lru_cache(maxsize=None)
def load_extra_closed_days():
    """Return extra closed days from the config file as a frozenset of dates."""
    with open(EXTRA_CLOSED_DAYS_PATH, encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}
    days = config.get("extra_closed_days") or []
    for day in days:
        # YAML turns 2024-07-12 into a date. Any other type is a config mistake.
        if not isinstance(day, date):
            raise ValueError(f"Invalid date in extra_closed_days: {day!r}")
    return frozenset(days)


def is_business_day(day, extra_closed_days=None):
    """Return True if day is Mon-Fri and not a closed day."""
    if extra_closed_days is None:
        extra_closed_days = load_extra_closed_days()
    is_weekend = day.weekday() >= 5
    is_holiday = day in get_tr_holidays(day.year)
    is_extra_closed = day in extra_closed_days
    return not (is_weekend or is_holiday or is_extra_closed)


def business_days_between(start_day, end_day, extra_closed_days=None):
    """Return business days from start_day to end_day (both included)."""
    days = []
    current_day = start_day
    while current_day <= end_day:
        if is_business_day(current_day, extra_closed_days):
            days.append(current_day)
        current_day = current_day + timedelta(days=1)
    return days
