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
