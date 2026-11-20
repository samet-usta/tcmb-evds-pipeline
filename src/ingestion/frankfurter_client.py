"""Frankfurter (ECB) client. Fallback source for the fx_rates group."""
import logging
import os

from src.ingestion.http_utils import HttpRequestError, get_with_retry
from src.ingestion.series_config import get_group_config

logger = logging.getLogger(__name__)

PROVIDER = "ecb"


class FrankfurterError(Exception):
    """Base class for Frankfurter client errors."""


class FrankfurterRequestError(FrankfurterError):
    """Timeout, connection error or HTTP error."""


class FrankfurterResponseError(FrankfurterError):
    """Response is not JSON or not in the expected format."""


class FrankfurterNoDataError(FrankfurterError):
    """No rate in the date range (weekend or ECB holiday)."""


def get_fallback_pairs(group_config):
    """Return EVDS series codes and unique (base, quote) pairs with Frankfurter fallback."""
    series_codes = []
    pairs = []
    for serie in group_config["series"]:
        fallback = serie.get("fallback")
        if fallback is None:
            continue
        if fallback["source"] != "frankfurter":
            continue
        series_codes.append(serie["code"])
        pair = (fallback["base"], fallback["quote"])
        # A and S series use the same pair. Send one request per pair.
        if pair not in pairs:
            pairs.append(pair)
    return series_codes, pairs


def build_url(base_url):
    """Return the ECB rates endpoint."""
    return f"{base_url.rstrip('/')}/providers/{PROVIDER}/rates"


def build_params(base, quote, start_date, end_date):
    """Return query parameters. Frankfurter uses YYYY-MM-DD."""
    params = {
        "from": start_date.isoformat(),
        "to": end_date.isoformat(),
        "base": base,
        "quotes": quote,
    }
    return params


def fetch(url, params):
    """Send the request and return the JSON payload. HTTP 404 means no data."""
    try:
        response = get_with_retry(url, params=params)
    except HttpRequestError as error:
        if error.status_code == 404:
            return []
        raise FrankfurterRequestError(str(error)) from error

    try:
        payload = response.json()
    except ValueError as error:
        raise FrankfurterResponseError("Response is not JSON") from error
    return payload


def parse_response(payload, start_date, end_date):
    """Check the format. Keep only items inside the date range."""
    if not isinstance(payload, list):
        raise FrankfurterResponseError("Response is not a list")

    start_text = start_date.isoformat()
    end_text = end_date.isoformat()
    items = []
    for item in payload:
        if not isinstance(item, dict) or "date" not in item:
            raise FrankfurterResponseError(f"Unexpected item: {item}")
        # If the range has no data (ex: weekend), the API returns the last earlier rate.
        if item["date"] < start_text:
            continue
        if item["date"] > end_text:
            continue
        items.append(item)
    return items


def fetch_group(group_name, start_date, end_date, config_path=None):
    """Fetch raw ECB rates for one series group and one date range."""
    if start_date > end_date:
        raise ValueError("start_date must be before or equal to end_date")

    group_config = get_group_config(group_name, config_path)
    series_codes, pairs = get_fallback_pairs(group_config)
    if not pairs:
        raise ValueError(f"Group has no Frankfurter fallback: {group_name}")

    url = build_url(os.environ["FRANKFURTER_BASE_URL"])
    items = []
    for base, quote in pairs:
        params = build_params(base, quote, start_date, end_date)
        logger.info("Fetching Frankfurter %s/%s from %s to %s", base, quote, start_date, end_date)
        payload = fetch(url, params)
        pair_items = parse_response(payload, start_date, end_date)
        items.extend(pair_items)

    if not items:
        raise FrankfurterNoDataError(f"No data for {group_name} from {start_date} to {end_date}")

    result = {
        "source": "frankfurter",
        "group": group_name,
        "series_codes": series_codes,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "items": items,
    }
    return result
