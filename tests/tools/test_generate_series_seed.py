"""Unit tests for the series seed generator."""

import pytest

from src.tools.generate_series_seed import COLUMNS, build_rows


def make_config():
    """Return a small config: a rate group with fallback and a volume group."""
    config = {
        "series_groups": [
            {
                "group": "fx_rates",
                "frequency": "business_daily",
                "unit": "TRY",
                "measure_type": "rate",
                "max_fill_days": 10,
                "available_from": "1950-01-02",
                "series": [
                    {
                        "code": "TP.DK.USD.A.YTL",
                        "name": "USD buying rate",
                        "fallback": {
                            "source": "frankfurter",
                            "base": "USD",
                            "quote": "TRY",
                        },
                    },
                    {"code": "TP.TEST.NOFB", "name": "Series without fallback"},
                ],
            },
            {
                "group": "loan_volumes",
                "frequency": "weekly_friday",
                "unit": "TRY_thousand",
                "measure_type": "volume",
                "max_fill_days": None,
                "available_from": "2024-06-28",
                "series": [
                    {"code": "TP.HPBITABLO6.1", "name": "Loan volume"},
                ],
            },
        ]
    }
    return config


def get_rows_by_code(config):
    rows = build_rows(config)
    rows_by_code = {}
    for row in rows:
        rows_by_code[row["series_code"]] = row
    return rows_by_code


def test_one_row_per_series():
    rows = build_rows(make_config())
    assert len(rows) == 3


def test_row_keys_match_columns():
    rows = build_rows(make_config())
    for row in rows:
        assert list(row.keys()) == COLUMNS


def test_series_with_fallback():
    row = get_rows_by_code(make_config())["TP.DK.USD.A.YTL"]
    assert row["fallback_source"] == "frankfurter"
    assert row["fallback_base_currency"] == "USD"
    assert row["fallback_quote_currency"] == "TRY"


def test_series_without_fallback():
    row = get_rows_by_code(make_config())["TP.TEST.NOFB"]
    assert row["fallback_source"] is None
    assert row["fallback_base_currency"] is None
    assert row["fallback_quote_currency"] is None


def test_group_fields_copied_to_series():
    rows_by_code = get_rows_by_code(make_config())
    rate_row = rows_by_code["TP.DK.USD.A.YTL"]
    volume_row = rows_by_code["TP.HPBITABLO6.1"]
    assert rate_row["measure_type"] == "rate"
    assert rate_row["max_fill_days"] == 10
    assert volume_row["measure_type"] == "volume"
    assert volume_row["max_fill_days"] is None


def test_duplicate_series_code_raises():
    config = make_config()
    duplicate = {"code": "TP.DK.USD.A.YTL", "name": "Duplicate"}
    config["series_groups"][1]["series"].append(duplicate)
    with pytest.raises(ValueError, match="Duplicate series code"):
        build_rows(config)


def test_missing_measure_type_raises():
    config = make_config()
    del config["series_groups"][0]["measure_type"]
    with pytest.raises(KeyError):
        build_rows(config)
