"""Recent projects store and lightweight git/system helpers for the TUI."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Optional

from ..config import CONFIG_DIR

RECENT_FILE = CONFIG_DIR / "recent.json"
MAX_RECENT = 20


def _read() -> List[dict]:
    try:
        return json.loads(RECENT_FILE.read_text())
    except Exception:
        return []


def _write(items: List[dict]) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        RECENT_FILE.write_text(json.dumps(items, indent=2))
    except Exception:
        pass


def record(path: Optional[str] = None) -> None:
    """Remember a project directory as recently opened."""
    p = Path(path or os.getcwd()).resolve()
    items = [i for i in _read() if i.get("path") != str(p)]
    fav = next((i.get("favorite", False) for i in _read() if i.get("path") == str(p)), False)
    items.insert(0, {
        "path": str(p),
        "name": p.name,
        "last_opened": time.time(),
        "favorite": fav,
    })
    _write(items[:MAX_RECENT])


def toggle_favorite(path: str) -> None:
    items = _read()
    for i in items:
        if i.get("path") == path:
            i["favorite"] = not i.get("favorite", False)
    _write(items)


def projects() -> List[dict]:
    """Recent projects, favorites first, then most recent."""
    items = _read()
    items.sort(key=lambda i: (not i.get("favorite", False), -i.get("last_opened", 0)))
    return items


def relative_time(ts: float) -> str:
    if not ts:
        return "never"
    delta = max(0, int(time.time() - ts))
    for unit, secs in (("d", 86400), ("h", 3600), ("m", 60)):
        if delta >= secs:
            return f"{delta // secs}{unit} ago"
    return "just now"


def git_branch(path: Optional[str] = None) -> Optional[str]:
    if not shutil.which("git"):
        return None
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=path or os.getcwd(), capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0:
            return r.stdout.strip() or None
    except Exception:
        return None
    return None


def _tool_version(binary: str, *args: str) -> Optional[str]:
    if not shutil.which(binary):
        return None
    try:
        r = subprocess.run([binary, *args], capture_output=True, text=True, timeout=3)
        out = (r.stdout or r.stderr).strip().splitlines()
        return out[0] if out else None
    except Exception:
        return None


def node_version() -> Optional[str]:
    return _tool_version("node", "--version")


def python_version() -> str:
    import platform
    return "v" + platform.python_version()
