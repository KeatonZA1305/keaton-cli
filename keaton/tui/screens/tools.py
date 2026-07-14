"""Installed Tools browser, backed by the real tool registry."""
from __future__ import annotations

from rich.console import Group
from rich.text import Text

from ...tools import registry
from .. import keys as K
from ..widgets import MenuItem, rounded_panel
from .base import ListScreen, Screen


class InstalledToolsScreen(ListScreen):
    title = "Installed Tools"
    empty_glyph = "⚒"
    empty_message = "No tools registered"

    def build_items(self):
        items = []
        for tool in registry.all():
            ok = tool.available()
            badge = "● installed" if ok else "○ missing"
            style = self.theme.good if ok else self.theme.dim
            items.append(MenuItem(
                tool.name, "⚒" if ok else "·", tool.description,
                value=tool.name, badge=badge, badge_style=style,
            ))
        return items

    def on_select(self, item):
        tool = registry.get(item.value)
        if tool:
            self.app.push(ToolDetailScreen(self.app, tool))


class ToolDetailScreen(Screen):
    def __init__(self, app, tool):
        super().__init__(app)
        self.tool = tool
        self.title = f"Tool · {tool.name}"

    def render_body(self, width: int, height: int):
        t = self.theme
        info = self.tool.help()
        head = Text()
        head.append(self.tool.description + "\n\n", style="default")
        status = "installed" if info["available"] else "not installed"
        head.append("Status   ", style=t.dim)
        head.append(status + "\n", style=t.good if info["available"] else t.warn)
        if info["version"]:
            head.append("Version  ", style=t.dim)
            head.append(str(info["version"])[:60] + "\n", style="default")
        if info["path"]:
            head.append("Path     ", style=t.dim)
            head.append(str(info["path"]) + "\n", style=t.muted)
        if not info["available"] and info["install_hint"]:
            head.append("Install  ", style=t.dim)
            head.append(info["install_hint"] + "\n", style=t.muted)

        caps = Text()
        caps.append("Capabilities\n", style=f"bold {t.accent}")
        for c in self.tool.capabilities:
            caps.append(f"  • {c}\n", style="default")

        ex = Text()
        ex.append("\nExamples\n", style=f"bold {t.accent}")
        for nl, cmd in self.tool.examples:
            ex.append(f"  {nl}\n", style=t.dim)
            ex.append(f"    {cmd}\n", style=t.accent)

        return Group(head, caps, ex)

    def footer_hints(self):
        return [("esc", "back"), ("^p", "palette"), ("^c", "quit")]

    def handle_key(self, key: str) -> None:
        if key == K.ESC:
            self.app.pop()
