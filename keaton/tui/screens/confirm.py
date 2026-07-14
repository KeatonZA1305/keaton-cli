"""A small yes/no confirmation screen."""
from __future__ import annotations

from typing import Callable

from rich.console import Group
from rich.text import Text

from ..widgets import MenuItem
from .base import ListScreen


class ConfirmScreen(ListScreen):
    search_enabled = False

    def __init__(self, app, message: str, on_confirm: Callable[[], None],
                 title: str = "Confirm"):
        self.message = message
        self._on_confirm = on_confirm
        self.title = title
        super().__init__(app)

    def build_items(self):
        return [
            MenuItem("No, cancel", "✗", value=False),
            MenuItem("Yes, continue", "✓", value=True),
        ]

    def render_body(self, width: int, height: int):
        msg = Text(self.message, style=self.theme.muted)
        return Group(msg, Text(""), super().render_body(width, height))

    def footer_hints(self):
        return [("↑↓", "move"), ("enter", "choose"), ("esc", "cancel")]

    def on_select(self, item):
        self.app.pop()
        if item.value:
            self._on_confirm()
