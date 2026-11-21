"""Unit tests for the S3 landing writer. The S3 client is a mock."""
import json
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.landing import s3_writer


def make_envelope(source="evds", fallback_reason=None):
    return {
        "source": source,
        "group": "fx_rates",
        "series_codes": ["TP.DK.USD.A.YTL"],
        "start_date": "2026-11-16",
        "end_date": "2026-11-20",
        "items": [{"Tarih": "20-11-2026", "TP_DK_USD_A_YTL": "42.1"}],
        "fallback_reason": fallback_reason,
    }


@pytest.fixture
def bucket_env(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "test-bucket")


def test_build_key_returns_partition_path():
    key = s3_writer.build_key("fx_rates", date(2026, 11, 20))
    assert key == "raw/fx_rates/dt=2026-11-20/data.json"


def test_build_key_rejects_datetime():
    with pytest.raises(ValueError):
        s3_writer.build_key("fx_rates", datetime(2026, 11, 20, 10, 0))


def test_build_key_rejects_string():
    with pytest.raises(ValueError):
        s3_writer.build_key("fx_rates", "2026-11-20")


def test_get_bucket_name_reads_env(bucket_env):
    assert s3_writer.get_bucket_name() == "test-bucket"


def test_get_bucket_name_missing_raises(monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    with pytest.raises(ValueError):
        s3_writer.get_bucket_name()


def test_build_payload_has_metadata_and_items():
    envelope = make_envelope()
    ingested_at = datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc)
    payload = s3_writer.build_payload(envelope, date(2026, 11, 20), ingested_at)

    metadata = payload["metadata"]
    assert metadata["dt"] == "2026-11-20"
    assert metadata["ingested_at"] == "2026-11-21T10:00:00+00:00"
    assert metadata["source"] == "evds"
    assert metadata["group"] == "fx_rates"
    assert metadata["fallback_reason"] is None
    assert metadata["request_params"] == {
        "start_date": "2026-11-16",
        "end_date": "2026-11-20",
        "series_codes": ["TP.DK.USD.A.YTL"],
    }
    assert payload["items"] == envelope["items"]


def test_build_payload_keeps_fallback_reason():
    envelope = make_envelope(source="frankfurter", fallback_reason="EvdsRequestError: HTTP 503")
    ingested_at = datetime(2026, 11, 21, tzinfo=timezone.utc)
    payload = s3_writer.build_payload(envelope, date(2026, 11, 20), ingested_at)
    assert payload["metadata"]["source"] == "frankfurter"
    assert payload["metadata"]["fallback_reason"] == "EvdsRequestError: HTTP 503"


def test_write_landing_puts_object(bucket_env):
    s3_client = MagicMock()
    uri = s3_writer.write_landing(make_envelope(), date(2026, 11, 20), s3_client=s3_client)

    assert uri == "s3://test-bucket/raw/fx_rates/dt=2026-11-20/data.json"
    s3_client.put_object.assert_called_once()
    kwargs = s3_client.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "test-bucket"
    assert kwargs["Key"] == "raw/fx_rates/dt=2026-11-20/data.json"
    assert kwargs["ContentType"] == "application/json"
    body = json.loads(kwargs["Body"].decode("utf-8"))
    assert body["metadata"]["source"] == "evds"
    assert len(body["items"]) == 1


def test_write_landing_same_dt_same_key(bucket_env):
    # Idempotency: two runs for the same dt write the same key.
    s3_client = MagicMock()
    s3_writer.write_landing(make_envelope(), date(2026, 11, 20), s3_client=s3_client)
    s3_writer.write_landing(make_envelope(), date(2026, 11, 20), s3_client=s3_client)

    first_key = s3_client.put_object.call_args_list[0].kwargs["Key"]
    second_key = s3_client.put_object.call_args_list[1].kwargs["Key"]
    assert first_key == second_key


def test_write_landing_without_bucket_does_not_call_s3(monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    s3_client = MagicMock()
    with pytest.raises(ValueError):
        s3_writer.write_landing(make_envelope(), date(2026, 11, 20), s3_client=s3_client)
    s3_client.put_object.assert_not_called()
