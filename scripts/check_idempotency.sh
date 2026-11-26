#!/usr/bin/env bash
# Idempotency check for one ds: run the DAG twice, compare
# the raw table, the S3 landing files and the dbt marts tables.
# Usage: bash scripts/check_idempotency.sh YYYY-MM-DD
set -euo pipefail

DS="${1:?usage: bash scripts/check_idempotency.sh YYYY-MM-DD}"
WORK_DIR="$(mktemp -d)"
PSQL='psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A'
MARTS_TABLES="dim_date dim_series fct_rates fct_rates_daily fct_volumes"

run_dag() {
  MSYS_NO_PATHCONV=1 docker compose exec -w /opt/pipeline airflow-scheduler \
    airflow dags test evds_daily "$DS" > "$WORK_DIR/$1.log" 2>&1 || true
  grep -o 'new_state=[a-z_]*' "$WORK_DIR/$1.log" | sort | uniq -c
  # Since A6-S6 the DAG must pass. A failed task fails the check.
  if grep -q 'new_state=failed' "$WORK_DIR/$1.log"; then
    echo "FAIL: a task failed in $1, see $WORK_DIR/$1.log"
    exit 1
  fi
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
  # dbt marts: row count and md5 of all rows (sorted) for each table.
  for table in $MARTS_TABLES; do
    docker compose exec -T warehouse sh -c "$PSQL" <<EOF
select '$table', count(*), md5(coalesce(string_agg(row_text, '|' order by row_text), ''))
from (select (to_jsonb(t) - 'ingested_at' - 'dbt_updated_at')::text as row_text from marts.$table t) s;
EOF
  done > "$WORK_DIR/$1.marts"
}

echo "ds=$DS work_dir=$WORK_DIR"
echo "--- run 1"; run_dag run1; snapshot snap1
echo "--- run 2"; run_dag run2; snapshot snap2

STATUS=0
[ -s "$WORK_DIR/snap1.s3" ] || { echo "FAIL: S3 snapshot is empty"; STATUS=1; }
[ -s "$WORK_DIR/snap1.marts" ] || { echo "FAIL: marts snapshot is empty"; STATUS=1; }
diff "$WORK_DIR/snap1.raw" "$WORK_DIR/snap2.raw" || STATUS=1
diff "$WORK_DIR/snap1.s3" "$WORK_DIR/snap2.s3" || STATUS=1
diff "$WORK_DIR/snap1.marts" "$WORK_DIR/snap2.marts" || STATUS=1
if cmp -s "$WORK_DIR/snap1.ts" "$WORK_DIR/snap2.ts"; then
  echo "FAIL: ingested_at did not change, run 2 wrote nothing"
  STATUS=1
fi

if [ "$STATUS" -eq 0 ]; then echo "PASS: idempotent"; else echo "FAIL: not idempotent"; fi
exit "$STATUS"
