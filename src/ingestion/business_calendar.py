"""Business day calendar for Turkey (TCMB).

Single source of truth: the DAG skip check and the Soda gap rule use it.
"""
from datetime import timedelta
from functools import lru_cache

import holidays


@lru_cache(maxsize=None)
def get_tr_holidays(year):
    """Return Turkish public holidays for one year (cached)."""
    return holidays.country_holidays("TR", years=year)


def is_business_day(day, extra_closed_days=None):
    """Return True if day is Mon-Fri and not a closed day."""
    if extra_closed_days is None:
        extra_closed_days = set()
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
