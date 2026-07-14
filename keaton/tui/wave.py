"""A procedural pixel-art ocean wave for the Keaton landing screen.

The scene is built from several overlapping sine "bands" drawn back to front in
a deep-blue to bright-cyan ramp, each capped with a foam line. It scales to any
width (looks clean from roughly 60 to 180 columns), uses Unicode block glyphs,
and its colours read on both dark and light terminals.
"""
from __future__ import annotations

import math
import time
from typing import List, Optional

from rich.align import Align
from rich.console import Console
from rich.text import Text

from .theme import FOAM, FOAM_SOFT, OCEAN

FULL = "█"
CAP = "▀"

# Back-to-front bands: (body colour, foam colour, amplitude, base fraction, phase).
_BANDS = [
    (OCEAN[1], OCEAN[3], 1.0, 0.34, 0.0),
    (OCEAN[2], OCEAN[4], 1.3, 0.50, 1.7),
    (OCEAN[3], OCEAN[5], 1.6, 0.66, 3.1),
    (OCEAN[4], FOAM_SOFT, 1.9, 0.82, 4.6),
]

MIN_WIDTH = 40
MAX_WIDTH = 180
DEFAULT_ROWS = 9


def _clamp_width(width: int) -> int:
    return max(MIN_WIDTH, min(MAX_WIDTH, width))


def render_lines(
    width: int,
    rows: int = DEFAULT_ROWS,
    phase: float = 0.0,
    brightness: float = 1.0,
    bright_foam: bool = True,
) -> List[Text]:
    """Render the wave as a list of Rich ``Text`` rows (no side padding)."""
    w = _clamp_width(width)
    wavelength = max(16.0, w / 6.0)
    k = 2 * math.pi / wavelength

    # grid[r][x] = (char, "#rrggbb") or None for open air above the water.
    grid: List[List[Optional[tuple]]] = [[None] * w for _ in range(rows)]

    for band_i, (body, foam, amp, base_frac, ph) in enumerate(_BANDS):
        base = rows * base_frac
        for x in range(w):
            angle = k * x + ph + phase
            surface = base - amp * math.sin(angle) - 0.4 * amp * math.sin(2 * angle + ph)
            top = int(round(surface))
            if top < 0:
                top = 0
            for r in range(top, rows):
                grid[r][x] = (FULL, body)
            if 0 <= top < rows:
                foam_col = foam
                if bright_foam and band_i == len(_BANDS) - 1 and (x % 6 == (band_i + int(phase)) % 6):
                    foam_col = FOAM
                grid[top][x] = (CAP, foam_col)

    def shade(hex_color: str) -> str:
        if brightness >= 0.999:
            return hex_color
        r = int(hex_color[1:3], 16) * brightness
        g = int(hex_color[3:5], 16) * brightness
        b = int(hex_color[5:7], 16) * brightness
        return f"#{int(r):02x}{int(g):02x}{int(b):02x}"

    lines: List[Text] = []
    for row in grid:
        line = Text(no_wrap=True, overflow="crop")
        for cell in row:
            if cell is None:
                line.append(" ")
            else:
                ch, col = cell
                line.append(ch, style=shade(col))
        lines.append(line)
    return lines


def render(width: int, rows: int = DEFAULT_ROWS, phase: float = 0.0,
           brightness: float = 1.0) -> Text:
    """Render the wave as one centered multi-line ``Text``."""
    lines = render_lines(width, rows=rows, phase=phase, brightness=brightness)
    out = Text(justify="center")
    for i, line in enumerate(lines):
        out.append_text(line)
        if i != len(lines) - 1:
            out.append("\n")
    return out


def banner(width: int, rows: int = DEFAULT_ROWS, phase: float = 0.0) -> Align:
    """Centered wave, ready to drop into a layout."""
    return Align.center(render(width, rows=rows, phase=phase))


def animate(console: Optional[Console] = None, *, duration: float = 1.3,
            frames: int = 22, rows: int = DEFAULT_ROWS) -> None:
    """Play the intro: the wave rolls in and brightens, then holds."""
    from rich.live import Live

    console = console or Console()
    if not console.is_terminal:
        return
    cs = "truecolor" if console.color_system == "truecolor" else "256"
    render_console = Console(color_system=cs)
    width = render_console.width

    with Live(console=render_console, refresh_per_second=60, transient=False) as live:
        for f in range(1, frames + 1):
            p = f / frames
            brightness = 1 - (1 - p) ** 3
            phase = (1 - p) * 2.2  # rolls into place
            live.update(Align.center(render(width, rows=rows, phase=phase,
                                            brightness=brightness)))
            time.sleep(max(0.0, duration / frames))
        live.update(Align.center(render(width, rows=rows, phase=0.0)))
