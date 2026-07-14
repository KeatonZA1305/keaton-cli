"""Keaton's interactive terminal UI (dashboard, marketplace, chat, and more).

``App``/``launch`` are exposed lazily so importing lightweight submodules (e.g.
``keaton.tui.marketplace`` from the CLI) does not pull in the whole rendering
stack.
"""

__all__ = ["App", "launch"]


def __getattr__(name):
    if name in __all__:
        from .app import App, launch
        return {"App": App, "launch": launch}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
