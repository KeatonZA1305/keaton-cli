from .base import Tool


class SshTool(Tool):
    name = "ssh"
    binary = "ssh"
    category = "remote"
    description = "Connect to and run commands on remote servers; tunnels; SCP."
    install_hint = "Usually preinstalled (OpenSSH)."
    keywords = ["ssh", "connect to server", "remote", "tunnel", "scp", "sftp",
                "remote execution", "server"]
    capabilities = ["Remote execution", "Key management", "Tunnels",
                    "File transfer (SCP/SFTP)", "Remote diagnostics"]
    examples = [
        ("connect to my server", "ssh user@host"),
        ("run uptime remotely", "ssh user@host uptime"),
    ]
    recipes = {"connect": ["{target}"], "run": ["{target}", "{command}"]}
