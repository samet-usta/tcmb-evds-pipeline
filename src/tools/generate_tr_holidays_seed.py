"""Generate the dbt seed file with Turkish public holidays."""

import csv
import os
from datetime import date
from pathlib import Path

import holidays

DEFAULT_OUTPUT_PATH = "/opt/pipeline/dbt/seeds/tr_holidays.csv"
START_YEAR = 2000

COLUMNS = ["holiday_date", "holiday_name"]


def build_rows(start_year, end_year):
    """Return one row per holiday date, from start_year to end_year (inclusive)."""
    years = range(start_year, end_year + 1)
    tr_holidays = holidays.country_holidays("TR", years=years)

    rows = []
    for holiday_date, holiday_name in sorted(tr_holidays.items()):
        row = {
            "holiday_date": holiday_date.isoformat(),
            "holiday_name": holiday_name,
        }
        rows.append(row)

    return rows


def write_rows(rows, output_path):
    """Write rows to a CSV file with LF line endings."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    output_path = os.environ.get("HOLIDAYS_SEED_PATH", DEFAULT_OUTPUT_PATH)

    # Gelecek yıl dahil: dim_date bugün + 1 yıl aralığını kapsar
    end_year = date.today().year + 1

    rows = build_rows(START_YEAR, end_year)
    write_rows(rows, output_path)
    print(f"Wrote {len(rows)} holidays ({START_YEAR}-{end_year}) to {output_path}")


if __name__ == "__main__":
    main()
