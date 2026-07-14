"""The Keaton TUI application: screen stack, rendering, and the input loop."""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import List, Optional

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.rule import Rule
from rich.text import Text

from ..config import load_config, save_config
from . import keys as K
from . import recent, updates, wave, widgets
from .theme import Theme


def _best_console() -> Console:
    probe = Console()
    cs = "truecolor" if probe.color_system == "truecolor" else "256"
    return Console(color_system=cs)


class App:
    """Owns global state and drives the render/input loop."""

    def __init__(self, console: Optional[Console] = None, key_reader=None,
                 config: Optional[dict] = None):
        self.console = console or _best_console()
        self.config = config if config is not None else load_config()
        self.theme = Theme.from_config(self.config)
        self.stack: List = []
        self.running = False
        self.live: Optional[Live] = None
        self._reader = key_reader
        self.active_agent = None          # set when a chat is opened
        self.active_model: Optional[str] = self.config.get("default_model")
        self._sys_cache = (0.0, [])

    # -- config helpers ---------------------------------------------------
    def set_config(self, key: str, value) -> None:
        self.config[key] = value
        save_config(self.config)
        self.theme = Theme.from_config(self.config)

    # -- screen stack -----------------------------------------------------
    def push(self, screen) -> None:
        self.stack.append(screen)
        screen.on_enter()

    def pop(self) -> None:
        if self.stack:
            self.stack.pop()
        if not self.stack:
            self.running = False

    def replace(self, screen) -> None:
        if self.stack:
            self.stack.pop()
        self.push(screen)

    def go_home(self) -> None:
        while len(self.stack) > 1:
            self.stack.pop()

    def quit(self) -> None:
        self.running = False

    def refresh(self) -> None:
        if self.live is not None:
            self.live.update(self.render_frame())
            self.live.refresh()

    # -- run loop ---------------------------------------------------------
    def run(self) -> None:
        from .screens.dashboard import Dashboard

        recent.record()
        updates.check_in_background()

        interactive = self.console.is_terminal and self._reader is None
        reader = self._reader or K.TerminalKeyReader()

        if interactive and self.config.get("animations", True) \
                and not os.environ.get("KEATON_NO_SPLASH"):
            try:
                wave.animate(self.console, duration=1.1)
            except Exception:
                pass

        self.push(Dashboard(self))
        self.running = True

        with reader:
            with Live(self.render_frame(), console=self.console, screen=interactive,
                      auto_refresh=False, transient=False) as live:
                self.live = live
                while self.running and self.stack:
                    live.update(self.render_frame())
                    live.refresh()
                    try:
                        key = reader.read_key()
                    except KeyboardInterrupt:
                        break
                    self._dispatch(key)
                self.live = None

    def _dispatch(self, key: str) -> None:
        if key == K.CTRL_C:
            self.quit()
            return
        top = self.stack[-1]
        from .screens.palette import CommandPalette
        if key == K.CTRL_P and not isinstance(top, CommandPalette):
            self.push(CommandPalette(self))
            return
        top.handle_key(key)

    # -- rendering --------------------------------------------------------
    def render_frame(self) -> Layout:
        width, height = self.console.size
        screen = self.stack[-1]

        if getattr(screen, "header", "slim") == "hero":
            wave_rows = max(5, min(9, height // 4))
            header = Group(
                wave.render(width, rows=wave_rows),
                Text(""),
                widgets.brand_block(self.theme),
            )
            header_size = wave_rows + 3
        else:
            header = self._slim_header(screen)
            header_size = 2

        body_h = max(3, height - header_size - 3)
        body = screen.render_body(max(24, width - 8), body_h)
        body_panel = widgets.rounded_panel(
            body, title=screen.title, theme=self.theme, active=True)

        footer = Group(
            widgets.hint_bar(self.theme, screen.footer_hints()),
            self._status_line(),
        )

        layout = Layout()
        layout.split_column(
            Layout(header, name="header", size=header_size),
            Layout(body_panel, name="body"),
            Layout(footer, name="footer", size=2),
        )
        return layout

    def _slim_header(self, screen) -> Group:
        line = Text(no_wrap=True, overflow="ellipsis")
        line.append("  Keaton CLI", style=f"bold {self.theme.accent}")
        if screen.title:
            line.append("   ▸   ", style=self.theme.dim)
            line.append(screen.title, style=self.theme.muted)
        return Group(line, Rule(style=self.theme.border))

    def _status_line(self) -> Text:
        now = datetime.now().strftime("%H:%M")
        ts, cached = self._sys_cache
        if time.time() - ts > 3:
            branch = recent.git_branch()
            cached = {
                "branch": branch or "no repo",
                "project": os.path.basename(os.getcwd()) or "~",
                "python": recent.python_version(),
                "node": recent.node_version() or "—",
            }
            self._sys_cache = (time.time(), cached)

        segments = [
            ("", cached["project"], self.theme.muted),
            ("⑂", cached["branch"], self.theme.muted),
        ]
        if self.active_agent is not None:
            segments.append(("◆", self.active_agent.name, self.theme.accent))
        segments += [
            ("py", cached["python"], self.theme.muted),
            ("node", cached["node"], self.theme.muted),
            ("", now, self.theme.muted),
        ]
        return widgets.status_bar(self.theme, segments)


def launch(config: Optional[dict] = None) -> None:
    """Entry point used by the CLI to open the dashboard."""
    App(config=config).run()
