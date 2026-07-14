"""The home dashboard: hero wave, a welcome strip, and the main menu."""
from __future__ import annotations

from datetime import date

from rich.console import Group
from rich.table import Table
from rich.text import Text

from ... import __version__
from .. import keys as K
from .. import recent, updates
from ..widgets import MenuItem
from .base import ListScreen

TIPS = [
    "Press Ctrl+P anywhere to open the command palette.",
    "Type / on any list to filter it instantly.",
    "Open AI Agents to chat with a role tuned assistant.",
    "The Tool Marketplace installs real tools via your package manager.",
    "Use j and k to move like in vim.",
    "Settings lets you switch accent colour and default model.",
]


class Dashboard(ListScreen):
    title = ""
    header = "hero"
    search_enabled = False

    def build_items(self):
        return [
            MenuItem("Projects", "▤", "recent work", value="projects"),
            MenuItem("AI Agents", "◆", "chat with an assistant", value="agents"),
            MenuItem("Tool Marketplace", "⬡", "install and manage tools", value="marketplace"),
            MenuItem("Installed Tools", "⚒", "what Keaton can drive", value="tools"),
            MenuItem("Settings", "⚙", "appearance and behaviour", value="settings"),
            MenuItem("Help", "?", "shortcuts and docs", value="help"),
            MenuItem("Exit", "⏻", "leave Keaton", value="exit"),
        ]

    def _welcome(self) -> Group:
        t = self.theme
        left = Text()
        left.append("Keaton CLI ", style=f"bold {t.accent}")
        left.append(f"v{__version__}", style=t.muted)
        latest = updates.update_available()
        if latest:
            left.append(f"   ⬆ {latest} available", style=t.warn)
        else:
            left.append("   up to date", style=t.dim)

        projs = recent.projects()
        if projs:
            left.append(f"    {len(projs)} recent project", style=t.dim)
            left.append("s" if len(projs) != 1 else "", style=t.dim)

        tip = TIPS[date.today().toordinal() % len(TIPS)]
        tip_line = Text()
        tip_line.append("Tip  ", style=f"bold {t.accent}")
        tip_line.append(tip, style=t.muted)
        return Group(left, Text(""), tip_line)

    def render_body(self, width: int, height: int):
        from rich.rule import Rule
        menu_body = super().render_body(width, height)
        return Group(self._welcome(), Text(""), Rule(style=self.theme.border),
                     Text(""), menu_body)

    def footer_hints(self):
        return [("↑↓/jk", "move"), ("enter", "open"), ("^p", "palette"),
                ("q", "quit")]

    def on_select(self, item):
        route = item.value
        if route == "exit":
            self.app.quit()
            return
        from .agents import AgentsScreen
        from .help import HelpScreen
        from .marketplace import MarketplaceScreen
        from .projects import ProjectsScreen
        from .settings import SettingsScreen
        from .tools import InstalledToolsScreen

        self.app.push({
            "projects": ProjectsScreen,
            "agents": AgentsScreen,
            "marketplace": MarketplaceScreen,
            "tools": InstalledToolsScreen,
            "settings": SettingsScreen,
            "help": HelpScreen,
        }[route](self.app))

    def handle_key(self, key: str) -> None:
        if key in ("q", "Q"):
            self.app.quit()
            return
        super().handle_key(key)
