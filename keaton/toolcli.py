"""Typer commands that expose the tool subsystem to the CLI."""
from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .tools import registry
from .tools.executor import Executor

console = Console()


def _doctor_extra() -> None:
    """Print availability of every supported developer tool."""
    table = Table(title="Developer Tools")
    table.add_column("Tool", style="cyan")
    table.add_column("Status")
    table.add_column("Version", style="dim")
    table.add_column("Path", style="dim")
    for tool in registry.all():
        if tool.available():
            status = "[green]✓ installed[/green]"
            version = (tool.version() or "")[:40]
            path = tool.which() or ""
        else:
            status = "[yellow]✗ missing[/yellow]"
            version = ""
            path = tool.install_hint
        table.add_row(tool.name, status, version, path)
    console.print(table)


def tools_command() -> None:
    """`keaton tools` — list every tool Keaton knows about."""
    table = Table(title="Keaton Tools")
    table.add_column("Name", style="cyan")
    table.add_column("Category", style="magenta")
    table.add_column("Available")
    table.add_column("Description")
    for tool in registry.all():
        table.add_row(
            tool.name,
            tool.category,
            "[green]✓[/green]" if tool.available() else "[yellow]—[/yellow]",
            tool.description,
        )
    console.print(table)


def tool_command(name: str) -> None:
    """`keaton tool <name>` — detailed docs for one tool."""
    tool = registry.get(name)
    if not tool:
        console.print(f"[red]No tool named '{name}'.[/red] Try 'keaton tools'.")
        raise typer.Exit(1)
    info = tool.help()
    status = "[green]installed[/green]" if info["available"] else "[yellow]not installed[/yellow]"
    body = [f"[bold]{tool.description}[/bold]", ""]
    body.append(f"Status: {status}")
    if info["version"]:
        body.append(f"Version: {info['version']}")
    if info["path"]:
        body.append(f"Path: {info['path']}")
    if not info["available"] and info["install_hint"]:
        body.append(f"Install: {info['install_hint']}")
    body.append("")
    body.append("[bold]Capabilities[/bold]")
    body += [f"  • {c}" for c in tool.capabilities]
    body.append("")
    body.append("[bold]Examples[/bold]")
    for nl, cmd in tool.examples:
        body.append(f"  [dim]{nl}[/dim]\n    [cyan]{cmd}[/cyan]")
    console.print(Panel("\n".join(body), title=f"keaton · {tool.name}", border_style="blue"))


def run_command(request: str, dry_run: bool = False, yes: bool = False) -> None:
    """`keaton run "<what you want>"` — route to a tool and show/execute it."""
    ranked = registry.route(request)
    if not ranked:
        console.print("[yellow]No matching tool. Try 'keaton tools' to see what's available.[/yellow]")
        raise typer.Exit(1)

    tool = ranked[0]
    console.print(f"[bold cyan]→ {tool.name}[/bold cyan] — {tool.description}")

    # Offer the closest example command as a safe, transparent default.
    suggestion = None
    for nl, cmd in tool.examples:
        if any(w in request.lower() for w in nl.lower().split()):
            suggestion = cmd
            break
    if suggestion is None and tool.examples:
        suggestion = tool.examples[0][1]

    if suggestion:
        console.print(Panel(suggestion, title="suggested command", border_style="green"))
    console.print("[dim]Tip: copy/adjust the command above, or run it directly in your shell.[/dim]")

    if not tool.available():
        console.print(f"[yellow]Heads up: '{tool.binary}' isn't installed. {tool.install_hint}[/yellow]")


def register(app: typer.Typer) -> None:
    """Wire the tool commands onto the main Typer app."""

    @app.command("tools")
    def _tools():
        """List every tool Keaton can orchestrate."""
        tools_command()

    @app.command("tool")
    def _tool(name: str = typer.Argument(..., help="Tool name, e.g. ffmpeg")):
        """Show detailed docs for a single tool."""
        tool_command(name)

    @app.command("run")
    def _run(
        request: str = typer.Argument(..., help="Describe what you want to do"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Preview only"),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    ):
        """Describe a task in plain English; Keaton routes it to the right tool."""
        run_command(request, dry_run=dry_run, yes=yes)
