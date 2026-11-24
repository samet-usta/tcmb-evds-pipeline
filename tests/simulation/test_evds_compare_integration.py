"""Integration tests for evds_compare. Use temporary schemas in the warehouse."""

import pytest

from src.load.postgres_loader import get_connection
from src.simulation import evds_compare

DEV = "test_cmp_dev"
REF = "test_cmp_ref"
TABLE = "fct_test"


def run(conn, query, params=None):
    with conn.cursor() as cur:
        cur.execute(query, params)


def drop_schemas(conn):
    run(conn, f"DROP SCHEMA IF EXISTS {DEV} CASCADE")
    run(conn, f"DROP SCHEMA IF EXISTS {REF} CASCADE")


def insert_row(conn, schema, series_code, value, ingested_at="2026-11-01"):
    query = (
        f"INSERT INTO {schema}.{TABLE} "
        "(series_code, value, ingested_at, dbt_updated_at) "
        "VALUES (%s, %s, %s, %s)"
    )
    run(conn, query, (series_code, value, ingested_at, ingested_at))


@pytest.fixture
def conn():
    connection = get_connection()
    connection.autocommit = True
    drop_schemas(connection)
    for schema in [DEV, REF]:
        run(connection, f"CREATE SCHEMA {schema}")
        run(
            connection,
            f"CREATE TABLE {schema}.{TABLE} ("
            "series_code text, value numeric, "
            "ingested_at timestamp, dbt_updated_at timestamp)",
        )
    yield connection
    drop_schemas(connection)
    connection.close()


def compare(conn):
    return evds_compare.compare_table(conn, TABLE, DEV, REF)


@pytest.mark.integration
def test_same_data_different_audit_columns_is_ok(conn):
    insert_row(conn, DEV, "A", 1, ingested_at="2026-11-01")
    insert_row(conn, REF, "A", 1, ingested_at="2026-11-20")
    result = compare(conn)
    assert result["ok"] is True


@pytest.mark.integration
def test_value_diff_is_found_both_directions(conn):
    insert_row(conn, DEV, "A", 1)
    insert_row(conn, REF, "A", 2)
    result = compare(conn)
    assert result["ok"] is False
    assert result["dev_minus_ref"] == 1
    assert result["ref_minus_dev"] == 1


@pytest.mark.integration
def test_extra_row_in_dev_is_found(conn):
    insert_row(conn, DEV, "A", 1)
    insert_row(conn, DEV, "B", 2)
    insert_row(conn, REF, "A", 1)
    result = compare(conn)
    assert result["ok"] is False
    assert result["dev_count"] == 2
    assert result["ref_count"] == 1
    assert result["dev_minus_ref"] == 1
    assert result["ref_minus_dev"] == 0


@pytest.mark.integration
def test_duplicate_row_in_dev_is_found(conn):
    insert_row(conn, DEV, "A", 1)
    insert_row(conn, DEV, "A", 1)
    insert_row(conn, REF, "A", 1)
    result = compare(conn)
    assert result["ok"] is False
    assert result["dev_minus_ref"] == 1
