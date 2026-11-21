"""Integration tests: LocalStack S3 -> warehouse raw.evds_landing."""

import datetime

import boto3
import pytest
from botocore.exceptions import ClientError

from src.landing.s3_writer import get_bucket_name, write_landing
from src.load.postgres_loader import get_connection, load_landing

pytestmark = pytest.mark.integration

GROUP = "integration_test"
DT = datetime.date(2026, 11, 20)


def make_envelope(source="evds", fallback_reason=None):
    envelope = {
        "source": source,
        "group": GROUP,
        "series_codes": ["TP.DK.USD.A.YTL"],
        "start_date": "2026-11-16",
        "end_date": "2026-11-20",
        "items": [{"Tarih": "20-11-2026", "TP_DK_USD_A_YTL": "42.10000000"}],
        "fallback_reason": fallback_reason,
    }
    return envelope


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


def fetch_rows(conn):
    """Return (dt, source, fallback_reason, ingested_at, loaded_at) rows of the test group."""
    with conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT dt, source, fallback_reason, ingested_at, loaded_at "
                "FROM raw.evds_landing WHERE group_name = %s ORDER BY dt",
                (GROUP,),
            )
            rows = cursor.fetchall()
    return rows


def test_same_file_loaded_twice_gives_one_row(s3_client, conn):
    write_landing(make_envelope(), DT, s3_client)

    load_landing(GROUP, DT, s3_client, conn)
    first_rows = fetch_rows(conn)
    load_landing(GROUP, DT, s3_client, conn)
    second_rows = fetch_rows(conn)

    assert len(second_rows) == 1
    # Same file: same ingested_at. New load: new loaded_at.
    assert second_rows[0][3] == first_rows[0][3]
    assert second_rows[0][4] > first_rows[0][4]


def test_rerun_after_fallback_updates_row(s3_client, conn):
    write_landing(make_envelope(), DT, s3_client)
    load_landing(GROUP, DT, s3_client, conn)

    fallback_envelope = make_envelope(source="frankfurter", fallback_reason="EvdsRequestError: test")
    write_landing(fallback_envelope, DT, s3_client)
    load_landing(GROUP, DT, s3_client, conn)

    rows = fetch_rows(conn)
    assert len(rows) == 1
    assert rows[0][1] == "frankfurter"
    assert rows[0][2] == "EvdsRequestError: test"


def test_different_dt_gives_two_rows(s3_client, conn):
    other_dt = datetime.date(2026, 11, 19)
    write_landing(make_envelope(), DT, s3_client)
    write_landing(make_envelope(), other_dt, s3_client)

    load_landing(GROUP, DT, s3_client, conn)
    load_landing(GROUP, other_dt, s3_client, conn)

    rows = fetch_rows(conn)
    assert len(rows) == 2
    assert rows[0][0] == other_dt
    assert rows[1][0] == DT


def test_missing_file_raises_and_writes_nothing(s3_client, conn):
    with pytest.raises(ClientError) as error_info:
        load_landing(GROUP, DT, s3_client, conn)

    assert error_info.value.response["Error"]["Code"] == "NoSuchKey"
    assert fetch_rows(conn) == []
