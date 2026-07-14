"""Reusable rendering widgets for the Keaton TUI."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from rich.align import Align
from rich.box import ROUNDED
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import keys as K
from .theme import Theme


def edit_text(value: str, key: str) -> tuple:
    """Apply a keypress to a single-line text field.

    Returns (new_value, action) where action is "submit", "cancel", or "" .
    """
    if key == K.ENTER:
        return value, "submit"
    if key == K.ESC:
        return value, "cancel"
    if key in (K.BACKSPACE,):
        return value[:-1], ""
    if key == K.CTRL_U:
        return "", ""
    if key == K.SPACE:
        return value + " ", ""
    if len(key) == 1 and key.isprintable():
        return value + key, ""
    return value, ""


@dataclass
class MenuItem:
    label: str
    glyph: str = "•"
    hint: str = ""
    value: Any = None
    badge: str = ""
    badge_style: str = ""
    enabled: bool = True


class Menu:
    """A vertical, filterable, keyboard-driven list with a highlighted row."""

    def __init__(self, items: List[MenuItem]):
        self.items = items
        self.index = 0
        self.query = ""

    # -- data --------------------------------------------------------------
    def filtered(self) -> List[MenuItem]:
        if not self.query:
            return self.items
        q = self.query.lower()
        return [i for i in self.items if q in i.label.lower() or q in i.hint.lower()]

    def current(self) -> Optional[MenuItem]:
        items = self.filtered()
        if not items:
            return None
        self.index = max(0, min(self.index, len(items) - 1))
        return items[self.index]

    # -- navigation --------------------------------------------------------
    def move(self, delta: int) -> None:
        n = len(self.filtered())
        if n:
            self.index = (self.index + delta) % n

    def set_query(self, query: str) -> None:
        self.query = query
        self.index = 0

    # -- render ------------------------------------------------------------
    def render(self, theme: Theme, width: int = 60) -> RenderableType:
        items = self.filtered()
        if not items:
            return Align.center(Text("No matches", style=theme.dim))
        table = Table.grid(padding=(0, 1), expand=True)
        table.add_column(justify="left", no_wrap=True)
        for i, item in enumerate(items):
            selected = i == self.index
            row = Text(overflow="ellipsis", no_wrap=True)
            marker = "▌ " if selected else "  "
            row.append(marker, style=theme.accent if selected else theme.dim)
            glyph_style = theme.accent if selected else theme.muted
            row.append(f"{item.glyph}  ", style=glyph_style)
            label_style = theme.selected if selected else ("default" if item.enabled else theme.dim)
            row.append(item.label, style=label_style)
            if item.badge:
                row.append("  ")
                row.append(item.badge, style=item.badge_style or theme.dim)
            if item.hint:
                row.append(f"   {item.hint}", style=theme.dim)
            table.add_row(row)
        return table


def rounded_panel(body: RenderableType, *, title: str = "", subtitle: str = "",
                  theme: Optional[Theme] = None, active: bool = False,
                  padding=(1, 2)) -> Panel:
    theme = theme or Theme()
    border = theme.border_active if active else theme.border
    title_text = Text(title, style=theme.title) if title else None
    sub = Text(subtitle, style=theme.dim) if subtitle else None
    return Panel(body, title=title_text, subtitle=sub, box=ROUNDED,
                 border_style=border, padding=padding, expand=True)


def brand_block(theme: Theme) -> RenderableType:
    """The 'Keaton CLI / Your AI Developer Workspace' wordmark."""
    name = Text("Keaton CLI", style=f"bold {theme.accent}", justify="center")
    tag = Text("Your AI Developer Workspace", style=theme.muted, justify="center")
    return Align.center(Group(name, tag))


def status_bar(theme: Theme, segments: List[tuple]) -> RenderableType:
    """Render a footer from (glyph, text, style) segments, spaced with dividers."""
    bar = Text(overflow="ellipsis", no_wrap=True)
    bar.append(" ")
    for i, (glyph, text, style) in enumerate(segments):
        if i:
            bar.append("  │  ", style=theme.dim)
        if glyph:
            bar.append(f"{glyph} ", style=theme.accent)
        bar.append(text, style=style or theme.muted)
    return bar


def hint_bar(theme: Theme, pairs: List[tuple]) -> RenderableType:
    """A keybinding hint line: [(keys, description), ...]."""
    bar = Text(justify="center", no_wrap=True, overflow="ellipsis")
    for i, (keys, desc) in enumerate(pairs):
        if i:
            bar.append("   ")
        bar.append(f" {keys} ", style=f"bold {theme.accent}")
        bar.append(f" {desc}", style=theme.dim)
    return bar


def empty_state(theme: Theme, glyph: str, message: str, hint: str = "") -> RenderableType:
    parts = [
        Text(glyph, style=theme.dim, justify="center"),
        Text(""),
        Text(message, style=theme.muted, justify="center"),
    ]
    if hint:
        parts += [Text(""), Text(hint, style=theme.dim, justify="center")]
    return Align.center(Group(*parts))
