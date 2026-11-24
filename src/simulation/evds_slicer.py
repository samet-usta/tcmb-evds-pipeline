"""Build the slice of an EVDS snapshot that is visible on a given dt."""

import calendar
from datetime import date, timedelta

from src.simulation.evds_snapshot import get_snapshot_dir, get_snapshot_path, read_snapshot

# Yayın gecikmesi (gün): gözlem tarihinden kaç gün sonra veri görünür olur.
# Simülasyon varsayımı. series.yaml'a girmez.
PUBLICATION_LAG_DAYS = {
    "fx_rates": 1,
    "funding_cost": 1,
    "deposit_rates": 6,
    "deposit_volumes": 6,
    "loan_rates": 6,
    "loan_volumes": 6,
    "policy_rate": 5,
}


def get_lag_days(group_name):
    """Return the publication lag of one group in days."""
    if group_name not in PUBLICATION_LAG_DAYS:
        raise ValueError(f"No publication lag for group: {group_name}")
    return PUBLICATION_LAG_DAYS[group_name]


def parse_observation_date(tarih_text):
    """Return the observation date. DD-MM-YYYY is one day. YYYY-M is the last day of the month."""
    parts = tarih_text.split("-")

    # Aylık seri: "2026-8". Veri ay bittiğinde oluşur, o yüzden ay sonu alınır.
    if len(parts[0]) == 4:
        year = int(parts[0])
        month = int(parts[1])
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, last_day)

    day = int(parts[0])
    month = int(parts[1])
    year = int(parts[2])
    return date(year, month, day)


def is_visible(item, lag_days, dt):
    """Return True if the item is published on dt."""
    observation_date = parse_observation_date(item["Tarih"])
    visible_from = observation_date + timedelta(days=lag_days)
    return visible_from <= dt


def slice_for_dt(result, dt):
    """Return the envelope of one group as it looks on dt. The slice only grows with dt."""
    lag_days = get_lag_days(result["group"])

    items_visible = []
    for item in result["items"]:
        if is_visible(item, lag_days, dt):
            items_visible.append(item)

    envelope = {
        "source": result["source"],
        "group": result["group"],
        "series_codes": result["series_codes"],
        "start_date": result["start_date"],
        "end_date": dt.isoformat(),
        # Snapshot'ta fallback_reason yok. write_landing bu alanı ister.
        "fallback_reason": None,
        "items": items_visible,
    }
    return envelope


def read_slice(group_name, dt, snapshot_dir=None):
    """Read the snapshot of one group and return its slice for dt."""
    if snapshot_dir is None:
        snapshot_dir = get_snapshot_dir()
    path = get_snapshot_path(snapshot_dir, group_name)
    result = read_snapshot(path)
    return slice_for_dt(result, dt)
