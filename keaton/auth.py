"""
Authentication module for Keaton CLI.
Handles login, logout, and status checking via Base44 CLI.
"""
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any
from .config import get_config_value, update_config

BASE44_CLI = "base44"


def _run_base44_command(args: list[str]) -> tuple[int, str, str]:
    """Run a base44 CLI command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            [BASE44_CLI] + args,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return (
            127,
            "",
            f"Base44 CLI not found. Please install it first: npm install -g base44@latest",
        )


def login() -> bool:
    """Log in to Base44 using the base44 CLI.
    Returns True if successful, False otherwise.
    """
    code, stdout, stderr = _run_base44_command(["login"])
    if code == 0:
        # After login, we can optionally fetch and store user info
        whoami()
        return True
    else:
        print(f"Login failed: {stderr}")
        return False


def logout() -> bool:
    """Log out from Base44 using the base44 CLI.
    Returns True if successful, False otherwise.
    """
    code, stdout, stderr = _run_base44_command(["logout"])
    if code == 0:
        # Clear stored user info
        update_config("default_agent", None)
        return True
    else:
        print(f"Logout failed: {stderr}")
        return False


def whoami() -> Optional[Dict[str, Any]]:
    """Get the current logged-in user from Base44 CLI.
    Returns user info dict or None if not logged in.
    """
    code, stdout, stderr = _run_base44_command(["whoami"])
    if code == 0 and stdout:
        try:
            user_info = json.loads(stdout)
            # Store useful info in config
            update_config("last_user", user_info.get("email"))
            # Note: We don't store the token here; we rely on base44 CLI's auth
            return user_info
        except json.JSONDecodeError:
            print(f"Failed to parse whoami output: {stdout}")
            return None
    else:
        # Not logged in
        return None


def is_logged_in() -> bool:
    """Check if the user is logged in to Base44."""
    return whoami() is not None


def get_stored_username() -> Optional[str]:
    """Get the username from config (if stored)."""
    return get_config_value("last_user")
