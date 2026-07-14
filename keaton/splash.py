"""Animated startup splash: a pixel-art portrait that fades/wipes into view.

Rendering uses the classic "half block" trick — each character cell (▀) shows
two vertical pixels (foreground = top pixel, background = bottom pixel), which
doubles the vertical resolution and keeps the pixels roughly square.

The splash is defensive by design: it is skipped when output isn't a TTY, can
be turned off (config `splash_enabled` or the KEATON_NO_SPLASH env var), and any
error is swallowed so it can never break the CLI.
"""
from __future__ import annotations

import base64
import os
import sys
import time
from typing import List, Optional, Tuple

from rich.color import Color
from rich.console import Console
from rich.live import Live
from rich.style import Style
from rich.text import Text

UPPER_HALF = "▀"  # ▀
Pixel = Tuple[int, int, int]


def _load() -> Tuple[int, int, List[Pixel]]:
    """Decode the bundled portrait into (width, height, flat RGB pixel list)."""
    from .assets import pixel_me as art

    raw = base64.b64decode(art.DATA)
    pixels = [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]
    return art.WIDTH, art.HEIGHT, pixels


def _ease_out(t: float) -> float:
    """Cubic ease-out for a smooth, natural-feeling transition."""
    return 1 - (1 - t) ** 3


def _dim(c: Pixel, b: float) -> Tuple[int, int, int]:
    return (int(c[0] * b), int(c[1] * b), int(c[2] * b))


def _frame(pixels: List[Pixel], w: int, h: int, brightness: float,
           visible_rows: int, pad: int) -> Text:
    """Build one animation frame as a Rich Text block."""
    text = Text(no_wrap=True, overflow="crop")
    rows = h // 2
    lead = " " * pad
    for tr in range(min(visible_rows, rows)):
        if pad:
            text.append(lead)
        for x in range(w):
            top = _dim(pixels[(2 * tr) * w + x], brightness)
            bot = _dim(pixels[(2 * tr + 1) * w + x], brightness)
            text.append(
                UPPER_HALF,
                style=Style(color=Color.from_rgb(*top),
                            bgcolor=Color.from_rgb(*bot)),
            )
        text.append("\n")
    return text


def play(console: Optional[Console] = None, *, duration: float = 0.9,
         frames: int = 18, caption: str = "K E A T O N") -> None:
    """Play the fade-in / top-down wipe transition, leaving the art on screen."""
    base = console or Console()
    if not base.is_terminal:
        return
    # A photo needs colour depth. Keep truecolor if the terminal has it,
    # otherwise force 256 — far better than the 8/16-colour auto-fallback.
    cs = "truecolor" if base.color_system == "truecolor" else "256"
    render = Console(color_system=cs)
    if not render.is_terminal:
        render = base

    w, h, pixels = _load()
    rows = h // 2
    pad = max(0, (render.width - w) // 2)

    with Live(console=render, refresh_per_second=60, transient=False) as live:
        for f in range(1, frames + 1):
            p = f / frames
            brightness = _ease_out(p)
            # Wipe reveals slightly ahead of the brightness ramp.
            visible = max(1, round(rows * _ease_out(min(1.0, p * 1.25))))
            live.update(_frame(pixels, w, h, brightness, visible, pad))
            time.sleep(max(0.0, duration / frames))
        live.update(_frame(pixels, w, h, 1.0, rows, pad))

    if caption:
        render.print(Text(caption.center(w + 2 * pad), style="bold cyan"))


def maybe_play(console: Optional[Console] = None) -> None:
    """Play the splash only when appropriate; never raise."""
    try:
        if os.environ.get("KEATON_NO_SPLASH"):
            return
        try:
            from .config import get_config_value
            if not get_config_value("splash_enabled", True):
                return
        except Exception:
            pass
        if not sys.stdout.isatty():
            return
        play(console)
    except Exception:
        # A cosmetic splash must never take down the CLI.
        pass
