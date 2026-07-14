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
