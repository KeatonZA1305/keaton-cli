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
