"""Settings: appearance and behaviour, persisted to the real config file."""
from __future__ import annotations

from rich.console import Group
from rich.text import Text

from .. import keys as K
from ..theme import ACCENTS
from ..widgets import MenuItem, edit_text
from .base import ListScreen

# (config key, label, kind, default). kind: toggle | cycle | text | action
SETTINGS = [
    ("accent", "Accent colour", "cycle", "cyan"),
    ("default_model", "Default AI model", "text", ""),
    ("animations", "Terminal animations", "toggle", True),
    ("auto_update", "Auto update checks", "toggle", True),
    ("stream_enabled", "Stream AI responses", "toggle", True),
    ("markdown_enabled", "Markdown rendering", "toggle", True),
    ("telemetry", "Telemetry", "toggle", False),
    ("tool_install_dir", "Tool install directory", "text", ""),
    ("__shortcuts__", "Keyboard shortcuts", "action", None),
]
_SPEC = {s[0]: s for s in SETTINGS}
_ACCENT_KEYS = list(ACCENTS)


class SettingsScreen(ListScreen):
    title = "Settings"
    search_enabled = False

    def __init__(self, app):
        self.editing = None      # config key being edited
        self.buffer = ""
        super().__init__(app)

    def _value(self, key, default):
        return self.app.config.get(key, default)

    def build_items(self):
        items = []
        for key, label, kind, default in SETTINGS:
            if kind == "action":
                items.append(MenuItem(label, "⌨", "", value=key))
                continue
            val = self._value(key, default)
            if kind == "toggle":
                badge = "on" if val else "off"
                style = self.theme.good if val else self.theme.dim
                glyph = "◉" if val else "◯"
            elif kind == "cycle":
                badge = str(val)
                style = self.theme.accent
                glyph = "◈"
            else:  # text
                badge = str(val) if val else "not set"
                style = self.theme.muted if val else self.theme.dim
                glyph = "✎"
            items.append(MenuItem(label, glyph, "", value=key,
                                  badge=badge, badge_style=style))
        return items

    def render_body(self, width: int, height: int):
        body = super().render_body(width, height)
        if self.editing:
            spec = _SPEC[self.editing]
            line = Text()
            line.append(f"\n  {spec[1]}: ", style=f"bold {self.theme.accent}")
            line.append(self.buffer, style="default")
            line.append("▏", style=self.theme.accent)
            return Group(body, line)
        return body

    def footer_hints(self):
        if self.editing:
            return [("type", "edit"), ("enter", "save"), ("esc", "cancel")]
        return [("↑↓/jk", "move"), ("enter", "change"), ("esc", "back"),
                ("^c", "quit")]

    def on_select(self, item):
        key = item.value
        spec = _SPEC[key]
        kind = spec[2]
        if kind == "toggle":
            self.app.set_config(key, not self._value(key, spec[3]))
            self.reload()
        elif kind == "cycle":
            cur = self._value(key, spec[3])
            nxt = _ACCENT_KEYS[(_ACCENT_KEYS.index(cur) + 1) % len(_ACCENT_KEYS)] \
                if cur in _ACCENT_KEYS else _ACCENT_KEYS[0]
            self.app.set_config(key, nxt)
            self.reload()
        elif kind == "text":
            self.editing = key
            self.buffer = str(self._value(key, "") or "")
        elif kind == "action":
            from .help import HelpScreen
            self.app.push(HelpScreen(self.app))

    def handle_key(self, key: str) -> None:
        if self.editing:
            new, action = edit_text(self.buffer, key)
            if action == "cancel":
                self.editing = None
            elif action == "submit":
                self.app.set_config(self.editing, self.buffer.strip())
                self.editing = None
                self.reload()
            else:
                self.buffer = new
            return
        super().handle_key(key)
