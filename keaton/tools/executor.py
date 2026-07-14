"""Runs tool commands with confirmation, dry-run, timing and safety checks."""
from __future__ import annotations

import subprocess
import time
from typing import List, Optional

from .base import ExecResult, Tool

# Patterns that always trip the safety brake regardless of tool.
_DANGER = ("rm -rf", "drop database", "drop table", "destroy", "--force", "mkfs", ":(){", "> /dev/")


def looks_dangerous(command: List[str]) -> bool:
    joined = " ".join(command).lower()
    return any(p in joined for p in _DANGER)


class Executor:
    """Validates then executes a command produced by a Tool."""

    def __init__(self, confirm=None, printer=None):
        # confirm(prompt:str)->bool ; printer(text:str)->None
        self.confirm = confirm or (lambda _p: True)
        self.printer = printer or (lambda _t: None)

    def run(
        self,
        tool: Tool,
        command: List[str],
        *,
        action: Optional[str] = None,
        dry_run: bool = False,
        stream: bool = True,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Optional[ExecResult]:
        if not tool.available():
            self.printer(f"'{tool.binary}' is not installed. {tool.install_hint}".strip())
            return None

        pretty = " ".join(command)
        self.printer(f"$ {pretty}")

        needs_confirm = (action and tool.is_destructive(action)) or looks_dangerous(command)
        if needs_confirm and not dry_run:
            if not self.confirm(f"This may be destructive. Run `{pretty}`?"):
                self.printer("Cancelled.")
                return None

        if dry_run:
            self.printer("(dry run — not executed)")
            return ExecResult(command, 0, "", "", 0.0)

        start = time.time()
        if stream:
            proc = subprocess.Popen(
                command, cwd=cwd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            out_lines = []
            assert proc.stdout is not None
            for line in proc.stdout:
                out_lines.append(line)
                self.printer(line.rstrip("\n"))
            proc.wait(timeout=timeout)
            return ExecResult(command, proc.returncode, "".join(out_lines), "",
                              time.time() - start)

        r = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return ExecResult(command, r.returncode, r.stdout, r.stderr, time.time() - start)
