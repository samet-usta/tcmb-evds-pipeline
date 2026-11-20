"""Read series groups from config/series.yaml."""
import os

import yaml


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


def get_group_config(group_name, config_path=None):
    """Return the config of one group. Raise ValueError if the group is unknown."""
    groups = load_series_config(config_path)
    if group_name not in groups:
        raise ValueError(f"Unknown series group: {group_name}")
    return groups[group_name]
