"""Non-blocking check for a newer Keaton release on PyPI.

Runs in a background thread, caches the result for a day, and never blocks
startup or raises. The dashboard reads the cached answer.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Optional

from .. import __version__
from ..config import CONFIG_DIR

CACHE = CONFIG_DIR / "update.json"
TTL = 86400  # one day


def _parse(v: str):
    parts = []
    for chunk in v.split("."):
        num = "".join(c for c in chunk if c.isdigit())
        parts.append(int(num) if num else 0)
    return tuple(parts)


def cached_latest() -> Optional[str]:
    try:
        data = json.loads(CACHE.read_text())
        if time.time() - data.get("checked", 0) < TTL:
            return data.get("latest")
    except Exception:
        return None
    return None


def update_available() -> Optional[str]:
    """Return the newer version string if one is cached, else None."""
    latest = cached_latest()
    if latest and _parse(latest) > _parse(__version__):
        return latest
    return None


def _fetch() -> None:
    try:
        import urllib.request

        with urllib.request.urlopen(
            "https://pypi.org/pypi/keaton-cli/json", timeout=4
        ) as resp:
            info = json.loads(resp.read().decode())
        latest = info.get("info", {}).get("version")
        if latest:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps({"latest": latest, "checked": time.time()}))
    except Exception:
        pass


def check_in_background() -> None:
    """Kick off a refresh if the cache is stale. Fire and forget."""
    if cached_latest() is not None:
        return
    threading.Thread(target=_fetch, daemon=True).start()
