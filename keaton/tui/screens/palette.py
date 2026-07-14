"""Ctrl+P command palette: a fuzzy, searchable list of global actions."""
from __future__ import annotations

import sys

from ..widgets import MenuItem
from .base import ListScreen


class CommandPalette(ListScreen):
    title = "Command Palette"

    def on_enter(self):
        self.searching = True  # open straight into filter mode

    def build_items(self):
        return [
            MenuItem("Install Tool", "⬡", "open the marketplace", value="marketplace"),
            MenuItem("Open Project", "▤", "recent projects", value="projects"),
            MenuItem("Chat with Agent", "◆", "pick an AI agent", value="agents"),
            MenuItem("Installed Tools", "⚒", "browse installed tools", value="tools"),
            MenuItem("Search Docs", "?", "help and shortcuts", value="help"),
            MenuItem("Settings", "⚙", "appearance and behaviour", value="settings"),
            MenuItem("Update Keaton CLI", "⬆", "upgrade via pip", value="update"),
            MenuItem("Exit", "⏻", "leave Keaton", value="exit"),
        ]

    def on_select(self, item):
        route = item.value
        self.app.pop()  # close the palette first
        if route == "exit":
            self.app.quit()
            return
        if route == "update":
            from .operations import OperationScreen
            self.app.push(OperationScreen(
                self.app, "Update Keaton CLI",
                [("Upgrading keaton-cli", [sys.executable, "-m", "pip",
                                           "install", "--upgrade", "keaton-cli"])],
            ))
            return
        from .agents import AgentsScreen
        from .help import HelpScreen
        from .marketplace import MarketplaceScreen
        from .projects import ProjectsScreen
        from .settings import SettingsScreen
        from .tools import InstalledToolsScreen

        self.app.push({
            "marketplace": MarketplaceScreen,
            "projects": ProjectsScreen,
            "agents": AgentsScreen,
            "tools": InstalledToolsScreen,
            "help": HelpScreen,
            "settings": SettingsScreen,
        }[route](self.app))
