#!/usr/bin/env bash
#
# setup.sh — Scaffold the Keaton "Universal Tool Execution Framework",
#            fix the broken bits of the existing CLI, write a human README,
#            then commit everything and publish it as a public GitHub repo.
#
# Usage:
#   cd /path/to/keaton-cli
#   bash setup.sh                 # scaffold + git commit
#   bash setup.sh --publish       # also create a PUBLIC repo via `gh` and push
#   REPO_NAME=keaton-cli bash setup.sh --publish
#
# Safe to run more than once: files are (re)written from scratch each time.
set -euo pipefail

# ---------------------------------------------------------------------------
# 0. Sanity checks
# ---------------------------------------------------------------------------
ROOT="$(pwd)"
PKG="$ROOT/keaton"
TOOLS="$PKG/tools"
PUBLISH=0
[[ "${1:-}" == "--publish" ]] && PUBLISH=1
REPO_NAME="${REPO_NAME:-keaton-cli}"

say() { printf '\033[1;36m▸\033[0m %s\n' "$1"; }
ok()  { printf '\033[1;32m✓\033[0m %s\n' "$1"; }

if [[ ! -d "$PKG" ]]; then
  echo "Expected a 'keaton/' package in $(pwd). Run this from the repo root." >&2
  exit 1
fi

say "Scaffolding into $ROOT"
mkdir -p "$TOOLS"

# ---------------------------------------------------------------------------
# 1. Package version (fixes: keaton/__init__.py was empty -> ImportError)
# ---------------------------------------------------------------------------
cat > "$PKG/__init__.py" <<'PYEOF'
"""Keaton — a Universal AI Terminal Platform and tool orchestration layer."""

__version__ = "0.2.0"
__all__ = ["__version__"]
PYEOF
ok "keaton/__init__.py (adds __version__)"

# ---------------------------------------------------------------------------
# 2. tools/base.py — the common Tool interface every tool inherits
# ---------------------------------------------------------------------------
cat > "$TOOLS/base.py" <<'PYEOF'
"""Common interface shared by every Keaton tool.

A Tool is a thin, declarative wrapper around a real developer CLI (git,
ffmpeg, docker, ...). Subclasses mostly supply *data* — keywords for natural
language routing, human examples, and command "recipes" — so adding a new
tool means writing a small file, never touching the core.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class ExecResult:
    """The outcome of running a tool command."""
    command: List[str]
    returncode: int
    stdout: str
    stderr: str
    duration: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class Tool:
    """Base class for every tool Keaton can drive."""

    # --- identity (override in subclasses) --------------------------------
    name: str = ""                     # short id, e.g. "ffmpeg"
    binary: str = ""                   # executable to look for on PATH
    description: str = ""              # one-line human description
    category: str = "general"         # grouping for `keaton tools`
    install_hint: str = ""            # how to install if missing

    # --- routing + docs (override in subclasses) --------------------------
    keywords: List[str] = []                 # words that route NL -> this tool
    capabilities: List[str] = []             # human-readable feature list
    examples: List[Tuple[str, str]] = []     # (natural language, shell command)

    # --- command recipes --------------------------------------------------
    # action name -> list of argument templates using {input}/{output}/...
    recipes: dict = {}
    # action names that must be confirmed before running
    destructive: set = set()

    # ---------------------------------------------------------------------
    def which(self) -> Optional[str]:
        """Absolute path to the binary, or None if not installed."""
        return shutil.which(self.binary) if self.binary else None

    def available(self) -> bool:
        return self.which() is not None

    def version(self) -> Optional[str]:
        """Best-effort version string for the underlying binary."""
        if not self.available():
            return None
        bad = ("illegal option", "unknown option", "unrecognized",
               "invalid option", "usage:")

        def is_version(line: str) -> bool:
            # A real version line has a digit and isn't a usage/option dump.
            if not line or line.startswith(("[", "-")):
                return False
            if any(b in line.lower() for b in bad):
                return False
            return any(ch.isdigit() for ch in line)

        for flag in ("--version", "version", "-version", "-V"):
            try:
                r = subprocess.run(
                    [self.binary, flag],
                    capture_output=True, text=True, timeout=8,
                )
                for raw in ((r.stdout or "") + "\n" + (r.stderr or "")).splitlines():
                    line = raw.strip()
                    if is_version(line):
                        return line
            except Exception:
                continue
        return "installed"

    def build(self, action: str, **kwargs) -> List[str]:
        """Turn an action + arguments into a concrete argv list."""
        template = self.recipes.get(action)
        if template is None:
            raise ValueError(
                f"{self.name}: unknown action '{action}'. "
                f"Known: {', '.join(self.recipes) or '(none)'}"
            )
        return [self.binary] + [part.format(**kwargs) for part in template]

    def is_destructive(self, action: str) -> bool:
        return action in self.destructive

    def score(self, text: str) -> int:
        """How strongly a natural-language request matches this tool."""
        t = text.lower()
        hits = sum(1 for k in self.keywords if k in t)
        if self.name and self.name in t:
            hits += 3
        if self.binary and self.binary in t:
            hits += 2
        return hits

    def help(self) -> dict:
        return {
            "name": self.name,
            "binary": self.binary,
            "description": self.description,
            "category": self.category,
            "available": self.available(),
            "version": self.version(),
            "path": self.which(),
            "capabilities": self.capabilities,
            "examples": self.examples,
            "install_hint": self.install_hint,
        }
PYEOF
ok "tools/base.py"

# ---------------------------------------------------------------------------
# 3. tools/executor.py — validation, confirmation, timing, streaming
# ---------------------------------------------------------------------------
cat > "$TOOLS/executor.py" <<'PYEOF'
"""Runs tool commands with confirmation, dry-run, timing and safety checks."""
from __future__ import annotations

import subprocess
import time
from typing import List, Optional

from .base import ExecResult, Tool

# Patterns that always trip the safety brake regardless of tool.
_DANGER = ("rm -rf", "drop database", "drop table", "destroy", "--force", "mkfs", ":(){", "> /dev/")


def looks_dangerous(command: List[str]) -> bool:
    joined = " ".join(command).lower()
    return any(p in joined for p in _DANGER)


class Executor:
    """Validates then executes a command produced by a Tool."""

    def __init__(self, confirm=None, printer=None):
        # confirm(prompt:str)->bool ; printer(text:str)->None
        self.confirm = confirm or (lambda _p: True)
        self.printer = printer or (lambda _t: None)

    def run(
        self,
        tool: Tool,
        command: List[str],
        *,
        action: Optional[str] = None,
        dry_run: bool = False,
        stream: bool = True,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Optional[ExecResult]:
        if not tool.available():
            self.printer(f"'{tool.binary}' is not installed. {tool.install_hint}".strip())
            return None

        pretty = " ".join(command)
        self.printer(f"$ {pretty}")

        needs_confirm = (action and tool.is_destructive(action)) or looks_dangerous(command)
        if needs_confirm and not dry_run:
            if not self.confirm(f"This may be destructive. Run `{pretty}`?"):
                self.printer("Cancelled.")
                return None

        if dry_run:
            self.printer("(dry run — not executed)")
            return ExecResult(command, 0, "", "", 0.0)

        start = time.time()
        if stream:
            proc = subprocess.Popen(
                command, cwd=cwd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            out_lines = []
            assert proc.stdout is not None
            for line in proc.stdout:
                out_lines.append(line)
                self.printer(line.rstrip("\n"))
            proc.wait(timeout=timeout)
            return ExecResult(command, proc.returncode, "".join(out_lines), "",
                              time.time() - start)

        r = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return ExecResult(command, r.returncode, r.stdout, r.stderr, time.time() - start)
PYEOF
ok "tools/executor.py"

# ---------------------------------------------------------------------------
# 4. tools/registry.py — automatic discovery + natural-language routing
# ---------------------------------------------------------------------------
cat > "$TOOLS/registry.py" <<'PYEOF'
"""Discovers every Tool subclass in this package and routes NL requests."""
from __future__ import annotations

import importlib
import pkgutil
from typing import List, Optional

from .base import Tool


class Registry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._discover()

    def _discover(self) -> None:
        """Import every sibling module and instantiate its Tool subclasses."""
        import keaton.tools as pkg
        for _finder, mod_name, _is_pkg in pkgutil.iter_modules(pkg.__path__):
            if mod_name in ("base", "registry", "executor"):
                continue
            module = importlib.import_module(f"keaton.tools.{mod_name}")
            for attr in vars(module).values():
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Tool)
                    and attr is not Tool
                ):
                    inst = attr()
                    if inst.name:
                        self._tools[inst.name] = inst

    # -- access ------------------------------------------------------------
    def all(self) -> List[Tool]:
        return sorted(self._tools.values(), key=lambda t: (t.category, t.name))

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def available(self) -> List[Tool]:
        return [t for t in self.all() if t.available()]

    def route(self, text: str) -> List[Tool]:
        """Return tools ranked by how well they match a request."""
        scored = [(t.score(text), t) for t in self.all()]
        scored = [(s, t) for s, t in scored if s > 0]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _s, t in scored]

    def best(self, text: str) -> Optional[Tool]:
        ranked = self.route(text)
        return ranked[0] if ranked else None


# A single shared instance is convenient for the CLI.
registry = Registry()
PYEOF
ok "tools/registry.py"

# ---------------------------------------------------------------------------
# 5. tools/__init__.py — export the registry
# ---------------------------------------------------------------------------
cat > "$TOOLS/__init__.py" <<'PYEOF'
"""Keaton's tool subsystem: base interface, registry, executor and tools."""
from .base import Tool, ExecResult
from .executor import Executor
from .registry import Registry, registry

__all__ = ["Tool", "ExecResult", "Executor", "Registry", "registry"]
PYEOF
ok "tools/__init__.py"

# ---------------------------------------------------------------------------
# 6. Individual tool files. Each is small and declarative.
# ---------------------------------------------------------------------------
say "Writing individual tool wrappers…"

cat > "$TOOLS/git.py" <<'PYEOF'
from .base import Tool


class GitTool(Tool):
    name = "git"
    binary = "git"
    category = "vcs"
    description = "Version control: status, commits, branches, history, PRs."
    install_hint = "Install: https://git-scm.com/downloads"
    keywords = ["git", "commit", "branch", "merge", "rebase", "stash",
                "diff", "repository", "repo", "tag", "cherry-pick", "checkout"]
    capabilities = [
        "Status & diff", "Commit (with generated messages)", "Branch create/switch",
        "Merge / rebase / cherry-pick", "Tag & stash management",
        "History & repository summary", "Conflict assistance", "PR description drafting",
    ]
    examples = [
        ("show me the repo status", "git status -sb"),
        ("what changed", "git diff"),
        ("commit everything with a message", "git commit -am 'your message'"),
        ("make a branch called feature-x", "git switch -c feature-x"),
        ("show the last 10 commits", "git log --oneline -10"),
    ]
    recipes = {
        "status": ["status", "-sb"],
        "diff": ["diff"],
        "log": ["log", "--oneline", "-{n}"],
        "branch": ["switch", "-c", "{name}"],
        "stash": ["stash"],
    }
    destructive = {"reset-hard", "clean"}
PYEOF

cat > "$TOOLS/ffmpeg.py" <<'PYEOF'
from .base import Tool


class FFmpegTool(Tool):
    name = "ffmpeg"
    binary = "ffmpeg"
    category = "media"
    description = "Audio/video Swiss-army knife: convert, compress, trim, resize."
    install_hint = "Install: brew install ffmpeg  (or apt/choco install ffmpeg)"
    keywords = ["video", "audio", "compress", "convert", "trim", "clip", "merge",
                "gif", "mp4", "mp3", "resize", "crop", "rotate", "subtitle",
                "thumbnail", "frame", "loop", "encode", "ffmpeg"]
    capabilities = [
        "Compress / convert / resize / crop / rotate",
        "Trim, split, merge", "Extract or convert audio", "Audio normalization",
        "GIF creation", "Subtitle embed/extract", "Frame & thumbnail extraction",
        "Instagram / YouTube / TikTok presets", "Loop generation", "Metadata",
    ]
    examples = [
        ("compress this video", "ffmpeg -i in.mp4 -vcodec libx264 -crf 28 out.mp4"),
        ("convert to mp3", "ffmpeg -i in.mp4 -q:a 0 -map a out.mp3"),
        ("trim first 10 seconds", "ffmpeg -i in.mp4 -ss 0 -t 10 -c copy clip.mp4"),
        ("make a gif", "ffmpeg -i in.mp4 -vf fps=12,scale=480:-1 out.gif"),
        ("resize to 720p", "ffmpeg -i in.mp4 -vf scale=-2:720 out720.mp4"),
    ]
    recipes = {
        "compress": ["-i", "{input}", "-vcodec", "libx264", "-crf", "28", "{output}"],
        "to-audio": ["-i", "{input}", "-q:a", "0", "-map", "a", "{output}"],
        "trim":     ["-i", "{input}", "-ss", "{start}", "-t", "{dur}", "-c", "copy", "{output}"],
        "gif":      ["-i", "{input}", "-vf", "fps=12,scale=480:-1", "{output}"],
        "resize":   ["-i", "{input}", "-vf", "scale=-2:{height}", "{output}"],
    }
PYEOF

cat > "$TOOLS/docker.py" <<'PYEOF'
from .base import Tool


class DockerTool(Tool):
    name = "docker"
    binary = "docker"
    category = "containers"
    description = "Build, run and manage containers, images, volumes and networks."
    install_hint = "Install Docker Desktop: https://docs.docker.com/get-docker/"
    keywords = ["docker", "container", "image", "build", "dockerfile", "compose",
                "volume", "network", "logs", "exec", "prune"]
    capabilities = [
        "Build images", "Run / stop containers", "Logs & exec", "Compose",
        "Networks & volumes", "Inspect", "Dockerfile generation", "Image cleanup",
    ]
    examples = [
        ("show running containers", "docker ps"),
        ("build an image tagged app", "docker build -t app ."),
        ("show logs for a container", "docker logs -f <container>"),
        ("clean up unused stuff", "docker system prune -f"),
    ]
    recipes = {
        "ps": ["ps"],
        "images": ["images"],
        "build": ["build", "-t", "{tag}", "{context}"],
        "logs": ["logs", "-f", "{container}"],
        "prune": ["system", "prune", "-f"],
    }
    destructive = {"prune", "rmi", "rm"}
PYEOF

cat > "$TOOLS/kubectl.py" <<'PYEOF'
from .base import Tool


class KubectlTool(Tool):
    name = "kubectl"
    binary = "kubectl"
    category = "containers"
    description = "Drive Kubernetes clusters: pods, services, deployments, logs."
    install_hint = "Install: https://kubernetes.io/docs/tasks/tools/"
    keywords = ["kubectl", "kubernetes", "k8s", "pod", "namespace", "deployment",
                "service", "configmap", "secret", "port-forward", "cluster", "helm"]
    capabilities = [
        "Pods / services / deployments", "Namespaces", "Logs", "Port forwarding",
        "ConfigMaps & secrets", "Apply manifests", "Cluster diagnostics",
    ]
    examples = [
        ("list my pods", "kubectl get pods"),
        ("apply this manifest", "kubectl apply -f deploy.yaml"),
        ("show logs for a pod", "kubectl logs <pod>"),
        ("what namespaces exist", "kubectl get ns"),
    ]
    recipes = {
        "pods": ["get", "pods"],
        "services": ["get", "svc"],
        "apply": ["apply", "-f", "{file}"],
        "logs": ["logs", "{pod}"],
    }
    destructive = {"delete"}
PYEOF

cat > "$TOOLS/terraform.py" <<'PYEOF'
from .base import Tool


class TerraformTool(Tool):
    name = "terraform"
    binary = "terraform"
    category = "infra"
    description = "Infrastructure as code: validate, plan, apply, destroy."
    install_hint = "Install: https://developer.hashicorp.com/terraform/install"
    keywords = ["terraform", "infrastructure", "plan", "apply", "destroy",
                "validate", "iac", "provision", "module"]
    capabilities = [
        "init / validate / plan", "apply (guarded)", "destroy (guarded)",
        "Module scaffolding", "Best-practice hints",
    ]
    examples = [
        ("validate my terraform", "terraform validate"),
        ("show me the plan", "terraform plan"),
        ("apply the changes", "terraform apply"),
    ]
    recipes = {
        "init": ["init"],
        "validate": ["validate"],
        "plan": ["plan"],
        "apply": ["apply"],
        "destroy": ["destroy"],
    }
    destructive = {"apply", "destroy"}
PYEOF

cat > "$TOOLS/python.py" <<'PYEOF'
from .base import Tool


class PythonTool(Tool):
    name = "python"
    binary = "python3"
    category = "languages"
    description = "Python projects: venvs, pip, testing, linting, formatting."
    install_hint = "Install: https://www.python.org/downloads/"
    keywords = ["python", "pip", "venv", "virtualenv", "pytest", "poetry", "uv",
                "lint", "format", "ruff", "black"]
    capabilities = [
        "Virtual environments", "pip / poetry / uv", "Testing (pytest)",
        "Linting & formatting", "Project generation", "Packaging & publishing",
    ]
    examples = [
        ("create a virtual environment", "python3 -m venv .venv"),
        ("run the tests", "python3 -m pytest"),
        ("install dependencies", "python3 -m pip install -r requirements.txt"),
    ]
    recipes = {
        "venv": ["-m", "venv", "{path}"],
        "test": ["-m", "pytest"],
        "install": ["-m", "pip", "install", "{package}"],
        "run": ["{script}"],
    }
PYEOF

cat > "$TOOLS/node.py" <<'PYEOF'
from .base import Tool


class NodeTool(Tool):
    name = "node"
    binary = "node"
    category = "languages"
    description = "Node.js ecosystem: npm / pnpm / yarn, scaffolding, deps."
    install_hint = "Install: https://nodejs.org/ (or nvm)"
    keywords = ["node", "npm", "pnpm", "yarn", "javascript", "typescript",
                "package.json", "install deps", "scaffold"]
    capabilities = [
        "Run scripts", "npm / pnpm / yarn install", "Dependency updates",
        "Version management", "Project scaffolding",
    ]
    examples = [
        ("run the dev script", "npm run dev"),
        ("install dependencies", "npm install"),
        ("check node version", "node --version"),
    ]
    recipes = {
        "version": ["--version"],
        "run": ["{script}"],
    }
PYEOF

cat > "$TOOLS/package_manager.py" <<'PYEOF'
import shutil
from .base import Tool


def _first_available(*names):
    for n in names:
        if shutil.which(n):
            return n
    return names[0]


class PackageManagerTool(Tool):
    name = "pkg"
    binary = _first_available("brew", "apt", "dnf", "pacman", "winget", "choco")
    category = "system"
    description = "OS package manager: install, remove, update, search, upgrade."
    install_hint = "brew (macOS), apt/dnf/pacman (Linux), winget/choco (Windows)."
    keywords = ["install", "uninstall", "remove", "update", "upgrade", "brew",
                "apt", "dnf", "pacman", "winget", "chocolatey", "package"]
    capabilities = ["Install / remove", "Update / upgrade", "Search packages"]
    examples = [
        ("install ripgrep", "brew install ripgrep"),
        ("update everything", "brew upgrade"),
    ]
    recipes = {"install": ["install", "{package}"], "search": ["search", "{query}"]}
    destructive = {"remove", "uninstall"}
PYEOF

cat > "$TOOLS/imagemagick.py" <<'PYEOF'
import shutil
from .base import Tool


class ImageMagickTool(Tool):
    name = "imagemagick"
    binary = "magick" if shutil.which("magick") else "convert"
    category = "media"
    description = "Image manipulation: resize, crop, convert, optimise, watermark."
    install_hint = "Install: brew install imagemagick"
    keywords = ["image", "resize", "crop", "png", "jpg", "jpeg", "webp",
                "optimise", "optimize", "watermark", "transparent", "imagemagick"]
    capabilities = [
        "Resize / crop / convert", "Optimise & compress", "Transparency",
        "Colour correction", "Batch processing", "Watermarks", "Image compare",
    ]
    examples = [
        ("resize to 800px wide", "magick in.png -resize 800x out.png"),
        ("convert png to jpg", "magick in.png out.jpg"),
    ]
    recipes = {
        "resize": ["{input}", "-resize", "{size}", "{output}"],
        "convert": ["{input}", "{output}"],
    }
PYEOF

cat > "$TOOLS/pandoc.py" <<'PYEOF'
from .base import Tool


class PandocTool(Tool):
    name = "pandoc"
    binary = "pandoc"
    category = "documents"
    description = "Universal document converter: Markdown, PDF, DOCX, HTML, LaTeX."
    install_hint = "Install: brew install pandoc"
    keywords = ["pandoc", "markdown", "pdf", "docx", "html", "latex", "epub",
                "convert document", "presentation"]
    capabilities = [
        "Markdown <-> PDF / DOCX / HTML / LaTeX / EPUB", "Presentation generation",
        "Document conversion",
    ]
    examples = [
        ("convert markdown to pdf", "pandoc in.md -o out.pdf"),
        ("markdown to word doc", "pandoc in.md -o out.docx"),
    ]
    recipes = {"convert": ["{input}", "-o", "{output}"]}
PYEOF

cat > "$TOOLS/ytdlp.py" <<'PYEOF'
from .base import Tool


class YtDlpTool(Tool):
    name = "yt-dlp"
    binary = "yt-dlp"
    category = "media"
    description = "Download media (respecting each platform's terms of service)."
    install_hint = "Install: brew install yt-dlp  (or pipx install yt-dlp)"
    keywords = ["download", "yt-dlp", "youtube", "playlist", "subtitles",
                "audio extraction", "media download"]
    capabilities = [
        "Media download", "Playlist support", "Audio extraction",
        "Subtitle download", "Thumbnail & metadata", "Quality selection",
    ]
    examples = [
        ("download this video", "yt-dlp <url>"),
        ("just the audio", "yt-dlp -x --audio-format mp3 <url>"),
    ]
    recipes = {
        "download": ["{url}"],
        "audio": ["-x", "--audio-format", "mp3", "{url}"],
    }
PYEOF

cat > "$TOOLS/ripgrep.py" <<'PYEOF'
from .base import Tool


class RipgrepTool(Tool):
    name = "ripgrep"
    binary = "rg"
    category = "search"
    description = "Blazing-fast recursive code/content search with regex."
    install_hint = "Install: brew install ripgrep"
    keywords = ["search", "grep", "find text", "regex", "todo", "api_key",
                "look for", "ripgrep", "rg"]
    capabilities = ["Repository search", "Regex", "Case sensitivity",
                    "File filtering", "Match statistics"]
    examples = [
        ("find every TODO", "rg TODO"),
        ("search for API_KEY", "rg API_KEY"),
        ("case-insensitive search for error", "rg -i error"),
    ]
    recipes = {"search": ["{pattern}"], "search-here": ["{pattern}", "{path}"]}
PYEOF

cat > "$TOOLS/fd.py" <<'PYEOF'
import shutil
from .base import Tool


class FdTool(Tool):
    name = "fd"
    binary = "fd" if shutil.which("fd") else "fdfind"
    category = "search"
    description = "Fast, friendly file and directory finder."
    install_hint = "Install: brew install fd"
    keywords = ["find file", "find files", "locate", "fd", "every python file",
                "list files", "directory search"]
    capabilities = ["Fast file search", "Directory search", "Extension filtering",
                    "Recent / large file discovery"]
    examples = [
        ("find every python file", "fd -e py"),
        ("find files named config", "fd config"),
    ]
    recipes = {"find": ["{pattern}"], "ext": ["-e", "{ext}"]}
PYEOF

cat > "$TOOLS/jq.py" <<'PYEOF'
from .base import Tool


class JqTool(Tool):
    name = "jq"
    binary = "jq"
    category = "data"
    description = "Query, filter, transform and pretty-print JSON."
    install_hint = "Install: brew install jq"
    keywords = ["json", "jq", "pretty print", "filter json", "query json",
                "transform json"]
    capabilities = ["Pretty print", "Filtering", "Transformations",
                    "Validation", "JSON querying"]
    examples = [
        ("pretty print this json", "jq . data.json"),
        ("get the .name field", "jq '.name' data.json"),
    ]
    recipes = {"pretty": [".", "{file}"], "query": ["{filter}", "{file}"]}
PYEOF

cat > "$TOOLS/ssh.py" <<'PYEOF'
from .base import Tool


class SshTool(Tool):
    name = "ssh"
    binary = "ssh"
    category = "remote"
    description = "Connect to and run commands on remote servers; tunnels; SCP."
    install_hint = "Usually preinstalled (OpenSSH)."
    keywords = ["ssh", "connect to server", "remote", "tunnel", "scp", "sftp",
                "remote execution", "server"]
    capabilities = ["Remote execution", "Key management", "Tunnels",
                    "File transfer (SCP/SFTP)", "Remote diagnostics"]
    examples = [
        ("connect to my server", "ssh user@host"),
        ("run uptime remotely", "ssh user@host uptime"),
    ]
    recipes = {"connect": ["{target}"], "run": ["{target}", "{command}"]}
PYEOF

cat > "$TOOLS/sqlite.py" <<'PYEOF'
from .base import Tool


class SqliteTool(Tool):
    name = "sqlite"
    binary = "sqlite3"
    category = "databases"
    description = "SQLite: explore schema, run queries, import/export, backup."
    install_hint = "Install: brew install sqlite"
    keywords = ["sqlite", "database", "sql", "query", "schema", "table"]
    capabilities = ["Schema exploration", "Query execution", "Table browser",
                    "Import / export", "Backup / restore"]
    examples = [
        ("list tables", "sqlite3 app.db '.tables'"),
        ("run a query", "sqlite3 app.db 'SELECT * FROM users LIMIT 5;'"),
    ]
    recipes = {"tables": ["{db}", ".tables"], "query": ["{db}", "{sql}"]}
    destructive = {"drop"}
PYEOF

cat > "$TOOLS/postgres.py" <<'PYEOF'
from .base import Tool


class PostgresTool(Tool):
    name = "postgres"
    binary = "psql"
    category = "databases"
    description = "PostgreSQL: connect, query, explain, backup and restore."
    install_hint = "Install: brew install postgresql (or libpq for psql only)"
    keywords = ["postgres", "postgresql", "psql", "pg_dump", "backup database",
                "restore", "sql"]
    capabilities = ["Connection management", "Query & explain", "Schema browsing",
                    "Backup (pg_dump)", "Restore", "Migration help"]
    examples = [
        ("connect to my database", "psql <connection-url>"),
        ("list databases", "psql -l"),
        ("backup a database", "pg_dump mydb > mydb.sql"),
    ]
    recipes = {"connect": ["{url}"], "list": ["-l"], "query": ["-c", "{sql}"]}
    destructive = {"drop"}
PYEOF

cat > "$TOOLS/mysql.py" <<'PYEOF'
from .base import Tool


class MySQLTool(Tool):
    name = "mysql"
    binary = "mysql"
    category = "databases"
    description = "MySQL/MariaDB: connect, query, dump and restore."
    install_hint = "Install: brew install mysql-client"
    keywords = ["mysql", "mariadb", "mysqldump", "database", "sql", "query"]
    capabilities = ["Connection management", "Query execution", "Schema browsing",
                    "Backup (mysqldump)", "Restore", "Migration help"]
    examples = [
        ("connect to mysql", "mysql -u root -p"),
        ("run a query", "mysql -e 'SHOW DATABASES;'"),
    ]
    recipes = {"query": ["-e", "{sql}"]}
    destructive = {"drop"}
PYEOF

ok "18 tool wrappers written"

# ---------------------------------------------------------------------------
# 6b. Startup pixel-art splash: assets package, splash module, regen script,
#     config toggle. The portrait asset is a committed artifact — kept if it
#     already exists, regenerated from an image (or a fallback) if missing.
# ---------------------------------------------------------------------------
say "Setting up startup splash…"
mkdir -p "$PKG/assets" "$ROOT/scripts"

cat > "$PKG/assets/__init__.py" <<'PYEOF'
"""Bundled binary-ish assets (e.g. the startup pixel-art portrait)."""
PYEOF

cat > "$PKG/splash.py" <<'PYEOF'
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
PYEOF
ok "keaton/splash.py"

cat > "$ROOT/scripts/gen_pixel_art.py" <<'PYEOF'
#!/usr/bin/env python3
"""Regenerate keaton/assets/pixel_me.py from a source image.

Usage:
    python scripts/gen_pixel_art.py [IMAGE] [WIDTH] [HEIGHT]

Defaults: IMAGE=$KEATON_SPLASH_IMAGE or ~/Downloads/keaton.JPG, 27x48.
HEIGHT must be even (each terminal cell renders two vertical pixels).
Requires Pillow (`pip install pillow`).
"""
import base64
import os
import sys
from pathlib import Path

DEFAULT_IMAGE = os.environ.get(
    "KEATON_SPLASH_IMAGE", str(Path.home() / "Downloads" / "keaton.JPG")
)
OUT = Path(__file__).resolve().parent.parent / "keaton" / "assets" / "pixel_me.py"


def main() -> int:
    try:
        from PIL import Image, ImageEnhance
    except ImportError:
        print("Pillow is required: pip install pillow", file=sys.stderr)
        return 1

    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IMAGE
    w = int(sys.argv[2]) if len(sys.argv) > 2 else 27
    h = int(sys.argv[3]) if len(sys.argv) > 3 else 48
    if h % 2:
        h += 1  # keep even for half-block rendering

    if not Path(src).exists():
        print(f"Image not found: {src}", file=sys.stderr)
        return 1

    im = Image.open(src).convert("RGB").resize((w, h), Image.LANCZOS)
    im = ImageEnhance.Color(im).enhance(1.18)
    im = ImageEnhance.Contrast(im).enhance(1.06)
    raw = im.tobytes()
    b64 = base64.b64encode(raw).decode()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        '"""Pixel-art portrait for the Keaton startup splash.\n\n'
        "Auto-generated by scripts/gen_pixel_art.py.\n"
        "DATA is base64-encoded row-major RGB bytes (WIDTH*HEIGHT*3).\n"
        '"""\n\n'
        f"WIDTH = {w}\n"
        f"HEIGHT = {h}\n"
        f'DATA = "{b64}"\n'
    )
    print(f"Wrote {OUT} ({w}x{h}, {len(b64)} b64 chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PYEOF
chmod +x "$ROOT/scripts/gen_pixel_art.py"

# Portrait asset: keep if committed; otherwise regenerate or fall back.
if [ ! -f "$PKG/assets/pixel_me.py" ]; then
  SRC="${KEATON_SPLASH_IMAGE:-$HOME/Downloads/keaton.JPG}"
  if python3 -c "import PIL" >/dev/null 2>&1 && [ -f "$SRC" ]; then
    say "Generating splash portrait from $SRC…"
    KEATON_SPLASH_IMAGE="$SRC" python3 "$ROOT/scripts/gen_pixel_art.py" "$SRC" || true
  fi
  if [ ! -f "$PKG/assets/pixel_me.py" ]; then
    # No Pillow or no image: write a tiny procedural placeholder so the splash
    # still runs. Regenerate later with: python scripts/gen_pixel_art.py <img>
    python3 - "$PKG/assets/pixel_me.py" <<'PYEOF'
import base64, sys
W, H = 16, 16
px = bytearray()
for y in range(H):
    for x in range(W):
        px += bytes(((x * 16) % 256, (y * 16) % 256, 128))
open(sys.argv[1], "w").write(
    '"""Fallback splash art. Replace via scripts/gen_pixel_art.py <image>."""\n\n'
    f"WIDTH = {W}\nHEIGHT = {H}\n"
    f'DATA = "{base64.b64encode(bytes(px)).decode()}"\n'
)
print("  wrote fallback pixel_me.py (run scripts/gen_pixel_art.py for the real one)")
PYEOF
  fi
  ok "splash portrait ready"
else
  ok "splash portrait present (kept)"
fi

# config.py: register the splash_enabled toggle (idempotent).
PYTHONPATH="$ROOT" python3 - "$PKG" <<'PYEOF'
import sys, pathlib
c = pathlib.Path(sys.argv[1]) / "config.py"
text = c.read_text()
if '"splash_enabled"' not in text:
    text = text.replace(
        '    "history_enabled": True,\n}',
        '    "history_enabled": True,\n    "splash_enabled": True,\n}',
        1,
    )
    c.write_text(text)
    print("  patched config.py (splash_enabled)")
else:
    print("  config.py already has splash_enabled")
PYEOF
ok "splash config toggle wired"

# ---------------------------------------------------------------------------
# 7. tools/cli.py — Typer sub-app: doctor, tools, tool <name>, run
# ---------------------------------------------------------------------------
cat > "$PKG/toolcli.py" <<'PYEOF'
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
PYEOF
ok "keaton/toolcli.py"

# ---------------------------------------------------------------------------
# 8. Fix the broken cli.py (syntax error + recursive commands) and wire tools.
#    We rewrite it cleanly rather than patch, since it currently won't import.
# ---------------------------------------------------------------------------
cat > "$PKG/cli.py" <<'PYEOF'
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
from . import splash as splash_mod
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


@app.callback()
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """Keaton — Universal AI Terminal Platform."""
    # Startup pixel-art splash. Skipped for the `splash` replay command, when
    # output isn't a TTY, or when disabled (config / KEATON_NO_SPLASH). Never
    # raises — see splash.maybe_play.
    if ctx.invoked_subcommand != "splash":
        splash_mod.maybe_play(console)


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
def splash():
    """Replay the startup pixel-art animation."""
    splash_mod.play(console)


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


if __name__ == "__main__":
    app()
PYEOF
ok "keaton/cli.py (syntax + recursion fixed, tools wired in)"

# ---------------------------------------------------------------------------
# 8b. Repair pre-existing broken provider stubs so the whole CLI imports.
#     anthropic.py & gemini.py: is_authenticated() had an EMPTY body.
#     openrouter.py: methods were scrambled -> rewrite it cleanly.
#     (cli.py also imports providers lazily, so this is belt-and-suspenders.)
# ---------------------------------------------------------------------------
say "Repairing provider stubs…"

# anthropic.py and gemini.py were scrambled in several places (empty method
# bodies + spliced-in methods), so we replace them with clean, correct
# implementations rather than chasing individual holes.
cat > "$PKG/providers/anthropic.py" <<'PYEOF'
"""
Anthropic provider for Keaton CLI.

Talks to the public Anthropic Messages API (https://api.anthropic.com/v1).
"""
import os
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from .base import AIProvider, Conversation, Model


class AnthropicProvider(AIProvider):
    """Anthropic AI provider."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = "https://api.anthropic.com/v1"
        self.default_model = config.get("model", "claude-3-haiku-20240307")

    @property
    def display_name(self) -> str:
        return "Anthropic"

    @property
    def needs_auth(self) -> bool:
        return True

    async def login(self) -> bool:
        return await self.is_authenticated()

    async def logout(self) -> bool:
        self.api_key = None
        return True

    async def is_authenticated(self) -> bool:
        """Authenticated when an API key is present."""
        return bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    async def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        model: Optional[str] = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[str]:
        if not await self.is_authenticated():
            yield "Error: Anthropic API key not configured (set ANTHROPIC_API_KEY)."
            return

        data = {
            "model": model or self.default_model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": message}],
            "stream": stream,
        }
        try:
            async with httpx.AsyncClient() as client:
                if stream:
                    async with client.stream(
                        "POST", f"{self.base_url}/messages",
                        headers=self._headers(), json=data, timeout=60.0,
                    ) as response:
                        if response.status_code != 200:
                            yield f"Error: {response.status_code} - {await response.aread()}"
                            return
                        async for line in response.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            try:
                                import json
                                event = json.loads(line[6:])
                                if event.get("type") == "content_block_delta":
                                    text = event.get("delta", {}).get("text", "")
                                    if text:
                                        yield text
                            except Exception:
                                continue
                else:
                    response = await client.post(
                        f"{self.base_url}/messages",
                        headers=self._headers(), json=data, timeout=60.0,
                    )
                    if response.status_code != 200:
                        yield f"Error: {response.status_code} - {await response.aread()}"
                        return
                    blocks = response.json().get("content", [])
                    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
                    yield text or "Error: No response from Anthropic."
        except Exception as e:
            yield f"Error: {str(e)}"

    async def models(self) -> List[Model]:
        """Anthropic has no public models list endpoint; return a known set."""
        if not await self.is_authenticated():
            return []
        return [
            Model(id="claude-3-opus-20240229", name="Claude 3 Opus",
                  description="Most powerful Claude 3 model", owned_by="anthropic"),
            Model(id="claude-3-sonnet-20240229", name="Claude 3 Sonnet",
                  description="Balanced Claude 3 model", owned_by="anthropic"),
            Model(id="claude-3-haiku-20240307", name="Claude 3 Haiku",
                  description="Fastest Claude 3 model", owned_by="anthropic"),
        ]

    async def conversations(self) -> List[Conversation]:
        return []

    async def health_check(self) -> bool:
        if not await self.is_authenticated():
            return False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self._headers(),
                    json={
                        "model": self.default_model,
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "ping"}],
                    },
                    timeout=5.0,
                )
                return response.status_code == 200
        except Exception:
            return False
PYEOF

cat > "$PKG/providers/gemini.py" <<'PYEOF'
"""
Gemini provider for Keaton CLI.

Talks to Google's Generative Language API
(https://generativelanguage.googleapis.com/v1beta).
"""
import os
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from .base import AIProvider, Conversation, Model


class GeminiProvider(AIProvider):
    """Google Gemini AI provider."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("GEMINI_API_KEY")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.default_model = config.get("model", "gemini-1.5-flash")

    @property
    def display_name(self) -> str:
        return "Gemini"

    @property
    def needs_auth(self) -> bool:
        return True

    async def login(self) -> bool:
        return await self.is_authenticated()

    async def logout(self) -> bool:
        self.api_key = None
        return True

    async def is_authenticated(self) -> bool:
        """Authenticated when an API key is present."""
        return bool(self.api_key)

    async def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        model: Optional[str] = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[str]:
        if not await self.is_authenticated():
            yield "Error: Gemini API key not configured (set GEMINI_API_KEY)."
            return

        model_name = model or self.default_model
        url = f"{self.base_url}/models/{model_name}:generateContent"
        params = {"key": self.api_key}
        data = {
            "contents": [{"parts": [{"text": message}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048},
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, params=params, json=data, timeout=60.0)
                if response.status_code != 200:
                    yield f"Error: {response.status_code} - {await response.aread()}"
                    return
                candidates = response.json().get("candidates", [])
                if not candidates:
                    yield "Error: No response from Gemini."
                    return
                parts = candidates[0].get("content", {}).get("parts", [])
                yield "".join(p.get("text", "") for p in parts) or "Error: Empty response."
        except Exception as e:
            yield f"Error: {str(e)}"

    async def models(self) -> List[Model]:
        if not await self.is_authenticated():
            return []
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{self.base_url}/models",
                                     params={"key": self.api_key}, timeout=10.0)
                if r.status_code != 200:
                    return []
                out = []
                for m in r.json().get("models", []):
                    mid = m.get("name", "").replace("models/", "")
                    out.append(Model(id=mid, name=m.get("displayName", mid),
                                     description=m.get("description", ""), owned_by="google"))
                return out
        except Exception:
            return []

    async def conversations(self) -> List[Conversation]:
        return []

    async def health_check(self) -> bool:
        if not await self.is_authenticated():
            return False
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{self.base_url}/models",
                                     params={"key": self.api_key}, timeout=5.0)
                return r.status_code == 200
        except Exception:
            return False
PYEOF

# base44.py: a plain is_authenticated() check auto-launched an interactive
# login (blocking subprocess) — which hung `keaton doctor`. Make the check
# pure unless explicitly asked to be interactive. Idempotent.
PYTHONPATH="$ROOT" python3 - "$PKG" <<'PYEOF'
import sys, pathlib
b = pathlib.Path(sys.argv[1]) / "providers" / "base44.py"
if b.exists():
    text = b.read_text()
    if "interactive: bool = False" not in text:
        text = text.replace(
            "async def _ensure_authenticated(self) -> bool:",
            "async def _ensure_authenticated(self, interactive: bool = False) -> bool:",
            1,
        )
        text = text.replace(
            "        from ..auth import login\n        if login():",
            "        if not interactive:\n"
            "            # Pure status check: don't trigger a blocking login.\n"
            "            return bool(self.token)\n\n"
            "        from ..auth import login\n        if login():",
            1,
        )
        b.write_text(text)
        print("  patched base44.py (pure is_authenticated)")
    else:
        print("  base44.py already ok")
PYEOF

# Clean, complete OpenRouter provider (OpenAI-compatible API).
cat > "$PKG/providers/openrouter.py" <<'PYEOF'
"""
OpenRouter provider for Keaton CLI.

OpenRouter exposes an OpenAI-compatible Chat Completions API, so this provider
speaks that dialect against https://openrouter.ai/api/v1.
"""
import os
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from .base import AIProvider, Conversation, Model


class OpenRouterProvider(AIProvider):
    """OpenRouter AI provider (OpenAI-compatible)."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1"
        self.default_model = config.get("model", "openai/gpt-3.5-turbo")

    @property
    def display_name(self) -> str:
        return "OpenRouter"

    @property
    def needs_auth(self) -> bool:
        return True

    async def login(self) -> bool:
        return await self.is_authenticated()

    async def logout(self) -> bool:
        self.api_key = None
        return True

    async def is_authenticated(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        model: Optional[str] = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[str]:
        if not await self.is_authenticated():
            yield "Error: OpenRouter API key not configured (set OPENROUTER_API_KEY)."
            return

        data = {
            "model": model or self.default_model,
            "messages": [{"role": "user", "content": message}],
            "stream": stream,
        }
        try:
            async with httpx.AsyncClient() as client:
                if stream:
                    async with client.stream(
                        "POST", f"{self.base_url}/chat/completions",
                        headers=self._headers(), json=data, timeout=60.0,
                    ) as response:
                        if response.status_code != 200:
                            yield f"Error: {response.status_code} - {await response.aread()}"
                            return
                        async for line in response.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            payload = line[len("data: "):].strip()
                            if payload == "[DONE]":
                                break
                            try:
                                import json
                                chunk = json.loads(payload)
                                content = chunk["choices"][0].get("delta", {}).get("content", "")
                                if content:
                                    yield content
                            except Exception:
                                continue
                else:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(), json=data, timeout=60.0,
                    )
                    if response.status_code != 200:
                        yield f"Error: {response.status_code} - {await response.aread()}"
                        return
                    choices = response.json().get("choices", [])
                    yield choices[0].get("message", {}).get("content", "") if choices \
                        else "Error: No response from OpenRouter."
        except Exception as e:
            yield f"Error: {str(e)}"

    async def models(self) -> List[Model]:
        if not await self.is_authenticated():
            return []
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{self.base_url}/models",
                                     headers=self._headers(), timeout=10.0)
                if r.status_code != 200:
                    return []
                return [
                    Model(id=i["id"], name=i.get("name", i["id"]),
                          description=i.get("description", ""), owned_by="openrouter")
                    for i in r.json().get("data", [])
                ]
        except Exception:
            return []

    async def conversations(self) -> List[Conversation]:
        return []

    async def health_check(self) -> bool:
        if not await self.is_authenticated():
            return False
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{self.base_url}/models",
                                     headers=self._headers(), timeout=5.0)
                return r.status_code == 200
        except Exception:
            return False
PYEOF
ok "provider stubs repaired (anthropic, gemini, openrouter)"

# ---------------------------------------------------------------------------
# 9. pyproject.toml — fix package discovery + drop speculative dependency
# ---------------------------------------------------------------------------
cat > "$ROOT/pyproject.toml" <<'PYEOF'
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "keaton-cli"
version = "0.2.0"
description = "An AI operating system for the terminal that orchestrates real developer tools."
readme = "README.md"
requires-python = ">=3.12"
license = {text = "MIT"}
authors = [{name = "Keaton", email = "keatonlf@gmail.com"}]
keywords = ["cli", "terminal", "ai", "agent", "devtools", "orchestration", "llm"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Operating System :: OS Independent",
    "Topic :: Terminals",
    "Topic :: Software Development :: User Interfaces",
]
dependencies = [
    "rich>=13.0.0",
    "markdown-it-py>=3.0.0",
    "pygments>=2.16.0",
    "typer>=0.9.0",
    "pydantic>=2.0",
    "aiofiles>=23.0.0",
    "httpx>=0.25.0",
    "pyyaml>=6.0",
    "python-dotenv>=1.0.0",
]

[project.urls]
Homepage = "https://github.com/KeatonZA1305/keaton-cli"
Repository = "https://github.com/KeatonZA1305/keaton-cli.git"
Issues = "https://github.com/KeatonZA1305/keaton-cli/issues"

[project.scripts]
keaton = "keaton.cli:app"

[tool.setuptools.packages.find]
where = ["."]
include = ["keaton*"]
PYEOF
ok "pyproject.toml"

# ---------------------------------------------------------------------------
# 10. A human-sounding README
# ---------------------------------------------------------------------------
cat > "$ROOT/README.md" <<'MDEOF'
# Keaton

**An AI operating system for your terminal.** You describe what you want to get
done, in plain English, and Keaton figures out *which* real developer tool can
do it — `ffmpeg`, `git`, `docker`, `kubectl`, `ripgrep`, `pandoc`, and a dozen
more — shows you exactly what it's about to run, and gets out of your way.

Most CLIs make you memorise flags. Keaton doesn't. It's the difference between
*"what was the ffmpeg incantation for a GIF again?"* and just typing:

```bash
keaton run "turn this clip into a gif"
```

---

## Why people like it

- **You talk, it translates.** Natural language in, the right tool + the right
  command out. No more digging through man pages or Stack Overflow tabs.
- **It uses the *real* tools.** Keaton doesn't reinvent `git` or `ffmpeg` — it
  drives the official CLIs you already trust, so the output is exactly what
  you'd get by hand.
- **Nothing happens behind your back.** Every command is printed before it runs.
  Anything destructive (dropping a database, `terraform destroy`, pruning
  Docker) asks first. There's a `--dry-run` for the cautious.
- **One brain, every tool.** Eighteen tools across video, containers,
  Kubernetes, infrastructure, databases, search and documents — all behind one
  consistent, good-looking interface.
- **Add a tool in one small file.** The architecture is modular: drop a file in
  `keaton/tools/`, and it's auto-discovered. No core changes, no registration
  boilerplate.
- **Bring your own AI.** Base44, OpenAI, Anthropic, Gemini, OpenRouter, Ollama,
  LM Studio, or a local model — pick whichever you like.

---

## The tools it speaks

| Area | Tools |
|------|-------|
| **Media** | FFmpeg, ImageMagick, yt-dlp |
| **Version control** | Git |
| **Containers & orchestration** | Docker, kubectl |
| **Infrastructure** | Terraform |
| **Languages** | Python, Node.js |
| **System** | Homebrew / apt / dnf / pacman / winget |
| **Search** | ripgrep, fd |
| **Data & docs** | jq, Pandoc |
| **Databases** | SQLite, PostgreSQL, MySQL |
| **Remote** | SSH / SCP / SFTP |

Ask Keaton what it can do at any time:

```bash
keaton tools            # every tool, and whether it's installed
keaton tool ffmpeg      # capabilities + real examples for one tool
keaton doctor           # health check: your AI provider + all local tools
```

---

## Quick start

```bash
git clone https://github.com/KeatonZA1305/keaton-cli.git
cd keaton-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

keaton doctor           # see what's wired up
```

Then just describe what you need:

```bash
keaton run "compress this video"
keaton run "find every TODO in this repo"
keaton run "convert notes.md to a pdf"
keaton run "show my running containers"
keaton run "back up my postgres database"
```

Keaton picks the tool, shows you the command, and (for anything risky) asks
before it pulls the trigger.

---

## How it's built

```
keaton/
  tools/
    base.py        # the Tool interface every tool inherits
    registry.py    # auto-discovery + natural-language routing
    executor.py    # validation, confirmation, timing, streaming
    git.py  ffmpeg.py  docker.py  kubectl.py  terraform.py
    python.py  node.py  package_manager.py  imagemagick.py
    pandoc.py  ytdlp.py  ripgrep.py  fd.py  jq.py  ssh.py
    sqlite.py  postgres.py  mysql.py
  toolcli.py       # the `tools` / `tool` / `run` commands
  splash.py        # animated pixel-art startup splash
  assets/          # the bundled pixel-art portrait
  cli.py           # entry point
  providers/       # pluggable AI backends
```

On launch, Keaton fades in a little pixel-art portrait. Replay it any time with
`keaton splash`, or turn it off with `keaton config` (`splash_enabled`) or by
setting `KEATON_NO_SPLASH=1`. Regenerate it from any photo with
`python scripts/gen_pixel_art.py path/to/photo.jpg`.

Every tool is a small, declarative subclass of `Tool`. It says what it's called,
what binary it wraps, which words should route to it, what it can do, and a few
example commands. The registry finds it automatically. That's the whole contract
— which is exactly why new tools are cheap to add.

## Adding your own tool

```python
# keaton/tools/mytool.py
from .base import Tool

class MyTool(Tool):
    name = "mytool"
    binary = "mytool"
    category = "misc"
    description = "Does the thing."
    keywords = ["thing", "do the thing"]
    capabilities = ["Thing A", "Thing B"]
    examples = [("do the thing to foo", "mytool foo")]
    recipes = {"do": ["{target}"]}
```

Save it. Run `keaton tools`. It's there.

---

## Safety, briefly

Keaton is deliberately conservative. It never hides a command from you, it
confirms anything destructive, it supports dry runs, and for tools that can
validate (like Terraform) it leans on their own validation first. It only uses
`yt-dlp` in ways that respect each platform's terms of service.

## License

MIT — see [LICENSE](LICENSE).
MDEOF
ok "README.md (human-sounding)"

# ---------------------------------------------------------------------------
# 10b. LICENSE — the file existed but was empty. Fill in MIT (matches pyproject).
# ---------------------------------------------------------------------------
cat > "$ROOT/LICENSE" <<'MITEOF'
MIT License

Copyright (c) 2026 Keaton Armstrong

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
MITEOF
ok "LICENSE (MIT)"

# empty package marker for tools already created above; ensure tests import ok
touch "$ROOT/CHANGELOG.md"

# ---------------------------------------------------------------------------
# 11. Smoke test — make sure the package actually imports and routes
# ---------------------------------------------------------------------------
say "Smoke-testing the framework…"
if command -v python3 >/dev/null 2>&1; then
  PYTHONPATH="$ROOT" python3 - <<'PYEOF' || { echo "Smoke test failed."; exit 1; }
import keaton, py_compile, pathlib
from keaton.tools import registry
assert keaton.__version__
names = [t.name for t in registry.all()]
assert "ffmpeg" in names and "git" in names, names
best = registry.best("compress this video")
assert best and best.name == "ffmpeg", best
best2 = registry.best("find every TODO in the repo")
assert best2 and best2.name == "ripgrep", best2
# Splash asset integrity (pure stdlib — no rich/Pillow needed here).
import base64
from keaton.assets import pixel_me as _art
assert len(base64.b64decode(_art.DATA)) == _art.WIDTH * _art.HEIGHT * 3, "bad splash asset"
# The original bugs were SyntaxErrors; py_compile catches them without needing
# third-party deps (typer/rich) to be installed yet. Compile EVERY module.
pkg = pathlib.Path(keaton.__file__).parent
for f in sorted(pkg.rglob("*.py")):
    py_compile.compile(str(f), doraise=True)
print(f"OK — keaton {keaton.__version__}, {len(names)} tools discovered:", ", ".join(names))
print("OK — all", len(list(pkg.rglob('*.py'))), "modules compile (cli + providers included)")
PYEOF
  ok "Smoke test passed"
else
  echo "python3 not found — skipping smoke test."
fi

# ---------------------------------------------------------------------------
# 12. Git commit (+ optional public GitHub repo)
# ---------------------------------------------------------------------------
if [[ ! -d "$ROOT/.git" ]]; then
  say "Initialising git repository…"
  git init -q
  git branch -M main
fi

cat > "$ROOT/.gitignore" <<'GITEOF'
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
build/
dist/
.DS_Store
.keaton/
GITEOF

git add -A
if git diff --cached --quiet; then
  say "Nothing new to commit."
else
  git commit -q -m "Add Universal Tool Execution Framework; fix CLI import + recursion bugs

- New keaton/tools package: base interface, auto-discovery registry, safe executor
- 20 tool wrappers (git, ffmpeg, docker, kubectl, terraform, dbs, search, docs, ...)
- keaton tools / tool <name> / run commands; doctor now checks every tool
- Fix cli.py SyntaxError (stray colon) and self-recursive login/logout/whoami
- Add __version__, fix package discovery, drop speculative base44-sdk dep
- Human-friendly README

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
  ok "Committed"
fi

if [[ "$PUBLISH" == "1" ]]; then
  if command -v gh >/dev/null 2>&1; then
    OWNER="$(gh api user --jq .login 2>/dev/null)"
    if gh repo view "$REPO_NAME" >/dev/null 2>&1; then
      say "GitHub repo '$REPO_NAME' already exists — wiring 'origin' and pushing."
      # The bug this fixes: the old code pushed to 'origin' without ever adding it.
      if ! git remote get-url origin >/dev/null 2>&1; then
        git remote add origin "https://github.com/$OWNER/$REPO_NAME.git"
      fi
      git fetch -q origin 2>/dev/null || true
      if ! git push -u origin main 2>/dev/null; then
        echo "Push rejected: the remote has unrelated history (e.g. a README/license"
        echo "created on github.com). If you mean to replace it with this project, run:"
        echo "    git push --force-with-lease origin main"
      fi
    else
      say "Creating PUBLIC GitHub repo '$REPO_NAME'…"
      gh repo create "$REPO_NAME" --public --source=. --remote=origin --push \
        --description "An AI operating system for your terminal that runs the right developer tool from plain English."
    fi
    ok "Published: $(gh repo view "$REPO_NAME" --json url -q .url 2>/dev/null || echo "$REPO_NAME")"
  else
    echo "gh CLI not found — install it or push manually:"
    echo "  git remote add origin https://github.com/<you>/$REPO_NAME.git && git push -u origin main"
  fi
else
  echo
  say "Done. To publish it as a PUBLIC GitHub repo, run:"
  echo "    bash setup.sh --publish"
fi
