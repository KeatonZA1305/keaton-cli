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
