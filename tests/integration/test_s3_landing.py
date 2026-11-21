"""Integration tests for the S3 landing writer. Needs running LocalStack."""
import json
import os
from datetime import date

import boto3
import pytest
from botocore.exceptions import ClientError

from src.landing.s3_writer import write_landing

pytestmark = pytest.mark.integration

TEST_GROUP = "integration_test"
TEST_PREFIX = f"raw/{TEST_GROUP}/"


def make_envelope(source="evds", fallback_reason=None):
    return {
        "source": source,
        "group": TEST_GROUP,
        "series_codes": ["TP.DK.USD.A.YTL"],
        "start_date": "2026-11-16",
        "end_date": "2026-11-20",
        "items": [{"Tarih": "20-11-2026", "TP_DK_USD_A_YTL": "42.1"}],
        "fallback_reason": fallback_reason,
    }


def list_test_keys(s3_client, bucket):
    listing = s3_client.list_objects_v2(Bucket=bucket, Prefix=TEST_PREFIX)
    keys = []
    for obj in listing.get("Contents", []):
        keys.append(obj["Key"])
    return keys


@pytest.fixture
def bucket():
    return os.environ["S3_BUCKET"]


@pytest.fixture
def s3_client(bucket):
    client = boto3.client("s3")
    yield client
    # Cleanup: remove only the objects of this test group.
    for key in list_test_keys(client, bucket):
        client.delete_object(Bucket=bucket, Key=key)


def test_same_dt_twice_creates_one_object(s3_client, bucket):
    write_landing(make_envelope(), date(2026, 11, 20), s3_client=s3_client)
    write_landing(make_envelope(), date(2026, 11, 20), s3_client=s3_client)

    keys = list_test_keys(s3_client, bucket)
    assert keys == [f"{TEST_PREFIX}dt=2026-11-20/data.json"]


def test_fallback_rerun_overwrites_same_object(s3_client, bucket):
    # First run uses the fallback, the rerun uses EVDS: one object, last write wins.
    fallback_envelope = make_envelope(source="frankfurter", fallback_reason="EvdsRequestError: HTTP 503")
    write_landing(fallback_envelope, date(2026, 11, 20), s3_client=s3_client)
    write_landing(make_envelope(), date(2026, 11, 20), s3_client=s3_client)

    keys = list_test_keys(s3_client, bucket)
    assert len(keys) == 1
    body = s3_client.get_object(Bucket=bucket, Key=keys[0])["Body"].read()
    payload = json.loads(body)
    assert payload["metadata"]["source"] == "evds"
    assert payload["metadata"]["fallback_reason"] is None


def test_different_dt_creates_separate_objects(s3_client, bucket):
    write_landing(make_envelope(), date(2026, 11, 19), s3_client=s3_client)
    write_landing(make_envelope(), date(2026, 11, 20), s3_client=s3_client)

    keys = list_test_keys(s3_client, bucket)
    assert len(keys) == 2


def test_missing_bucket_fails(s3_client, monkeypatch):
    # Fail fast: the writer does not create buckets.
    monkeypatch.setenv("S3_BUCKET", "bucket-does-not-exist")
    with pytest.raises(ClientError):
        write_landing(make_envelope(), date(2026, 11, 20), s3_client=s3_client)
