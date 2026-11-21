"""Load one S3 landing file into raw.evds_landing (PostgreSQL)."""

import json
import logging
import os

import boto3
import psycopg2
from psycopg2.extras import Json

from src.landing.s3_writer import build_key, get_bucket_name

logger = logging.getLogger(__name__)

# Idempotent: same (group_name, dt) updates the same row.
UPSERT_SQL = """
INSERT INTO raw.evds_landing (
    group_name, dt, source, ingested_at, fallback_reason,
    s3_key, request_params, items, loaded_at
)
VALUES (
    %(group_name)s, %(dt)s, %(source)s, %(ingested_at)s, %(fallback_reason)s,
    %(s3_key)s, %(request_params)s, %(items)s, now()
)
ON CONFLICT (group_name, dt) DO UPDATE SET
    source = EXCLUDED.source,
    ingested_at = EXCLUDED.ingested_at,
    fallback_reason = EXCLUDED.fallback_reason,
    s3_key = EXCLUDED.s3_key,
    request_params = EXCLUDED.request_params,
    items = EXCLUDED.items,
    loaded_at = now()
"""


def get_connection():
    """Open a PostgreSQL connection from WAREHOUSE_* env vars."""
    conn = psycopg2.connect(
        host=os.environ["WAREHOUSE_HOST"],
        port=os.environ["WAREHOUSE_PORT"],
        dbname=os.environ["WAREHOUSE_DB"],
        user=os.environ["WAREHOUSE_USER"],
        password=os.environ["WAREHOUSE_PASSWORD"],
        connect_timeout=10,
    )
    return conn


def read_landing(group_name, dt, s3_client=None):
    """Read one landing file from S3. Return (s3_key, payload)."""
    if s3_client is None:
        s3_client = boto3.client("s3")
    bucket = get_bucket_name()
    s3_key = build_key(group_name, dt)
    response = s3_client.get_object(Bucket=bucket, Key=s3_key)
    body = response["Body"].read()
    payload = json.loads(body)
    return s3_key, payload


def build_row(payload, s3_key, group_name, dt):
    """Map the payload to a table row. Check metadata against the key."""
    metadata = payload["metadata"]
    if metadata["group"] != group_name:
        raise ValueError(
            f"Metadata group '{metadata['group']}' does not match '{group_name}'"
        )
    if metadata["dt"] != dt.isoformat():
        raise ValueError(
            f"Metadata dt '{metadata['dt']}' does not match '{dt.isoformat()}'"
        )
    row = {
        "group_name": group_name,
        "dt": dt,
        "source": metadata["source"],
        "ingested_at": metadata["ingested_at"],
        "fallback_reason": metadata["fallback_reason"],
        "s3_key": s3_key,
        "request_params": Json(metadata["request_params"]),
        "items": Json(payload["items"]),
    }
    return row


def upsert_row(conn, row):
    """Write one row in one transaction."""
    # "with conn" commits on success and rolls back on error.
    with conn:
        with conn.cursor() as cursor:
            cursor.execute(UPSERT_SQL, row)


def load_landing(group_name, dt, s3_client=None, conn=None):
    """Load the landing file of (group_name, dt) into raw.evds_landing."""
    s3_key, payload = read_landing(group_name, dt, s3_client)
    row = build_row(payload, s3_key, group_name, dt)

    # Close only the connection that this function opens.
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        upsert_row(conn, row)
    finally:
        if own_conn:
            conn.close()

    item_count = len(payload["items"])
    logger.info("Loaded %s (%s items) into raw.evds_landing", s3_key, item_count)
    return s3_key
