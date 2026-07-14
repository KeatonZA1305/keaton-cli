"""Base class for TUI screens."""
from __future__ import annotations

from typing import List, Tuple

from rich.console import RenderableType

from .. import keys as K


class Screen:
    """A single view in the app. Subclasses render a body and handle keys."""

    title: str = ""
    header: str = "slim"  # "hero" for the dashboard, "slim" elsewhere

    def __init__(self, app):
        self.app = app

    @property
    def theme(self):
        return self.app.theme

    # Lifecycle -----------------------------------------------------------
    def on_enter(self) -> None:
        """Called when this screen becomes active."""

    # Rendering -----------------------------------------------------------
    def render_body(self, width: int, height: int) -> RenderableType:  # pragma: no cover
        raise NotImplementedError

    def footer_hints(self) -> List[Tuple[str, str]]:
        return [("↑↓/jk", "move"), ("enter", "open"), ("esc", "back"),
                ("/", "search"), ("^p", "palette"), ("^c", "quit")]

    # Input ---------------------------------------------------------------
    def handle_key(self, key: str) -> None:
        """Handle a key. Default: esc pops the screen."""
        if key == K.ESC:
            self.app.pop()


class ListScreen(Screen):
    """A screen built around a filterable, keyboard-driven menu.

    Subclasses provide ``build_items`` and ``on_select``. Search (``/``) and
    navigation (arrows + vim keys) are handled here.
    """

    search_enabled: bool = True
    empty_glyph: str = "◎"
    empty_message: str = "Nothing here yet"

    def __init__(self, app):
        super().__init__(app)
        from ..widgets import Menu
        self.menu = Menu(self.build_items())
        self.searching = False

    # Override these -------------------------------------------------------
    def build_items(self):  # pragma: no cover
        return []

    def on_select(self, item) -> None:  # pragma: no cover
        pass

    def reload(self) -> None:
        idx = self.menu.index
        self.menu.items = self.build_items()
        self.menu.index = idx

    # Rendering ------------------------------------------------------------
    def render_body(self, width: int, height: int):
        from rich.console import Group
        from rich.text import Text
        from ..widgets import empty_state

        if not self.menu.items:
            return empty_state(self.theme, self.empty_glyph, self.empty_message)
        parts = []
        if self.searching or self.menu.query:
            q = Text()
            q.append("  ", style=self.theme.dim)
            q.append("/ ", style=self.theme.accent)
            q.append(self.menu.query or "", style="default")
            if self.searching:
                q.append("▏", style=self.theme.accent)
            parts.append(q)
            parts.append(Text(""))
        parts.append(self.menu.render(self.theme, width))
        return Group(*parts)

    def footer_hints(self):
        if self.searching:
            return [("type", "filter"), ("enter", "select"), ("esc", "cancel")]
        base = [("↑↓/jk", "move"), ("enter", "open")]
        if self.search_enabled:
            base.append(("/", "search"))
        base += [("esc", "back"), ("^p", "palette"), ("^c", "quit")]
        return base

    # Input ---------------------------------------------------------------
    def handle_key(self, key: str) -> None:
        from ..widgets import edit_text

        if self.searching:
            new, action = edit_text(self.menu.query, key)
            if action == "cancel":
                self.searching = False
                self.menu.set_query("")
            elif action == "submit":
                self.searching = False
                item = self.menu.current()
                if item and item.enabled:
                    self.on_select(item)
            else:
                self.menu.set_query(new)
            return

        if key in K.NAV_UP:
            self.menu.move(-1)
        elif key in K.NAV_DOWN:
            self.menu.move(1)
        elif key == K.ENTER:
            item = self.menu.current()
            if item and item.enabled:
                self.on_select(item)
        elif key == "/" and self.search_enabled:
            self.searching = True
        elif key == K.ESC:
            if self.menu.query:
                self.menu.set_query("")
            else:
                self.app.pop()
