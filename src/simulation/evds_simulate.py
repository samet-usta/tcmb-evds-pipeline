"""Simulation loop: slice, landing, load, dbt incremental, dbt full refresh, compare."""
import argparse
import csv
import subprocess
import time
from datetime import date, timedelta

import boto3

from src.landing.s3_writer import write_landing
from src.load.postgres_loader import get_connection, load_landing
from src.simulation.evds_compare import TABLES, compare_marts
from src.simulation.evds_slicer import PUBLICATION_LAG_DAYS, read_slice

DBT_BIN = "/opt/dbt-venv/bin/dbt"
DBT_DIR = "/opt/pipeline/dbt"
SIM_LOG_PATH = "data/sim_output/sim_log.csv"


def build_log_columns():
    """Return the CSV header. One row per dt."""
    columns = ["dt", "status", "sec_load", "sec_dev", "sec_ref"]
    for table in TABLES:
        columns.append(f"{table}_dev")
        columns.append(f"{table}_ref")
        columns.append(f"{table}_diff")
    return columns


LOG_COLUMNS = build_log_columns()


def run_dbt(args):
    """Run one dbt command. Return True if the exit code is 0."""
    command = [DBT_BIN] + args
    result = subprocess.run(command, cwd=DBT_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        # Hata olunca dbt çıktısını göster
        print(result.stdout)
        print(result.stderr)
    return result.returncode == 0


def load_one_day(dt, s3_client, conn):
    """Slice, write and load all groups for one dt."""
    for group_name in PUBLICATION_LAG_DAYS:
        envelope = read_slice(group_name, dt)
        write_landing(envelope, dt, s3_client)
        load_landing(group_name, dt, s3_client, conn)


def run_one_day(dt, s3_client):
    """Run all steps for one dt. Return one log row (dict)."""
    row = {"dt": dt.isoformat(), "status": ""}
    as_of_json = '{"as_of_date": "' + dt.isoformat() + '"}'

    start = time.time()
    conn = get_connection()
    try:
        load_one_day(dt, s3_client, conn)
    finally:
        conn.close()
    row["sec_load"] = round(time.time() - start, 1)

    start = time.time()
    ok_dev = run_dbt(["run", "-t", "dev", "--vars", as_of_json])
    row["sec_dev"] = round(time.time() - start, 1)
    if not ok_dev:
        row["status"] = "dbt_dev_failed"
        return row

    start = time.time()
    ok_ref = run_dbt(["run", "--full-refresh", "-t", "full_refresh_check", "--vars", as_of_json])
    row["sec_ref"] = round(time.time() - start, 1)
    if not ok_ref:
        row["status"] = "dbt_ref_failed"
        return row

    conn = get_connection()
    try:
        results = compare_marts(conn)
    finally:
        conn.close()

    all_ok = True
    for result in results:
        table = result["table"]
        row[f"{table}_dev"] = result["dev_count"]
        row[f"{table}_ref"] = result["ref_count"]
        row[f"{table}_diff"] = result["dev_minus_ref"] + result["ref_minus_dev"]
        if not result["ok"]:
            all_ok = False

    row["status"] = "ok" if all_ok else "diff"
    return row


def run_simulation(start_dt, end_dt, log_path=SIM_LOG_PATH):
    """Run the loop from start_dt to end_dt. Stop at the first problem."""
    s3_client = boto3.client("s3")
    dt = start_dt

    with open(log_path, "w", newline="", encoding="utf-8") as log_file:
        writer = csv.DictWriter(log_file, fieldnames=LOG_COLUMNS)
        writer.writeheader()
        while dt <= end_dt:
            row = run_one_day(dt, s3_client)
            writer.writerow(row)
            log_file.flush()
            print(row)
            if row["status"] != "ok":
                print("STOP:", dt, row["status"])
                return 1
            dt = dt + timedelta(days=1)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Run the EVDS simulation loop.")
    parser.add_argument("--start", required=True, help="First dt (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="Last dt (YYYY-MM-DD)")
    args = parser.parse_args()
    start_dt = date.fromisoformat(args.start)
    end_dt = date.fromisoformat(args.end)
    return run_simulation(start_dt, end_dt)


if __name__ == "__main__":
    raise SystemExit(main())
