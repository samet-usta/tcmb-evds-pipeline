"""Fetch a series group from EVDS, with Frankfurter fallback for supported groups."""
import logging

from src.ingestion import evds_client
from src.ingestion import frankfurter_client
from src.ingestion.series_config import get_group_config

logger = logging.getLogger(__name__)


class IngestionError(Exception):
    """Raised when EVDS and the fallback source both fail."""


def has_fallback(group_config):
    """Return True if at least one series in the group has a fallback source."""
    for series in group_config["series"]:
        if series.get("fallback"):
            return True
    return False


def fetch_with_fallback(group_name, start_date, end_date, config_path=None):
    """Fetch a group from EVDS. On request or response error, use the fallback source."""
    try:
        result = evds_client.fetch_group(group_name, start_date, end_date, config_path)
        result["fallback_reason"] = None
        return result
    # EvdsNoDataError ve ValueError burada yakalanmaz: fallback tetiklemez
    except (evds_client.EvdsRequestError, evds_client.EvdsResponseError) as evds_error:
        group_config = get_group_config(group_name, config_path)
        if not has_fallback(group_config):
            raise

        fallback_reason = f"{type(evds_error).__name__}: {evds_error}"
        logger.warning(
            "EVDS failed for group %s, using Frankfurter. Reason: %s",
            group_name,
            fallback_reason,
        )

        try:
            result = frankfurter_client.fetch_group(group_name, start_date, end_date, config_path)
        except frankfurter_client.FrankfurterError as frankfurter_error:
            frankfurter_reason = f"{type(frankfurter_error).__name__}: {frankfurter_error}"
            message = (
                f"Both sources failed for group {group_name}. "
                f"EVDS: {fallback_reason}. Frankfurter: {frankfurter_reason}"
            )
            # from: traceback iki hatayı da gösterir
            raise IngestionError(message) from frankfurter_error

        result["fallback_reason"] = fallback_reason
        return result
