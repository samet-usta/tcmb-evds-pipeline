"""Unit tests for src/load/postgres_loader.py (no S3, no database)."""

import datetime
import json
from unittest.mock import MagicMock, patch

import pytest

from src.load import postgres_loader

DT = datetime.date(2026, 11, 20)
KEY = "raw/fx_rates/dt=2026-11-20/data.json"


@pytest.fixture
def bucket_env(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "test-bucket")


@pytest.fixture
def warehouse_env(monkeypatch):
    monkeypatch.setenv("WAREHOUSE_HOST", "test-host")
    monkeypatch.setenv("WAREHOUSE_PORT", "5432")
    monkeypatch.setenv("WAREHOUSE_DB", "test-db")
    monkeypatch.setenv("WAREHOUSE_USER", "test-user")
    monkeypatch.setenv("WAREHOUSE_PASSWORD", "test-password")


def make_payload(group_name="fx_rates", dt_text="2026-11-20"):
    payload = {
        "metadata": {
            "dt": dt_text,
            "ingested_at": "2026-11-21T10:00:00+00:00",
            "source": "evds",
            "group": group_name,
            "fallback_reason": None,
            "request_params": {"start_date": "2026-11-16", "end_date": "2026-11-20"},
        },
        "items": [{"Tarih": "20-11-2026", "TP_DK_USD_A_YTL": "42.10000000"}],
    }
    return payload


def make_s3_client(payload):
    body = MagicMock()
    body.read.return_value = json.dumps(payload).encode("utf-8")
    s3_client = MagicMock()
    s3_client.get_object.return_value = {"Body": body}
    return s3_client


def get_cursor(conn):
    # "with conn.cursor() as cursor" gives the __enter__ return value.
    return conn.cursor.return_value.__enter__.return_value


# --- get_connection ---

def test_get_connection_uses_warehouse_env(warehouse_env):
    with patch.object(postgres_loader.psycopg2, "connect") as mock_connect:
        postgres_loader.get_connection()

    mock_connect.assert_called_once_with(
        host="test-host",
        port="5432",
        dbname="test-db",
        user="test-user",
        password="test-password",
        connect_timeout=10,
    )


# --- read_landing ---

def test_read_landing_reads_only_dt_key(bucket_env):
    payload = make_payload()
    s3_client = make_s3_client(payload)

    s3_key, result = postgres_loader.read_landing("fx_rates", DT, s3_client)

    s3_client.get_object.assert_called_once_with(Bucket="test-bucket", Key=KEY)
    assert s3_key == KEY
    assert result == payload


def test_read_landing_rejects_string_dt(bucket_env):
    s3_client = MagicMock()

    with pytest.raises(ValueError):
        postgres_loader.read_landing("fx_rates", "2026-11-20", s3_client)

    s3_client.get_object.assert_not_called()


# --- build_row ---

def test_build_row_maps_fields():
    payload = make_payload()

    row = postgres_loader.build_row(payload, KEY, "fx_rates", DT)

    assert row["group_name"] == "fx_rates"
    assert row["dt"] == DT
    assert row["source"] == "evds"
    assert row["ingested_at"] == "2026-11-21T10:00:00+00:00"
    assert row["fallback_reason"] is None
    assert row["s3_key"] == KEY
    # Json wraps the value for jsonb; .adapted is the original value.
    assert row["request_params"].adapted == payload["metadata"]["request_params"]
    assert row["items"].adapted == payload["items"]


def test_build_row_group_mismatch_raises():
    payload = make_payload(group_name="deposit_rates")

    with pytest.raises(ValueError, match="group"):
        postgres_loader.build_row(payload, KEY, "fx_rates", DT)


def test_build_row_dt_mismatch_raises():
    payload = make_payload(dt_text="2026-11-19")

    with pytest.raises(ValueError, match="dt"):
        postgres_loader.build_row(payload, KEY, "fx_rates", DT)


# --- upsert_row ---

def test_upsert_row_executes_sql_with_row():
    conn = MagicMock()
    row = {"group_name": "fx_rates"}

    postgres_loader.upsert_row(conn, row)

    get_cursor(conn).execute.assert_called_once_with(postgres_loader.UPSERT_SQL, row)
    conn.__enter__.assert_called_once()


def test_upsert_sql_is_idempotent():
    assert "ON CONFLICT (group_name, dt) DO UPDATE" in postgres_loader.UPSERT_SQL
    assert "loaded_at = now()" in postgres_loader.UPSERT_SQL


# --- load_landing ---

def test_load_landing_given_conn_is_not_closed(bucket_env):
    s3_client = make_s3_client(make_payload())
    conn = MagicMock()

    result = postgres_loader.load_landing("fx_rates", DT, s3_client, conn)

    assert result == KEY
    get_cursor(conn).execute.assert_called_once()
    conn.close.assert_not_called()


def test_load_landing_own_conn_is_closed(bucket_env):
    s3_client = make_s3_client(make_payload())
    conn = MagicMock()

    with patch.object(postgres_loader, "get_connection", return_value=conn):
        postgres_loader.load_landing("fx_rates", DT, s3_client)

    conn.close.assert_called_once()


def test_load_landing_closes_conn_on_error(bucket_env):
    s3_client = make_s3_client(make_payload())
    conn = MagicMock()
    get_cursor(conn).execute.side_effect = RuntimeError("database error")

    with patch.object(postgres_loader, "get_connection", return_value=conn):
        with pytest.raises(RuntimeError):
            postgres_loader.load_landing("fx_rates", DT, s3_client)

    conn.close.assert_called_once()
