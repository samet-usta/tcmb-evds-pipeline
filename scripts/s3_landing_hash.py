"""Print an md5 hash for each S3 landing object of one dt (ingested_at excluded)."""
import hashlib
import json
import os

from airflow.providers.amazon.aws.hooks.s3 import S3Hook

dt = os.environ["DT"]
hook = S3Hook(aws_conn_id="aws_localstack")
client = hook.get_conn()
paginator = client.get_paginator("list_objects_v2")

for bucket in client.list_buckets()["Buckets"]:
    bucket_name = bucket["Name"]
    keys = []
    for page in paginator.paginate(Bucket=bucket_name, Prefix="raw/"):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    print("bucket:", bucket_name, "total_keys:", len(keys))

    for key in sorted(keys):
        if "dt=" + dt not in key:
            continue
        response = client.get_object(Bucket=bucket_name, Key=key)
        body_dict = json.loads(response["Body"].read().decode("utf-8"))
        # ingested_at is inside metadata and changes on every run
        body_dict["metadata"].pop("ingested_at", None)
        body_clean = json.dumps(body_dict, sort_keys=True)
        print(key, hashlib.md5(body_clean.encode("utf-8")).hexdigest())
