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
