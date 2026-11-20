"""EVDS 3 API client: reads the series config and fetches raw observations."""

import logging
import os
import time

import requests
import yaml

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = (5, 30)  # (connect, read) seconds
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 2
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class EvdsError(Exception):
    """Base error for the EVDS client."""


class EvdsRequestError(EvdsError):
    """Network, timeout or HTTP error after all retries."""


class EvdsResponseError(EvdsError):
    """Response is not JSON or has an unexpected format."""


class EvdsNoDataError(EvdsError):
    """Response is valid but has no items for the date range."""


def load_series_config(config_path=None):
    """Read series.yaml and return the groups as a dict keyed by group name."""
    if config_path is None:
        config_path = os.environ["SERIES_CONFIG_PATH"]
    with open(config_path, encoding="utf-8") as file:
        config = yaml.safe_load(file)
    groups = {}
    for group in config["series_groups"]:
        groups[group["group"]] = group
    return groups


def get_series_codes(group_config):
    """Return the series codes of one group as a list."""
    codes = []
    for series in group_config["series"]:
        codes.append(series["code"])
    return codes


def format_evds_date(value):
    """Convert a date to the EVDS format dd-mm-yyyy."""
    return value.strftime("%d-%m-%Y")


def build_url(base_url, series_codes, start_date, end_date):
    """Build the request URL. EVDS 3 takes the parameters without '?'."""
    series_param = "-".join(series_codes)
    start_param = format_evds_date(start_date)
    end_param = format_evds_date(end_date)
    if not base_url.endswith("/"):
        base_url = base_url + "/"
    query = f"series={series_param}&startDate={start_param}&endDate={end_param}&type=json"
    return base_url + query


def read_json(response):
    """Return the response body as JSON or raise EvdsResponseError."""
    try:
        return response.json()
    except ValueError:
        content_type = response.headers.get("Content-Type", "")
        raise EvdsResponseError(f"Response is not JSON (Content-Type: {content_type})")


def fetch(url, api_key):
    """GET the URL with timeout, retry and backoff. Return the JSON payload."""
    # Key sadece header'da. Log ve exception mesajına header girmez.
    headers = {"key": api_key}
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            status_code = response.status_code
        except (requests.Timeout, requests.ConnectionError) as error:
            status_code = None
            last_error = type(error).__name__

        if status_code == 200:
            return read_json(response)

        if status_code is not None:
            last_error = f"HTTP {status_code}"
            # 429 ve 5xx dışındaki hata kalıcıdır (ör. 401 yanlış key). Retry yapılmaz.
            if status_code not in RETRY_STATUS_CODES:
                raise EvdsRequestError(f"EVDS request failed: {last_error}")

        logger.warning("EVDS attempt %s/%s failed: %s", attempt, MAX_ATTEMPTS, last_error)
        if attempt < MAX_ATTEMPTS:
            wait_seconds = BACKOFF_SECONDS ** attempt
            time.sleep(wait_seconds)

    raise EvdsRequestError(f"EVDS request failed after {MAX_ATTEMPTS} attempts: {last_error}")


def parse_response(payload):
    """Check the payload format and return the raw items list."""
    if not isinstance(payload, dict):
        raise EvdsResponseError("Response is not a JSON object")
    if "items" not in payload:
        raise EvdsResponseError("Response has no 'items' key")
    items = payload["items"]
    if not isinstance(items, list):
        raise EvdsResponseError("'items' is not a list")
    if len(items) == 0:
        raise EvdsNoDataError("No items for the date range")
    return items


def fetch_group(group_name, start_date, end_date, config_path=None):
    """Fetch raw items for one series group and one date range."""
    if start_date > end_date:
        raise ValueError("start_date must be before or equal to end_date")

    groups = load_series_config(config_path)
    if group_name not in groups:
        raise ValueError(f"Unknown series group: {group_name}")

    group_config = groups[group_name]
    series_codes = get_series_codes(group_config)
    base_url = os.environ["EVDS_BASE_URL"]
    api_key = os.environ["EVDS_API_KEY"]
    url = build_url(base_url, series_codes, start_date, end_date)

    logger.info("Fetching EVDS group=%s from %s to %s", group_name, start_date, end_date)
    payload = fetch(url, api_key)
    items = parse_response(payload)

    result = {
        "source": "evds",
        "group": group_name,
        "series_codes": series_codes,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "items": items,
    }
    return result
