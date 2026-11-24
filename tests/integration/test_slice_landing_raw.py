"""Integration test: snapshot slice -> S3 landing -> raw.evds_landing item counts."""

import datetime
import json

import boto3
import pytest

from src.landing.s3_writer import build_key, get_bucket_name, write_landing
from src.load.postgres_loader import get_connection, load_landing
from src.simulation.evds_slicer import slice_for_dt
from src.simulation.evds_snapshot import get_snapshot_dir, get_snapshot_path, read_snapshot

pytestmark = pytest.mark.integration

# Test grubu: gerçek raw verisine dokunulmaz.
GROUP = "integration_test"

# İlk dt boş dilim verir. Son dt tam dilim verir.
TEST_DTS = [
    datetime.date(2026, 8, 24),
    datetime.date(2026, 9, 5),
    datetime.date(2026, 10, 1),
    datetime.date(2026, 11, 13),
    datetime.date(2026, 11, 21),
]


@pytest.fixture
def s3_client():
    client = boto3.client("s3")
    yield client
    # Teardown: delete the test files.
    bucket = get_bucket_name()
    response = client.list_objects_v2(Bucket=bucket, Prefix=f"raw/{GROUP}/")
    for s3_object in response.get("Contents", []):
        client.delete_object(Bucket=bucket, Key=s3_object["Key"])


@pytest.fixture
def conn():
    connection = get_connection()
    yield connection
    # Teardown: delete the test rows.
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM raw.evds_landing WHERE group_name = %s", (GROUP,))
    connection.close()


def count_landing_items(s3_client, dt):
    """Return the item count inside the S3 landing file."""
    key = build_key(GROUP, dt)
    response = s3_client.get_object(Bucket=get_bucket_name(), Key=key)
    payload = json.loads(response["Body"].read())
    return len(payload["items"])


def count_raw_items(conn, dt):
    """Return the item count inside the raw.evds_landing row."""
    with conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT jsonb_array_length(items::jsonb) FROM raw.evds_landing "
                "WHERE group_name = %s AND dt = %s",
                (GROUP, dt),
            )
            row = cursor.fetchone()
    return row[0]


def count_raw_rows(conn):
    """Return the row count of the test group in raw.evds_landing."""
    with conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM raw.evds_landing WHERE group_name = %s", (GROUP,)
            )
            row = cursor.fetchone()
    return row[0]


@pytest.mark.parametrize("snapshot_group", ["fx_rates", "deposit_rates", "policy_rate"])
def test_landing_and_raw_have_same_item_count(s3_client, conn, snapshot_group):
    path = get_snapshot_path(get_snapshot_dir(), snapshot_group)
    result = read_snapshot(path)

    previous_count = 0
    for dt in TEST_DTS:
        # slice_for_dt gecikmeyi result["group"] ile bulur. Group adı sonra değişir.
        envelope = slice_for_dt(result, dt)
        envelope["group"] = GROUP

        write_landing(envelope, dt, s3_client)
        load_landing(GROUP, dt, s3_client, conn)

        count_slice = len(envelope["items"])
        count_landing = count_landing_items(s3_client, dt)
        count_raw = count_raw_items(conn, dt)

        assert count_landing == count_slice
        assert count_raw == count_landing
        # Dilim büyür, küçülmez.
        assert count_raw >= previous_count
        previous_count = count_raw

    # Boş dilim de bir satır yazar.
    assert count_raw_rows(conn) == len(TEST_DTS)
