"""EVDS snapshot: fetch each series group once and store the raw response as JSON."""

import json
import logging
import os
from datetime import date
from pathlib import Path

from src.ingestion import evds_client
from src.ingestion.series_config import load_series_config

logger = logging.getLogger(__name__)

# Aralık sabit: snapshot her zaman aynı veri aralığını temsil eder.
SNAPSHOT_START = date(2026, 8, 24)
SNAPSHOT_END = date(2026, 11, 21)


def get_snapshot_dir():
    """Return the snapshot folder from the env EVDS_REPLAY_SNAPSHOT_DIR."""
    folder = os.environ["EVDS_REPLAY_SNAPSHOT_DIR"]
    return Path(folder)


def get_snapshot_path(snapshot_dir, group_name):
    """Return the file path of one group snapshot."""
    file_name = f"{group_name}.json"
    return Path(snapshot_dir) / file_name


def read_snapshot(path):
    """Read one snapshot file and return the result dict."""
    with open(path, encoding="utf-8") as file:
        result = json.load(file)
    return result


def write_snapshot(path, result):
    """Write the result to a temp file, then rename it."""
    # Geçici dosya + rename: yarıda kesilen yazma bozuk snapshot bırakmaz.
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = Path(str(path) + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False)
    os.replace(temp_path, path)


def check_snapshot_range(result, group_name):
    """Raise ValueError if the stored date range differs from the fixed range."""
    expected_start = SNAPSHOT_START.isoformat()
    expected_end = SNAPSHOT_END.isoformat()
    if result["start_date"] != expected_start or result["end_date"] != expected_end:
        raise ValueError(
            f"Snapshot range mismatch for {group_name}: "
            f"{result['start_date']} to {result['end_date']}. "
            f"Expected {expected_start} to {expected_end}."
        )


def ensure_group(group_name, snapshot_dir, config_path=None, fetch_func=evds_client.fetch_group):
    """Return (result, downloaded). Read the file if it exists, else fetch and write it."""
    path = get_snapshot_path(snapshot_dir, group_name)

    if path.exists():
        result = read_snapshot(path)
        check_snapshot_range(result, group_name)
        logger.info("Snapshot cache hit: %s", group_name)
        return result, False

    result = fetch_func(group_name, SNAPSHOT_START, SNAPSHOT_END, config_path)
    write_snapshot(path, result)
    logger.info("Snapshot written: %s", group_name)
    return result, True


def ensure_snapshot(snapshot_dir=None, config_path=None, fetch_func=evds_client.fetch_group):
    """Make sure every group has a snapshot file. Return (results, downloaded, cached)."""
    if snapshot_dir is None:
        snapshot_dir = get_snapshot_dir()

    group_names = list(load_series_config(config_path).keys())
    results = {}
    count_downloaded = 0
    count_cached = 0

    for group_name in group_names:
        result, downloaded = ensure_group(group_name, snapshot_dir, config_path, fetch_func)
        results[group_name] = result
        if downloaded:
            count_downloaded = count_downloaded + 1
        else:
            count_cached = count_cached + 1

    return results, count_downloaded, count_cached


def main():
    logging.basicConfig(level=logging.INFO)
    results, count_downloaded, count_cached = ensure_snapshot()
    print(f"groups={len(results)} downloaded={count_downloaded} cached={count_cached}")


if __name__ == "__main__":
    main()
