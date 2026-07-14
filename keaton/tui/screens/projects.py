"""Recent projects: open, favourite, and see git/last-opened at a glance."""
from __future__ import annotations

import os

from rich.text import Text

from .. import keys as K
from .. import recent
from ..widgets import MenuItem
from .base import ListScreen


class ProjectsScreen(ListScreen):
    title = "Projects"
    empty_glyph = "▤"
    empty_message = "No recent projects yet"

    def build_items(self):
        items = []
        for p in recent.projects():
            star = "★" if p.get("favorite") else " "
            branch = recent.git_branch(p["path"]) or ""
            when = recent.relative_time(p.get("last_opened", 0))
            hint = f"{when}"
            if branch:
                hint += f"  ⑂ {branch}"
            items.append(MenuItem(
                p["name"], star, hint, value=p["path"],
                badge=self._short(p["path"]), badge_style=self.theme.dim,
            ))
        return items

    @staticmethod
    def _short(path: str) -> str:
        home = os.path.expanduser("~")
        return path.replace(home, "~")

    def on_select(self, item):
        path = item.value
        if os.path.isdir(path):
            os.chdir(path)
            recent.record(path)
            self.app._sys_cache = (0.0, [])  # force status bar refresh
            self.app.go_home()

    def footer_hints(self):
        if self.searching:
            return super().footer_hints()
        return [("↑↓/jk", "move"), ("enter", "open"), ("f", "favourite"),
                ("esc", "back"), ("^c", "quit")]

    def handle_key(self, key: str) -> None:
        if not self.searching and key in ("f", "F"):
            item = self.menu.current()
            if item:
                recent.toggle_favorite(item.value)
                self.reload()
            return
        super().handle_key(key)
