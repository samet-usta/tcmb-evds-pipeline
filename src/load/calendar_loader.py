"""Load the business calendar into raw.business_calendar (idempotent)."""
import logging
from datetime import timedelta

from src.ingestion.business_calendar import is_business_day
from src.load.postgres_loader import get_connection

logger = logging.getLogger(__name__)

# Same day updates the same row, so a re-run gives the same result.
UPSERT_SQL = """
INSERT INTO raw.business_calendar (dt, is_business_day)
VALUES (%(dt)s, %(is_business_day)s)
ON CONFLICT (dt) DO UPDATE SET is_business_day = EXCLUDED.is_business_day
"""


def build_calendar_rows(start_day, end_day):
    """Return one row per calendar day from start_day to end_day."""
    rows = []
    current_day = start_day
    while current_day <= end_day:
        row = {"dt": current_day, "is_business_day": is_business_day(current_day)}
        rows.append(row)
        current_day = current_day + timedelta(days=1)
    return rows


def load_calendar(start_day, end_day):
    """Upsert calendar rows into raw.business_calendar. Return row count."""
    rows = build_calendar_rows(start_day, end_day)
    conn = get_connection()
    try:
        # "with conn" commits on success and rolls back on error.
        with conn:
            with conn.cursor() as cur:
                cur.executemany(UPSERT_SQL, rows)
    finally:
        conn.close()
    logger.info("Loaded %s calendar rows", len(rows))
    return len(rows)
