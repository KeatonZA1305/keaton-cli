"""Keaton CLI — main application entry point."""
import os
import json
import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

import importlib

from . import __version__
from . import auth as auth_mod
from . import toolcli
from . import marketcli
from .tools import registry
from .config import update_config, load_config

app = typer.Typer(
    name="keaton",
    help="Keaton — Universal AI Terminal Platform & tool orchestrator",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()

# Providers are imported lazily: a single broken/half-written provider file must
# never take down the whole CLI (especially the tool commands, which need none
# of them). module:ClassName pairs.
_PROVIDER_SPECS = {
    "base44": ("keaton.providers.base44", "Base44Provider"),
    "openai": ("keaton.providers.openai", "OpenAIProvider"),
    "anthropic": ("keaton.providers.anthropic", "AnthropicProvider"),
    "ollama": ("keaton.providers.ollama", "OllamaProvider"),
    "gemini": ("keaton.providers.gemini", "GeminiProvider"),
    "openrouter": ("keaton.providers.openrouter", "OpenRouterProvider"),
    "lmstudio": ("keaton.providers.lmstudio", "LMStudioProvider"),
    "local": ("keaton.providers.local", "LocalProvider"),
}
PROVIDERS = list(_PROVIDER_SPECS)


def _load_provider_class(provider_name: str):
    spec = _PROVIDER_SPECS.get(provider_name)
    if not spec:
        return None
    module_path, class_name = spec
    module = importlib.import_module(module_path)
    return getattr(module, class_name)

_ENV_KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def get_provider_instance(provider_name: str, config: dict):
    if provider_name not in _PROVIDER_SPECS:
        console.print(f"[red]Error: Unknown provider '{provider_name}'[/red]")
        raise typer.Exit(1)
    try:
        provider_class = _load_provider_class(provider_name)
    except Exception as e:
        console.print(f"[red]Error: provider '{provider_name}' failed to load: {e}[/red]")
        raise typer.Exit(1)
    return provider_class(config)


def _provider_config(config: dict, provider_name: str) -> dict:
    cfg = {
        "app_id": config.get("app_id"),
        "agent_name": config.get("agent_name"),
        "agent_id": config.get("agent_id"),
    }
    env_key = _ENV_KEYS.get(provider_name)
    if env_key:
        cfg["api_key"] = os.getenv(env_key)
    return cfg


def version_callback(value: bool):
    if value:
        console.print(f"Keaton CLI version: {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """Keaton — Universal AI Terminal Platform."""
    # Bare `keaton` opens the interactive dashboard (the home screen). Any
    # explicit subcommand (chat, tools, doctor, …) runs as before.
    if ctx.invoked_subcommand is None:
        import sys
        if sys.stdout.isatty() and sys.stdin.isatty():
            from .tui.app import launch
            launch(config=load_config())
        else:
            console.print("Keaton — run in an interactive terminal for the dashboard, "
                          "or try [bold]keaton --help[/bold], [bold]keaton tools[/bold], "
                          "[bold]keaton run \"...\"[/bold].")


@app.command()
def login():
    """Log in to Base44."""
    if auth_mod.login():
        console.print("[green]Successfully logged in to Base44[/green]")
    else:
        console.print("[red]Failed to log in to Base44[/red]")
        raise typer.Exit(1)


@app.command()
def logout():
    """Log out from Base44."""
    if auth_mod.logout():
        console.print("[green]Successfully logged out from Base44[/green]")
    else:
        console.print("[red]Failed to log out from Base44[/red]")
        raise typer.Exit(1)


@app.command()
def whoami():
    """Display the current logged-in user and workspace."""
    user_info = auth_mod.whoami()
    if user_info:
        config = load_config()
        panel = Panel.fit(
            f"[bold]User:[/bold] {user_info.get('email', 'Unknown')}\n"
            f"[bold]User ID:[/bold] {user_info.get('id', 'Unknown')}\n"
            f"[bold]App ID:[/bold] {config.get('app_id') or 'Not set'}\n"
            f"[bold]Agent:[/bold] {config.get('agent_name') or 'Not set'}",
            title="Keaton Account Info",
            border_style="blue",
        )
        console.print(panel)
    else:
        console.print("[yellow]Not logged in. Run 'keaton login' to authenticate.[/yellow]")


@app.command()
def providers():
    """List available AI providers."""
    rows = [
        ("base44", "Base44", True), ("openai", "OpenAI", True),
        ("anthropic", "Anthropic", True), ("ollama", "Ollama", False),
        ("gemini", "Gemini", True), ("openrouter", "OpenRouter", True),
        ("lmstudio", "LM Studio", False), ("local", "Local Models", False),
    ]
    table = Table(title="Available Providers")
    table.add_column("Name", style="cyan")
    table.add_column("Display Name", style="magenta")
    table.add_column("Requires Auth", style="green")
    for name, display, needs_auth in rows:
        table.add_row(name, display, "✓" if needs_auth else "✗")
    console.print(table)


@app.command("provider-use")
def provider_use(provider_name: str = typer.Argument(..., help="Provider to use")):
    """Set the active provider."""
    if provider_name in PROVIDERS:
        update_config("provider", provider_name)
        console.print(f"[green]Provider set to: {provider_name}[/green]")
    else:
        console.print(f"[red]Provider '{provider_name}' not supported.[/red]")
        console.print(f"Supported: {', '.join(PROVIDERS)}")
        raise typer.Exit(1)


@app.command()
def config():
    """Show current configuration."""
    cfg = load_config()
    safe = {
        k: v for k, v in cfg.items()
        if not any(s in k.lower() for s in ("token", "key", "secret"))
    }
    console.print(Panel(json.dumps(safe, indent=2),
                        title="Keaton Configuration", border_style="blue", expand=False))


@app.command()
def home():
    """Open the interactive dashboard (same as running `keaton`)."""
    from .tui.app import launch
    launch(config=load_config())


@app.command()
def splash():
    """Replay the ocean wave intro animation."""
    from .tui import wave
    wave.animate(console)


@app.command()
def doctor():
    """Check system health: AI providers AND every developer tool."""
    console.print("[bold]Running system health check…[/bold]\n")

    config = load_config()
    provider_name = config.get("provider", "base44")
    provider = get_provider_instance(provider_name, _provider_config(config, provider_name))

    async def check_provider():
        # Bound each check so a slow/misconfigured provider can't hang doctor.
        try:
            authed = await asyncio.wait_for(provider.is_authenticated(), timeout=8)
        except Exception:
            authed = False
        console.print(
            f"[green]✓ {provider.display_name} authenticated[/green]" if authed
            else f"[yellow]⚠ {provider.display_name} not authenticated[/yellow]"
        )
        try:
            healthy = await asyncio.wait_for(provider.health_check(), timeout=8)
        except Exception:
            healthy = False
        console.print(
            f"[green]✓ {provider.display_name} reachable[/green]" if healthy
            else f"[yellow]⚠ {provider.display_name} unreachable[/yellow]"
        )

    try:
        asyncio.run(check_provider())
    except Exception as e:
        console.print(f"[yellow]⚠ Provider check skipped: {e}[/yellow]")

    console.print()
    toolcli._doctor_extra()


async def chat_loop(provider, stream: bool = True):
    """Run an interactive chat session."""
    console.print("[bold]Welcome to Keaton Chat![/bold]")
    console.print("Type /help for commands, /exit to quit.\n")
    conversation_id = None
    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
            if user_input.startswith("/"):
                if user_input in ("/exit", "/quit"):
                    break
                if user_input == "/help":
                    console.print("/help /new /clear /exit")
                    continue
                if user_input == "/new":
                    conversation_id = None
                    console.print("[yellow]Started a new conversation.[/yellow]")
                    continue
                if user_input == "/clear":
                    os.system("clear" if os.name == "posix" else "cls")
                    continue
                console.print(f"[yellow]Unknown command: {user_input}[/yellow]")
                continue
            if not user_input.strip():
                continue
            with console.status("[bold green]Thinking…", spinner="dots"):
                try:
                    async for chunk in provider.chat(
                        message=user_input, conversation_id=conversation_id, stream=stream
                    ):
                        console.print(chunk, end="")
                    console.print()
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Use /exit to quit.[/yellow]")
            continue
        except EOFError:
            break


chat_app = typer.Typer(help="Chat with AI agents")
app.add_typer(chat_app, name="chat")


def _prepare_provider():
    config = load_config()
    provider_name = config.get("provider", "base44")
    provider = get_provider_instance(provider_name, _provider_config(config, provider_name))

    async def check_auth():
        if not await provider.is_authenticated():
            console.print(f"[red]Error: {provider.display_name} not authenticated.[/red]")
            if provider_name == "base44":
                console.print("Run 'keaton login' to authenticate with Base44.")
            else:
                console.print(f"Set the {provider_name.upper()}_API_KEY environment variable.")
            raise typer.Exit(1)

    asyncio.run(check_auth())
    return provider


@chat_app.command()
def start(
    message: Optional[str] = typer.Argument(None, help="Initial message to send"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Stream response"),
):
    """Start an interactive chat session."""
    provider = _prepare_provider()
    if message:
        async def send_single():
            async for chunk in provider.chat(message=message, stream=stream):
                print(chunk, end="", flush=True)
            print()
        asyncio.run(send_single())
        return
    asyncio.run(chat_loop(provider, stream))


@chat_app.command()
def ask(
    message: str = typer.Argument(..., help="Question to ask"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Stream response"),
):
    """Ask a single question and exit."""
    provider = _prepare_provider()

    async def ask_question():
        async for chunk in provider.chat(message=message, stream=stream):
            print(chunk, end="", flush=True)
        print()

    asyncio.run(ask_question())


# Wire in the Universal Tool Execution Framework commands.
toolcli.register(app)
# Wire in the marketplace commands (install / update / remove / marketplace).
marketcli.register(app)


if __name__ == "__main__":
    app()
