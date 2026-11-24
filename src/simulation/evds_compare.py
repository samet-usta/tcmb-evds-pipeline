"""Compare dev marts with the full-refresh reference marts."""

import sys

from psycopg2 import sql

from src.load.postgres_loader import get_connection

DEV_SCHEMA = "dbt_dev_marts"
REF_SCHEMA = "dbt_full_refresh_check_marts"
TABLES = ["fct_rates", "fct_volumes", "fct_rates_daily"]

# Audit kolonları run zamanına bağlı. Full-refresh hepsini yeniden yazar,
# incremental eski değeri korur. Bu yüzden karşılaştırmaya girmez.
EXCLUDED_COLUMNS = ["ingested_at", "dbt_updated_at"]


def get_compare_columns(conn, schema, table):
    """Return the table columns without audit columns, in table order."""
    query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
    """
    with conn.cursor() as cur:
        cur.execute(query, (schema, table))
        rows = cur.fetchall()

    columns = []
    for row in rows:
        column_name = row[0]
        if column_name not in EXCLUDED_COLUMNS:
            columns.append(column_name)
    return columns


def count_rows(conn, schema, table):
    """Return the row count of schema.table."""
    query = sql.SQL("SELECT count(*) FROM {}.{}").format(
        sql.Identifier(schema), sql.Identifier(table)
    )
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchone()[0]


def count_except(conn, table, columns, schema_a, schema_b):
    """Count rows that are in schema_a.table but not in schema_b.table."""
    identifiers = []
    for column in columns:
        identifiers.append(sql.Identifier(column))
    column_list = sql.SQL(", ").join(identifiers)

    # EXCEPT ALL: tekrarlı satır farkını da yakalar
    query = sql.SQL(
        "SELECT count(*) FROM ("
        "SELECT {cols} FROM {a}.{t} EXCEPT ALL SELECT {cols} FROM {b}.{t}"
        ") AS diff"
    ).format(
        cols=column_list,
        a=sql.Identifier(schema_a),
        b=sql.Identifier(schema_b),
        t=sql.Identifier(table),
    )
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchone()[0]


def compare_table(conn, table, dev_schema=DEV_SCHEMA, ref_schema=REF_SCHEMA):
    """Compare one table. Return a dict with counts and an ok flag."""
    columns = get_compare_columns(conn, dev_schema, table)

    dev_count = count_rows(conn, dev_schema, table)
    ref_count = count_rows(conn, ref_schema, table)
    dev_minus_ref = count_except(conn, table, columns, dev_schema, ref_schema)
    ref_minus_dev = count_except(conn, table, columns, ref_schema, dev_schema)

    is_ok = dev_count == ref_count and dev_minus_ref == 0 and ref_minus_dev == 0
    return {
        "table": table,
        "dev_count": dev_count,
        "ref_count": ref_count,
        "dev_minus_ref": dev_minus_ref,
        "ref_minus_dev": ref_minus_dev,
        "ok": is_ok,
    }


def compare_marts(conn, dev_schema=DEV_SCHEMA, ref_schema=REF_SCHEMA):
    """Compare all mart tables. Return one result dict per table."""
    results = []
    for table in TABLES:
        results.append(compare_table(conn, table, dev_schema, ref_schema))
    return results


def print_report(results):
    """Print one line per table."""
    for result in results:
        status = "OK" if result["ok"] else "DIFF"
        print(
            f"{status} {result['table']}: "
            f"dev={result['dev_count']} ref={result['ref_count']} "
            f"dev-ref={result['dev_minus_ref']} ref-dev={result['ref_minus_dev']}"
        )


def main():
    """Compare marts. Return exit code: 0 = no diff, 1 = diff."""
    conn = get_connection()
    try:
        results = compare_marts(conn)
    finally:
        conn.close()

    print_report(results)

    has_diff = False
    for result in results:
        if not result["ok"]:
            has_diff = True
    return 1 if has_diff else 0


if __name__ == "__main__":
    sys.exit(main())
