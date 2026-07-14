"""Common interface shared by every Keaton tool.

A Tool is a thin, declarative wrapper around a real developer CLI (git,
ffmpeg, docker, ...). Subclasses mostly supply *data* — keywords for natural
language routing, human examples, and command "recipes" — so adding a new
tool means writing a small file, never touching the core.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class ExecResult:
    """The outcome of running a tool command."""
    command: List[str]
    returncode: int
    stdout: str
    stderr: str
    duration: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class Tool:
    """Base class for every tool Keaton can drive."""

    # --- identity (override in subclasses) --------------------------------
    name: str = ""                     # short id, e.g. "ffmpeg"
    binary: str = ""                   # executable to look for on PATH
    description: str = ""              # one-line human description
    category: str = "general"         # grouping for `keaton tools`
    install_hint: str = ""            # how to install if missing

    # --- routing + docs (override in subclasses) --------------------------
    keywords: List[str] = []                 # words that route NL -> this tool
    capabilities: List[str] = []             # human-readable feature list
    examples: List[Tuple[str, str]] = []     # (natural language, shell command)

    # --- command recipes --------------------------------------------------
    # action name -> list of argument templates using {input}/{output}/...
    recipes: dict = {}
    # action names that must be confirmed before running
    destructive: set = set()

    # ---------------------------------------------------------------------
    def which(self) -> Optional[str]:
        """Absolute path to the binary, or None if not installed."""
        return shutil.which(self.binary) if self.binary else None

    def available(self) -> bool:
        return self.which() is not None

    def version(self) -> Optional[str]:
        """Best-effort version string for the underlying binary."""
        if not self.available():
            return None
        bad = ("illegal option", "unknown option", "unrecognized",
               "invalid option", "usage:")

        def is_version(line: str) -> bool:
            # A real version line has a digit and isn't a usage/option dump.
            if not line or line.startswith(("[", "-")):
                return False
            if any(b in line.lower() for b in bad):
                return False
            return any(ch.isdigit() for ch in line)

        for flag in ("--version", "version", "-version", "-V"):
            try:
                r = subprocess.run(
                    [self.binary, flag],
                    capture_output=True, text=True, timeout=8,
                )
                for raw in ((r.stdout or "") + "\n" + (r.stderr or "")).splitlines():
                    line = raw.strip()
                    if is_version(line):
                        return line
            except Exception:
                continue
        return "installed"

    def build(self, action: str, **kwargs) -> List[str]:
        """Turn an action + arguments into a concrete argv list."""
        template = self.recipes.get(action)
        if template is None:
            raise ValueError(
                f"{self.name}: unknown action '{action}'. "
                f"Known: {', '.join(self.recipes) or '(none)'}"
            )
        return [self.binary] + [part.format(**kwargs) for part in template]

    def is_destructive(self, action: str) -> bool:
        return action in self.destructive

    def score(self, text: str) -> int:
        """How strongly a natural-language request matches this tool."""
        t = text.lower()
        hits = sum(1 for k in self.keywords if k in t)
        if self.name and self.name in t:
            hits += 3
        if self.binary and self.binary in t:
            hits += 2
        return hits

    def help(self) -> dict:
        return {
            "name": self.name,
            "binary": self.binary,
            "description": self.description,
            "category": self.category,
            "available": self.available(),
            "version": self.version(),
            "path": self.which(),
            "capabilities": self.capabilities,
            "examples": self.examples,
            "install_hint": self.install_hint,
        }
