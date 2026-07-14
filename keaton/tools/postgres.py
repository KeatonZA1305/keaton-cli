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
