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
