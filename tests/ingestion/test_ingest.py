"""Tests for ingest.fetch_with_fallback. Both clients are mocked."""
import logging
from datetime import date
from unittest.mock import patch

import pytest

from src.ingestion.evds_client import EvdsNoDataError, EvdsRequestError, EvdsResponseError
from src.ingestion.frankfurter_client import FrankfurterNoDataError
from src.ingestion.ingest import IngestionError, fetch_with_fallback, has_fallback
from src.ingestion.series_config import get_group_config

EVDS_FETCH = "src.ingestion.ingest.evds_client.fetch_group"
FRANKFURTER_FETCH = "src.ingestion.ingest.frankfurter_client.fetch_group"
START = date(2026, 11, 16)
END = date(2026, 11, 20)


def make_envelope(source):
    """Return a small client output dict."""
    return {"source": source, "group": "fx_rates", "items": [{"x": 1}]}


def test_has_fallback(series_config_path):
    fx_config = get_group_config("fx_rates", series_config_path)
    deposit_config = get_group_config("deposit_rates", series_config_path)

    assert has_fallback(fx_config) is True
    assert has_fallback(deposit_config) is False


def test_evds_success_no_fallback(series_config_path):
    with patch(EVDS_FETCH, return_value=make_envelope("evds")), \
            patch(FRANKFURTER_FETCH) as mock_frankfurter:
        result = fetch_with_fallback("fx_rates", START, END, series_config_path)

    assert result["source"] == "evds"
    assert result["fallback_reason"] is None
    mock_frankfurter.assert_not_called()


@pytest.mark.parametrize("evds_error_class", [EvdsRequestError, EvdsResponseError])
def test_evds_error_uses_frankfurter(series_config_path, evds_error_class, caplog):
    evds_error = evds_error_class("EVDS failed")

    with patch(EVDS_FETCH, side_effect=evds_error), \
            patch(FRANKFURTER_FETCH, return_value=make_envelope("frankfurter")):
        with caplog.at_level(logging.WARNING):
            result = fetch_with_fallback("fx_rates", START, END, series_config_path)

    assert result["source"] == "frankfurter"
    assert result["fallback_reason"] == f"{evds_error_class.__name__}: EVDS failed"
    assert "using Frankfurter" in caplog.text


def test_group_without_fallback_raises_evds_error(series_config_path):
    with patch(EVDS_FETCH, side_effect=EvdsRequestError("HTTP 401")), \
            patch(FRANKFURTER_FETCH) as mock_frankfurter:
        with pytest.raises(EvdsRequestError):
            fetch_with_fallback("deposit_rates", START, END, series_config_path)

    mock_frankfurter.assert_not_called()


# NoData and ValueError are not request problems: fallback does not help.
@pytest.mark.parametrize("error", [EvdsNoDataError("no items"), ValueError("bad dates")])
def test_no_fallback_for_no_data_and_value_error(series_config_path, error):
    with patch(EVDS_FETCH, side_effect=error), patch(FRANKFURTER_FETCH) as mock_frankfurter:
        with pytest.raises(type(error)):
            fetch_with_fallback("fx_rates", START, END, series_config_path)

    mock_frankfurter.assert_not_called()


def test_both_sources_fail_raises_ingestion_error(series_config_path):
    frankfurter_error = FrankfurterNoDataError("no data")

    with patch(EVDS_FETCH, side_effect=EvdsRequestError("HTTP 401")), \
            patch(FRANKFURTER_FETCH, side_effect=frankfurter_error):
        with pytest.raises(IngestionError) as error_info:
            fetch_with_fallback("fx_rates", START, END, series_config_path)

    message = str(error_info.value)
    assert "EvdsRequestError: HTTP 401" in message
    assert "FrankfurterNoDataError: no data" in message
    assert error_info.value.__cause__ is frankfurter_error
