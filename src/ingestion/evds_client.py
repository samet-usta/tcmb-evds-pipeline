"""EVDS 3 API client: reads the series config and fetches raw observations."""

import logging
import os

from src.ingestion.http_utils import HttpRequestError, get_with_retry
from src.ingestion.series_config import get_group_config

logger = logging.getLogger(__name__)


class EvdsError(Exception):
    """Base error for the EVDS client."""


class EvdsRequestError(EvdsError):
    """Network, timeout or HTTP error after all retries."""


class EvdsResponseError(EvdsError):
    """Response is not JSON or has an unexpected format."""


class EvdsNoDataError(EvdsError):
    """Response is valid but has no items for the date range."""


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
    try:
        response = get_with_retry(url, headers=headers)
    except HttpRequestError as error:
        raise EvdsRequestError(f"EVDS request failed: {error}") from error
    return read_json(response)


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

    group_config = get_group_config(group_name, config_path)
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
