"""CLI commands for the tool marketplace: install, update, remove, list.

These are thin wrappers over ``keaton.tui.marketplace`` so the same catalog and
installer logic backs both the dashboard and the plain CLI.
"""
from __future__ import annotations

import subprocess
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from .tui import marketplace as mkt

console = Console()


def _resolve(name: str):
    """Find a catalog item by key or (case-insensitive) name."""
    item = mkt.get(name)
    if item:
        return item
    low = name.lower()
    for it in mkt.CATALOG:
        if it.key.lower() == low or it.name.lower() == low or it.binary.lower() == low:
            return it
    # last resort: unique prefix match
    matches = [it for it in mkt.CATALOG if it.name.lower().startswith(low)
               or it.key.lower().startswith(low)]
    return matches[0] if len(matches) == 1 else None


def _run(cmd: List[str], action: str, name: str) -> bool:
    console.print(f"[bold]{action} {name}[/bold]")
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
    try:
        rc = subprocess.run(cmd).returncode
    except FileNotFoundError:
        console.print(f"[red]command not found: {cmd[0]}[/red]")
        return False
    except KeyboardInterrupt:
        console.print("[yellow]cancelled[/yellow]")
        return False
    if rc == 0:
        console.print(f"[green]✓ {name} {action.lower()} complete[/green]")
        return True
    console.print(f"[red]✗ {name} failed (exit {rc})[/red]")
    return False


def register(app: typer.Typer) -> None:
    @app.command()
    def marketplace(
        query: Optional[str] = typer.Argument(None, help="Filter by name/category"),
    ):
        """Browse installable tools (status, version, size)."""
        table = Table(title="Tool Marketplace")
        table.add_column("Tool", style="cyan")
        table.add_column("Category", style="magenta")
        table.add_column("Status")
        table.add_column("Version", style="dim")
        table.add_column("Size", style="dim")
        table.add_column("Description")
        q = (query or "").lower()
        rows = 0
        for it in sorted(mkt.CATALOG, key=lambda i: (not mkt.installed(i), i.name.lower())):
            if q and q not in it.name.lower() and q not in it.category.lower() \
                    and q not in it.description.lower():
                continue
            inst = mkt.installed(it)
            status = "[green]● installed[/green]" if inst else "[dim]○ available[/dim]"
            ver = (mkt.current_version(it) or "") if inst else ""
            table.add_row(it.name, it.category, status, ver, it.size, it.description)
            rows += 1
        if not rows:
            console.print(f"[yellow]No tools match '{query}'.[/yellow]")
            return
        console.print(table)
        console.print("[dim]Install with:[/dim] keaton install <name>")

    @app.command()
    def install(
        tools: List[str] = typer.Argument(..., help="Tool name(s) to install"),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    ):
        """Install one or more tools from the marketplace."""
        failures = 0
        for name in tools:
            it = _resolve(name)
            if not it:
                console.print(f"[yellow]'{name}' is not in the catalog.[/yellow] "
                              "Run 'keaton marketplace' to see options.")
                failures += 1
                continue
            if mkt.installed(it):
                ver = mkt.current_version(it) or ""
                console.print(f"[green]{it.name} is already installed[/green] {ver}")
                continue
            cmd = mkt.install_command(it)
            if not cmd:
                console.print(f"[yellow]No installer for {it.name} on this system.[/yellow] "
                              f"See {it.url or 'the tool docs'}.")
                failures += 1
                continue
            console.print(f"[dim]{it.name}: {' '.join(cmd)}[/dim]")
            if not yes and not typer.confirm(f"Install {it.name} ({it.size})?", default=True):
                continue
            if not _run(cmd, "Installing", it.name):
                failures += 1
        if failures:
            raise typer.Exit(1)

    @app.command()
    def update(
        tools: List[str] = typer.Argument(..., help="Tool name(s) to update"),
    ):
        """Update installed tools to the latest version."""
        for name in tools:
            it = _resolve(name)
            if not it:
                console.print(f"[yellow]'{name}' is not in the catalog.[/yellow]")
                continue
            cmd = mkt.update_command(it)
            if not cmd:
                console.print(f"[yellow]No updater for {it.name} here.[/yellow]")
                continue
            _run(cmd, "Updating", it.name)

    @app.command(name="remove")
    def remove(
        tools: List[str] = typer.Argument(..., help="Tool name(s) to remove"),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    ):
        """Remove installed tools."""
        for name in tools:
            it = _resolve(name)
            if not it:
                console.print(f"[yellow]'{name}' is not in the catalog.[/yellow]")
                continue
            if not mkt.installed(it):
                console.print(f"[dim]{it.name} is not installed[/dim]")
                continue
            cmd = mkt.remove_command(it)
            if not cmd:
                console.print(f"[yellow]No removal command for {it.name} here.[/yellow]")
                continue
            console.print(f"[dim]{it.name}: {' '.join(cmd)}[/dim]")
            if not yes and not typer.confirm(f"Remove {it.name}?", default=False):
                continue
            _run(cmd, "Removing", it.name)
