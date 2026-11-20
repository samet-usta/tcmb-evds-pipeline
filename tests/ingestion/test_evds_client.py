"""Tests for evds_client. get_with_retry is mocked; no network."""
from datetime import date
from unittest.mock import patch

import pytest

from src.ingestion import evds_client
from src.ingestion.evds_client import (
    EvdsNoDataError,
    EvdsRequestError,
    EvdsResponseError,
    build_url,
    fetch_group,
    parse_response,
)
from src.ingestion.http_utils import HttpRequestError

GET_PATH = "src.ingestion.evds_client.get_with_retry"
START = date(2026, 11, 16)
END = date(2026, 11, 20)


def test_build_url_adds_slash_and_formats_dates():
    url = build_url("https://evds.test/api", ["A", "B"], START, END)

    expected = "https://evds.test/api/series=A-B&startDate=16-11-2026&endDate=20-11-2026&type=json"
    assert url == expected


def test_fetch_group_success(series_config_path, make_response):
    items = [{"Tarih": "16-11-2026", "TP_DK_USD_A_YTL": "50.1"}]
    response = make_response(200, json_data={"items": items})

    with patch(GET_PATH, return_value=response) as mock_get:
        result = fetch_group("fx_rates", START, END, series_config_path)

    assert result["source"] == "evds"
    assert result["group"] == "fx_rates"
    assert len(result["series_codes"]) == 3
    assert result["start_date"] == "2026-11-16"
    assert result["end_date"] == "2026-11-20"
    assert result["items"] == items
    # API key goes in the header, not in the URL.
    assert mock_get.call_args.kwargs["headers"] == {"key": "test-secret-key"}
    assert "test-secret-key" not in mock_get.call_args.args[0]


def test_start_after_end_raises_value_error(series_config_path):
    with patch(GET_PATH) as mock_get:
        with pytest.raises(ValueError):
            fetch_group("fx_rates", END, START, series_config_path)

    mock_get.assert_not_called()


def test_unknown_group_raises_value_error(series_config_path):
    with patch(GET_PATH) as mock_get:
        with pytest.raises(ValueError):
            fetch_group("no_such_group", START, END, series_config_path)

    mock_get.assert_not_called()


def test_http_error_becomes_evds_request_error(series_config_path):
    http_error = HttpRequestError("HTTP 401: Invalid API Key", status_code=401)

    with patch(GET_PATH, side_effect=http_error):
        with pytest.raises(EvdsRequestError) as error_info:
            fetch_group("fx_rates", START, END, series_config_path)

    assert "401" in str(error_info.value)
    assert error_info.value.__cause__ is http_error


def test_non_json_response_raises_response_error(series_config_path, make_response):
    html_response = make_response(200, json_data=None, headers={"Content-Type": "text/html"})

    with patch(GET_PATH, return_value=html_response):
        with pytest.raises(EvdsResponseError, match="not JSON"):
            fetch_group("fx_rates", START, END, series_config_path)


@pytest.mark.parametrize(
    "payload, message",
    [
        ([], "not a JSON object"),
        ({"data": []}, "no 'items' key"),
        ({"items": "text"}, "not a list"),
    ],
)
def test_parse_response_bad_format(payload, message):
    with pytest.raises(EvdsResponseError, match=message):
        parse_response(payload)


def test_parse_response_empty_items_raises_no_data():
    with pytest.raises(EvdsNoDataError):
        parse_response({"items": []})


def test_parse_response_null_values_are_not_an_error():
    # Weekend: EVDS returns rows with null values, not an empty list.
    items = [{"Tarih": "15-11-2026", "TP_DK_USD_A_YTL": None}]

    result = parse_response({"items": items})

    assert result == items


def test_exception_classes_share_base():
    assert issubclass(EvdsRequestError, evds_client.EvdsError)
    assert issubclass(EvdsResponseError, evds_client.EvdsError)
    assert issubclass(EvdsNoDataError, evds_client.EvdsError)
