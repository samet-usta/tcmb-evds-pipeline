"""Unit tests for the EVDS snapshot. No real EVDS call is made."""

import pytest

from src.simulation import evds_snapshot


class FakeFetch:
    """Fake for evds_client.fetch_group. It counts the calls."""

    def __init__(self):
        self.calls = []

    def __call__(self, group_name, start_date, end_date, config_path=None):
        self.calls.append(group_name)
        return {
            "source": "evds",
            "group": group_name,
            "series_codes": ["TP.TEST"],
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "items": [{"Tarih": "01-09-2026", "TP_TEST": "1.5"}],
        }


def failing_fetch(group_name, start_date, end_date, config_path=None):
    raise RuntimeError("EVDS is down")


def test_downloads_when_file_is_missing(tmp_path):
    fake_fetch = FakeFetch()

    result, downloaded = evds_snapshot.ensure_group("fx_rates", tmp_path, fetch_func=fake_fetch)

    path = evds_snapshot.get_snapshot_path(tmp_path, "fx_rates")
    assert downloaded is True
    assert path.exists()
    assert fake_fetch.calls == ["fx_rates"]
    assert result["group"] == "fx_rates"


def test_reads_when_file_exists(tmp_path):
    fake_fetch = FakeFetch()
    first_result, _ = evds_snapshot.ensure_group("fx_rates", tmp_path, fetch_func=fake_fetch)

    second_result, downloaded = evds_snapshot.ensure_group("fx_rates", tmp_path, fetch_func=fake_fetch)

    assert downloaded is False
    assert len(fake_fetch.calls) == 1
    assert second_result == first_result


def test_range_mismatch_raises_error(tmp_path):
    path = evds_snapshot.get_snapshot_path(tmp_path, "fx_rates")
    old_result = {"group": "fx_rates", "start_date": "2026-01-01", "end_date": "2026-01-31", "items": []}
    evds_snapshot.write_snapshot(path, old_result)

    with pytest.raises(ValueError):
        evds_snapshot.ensure_group("fx_rates", tmp_path, fetch_func=FakeFetch())


def test_fetch_error_leaves_no_file(tmp_path):
    with pytest.raises(RuntimeError):
        evds_snapshot.ensure_group("fx_rates", tmp_path, fetch_func=failing_fetch)

    path = evds_snapshot.get_snapshot_path(tmp_path, "fx_rates")
    assert not path.exists()


def test_snapshot_has_7_files_and_second_run_makes_0_calls(tmp_path):
    fake_fetch = FakeFetch()

    results, count_downloaded, count_cached = evds_snapshot.ensure_snapshot(
        snapshot_dir=tmp_path, fetch_func=fake_fetch
    )
    files = list(tmp_path.glob("*.json"))

    assert len(results) == 7
    assert len(files) == 7
    assert count_downloaded == 7
    assert count_cached == 0
    assert len(fake_fetch.calls) == 7

    calls_before = len(fake_fetch.calls)
    results, count_downloaded, count_cached = evds_snapshot.ensure_snapshot(
        snapshot_dir=tmp_path, fetch_func=fake_fetch
    )

    assert count_downloaded == 0
    assert count_cached == 7
    assert len(fake_fetch.calls) == calls_before
