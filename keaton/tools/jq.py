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
