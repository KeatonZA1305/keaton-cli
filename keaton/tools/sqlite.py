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
