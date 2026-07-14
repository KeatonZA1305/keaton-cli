"""Help: shortcuts, commands, troubleshooting, docs, and version."""
from __future__ import annotations

from rich.columns import Columns
from rich.console import Group
from rich.table import Table
from rich.text import Text

from ... import __version__
from .. import keys as K
from ..widgets import rounded_panel
from .base import Screen

SHORTCUTS = [
    ("↑ ↓ / j k", "Move selection"),
    ("Enter", "Open / confirm"),
    ("Esc", "Go back"),
    ("/", "Search the current list"),
    ("Ctrl+P", "Command palette"),
    ("Space", "Toggle selection (marketplace)"),
    ("Tab", "Switch focus where available"),
    ("Ctrl+C", "Quit Keaton"),
]

COMMANDS = [
    ("keaton", "Open this dashboard"),
    ("keaton run \"...\"", "Route a task to the right tool"),
    ("keaton tools", "List every tool"),
    ("keaton doctor", "Health check tools and provider"),
    ("keaton chat", "Classic one shot chat"),
]

TROUBLESHOOTING = [
    "Colours look flat: your terminal may be limited to 256 colours.",
    "No AI response: set your provider key, e.g. ANTHROPIC_API_KEY.",
    "A tool shows missing: install it from the Tool Marketplace.",
    "Disable animations in Settings if your terminal is slow.",
]


class HelpScreen(Screen):
    title = "Help"

    def _table(self, rows, key_style):
        t = Table.grid(padding=(0, 2))
        t.add_column(justify="left", no_wrap=True, style=key_style)
        t.add_column(justify="left", style="default")
        for k, v in rows:
            t.add_row(k, v)
        return t

    def render_body(self, width: int, height: int):
        th = self.theme
        left = rounded_panel(
            self._table(SHORTCUTS, f"bold {th.accent}"),
            title="Keyboard", theme=th, active=False, padding=(1, 2))
        right = rounded_panel(
            self._table(COMMANDS, th.accent),
            title="Commands", theme=th, active=False, padding=(1, 2))

        trouble = Text()
        trouble.append("Troubleshooting\n", style=f"bold {th.accent}")
        for line in TROUBLESHOOTING:
            trouble.append(f"  • {line}\n", style=th.muted)

        footer = Text()
        footer.append("\nDocs  ", style=f"bold {th.accent}")
        footer.append("github.com/KeatonZA1305/keaton-cli", style=th.muted)
        footer.append(f"      Version  v{__version__}", style=th.dim)

        return Group(Columns([left, right], expand=True, equal=True),
                     Text(""), trouble, footer)

    def footer_hints(self):
        return [("esc", "back"), ("^p", "palette"), ("^c", "quit")]

    def handle_key(self, key: str) -> None:
        if key == K.ESC:
            self.app.pop()
