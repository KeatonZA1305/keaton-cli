"""Colour palette and styling for the Keaton TUI.

Centralises every colour so the whole app stays consistent and a user's accent
choice (from config) flows everywhere. Colours are picked to read well on both
dark and light terminals: mid cyans and blues rather than near-black or
near-white extremes.
"""
from __future__ import annotations

from dataclasses import dataclass

# Named accent options offered in Settings.
ACCENTS = {
    "cyan": "#22d3ee",
    "blue": "#3b82f6",
    "teal": "#2dd4bf",
    "violet": "#a78bfa",
    "green": "#34d399",
    "amber": "#f59e0b",
    "rose": "#fb7185",
}

# The blue/cyan ramp used by the ocean wave (deep water to bright foam).
OCEAN = [
    "#0c2d6b",  # deep
    "#12468f",
    "#1565c0",
    "#1e88e5",
    "#29b6f6",
    "#4dd0e1",
    "#80deea",  # foam-ish
]
FOAM = "#d6f4fb"
FOAM_SOFT = "#7fd3e6"  # foam that still shows on light terminals


@dataclass(frozen=True)
class Theme:
    accent: str = ACCENTS["cyan"]
    muted: str = "#8b9bb4"
    dim: str = "#5b6b82"
    text: str = "default"
    good: str = "#34d399"
    warn: str = "#fbbf24"
    bad: str = "#f87171"
    border: str = "#3a4a63"
    border_active: str = ACCENTS["cyan"]

    @classmethod
    def from_config(cls, config: dict) -> "Theme":
        accent_name = (config or {}).get("accent") or (config or {}).get("theme") or "cyan"
        accent = ACCENTS.get(accent_name, ACCENTS["cyan"])
        return cls(accent=accent, border_active=accent)

    # Convenience Rich style strings -------------------------------------
    @property
    def title(self) -> str:
        return f"bold {self.accent}"

    @property
    def selected(self) -> str:
        return f"bold {self.accent}"

    def selected_bar(self) -> str:
        # Highlight style for the focused row.
        return f"bold #0b1220 on {self.accent}"
