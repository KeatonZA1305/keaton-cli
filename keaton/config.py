"""
Configuration management for Keaton CLI.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

CONFIG_DIR = Path.home() / ".keaton"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "theme": "cyan",
    "default_agent": None,
    "app_id": None,
    "agent_name": None,
    "stream_enabled": True,
    "markdown_enabled": True,
    "history_enabled": True,
    "splash_enabled": True,
}


def ensure_config_dir() -> None:
    """Ensure the configuration directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> Dict[str, Any]:
    """Load configuration from file, creating default if not exists."""
    ensure_config_dir()
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        # Merge with defaults to ensure all keys exist
        config = {**DEFAULT_CONFIG, **config}
        return config
    except (json.JSONDecodeError, IOError):
        # If corrupted, return defaults
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to file."""
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_config() -> Dict[str, Any]:
    """Get the current configuration."""
    return load_config()


def update_config(key: str, value: Any) -> None:
    """Update a single configuration key."""
    config = load_config()
    config[key] = value
    save_config(config)


def get_config_value(key: str, default: Any = None) -> Any:
    """Get a specific configuration value."""
    config = load_config()
    return config.get(key, default)
