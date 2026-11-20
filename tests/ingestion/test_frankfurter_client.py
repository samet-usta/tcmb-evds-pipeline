"""Tests for frankfurter_client. get_with_retry is mocked; no network."""
from datetime import date
from unittest.mock import patch

import pytest

from src.ingestion.frankfurter_client import (
    FrankfurterNoDataError,
    FrankfurterRequestError,
    FrankfurterResponseError,
    build_url,
    fetch_group,
    get_fallback_pairs,
    parse_response,
)
from src.ingestion.http_utils import HttpRequestError
from src.ingestion.series_config import get_group_config

GET_PATH = "src.ingestion.frankfurter_client.get_with_retry"
START = date(2026, 11, 16)
END = date(2026, 11, 20)


def rate_item(day, base):
    """Return one raw Frankfurter item."""
    return {"date": day, "base": base, "quote": "TRY", "rate": 50.0}


def test_get_fallback_pairs(series_config_path):
    group_config = get_group_config("fx_rates", series_config_path)

    series_codes, pairs = get_fallback_pairs(group_config)

    assert len(series_codes) == 3
    # USD A and S use the same pair: one request only.
    assert pairs == [("USD", "TRY"), ("EUR", "TRY")]


def test_build_url_strips_slash():
    assert build_url("https://frankfurter.test/v2/") == "https://frankfurter.test/v2/providers/ecb/rates"


def test_fetch_group_success(series_config_path, make_response):
    usd_response = make_response(200, json_data=[rate_item("2026-11-16", "USD"), rate_item("2026-11-17", "USD")])
    eur_response = make_response(200, json_data=[rate_item("2026-11-16", "EUR")])

    with patch(GET_PATH, side_effect=[usd_response, eur_response]) as mock_get:
        result = fetch_group("fx_rates", START, END, series_config_path)

    assert result["source"] == "frankfurter"
    assert len(result["series_codes"]) == 3
    assert len(result["items"]) == 3
    assert mock_get.call_count == 2
    first_params = mock_get.call_args_list[0].kwargs["params"]
    assert first_params == {"from": "2026-11-16", "to": "2026-11-20", "base": "USD", "quotes": "TRY"}


def test_items_outside_range_are_removed():
    payload = [rate_item("2026-11-13", "USD"), rate_item("2026-11-16", "USD"), rate_item("2026-11-21", "USD")]

    items = parse_response(payload, START, END)

    assert len(items) == 1
    assert items[0]["date"] == "2026-11-16"


def test_weekend_returns_no_data(series_config_path, make_response):
    # No data on 14-15.11: the API returns Friday 13.11. The client removes it.
    friday_usd = make_response(200, json_data=[rate_item("2026-11-13", "USD")])
    friday_eur = make_response(200, json_data=[rate_item("2026-11-13", "EUR")])

    with patch(GET_PATH, side_effect=[friday_usd, friday_eur]):
        with pytest.raises(FrankfurterNoDataError):
            fetch_group("fx_rates", date(2026, 11, 14), date(2026, 11, 15), series_config_path)


def test_404_for_one_pair_is_empty(series_config_path, make_response):
    not_found = HttpRequestError("HTTP 404: not found", status_code=404)
    eur_response = make_response(200, json_data=[rate_item("2026-11-16", "EUR")])

    with patch(GET_PATH, side_effect=[not_found, eur_response]):
        result = fetch_group("fx_rates", START, END, series_config_path)

    assert len(result["items"]) == 1
    assert result["items"][0]["base"] == "EUR"


def test_404_for_all_pairs_raises_no_data(series_config_path):
    not_found = HttpRequestError("HTTP 404: not found", status_code=404)

    with patch(GET_PATH, side_effect=not_found):
        with pytest.raises(FrankfurterNoDataError):
            fetch_group("fx_rates", START, END, series_config_path)


def test_http_error_becomes_request_error(series_config_path):
    server_error = HttpRequestError("HTTP 503: unavailable", status_code=503)

    with patch(GET_PATH, side_effect=server_error):
        with pytest.raises(FrankfurterRequestError) as error_info:
            fetch_group("fx_rates", START, END, series_config_path)

    assert error_info.value.__cause__ is server_error


def test_non_json_raises_response_error(series_config_path, make_response):
    with patch(GET_PATH, return_value=make_response(200, json_data=None)):
        with pytest.raises(FrankfurterResponseError, match="not JSON"):
            fetch_group("fx_rates", START, END, series_config_path)


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"rates": []}, "not a list"),
        ([{"base": "USD"}], "Unexpected item"),
    ],
)
def test_parse_response_bad_format(payload, message):
    with pytest.raises(FrankfurterResponseError, match=message):
        parse_response(payload, START, END)


def test_group_without_fallback_raises_value_error(series_config_path):
    with patch(GET_PATH) as mock_get:
        with pytest.raises(ValueError, match="no Frankfurter fallback"):
            fetch_group("deposit_rates", START, END, series_config_path)

    mock_get.assert_not_called()


def test_start_after_end_raises_value_error(series_config_path):
    with patch(GET_PATH) as mock_get:
        with pytest.raises(ValueError):
            fetch_group("fx_rates", END, START, series_config_path)

    mock_get.assert_not_called()
