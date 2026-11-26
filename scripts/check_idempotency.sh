#!/usr/bin/env bash
# Idempotency check for one ds: run the DAG twice, compare raw table and S3 snapshots.
# Usage: bash scripts/check_idempotency.sh YYYY-MM-DD
set -euo pipefail

DS="${1:?usage: bash scripts/check_idempotency.sh YYYY-MM-DD}"
WORK_DIR="$(mktemp -d)"
PSQL='psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A'

run_dag() {
  # Soda gap check fails until A6-S6, so a non-zero exit is allowed here.
  MSYS_NO_PATHCONV=1 docker compose exec -w /opt/pipeline airflow-scheduler \
    airflow dags test evds_daily "$DS" > "$WORK_DIR/$1.log" 2>&1 || true
  grep -o 'new_state=[a-z_]*' "$WORK_DIR/$1.log" | sort | uniq -c
}

snapshot() {
  docker compose exec -T warehouse sh -c "$PSQL" <<EOF > "$WORK_DIR/$1.raw"
select count(*) from raw.evds_landing;
select group_name, dt, md5(items::text) from raw.evds_landing where dt = '$DS' order by group_name;
EOF
  docker compose exec -T warehouse sh -c "$PSQL" <<EOF > "$WORK_DIR/$1.ts"
select max(ingested_at) from raw.evds_landing where dt = '$DS';
EOF
  MSYS_NO_PATHCONV=1 docker compose exec -T -e DT="$DS" -w /opt/pipeline airflow-scheduler \
    python -W ignore - < scripts/s3_landing_hash.py 2>/dev/null \
    | grep -E '^(bucket|raw/)' > "$WORK_DIR/$1.s3" || true
}

echo "ds=$DS work_dir=$WORK_DIR"
echo "--- run 1"; run_dag run1; snapshot snap1
echo "--- run 2"; run_dag run2; snapshot snap2

STATUS=0
[ -s "$WORK_DIR/snap1.s3" ] || { echo "FAIL: S3 snapshot is empty"; STATUS=1; }
diff "$WORK_DIR/snap1.raw" "$WORK_DIR/snap2.raw" || STATUS=1
diff "$WORK_DIR/snap1.s3" "$WORK_DIR/snap2.s3" || STATUS=1
if cmp -s "$WORK_DIR/snap1.ts" "$WORK_DIR/snap2.ts"; then
  echo "FAIL: ingested_at did not change, run 2 wrote nothing"
  STATUS=1
fi

if [ "$STATUS" -eq 0 ]; then echo "PASS: idempotent"; else echo "FAIL: not idempotent"; fi
exit "$STATUS"
