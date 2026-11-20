"""Shared HTTP helper: GET request with timeout and retry."""
import logging
import time

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = (5, 30)
MAX_ATTEMPTS = 3


class HttpRequestError(Exception):
    """Request failed. status_code is None for timeout and connection errors."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def is_retryable_status(status_code):
    """Return True for 429 and 5xx."""
    if status_code == 429:
        return True
    return status_code >= 500


def get_wait_seconds(response, attempt):
    """Use Retry-After header if it is a number, else 2 ** attempt."""
    wait_seconds = 2 ** attempt
    if response is None:
        return wait_seconds
    retry_after = response.headers.get("Retry-After", "")
    if retry_after.isdigit():
        wait_seconds = int(retry_after)
    return wait_seconds


def get_with_retry(url, headers=None, params=None,
                   timeout=DEFAULT_TIMEOUT, max_attempts=MAX_ATTEMPTS):
    """Send GET. Retry on timeout, connection error, 429 and 5xx."""
    # Headers (ör. API key) log ve exception mesajına girmez.
    last_error = None

    for attempt in range(1, max_attempts + 1):
        response = None
        try:
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError) as error:
            last_error = HttpRequestError(f"{type(error).__name__} (attempt {attempt})")
        else:
            status_code = response.status_code
            if status_code < 400:
                return response
            last_error = HttpRequestError(
                f"HTTP {status_code}: {response.text[:200]}", status_code=status_code
            )
            # Other 4xx: the request is wrong. Retry does not help.
            if not is_retryable_status(status_code):
                raise last_error

        logger.warning("HTTP attempt %s/%s failed: %s", attempt, max_attempts, last_error)
        if attempt < max_attempts:
            time.sleep(get_wait_seconds(response, attempt))

    raise last_error
