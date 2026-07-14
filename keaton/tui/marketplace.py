"""The tool marketplace catalog and real install/update/remove plumbing.

Every catalog entry maps to an official installer (Homebrew formula/cask, a tap,
npm, or pip). Detection and version reads are real (``shutil.which`` plus the
tool's own ``--version``). Installs shell out to the detected package manager
and stream their output; nothing is faked.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

IS_MAC = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


@dataclass(frozen=True)
class MarketItem:
    key: str
    name: str
    binary: str
    category: str
    description: str
    size: str                      # estimated install size, e.g. "45 MB"
    brew: Optional[str] = None     # formula name
    cask: bool = False             # brew cask?
    npm: Optional[str] = None      # npm global package
    pip: Optional[str] = None      # pip/pipx package
    apt: Optional[str] = None      # apt package name
    url: Optional[str] = None      # docs / manual install
    version_args: Tuple[str, ...] = ("--version",)


CATALOG: List[MarketItem] = [
    MarketItem("git", "Git", "git", "Version control", "Distributed version control.", "45 MB", brew="git", apt="git"),
    MarketItem("node", "Node.js", "node", "Languages", "JavaScript runtime.", "90 MB", brew="node", apt="nodejs"),
    MarketItem("python", "Python", "python3", "Languages", "The Python interpreter.", "110 MB", brew="python", apt="python3"),
    MarketItem("go", "Go", "go", "Languages", "The Go programming language.", "180 MB", brew="go", apt="golang"),
    MarketItem("rust", "Rust", "rustc", "Languages", "Rust compiler and Cargo.", "320 MB", brew="rust"),
    MarketItem("deno", "Deno", "deno", "Languages", "Secure TypeScript runtime.", "40 MB", brew="deno"),
    MarketItem("bun", "Bun", "bun", "Languages", "Fast all in one JS runtime.", "60 MB", brew="oven-sh/bun/bun"),
    MarketItem("uv", "uv", "uv", "Languages", "Fast Python package manager.", "35 MB", brew="uv", pip="uv"),
    MarketItem("pnpm", "pnpm", "pnpm", "Languages", "Efficient Node package manager.", "20 MB", brew="pnpm", npm="pnpm"),
    MarketItem("docker", "Docker", "docker", "Containers", "Container build and runtime.", "600 MB", brew="docker", cask=True),
    MarketItem("kubectl", "kubectl", "kubectl", "Containers", "Kubernetes command line.", "50 MB", brew="kubernetes-cli", apt="kubectl"),
    MarketItem("helm", "Helm", "helm", "Containers", "Kubernetes package manager.", "50 MB", brew="helm"),
    MarketItem("terraform", "Terraform", "terraform", "Infrastructure", "Infrastructure as code.", "80 MB", brew="terraform"),
    MarketItem("awscli", "AWS CLI", "aws", "Cloud", "Amazon Web Services CLI.", "120 MB", brew="awscli", cask=False),
    MarketItem("azurecli", "Azure CLI", "az", "Cloud", "Microsoft Azure CLI.", "220 MB", brew="azure-cli"),
    MarketItem("gcloud", "Google Cloud SDK", "gcloud", "Cloud", "Google Cloud CLI.", "430 MB", brew="google-cloud-sdk", cask=True),
    MarketItem("supabase", "Supabase CLI", "supabase", "Cloud", "Supabase project CLI.", "40 MB", brew="supabase/tap/supabase"),
    MarketItem("sqlite", "SQLite", "sqlite3", "Databases", "Embedded SQL database.", "15 MB", brew="sqlite", apt="sqlite3"),
    MarketItem("postgres", "PostgreSQL", "psql", "Databases", "PostgreSQL client and server.", "50 MB", brew="postgresql", apt="postgresql"),
    MarketItem("redis", "Redis", "redis-server", "Databases", "In memory data store.", "10 MB", brew="redis", apt="redis"),
    MarketItem("gh", "GitHub CLI", "gh", "Developer", "GitHub from your terminal.", "40 MB", brew="gh", apt="gh"),
    MarketItem("claude", "Claude Code", "claude", "AI", "Anthropic's agentic CLI.", "120 MB", npm="@anthropic-ai/claude-code"),
    MarketItem("openai", "OpenAI CLI", "openai", "AI", "OpenAI command line client.", "30 MB", pip="openai"),
]

_BY_KEY = {i.key: i for i in CATALOG}


def get(key: str) -> Optional[MarketItem]:
    return _BY_KEY.get(key)


def installed(item: MarketItem) -> bool:
    return shutil.which(item.binary) is not None


def current_version(item: MarketItem) -> Optional[str]:
    if not installed(item):
        return None
    for args in (item.version_args, ("version",), ("-V",), ("-version",)):
        try:
            r = subprocess.run([item.binary, *args], capture_output=True, text=True, timeout=5)
            for raw in ((r.stdout or "") + "\n" + (r.stderr or "")).splitlines():
                line = raw.strip()
                if line and not line.startswith(("[", "-")) and any(c.isdigit() for c in line) \
                        and "usage" not in line.lower():
                    return line
        except Exception:
            continue
    return "installed"


def _pkg_manager() -> Optional[str]:
    for pm in ("brew", "apt-get", "dnf", "pacman"):
        if shutil.which(pm):
            return pm
    return None


def install_command(item: MarketItem) -> Optional[List[str]]:
    """The real command to install this item, or None if unsupported here."""
    pm = _pkg_manager()
    if pm == "brew" and item.brew:
        cmd = ["brew", "install"]
        if item.cask:
            cmd.append("--cask")
        return cmd + [item.brew]
    if item.npm and shutil.which("npm"):
        return ["npm", "install", "-g", item.npm]
    if item.pip and shutil.which("pipx"):
        return ["pipx", "install", item.pip]
    if item.pip and shutil.which("pip3"):
        return ["pip3", "install", "--user", item.pip]
    if pm in ("apt-get",) and item.apt:
        return ["sudo", "apt-get", "install", "-y", item.apt]
    if pm == "dnf" and item.apt:
        return ["sudo", "dnf", "install", "-y", item.apt]
    if pm == "pacman" and item.apt:
        return ["sudo", "pacman", "-S", "--noconfirm", item.apt]
    return None


def update_command(item: MarketItem) -> Optional[List[str]]:
    pm = _pkg_manager()
    if pm == "brew" and item.brew:
        return ["brew", "upgrade", item.brew.split("/")[-1]]
    if item.npm and shutil.which("npm"):
        return ["npm", "update", "-g", item.npm]
    return install_command(item)


def remove_command(item: MarketItem) -> Optional[List[str]]:
    pm = _pkg_manager()
    if pm == "brew" and item.brew:
        cmd = ["brew", "uninstall"]
        if item.cask:
            cmd.append("--cask")
        return cmd + [item.brew.split("/")[-1]]
    if item.npm and shutil.which("npm"):
        return ["npm", "uninstall", "-g", item.npm]
    if item.pip and shutil.which("pipx"):
        return ["pipx", "uninstall", item.pip]
    return None


def latest_version(item: MarketItem) -> Optional[str]:
    """Best effort latest version via `brew info` (only when brew is present)."""
    if not (shutil.which("brew") and item.brew):
        return None
    try:
        import json
        r = subprocess.run(
            ["brew", "info", "--json=v2", item.brew.split("/")[-1]],
            capture_output=True, text=True, timeout=8,
        )
        if r.returncode != 0:
            return None
        data = json.loads(r.stdout)
        formulae = data.get("formulae") or data.get("casks") or []
        if formulae:
            f = formulae[0]
            return (f.get("versions", {}) or {}).get("stable") or f.get("version")
    except Exception:
        return None
    return None
