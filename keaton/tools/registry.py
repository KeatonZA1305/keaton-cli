"""Discovers every Tool subclass in this package and routes NL requests."""
from __future__ import annotations

import importlib
import pkgutil
from typing import List, Optional

from .base import Tool


class Registry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._discover()

    def _discover(self) -> None:
        """Import every sibling module and instantiate its Tool subclasses."""
        import keaton.tools as pkg
        for _finder, mod_name, _is_pkg in pkgutil.iter_modules(pkg.__path__):
            if mod_name in ("base", "registry", "executor"):
                continue
            module = importlib.import_module(f"keaton.tools.{mod_name}")
            for attr in vars(module).values():
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Tool)
                    and attr is not Tool
                ):
                    inst = attr()
                    if inst.name:
                        self._tools[inst.name] = inst

    # -- access ------------------------------------------------------------
    def all(self) -> List[Tool]:
        return sorted(self._tools.values(), key=lambda t: (t.category, t.name))

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def available(self) -> List[Tool]:
        return [t for t in self.all() if t.available()]

    def route(self, text: str) -> List[Tool]:
        """Return tools ranked by how well they match a request."""
        scored = [(t.score(text), t) for t in self.all()]
        scored = [(s, t) for s, t in scored if s > 0]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _s, t in scored]

    def best(self, text: str) -> Optional[Tool]:
        ranked = self.route(text)
        return ranked[0] if ranked else None


# A single shared instance is convenient for the CLI.
registry = Registry()
