"""A screen that runs one or more shell commands and streams their output.

Used for installs, updates, removals, and self-update. Output streams live into
a panel with a spinner and an overall step progress bar. Ctrl+C terminates the
running command and returns you to where you were.
"""
from __future__ import annotations

import subprocess
from typing import List, Tuple

from rich.console import Group
from rich.text import Text

from .. import keys as K
from ..widgets import rounded_panel
from .base import Screen

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class OperationScreen(Screen):
    def __init__(self, app, title: str, steps: List[Tuple[str, List[str]]]):
        super().__init__(app)
        self.title = title
        self.steps = steps
        self.lines: List[str] = []
        self.step = 0
        self.status = "running"   # running | done | error | cancelled
        self.rc = 0
        self._tick = 0

    def on_enter(self) -> None:
        self._run()

    # -- execution --------------------------------------------------------
    def _emit(self, text: str, dim: bool = False) -> None:
        self.lines.append(("\x00" if dim else "") + text)
        self.lines = self.lines[-400:]
        self._tick += 1
        self.app.refresh()

    def _run(self) -> None:
        total = len(self.steps)
        for i, (label, command) in enumerate(self.steps):
            self.step = i + 1
            self._emit(f"› {label}", dim=True)
            self._emit(f"$ {' '.join(command)}", dim=True)
            try:
                proc = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1,
                )
            except FileNotFoundError:
                self._emit(f"command not found: {command[0]}")
                self.status = "error"
                self.rc = 127
                self.app.refresh()
                return
            try:
                assert proc.stdout is not None
                for line in proc.stdout:
                    self._emit(line.rstrip("\n"))
                proc.wait()
            except KeyboardInterrupt:
                proc.terminate()
                self.status = "cancelled"
                self._emit("cancelled")
                self.app.refresh()
                return
            if proc.returncode != 0:
                self.status = "error"
                self.rc = proc.returncode
                self._emit(f"exited with code {proc.returncode}")
                self.app.refresh()
                return
        self.status = "done"
        self.app.refresh()

    # -- rendering --------------------------------------------------------
    def render_body(self, width: int, height: int):
        t = self.theme
        total = len(self.steps)
        head = Text()
        if self.status == "running":
            spin = SPINNER[self._tick % len(SPINNER)]
            head.append(f"{spin} ", style=t.accent)
            head.append(f"Step {self.step}/{total}", style="default")
        elif self.status == "done":
            head.append("✓ ", style=t.good)
            head.append("Completed", style=t.good)
        elif self.status == "cancelled":
            head.append("■ ", style=t.warn)
            head.append("Cancelled", style=t.warn)
        else:
            head.append("✗ ", style=t.bad)
            head.append(f"Failed (exit {self.rc})", style=t.bad)

        # progress bar
        filled = int((self.step / total) * 24) if total else 24
        if self.status == "done":
            filled = 24
        bar = Text()
        bar.append("█" * filled, style=t.accent)
        bar.append("░" * (24 - filled), style=t.dim)

        log_h = max(4, height - 6)
        shown = self.lines[-log_h:]
        log = Text(no_wrap=False, overflow="fold")
        for raw in shown:
            if raw.startswith("\x00"):
                log.append(raw[1:] + "\n", style=t.dim)
            else:
                log.append(raw + "\n", style="default")
        panel = rounded_panel(log, title="output", theme=t, active=False,
                              padding=(0, 1))
        return Group(head, Text(""), bar, Text(""), panel)

    def footer_hints(self):
        if self.status == "running":
            return [("^c", "cancel")]
        return [("esc/enter", "back"), ("^c", "quit")]

    def handle_key(self, key: str) -> None:
        if self.status == "running":
            return
        if key in (K.ESC, K.ENTER):
            self.app.pop()
