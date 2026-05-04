"""
PillSafe — Configuration Loader
Loads config.yaml and provides dot-notation access to parameters.
"""

import os
import yaml

_CONFIG = None
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")


class ConfigDict(dict):
    """Dictionary subclass allowing dot-notation access."""

    def __getattr__(self, key):
        try:
            value = self[key]
            if isinstance(value, dict):
                return ConfigDict(value)
            return value
        except KeyError:
            raise AttributeError(f"Config has no key '{key}'")


def load_config(path: str | None = None) -> ConfigDict:
    """Load and cache the YAML configuration file."""
    global _CONFIG
    if _CONFIG is None or path is not None:
        config_path = path or _CONFIG_PATH
        with open(config_path, "r") as f:
            _CONFIG = ConfigDict(yaml.safe_load(f))
    return _CONFIG


def get_config() -> ConfigDict:
    """Return the cached config, loading it if necessary."""
    if _CONFIG is None:
        return load_config()
    return _CONFIG
