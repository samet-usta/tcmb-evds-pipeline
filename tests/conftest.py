"""Shared pytest fixtures. No test sends a real network request."""
from unittest.mock import MagicMock

import pytest

TEST_SERIES_YAML = """
version: 1
series_groups:
  - group: fx_rates
    datagroup: bie_dkdovytl
    frequency: business_daily
    unit: TRY
    available_from: "2020-01-01"
    series:
      - code: TP.DK.USD.A.YTL
        name: USD buying
        fallback:
          source: frankfurter
          base: USD
          quote: TRY
      - code: TP.DK.USD.S.YTL
        name: USD selling
        fallback:
          source: frankfurter
          base: USD
          quote: TRY
      - code: TP.DK.EUR.A.YTL
        name: EUR buying
        fallback:
          source: frankfurter
          base: EUR
          quote: TRY
  - group: deposit_rates
    datagroup: bie_mt100h
    frequency: weekly_friday
    unit: percent
    available_from: "2020-01-01"
    series:
      - code: TP.TRY.MT06
        name: TRY deposit rate
"""


@pytest.fixture(autouse=True)
def env_vars(monkeypatch):
    """Set test env vars. The real API key is never used."""
    monkeypatch.setenv("EVDS_BASE_URL", "https://evds.test/api/")
    monkeypatch.setenv("EVDS_API_KEY", "test-secret-key")
    monkeypatch.setenv("FRANKFURTER_BASE_URL", "https://frankfurter.test/v2")


@pytest.fixture
def series_config_path(tmp_path):
    """Write a small series.yaml to a temp folder and return its path."""
    config_file = tmp_path / "series.yaml"
    config_file.write_text(TEST_SERIES_YAML, encoding="utf-8")
    return str(config_file)


@pytest.fixture
def make_response():
    """Return a function that builds a fake requests.Response."""

    def build(status_code=200, json_data=None, text="", headers=None):
        response = MagicMock()
        response.status_code = status_code
        response.text = text
        if headers is None:
            headers = {}
        response.headers = headers
        # json_data None: body is not JSON, like an HTML error page.
        if json_data is None:
            response.json.side_effect = ValueError("not JSON")
        else:
            response.json.return_value = json_data
        return response

    return build
