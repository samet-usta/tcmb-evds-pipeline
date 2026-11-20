"""Tests for series_config. Uses the temp series.yaml from conftest."""
import pytest

from src.ingestion.series_config import get_group_config, load_series_config


def test_load_returns_groups_by_name(series_config_path):
    groups = load_series_config(series_config_path)

    assert set(groups) == {"fx_rates", "deposit_rates"}


def test_get_group_config(series_config_path):
    group_config = get_group_config("fx_rates", series_config_path)

    assert group_config["frequency"] == "business_daily"
    assert len(group_config["series"]) == 3


def test_unknown_group_raises_value_error(series_config_path):
    with pytest.raises(ValueError, match="Unknown series group"):
        get_group_config("no_such_group", series_config_path)


def test_path_from_env_var(series_config_path, monkeypatch):
    monkeypatch.setenv("SERIES_CONFIG_PATH", series_config_path)

    groups = load_series_config()

    assert "deposit_rates" in groups
