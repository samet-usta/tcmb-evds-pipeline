"""Write ingestion envelopes to the S3 landing zone as raw JSON."""
import json
import logging
import os
from datetime import date, datetime, timezone

import boto3

logger = logging.getLogger(__name__)

LANDING_PREFIX = "raw"
FILE_NAME = "data.json"


def get_bucket_name():
    """Return the landing bucket name from the S3_BUCKET env var."""
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        raise ValueError("S3_BUCKET is not set")
    return bucket


def build_key(group_name, dt):
    """Return the S3 key: raw/<group>/dt=YYYY-MM-DD/data.json."""
    # datetime is a subclass of date; only a pure date is accepted.
    if isinstance(dt, datetime) or not isinstance(dt, date):
        raise ValueError(f"dt must be a datetime.date, got {type(dt).__name__}")
    dt_text = dt.isoformat()
    return f"{LANDING_PREFIX}/{group_name}/dt={dt_text}/{FILE_NAME}"


def build_payload(envelope, dt, ingested_at):
    """Return the landing payload: metadata plus raw items."""
    request_params = {
        "start_date": envelope["start_date"],
        "end_date": envelope["end_date"],
        "series_codes": envelope["series_codes"],
    }
    metadata = {
        "dt": dt.isoformat(),
        "ingested_at": ingested_at.isoformat(),
        "source": envelope["source"],
        "group": envelope["group"],
        "fallback_reason": envelope["fallback_reason"],
        "request_params": request_params,
    }
    payload = {"metadata": metadata, "items": envelope["items"]}
    return payload


def write_landing(envelope, dt, s3_client=None):
    """Write one envelope to S3. The same group and dt overwrite one object."""
    if s3_client is None:
        s3_client = boto3.client("s3")
    bucket = get_bucket_name()
    key = build_key(envelope["group"], dt)
    ingested_at = datetime.now(timezone.utc)
    payload = build_payload(envelope, dt, ingested_at)
    body = json.dumps(payload, ensure_ascii=False)

    # put_object replaces the object with the same key (idempotent write).
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json",
    )
    s3_uri = f"s3://{bucket}/{key}"
    logger.info("Landing file written: %s (%d items)", s3_uri, len(envelope["items"]))
    return s3_uri
