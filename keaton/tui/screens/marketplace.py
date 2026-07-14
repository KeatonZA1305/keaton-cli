"""Tool Marketplace: browse, search, and install/update/remove real tools."""
from __future__ import annotations

from rich.console import Group
from rich.text import Text

from .. import keys as K
from .. import marketplace as mkt
from ..widgets import MenuItem, rounded_panel
from .base import ListScreen, Screen
from .confirm import ConfirmScreen
from .operations import OperationScreen


class MarketplaceScreen(ListScreen):
    title = "Tool Marketplace"
    empty_glyph = "⬡"
    empty_message = "No tools in the catalog"

    def __init__(self, app):
        self.selected = set()
        self._ver_cache = {}
        super().__init__(app)

    def _version(self, item):
        if item.key not in self._ver_cache:
            self._ver_cache[item.key] = mkt.current_version(item) if mkt.installed(item) else None
        return self._ver_cache[item.key]

    def refresh_item(self, item):
        self._ver_cache.pop(item.key, None)
        self.reload()

    def build_items(self):
        items = []
        # Installed first, then available; each alphabetical.
        cat = sorted(mkt.CATALOG, key=lambda i: (not mkt.installed(i), i.name.lower()))
        for it in cat:
            inst = mkt.installed(it)
            picked = it.key in self.selected
            glyph = "✓" if picked else ("●" if inst else "○")
            ver = self._version(it)
            badge = f"{('v' + ver) if ver else 'available'}   {it.size}"
            style = self.theme.good if inst else self.theme.dim
            hint = f"{it.category} · {it.description}"
            items.append(MenuItem(it.name, glyph, hint, value=it.key,
                                  badge=badge, badge_style=style))
        return items

    def render_body(self, width: int, height: int):
        body = super().render_body(width, height)
        if self.selected and not self.searching:
            note = Text()
            note.append(f"\n  {len(self.selected)} selected", style=self.theme.accent)
            note.append("   press i to install all", style=self.theme.dim)
            return Group(body, note)
        return body

    def footer_hints(self):
        if self.searching:
            return super().footer_hints()
        return [("↑↓/jk", "move"), ("enter", "actions"), ("space", "select"),
                ("i", "install"), ("/", "search"), ("esc", "back")]

    def on_select(self, item):
        it = mkt.get(item.value)
        if it:
            self.app.push(ToolActionScreen(self.app, it, self))

    def handle_key(self, key: str) -> None:
        if self.searching:
            super().handle_key(key)
            return
        if key == K.SPACE:
            cur = self.menu.current()
            if cur:
                self.selected.symmetric_difference_update({cur.value})
                self.reload()
            return
        if key in ("i", "I"):
            self._install_selected()
            return
        super().handle_key(key)

    def _install_selected(self):
        keys = list(self.selected) or ([self.menu.current().value] if self.menu.current() else [])
        steps = []
        for k in keys:
            it = mkt.get(k)
            cmd = it and mkt.install_command(it)
            if cmd:
                steps.append((f"Install {it.name}", cmd))
        if not steps:
            return
        self.selected.clear()
        self._ver_cache.clear()
        self.app.push(OperationScreen(self.app, "Install tools", steps))


class ToolActionScreen(ListScreen):
    search_enabled = False

    def __init__(self, app, item, parent):
        self.item = item
        self.parent = parent
        self.title = f"Marketplace · {item.name}"
        super().__init__(app)

    def build_items(self):
        inst = mkt.installed(self.item)
        rows = []
        if not inst:
            rows.append(MenuItem("Install", "⬇", self.item.size, value="install"))
        else:
            rows.append(MenuItem("Update", "⬆", "upgrade to latest", value="update"))
            rows.append(MenuItem("Reinstall", "⟳", "", value="install"))
            rows.append(MenuItem("Remove", "✗", "", value="remove",
                                 badge_style=self.theme.bad))
        rows.append(MenuItem("View Details", "◇", "", value="details"))
        return rows

    def render_body(self, width: int, height: int):
        it = self.item
        head = Text()
        head.append(it.name, style=f"bold {self.theme.accent}")
        head.append(f"   {it.category}\n", style=self.theme.dim)
        head.append(it.description + "\n", style="default")
        ver = mkt.current_version(it) if mkt.installed(it) else None
        head.append("Status  ", style=self.theme.dim)
        head.append(("installed " + ("v" + ver if ver else "")) if ver else "not installed",
                    style=self.theme.good if ver else self.theme.warn)
        head.append(f"    Size  {it.size}\n\n", style=self.theme.dim)
        return Group(head, super().render_body(width, height))

    def footer_hints(self):
        return [("↑↓", "move"), ("enter", "run"), ("esc", "back")]

    def on_select(self, item):
        action = item.value
        it = self.item
        if action == "details":
            self.app.push(MarketDetailScreen(self.app, it))
            return
        if action == "install":
            cmd = mkt.install_command(it)
            self._run(cmd, f"Install {it.name}")
        elif action == "update":
            cmd = mkt.update_command(it)
            self._run(cmd, f"Update {it.name}")
        elif action == "remove":
            cmd = mkt.remove_command(it)
            if not cmd:
                self._run(None, "")
                return
            self.app.push(ConfirmScreen(
                self.app, f"Remove {it.name}? This runs: {' '.join(cmd)}",
                on_confirm=lambda: self._run(cmd, f"Remove {it.name}"),
                title="Remove tool"))

    def _run(self, cmd, label):
        self.parent._ver_cache.clear()
        if not cmd:
            self.app.push(_MessageScreen(
                self.app, "Unavailable",
                f"No installer for {self.item.name} on this system. "
                f"See {self.item.url or 'the tool docs'}."))
            return
        self.app.push(OperationScreen(self.app, label, [(label, cmd)]))


class MarketDetailScreen(Screen):
    def __init__(self, app, item):
        super().__init__(app)
        self.item = item
        self.title = f"Details · {item.name}"
        self._latest = None
        self._checked = False

    def on_enter(self):
        # Lazily fetch the latest version (may hit the network briefly).
        self._latest = mkt.latest_version(self.item)
        self._checked = True

    def render_body(self, width: int, height: int):
        it = self.item
        t = self.theme
        body = Text()
        body.append(it.description + "\n\n", style="default")
        cur = mkt.current_version(it) if mkt.installed(it) else None
        rows = [
            ("Category", it.category),
            ("Installed", "yes" if mkt.installed(it) else "no"),
            ("Current version", cur or "—"),
            ("Latest version", self._latest or ("checking…" if not self._checked else "unknown")),
            ("Estimated size", it.size),
            ("Install command", " ".join(mkt.install_command(it) or ["unavailable"])),
        ]
        for k, v in rows:
            body.append(f"{k:<18}", style=t.dim)
            body.append(f"{v}\n", style="default")
        return body

    def footer_hints(self):
        return [("esc", "back"), ("^c", "quit")]

    def handle_key(self, key: str) -> None:
        if key == K.ESC:
            self.app.pop()


class _MessageScreen(Screen):
    def __init__(self, app, title, message):
        super().__init__(app)
        self.title = title
        self.message = message

    def render_body(self, width: int, height: int):
        from ..widgets import empty_state
        return empty_state(self.theme, "ⓘ", self.message)

    def footer_hints(self):
        return [("esc", "back")]

    def handle_key(self, key: str) -> None:
        if key in (K.ESC, K.ENTER):
            self.app.pop()
