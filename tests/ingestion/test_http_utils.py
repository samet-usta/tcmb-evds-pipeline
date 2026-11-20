"""Tests for http_utils.get_with_retry. requests.get and time.sleep are mocked."""
from unittest.mock import call, patch

import pytest
import requests

from src.ingestion.http_utils import HttpRequestError, get_with_retry, is_retryable_status

URL = "https://example.test/data"
GET_PATH = "src.ingestion.http_utils.requests.get"
SLEEP_PATH = "src.ingestion.http_utils.time.sleep"


def test_success_returns_response(make_response):
    ok_response = make_response(200, json_data={"items": []})
    with patch(GET_PATH, return_value=ok_response) as mock_get, patch(SLEEP_PATH) as mock_sleep:
        result = get_with_retry(URL)

    assert result is ok_response
    assert mock_get.call_count == 1
    mock_sleep.assert_not_called()


def test_retry_on_5xx_then_success(make_response):
    responses = [make_response(500), make_response(500), make_response(200)]
    with patch(GET_PATH, side_effect=responses) as mock_get, patch(SLEEP_PATH) as mock_sleep:
        result = get_with_retry(URL)

    assert result.status_code == 200
    assert mock_get.call_count == 3
    # Backoff: 2 ** attempt
    assert mock_sleep.call_args_list == [call(2), call(4)]


def test_4xx_no_retry(make_response):
    with patch(GET_PATH, return_value=make_response(404, text="Not Found")) as mock_get, \
            patch(SLEEP_PATH) as mock_sleep:
        with pytest.raises(HttpRequestError) as error_info:
            get_with_retry(URL)

    assert error_info.value.status_code == 404
    assert mock_get.call_count == 1
    mock_sleep.assert_not_called()


def test_retry_after_header_is_used(make_response):
    responses = [make_response(429, headers={"Retry-After": "7"}), make_response(200)]
    with patch(GET_PATH, side_effect=responses), patch(SLEEP_PATH) as mock_sleep:
        get_with_retry(URL)

    mock_sleep.assert_called_once_with(7)


def test_timeout_all_attempts_fail():
    with patch(GET_PATH, side_effect=requests.Timeout("slow")) as mock_get, \
            patch(SLEEP_PATH) as mock_sleep:
        with pytest.raises(HttpRequestError) as error_info:
            get_with_retry(URL)

    assert error_info.value.status_code is None
    assert "Timeout (attempt 3)" in str(error_info.value)
    assert mock_get.call_count == 3
    # No sleep after the last attempt.
    assert mock_sleep.call_count == 2


def test_5xx_all_attempts_fail(make_response):
    with patch(GET_PATH, return_value=make_response(503)) as mock_get, patch(SLEEP_PATH):
        with pytest.raises(HttpRequestError) as error_info:
            get_with_retry(URL)

    assert error_info.value.status_code == 503
    assert mock_get.call_count == 3


def test_api_key_not_in_error_message(make_response):
    headers = {"key": "test-secret-key"}
    with patch(GET_PATH, return_value=make_response(401, text="Invalid API Key")), \
            patch(SLEEP_PATH):
        with pytest.raises(HttpRequestError) as error_info:
            get_with_retry(URL, headers=headers)

    assert "test-secret-key" not in str(error_info.value)


# parametrize: the same test runs once for each value pair.
@pytest.mark.parametrize(
    "status_code, expected",
    [(429, True), (500, True), (503, True), (400, False), (401, False), (404, False)],
)
def test_is_retryable_status(status_code, expected):
    assert is_retryable_status(status_code) == expected
