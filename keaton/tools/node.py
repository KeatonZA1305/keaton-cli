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
