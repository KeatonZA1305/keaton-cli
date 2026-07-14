"""Terminal key input for the Keaton TUI.

Reads one logical keypress at a time from a raw-mode terminal and decodes it
into a small set of stable tokens (``up``, ``down``, ``enter``, ``esc`` …) or,
for printable input, the character itself. A scripted reader is provided so the
app can be driven deterministically in tests without a real TTY.
"""
from __future__ import annotations

import contextlib
import os
import select
import sys
from typing import Callable, Iterable, Iterator, List, Optional

# Stable key tokens used throughout the TUI.
UP = "up"
DOWN = "down"
LEFT = "left"
RIGHT = "right"
ENTER = "enter"
ESC = "esc"
TAB = "tab"
SHIFT_TAB = "shift-tab"
BACKSPACE = "backspace"
DELETE = "delete"
HOME = "home"
END = "end"
PAGE_UP = "page-up"
PAGE_DOWN = "page-down"
CTRL_C = "ctrl-c"
CTRL_P = "ctrl-p"
CTRL_N = "ctrl-n"
CTRL_R = "ctrl-r"
CTRL_U = "ctrl-u"
SPACE = "space"

# Vim-style aliases the app treats as navigation.
VIM_DOWN = "j"
VIM_UP = "k"
VIM_LEFT = "h"
VIM_RIGHT = "l"


def _decode(first: str, more: Callable[[], str]) -> str:
    """Decode a single keypress given the first byte and a reader for more."""
    if first == "\x03":
        return CTRL_C
    if first == "\x10":
        return CTRL_P
    if first == "\x0e":
        return CTRL_N
    if first == "\x12":
        return CTRL_R
    if first == "\x15":
        return CTRL_U
    if first in ("\r", "\n"):
        return ENTER
    if first == "\t":
        return TAB
    if first in ("\x7f", "\x08"):
        return BACKSPACE
    if first == " ":
        return SPACE
    if first != "\x1b":
        return first  # printable character

    # Escape: could be a lone ESC or the start of a CSI/SS3 sequence.
    seq = more()
    if not seq:
        return ESC
    if seq not in ("[", "O"):
        return ESC
    body = ""
    ch = more()
    while ch and ch not in "ABCDFHPQRS~":
        body += ch
        ch = more()
    code = body + (ch or "")
    return {
        "A": UP, "B": DOWN, "C": RIGHT, "D": LEFT,
        "H": HOME, "F": END,
        "5~": PAGE_UP, "6~": PAGE_DOWN, "3~": DELETE,
        "Z": SHIFT_TAB,
    }.get(code, ESC)


class TerminalKeyReader:
    """Reads keys from stdin in cbreak mode, restoring the terminal on exit."""

    def __init__(self, stream=None):
        self.fd = (stream or sys.stdin).fileno()
        self._saved = None

    def __enter__(self) -> "TerminalKeyReader":
        import termios
        import tty

        self._saved = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, *exc) -> None:
        import termios

        if self._saved is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self._saved)

    def _read1(self, timeout: Optional[float] = None) -> str:
        if timeout is not None:
            r, _, _ = select.select([self.fd], [], [], timeout)
            if not r:
                return ""
        try:
            return os.read(self.fd, 1).decode("utf-8", "ignore")
        except (OSError, ValueError):
            return ""

    def read_key(self) -> str:
        first = self._read1()
        # For escape sequences, peek with a tiny timeout to tell ESC from CSI.
        return _decode(first, lambda: self._read1(timeout=0.02))


class ScriptedKeyReader:
    """A key reader driven by a predefined list of tokens (for tests/demos)."""

    def __init__(self, keys: Iterable[str]):
        self._it: Iterator[str] = iter(list(keys))

    def __enter__(self) -> "ScriptedKeyReader":
        return self

    def __exit__(self, *exc) -> None:
        return None

    def read_key(self) -> str:
        try:
            return next(self._it)
        except StopIteration:
            return CTRL_C  # ensure any loop terminates


NAV_UP = {UP, VIM_UP}
NAV_DOWN = {DOWN, VIM_DOWN}
NAV_LEFT = {LEFT, VIM_LEFT}
NAV_RIGHT = {RIGHT, VIM_RIGHT}


@contextlib.contextmanager
def raw_terminal(stream=None):
    """Convenience context manager returning a TerminalKeyReader."""
    reader = TerminalKeyReader(stream)
    with reader:
        yield reader
