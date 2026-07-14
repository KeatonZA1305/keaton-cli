"""AI Agents: pick a persona, then open an interactive chat."""
from __future__ import annotations

from ... import agents
from ..widgets import MenuItem
from .base import ListScreen


class AgentsScreen(ListScreen):
    title = "AI Agents"
    empty_glyph = "◆"
    empty_message = "No agents configured"

    def build_items(self):
        return [
            MenuItem(a.name, a.glyph, a.tagline, value=a.key)
            for a in agents.AGENTS
        ]

    def footer_hints(self):
        if self.searching:
            return super().footer_hints()
        return [("↑↓/jk", "move"), ("enter", "open chat"), ("/", "search"),
                ("esc", "back"), ("^c", "quit")]

    def on_select(self, item):
        from .chat import ChatScreen
        agent = agents.get(item.value)
        self.app.active_agent = agent
        self.app.push(ChatScreen(self.app, agent))
