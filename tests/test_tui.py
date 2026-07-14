"""Tests for the interactive TUI core: wave, keys, menu, screens, chat."""
from __future__ import annotations

import asyncio

from rich.console import Console

from keaton import agents
from keaton.tui import keys as K
from keaton.tui import marketplace as mkt
from keaton.tui import wave
from keaton.tui.app import App
from keaton.tui.keys import ScriptedKeyReader, _decode
from keaton.tui.widgets import Menu, MenuItem, edit_text


def _console():
    return Console(force_terminal=True, color_system="256", width=100, height=36,
                   record=True)


def _app():
    return App(console=_console(), key_reader=ScriptedKeyReader([]))


# -- wave -----------------------------------------------------------------
def test_wave_render_line_count_and_width():
    lines = wave.render_lines(100, rows=8)
    assert len(lines) == 8
    for ln in lines:
        assert ln.cell_len == 100  # no overflow, exact width


def test_wave_is_responsive():
    for w in (60, 80, 120, 180):
        lines = wave.render_lines(w, rows=6)
        assert all(ln.cell_len == max(wave.MIN_WIDTH, min(wave.MAX_WIDTH, w))
                   for ln in lines)


# -- keys -----------------------------------------------------------------
def test_key_decoding():
    assert _decode("\x1b", iter("[A").__next__) == K.UP
    assert _decode("\x1b", iter("[B").__next__) == K.DOWN
    assert _decode("\x1b", iter("[C").__next__) == K.RIGHT
    assert _decode("\x1b", iter("[D").__next__) == K.LEFT
    assert _decode("\r", lambda: "") == K.ENTER
    assert _decode("\x03", lambda: "") == K.CTRL_C
    assert _decode("\x10", lambda: "") == K.CTRL_P
    assert _decode("j", lambda: "") == "j"
    assert _decode("\x1b", lambda: "") == K.ESC  # lone escape


def test_edit_text():
    assert edit_text("ab", "c") == ("abc", "")
    assert edit_text("ab", K.BACKSPACE) == ("a", "")
    assert edit_text("ab", K.ENTER) == ("ab", "submit")
    assert edit_text("ab", K.ESC) == ("ab", "cancel")


# -- menu -----------------------------------------------------------------
def test_menu_navigation_wraps_and_filters():
    m = Menu([MenuItem("Apple"), MenuItem("Banana"), MenuItem("Cherry")])
    assert m.current().label == "Apple"
    m.move(-1)
    assert m.current().label == "Cherry"   # wraps to end
    m.move(1)
    assert m.current().label == "Apple"
    m.set_query("ban")
    assert [i.label for i in m.filtered()] == ["Banana"]


# -- agents & marketplace -------------------------------------------------
def test_agents_catalog():
    assert len(agents.AGENTS) >= 6
    assert agents.get("git").name == "Git Assistant"
    assert agents.default() is agents.AGENTS[0]


def test_marketplace_install_command_is_a_real_command_or_none():
    git = mkt.get("git")
    cmd = mkt.install_command(git)
    # Either a concrete argv (has a package manager) or None (unsupported here).
    assert cmd is None or (isinstance(cmd, list) and cmd)
    claude = mkt.get("claude")
    # claude-code installs via npm regardless of OS package manager.
    assert claude.npm == "@anthropic-ai/claude-code"


# -- screens render -------------------------------------------------------
def test_all_screens_render_without_error():
    from keaton.tui.screens.agents import AgentsScreen
    from keaton.tui.screens.dashboard import Dashboard
    from keaton.tui.screens.help import HelpScreen
    from keaton.tui.screens.marketplace import MarketplaceScreen
    from keaton.tui.screens.projects import ProjectsScreen
    from keaton.tui.screens.settings import SettingsScreen
    from keaton.tui.screens.tools import InstalledToolsScreen

    for factory in (Dashboard, ProjectsScreen, AgentsScreen, MarketplaceScreen,
                    InstalledToolsScreen, SettingsScreen, HelpScreen):
        app = _app()
        screen = factory(app)
        app.stack = [screen]
        screen.on_enter()
        app.console.print(app.render_frame())
        assert app.console.export_text().strip()


def test_settings_toggle_persists_in_memory():
    from keaton.tui.screens.settings import SettingsScreen

    app = _app()
    screen = SettingsScreen(app)
    app.stack = [screen]
    item = next(i for i in screen.menu.items if i.value == "animations")
    before = app.config.get("animations", True)
    screen.on_select(item)
    assert app.config.get("animations") == (not before)


def test_settings_provider_cycles_through_all_providers():
    from keaton.providers.factory import PROVIDER_NAMES
    from keaton.tui.screens.settings import SettingsScreen

    app = _app()
    app.config["provider"] = PROVIDER_NAMES[0]
    screen = SettingsScreen(app)
    app.stack = [screen]
    seen = [app.config["provider"]]
    for _ in range(len(PROVIDER_NAMES)):
        item = next(i for i in screen.menu.items if i.value == "provider")
        screen.on_select(item)
        seen.append(app.config["provider"])
    # cycling N times returns to the start and visits every provider
    assert set(PROVIDER_NAMES) <= set(seen)
    assert seen[0] == seen[-1] == PROVIDER_NAMES[0]


def test_chat_input_box_shows_placeholder_and_provider():
    from keaton.tui.screens.chat import ChatScreen

    app = _app()
    app.config["provider"] = "ollama"
    chat = ChatScreen(app, agents.default())
    app.stack = [chat]
    chat.on_enter()
    app.console.print(app.render_frame())
    out = app.console.export_text()
    assert "Type your message and press Enter" in out
    assert "message" in out and "ollama" in out


# -- chat -----------------------------------------------------------------
def test_chat_streams_from_provider():
    from keaton.tui.screens.chat import ChatScreen

    class FakeProvider:
        async def chat(self, message, stream=True, **kw):
            for tok in ("Hello ", "world"):
                yield tok

    app = _app()
    chat = ChatScreen(app, agents.default())
    app.stack = [chat]
    chat.provider = FakeProvider()
    chat.provider_name = "fake"
    chat._submit("hi")
    assert chat.messages[-1]["role"] == "assistant"
    assert chat.messages[-1]["content"] == "Hello world"
    assert chat.streaming is False
