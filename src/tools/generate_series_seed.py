"""Generate the dbt seed file for series metadata from config/series.yaml."""

import csv
import os
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = "/opt/pipeline/config/series.yaml"
DEFAULT_OUTPUT_PATH = "/opt/pipeline/dbt/seeds/series_metadata.csv"

COLUMNS = [
    "series_code",
    "series_name",
    "group_name",
    "frequency",
    "unit",
    "available_from",
    "fallback_source",
    "fallback_base_currency",
    "fallback_quote_currency",
]


def load_config(config_path):
    """Read the series config file."""
    with open(config_path, encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def build_rows(config):
    """Return one row per series. Raise ValueError on duplicate series codes."""
    rows = []
    seen_codes = set()

    for group in config["series_groups"]:
        for series in group["series"]:
            code = series["code"]
            if code in seen_codes:
                raise ValueError(f"Duplicate series code in config: {code}")
            seen_codes.add(code)

            # Series without fallback have no fallback field or null
            fallback = series.get("fallback") or {}

            row = {
                "series_code": code,
                "series_name": series["name"],
                "group_name": group["group"],
                "frequency": group["frequency"],
                "unit": group["unit"],
                "available_from": group.get("available_from"),
                "fallback_source": fallback.get("source"),
                "fallback_base_currency": fallback.get("base"),
                "fallback_quote_currency": fallback.get("quote"),
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
    config_path = os.environ.get("SERIES_CONFIG_PATH", DEFAULT_CONFIG_PATH)
    output_path = os.environ.get("SERIES_SEED_PATH", DEFAULT_OUTPUT_PATH)

    config = load_config(config_path)
    rows = build_rows(config)
    write_rows(rows, output_path)
    print(f"Wrote {len(rows)} series to {output_path}")


if __name__ == "__main__":
    main()
