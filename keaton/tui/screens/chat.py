"""Interactive chat with an AI agent: streaming, markdown, and code copy.

Works with whichever provider is configured (built via providers.factory). The
providers are single shot, so multi turn context is preserved by composing the
agent persona plus recent turns into each request.
"""
from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
from typing import List, Optional

from rich.console import Group
from rich.markdown import Markdown
from rich.rule import Rule
from rich.segment import Segment, Segments
from rich.text import Text

from ... import agents as agentmod
from ...providers.factory import build_provider
from .. import keys as K
from ..widgets import edit_text
from .base import Screen

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class ChatScreen(Screen):
    header = "slim"

    def __init__(self, app, agent):
        super().__init__(app)
        self.agent = agent
        self.messages: List[dict] = []       # {role, content}
        self.buffer = ""
        self.streaming = False
        self.notice = ""
        self._tick = 0
        self.title = f"Chat · {agent.name}"
        self.provider, self.provider_name = build_provider(app.config)

    # -- lifecycle --------------------------------------------------------
    def on_enter(self):
        if not self.messages:
            self.notice = f"Talking to {self.agent.name} via {self.provider_name}. " \
                          "Type a message, or /help for commands."

    # -- rendering --------------------------------------------------------
    def _transcript_renderable(self) -> Group:
        t = self.theme
        blocks = []
        if not self.messages:
            intro = Text()
            intro.append(f"{self.agent.glyph}  {self.agent.name}\n", style=f"bold {t.accent}")
            intro.append(self.agent.system_prompt, style=t.dim)
            blocks.append(intro)
        for m in self.messages:
            if m["role"] == "user":
                label = Text("❯ you", style=f"bold {t.accent}")
                body = Text(m["content"], style="default")
                blocks.append(Group(label, body, Text("")))
            else:
                label = Text(f"{self.agent.glyph} {self.agent.name}", style=f"bold {t.accent}")
                content = m["content"] or ("…" if self.streaming else "")
                if self.app.config.get("markdown_enabled", True) and content:
                    try:
                        rendered = Markdown(content)
                    except Exception:
                        rendered = Text(content)
                else:
                    rendered = Text(content)
                blocks.append(Group(label, rendered, Text("")))
        return Group(*blocks)

    def render_body(self, width: int, height: int):
        t = self.theme
        input_rows = 2
        notice_rows = 1 if self.notice else 0
        avail = max(3, height - input_rows - notice_rows - 1)

        # Bottom-anchored transcript via render_lines + tail slice.
        console = self.app.console
        options = console.options.update(width=width, height=None)
        lines = console.render_lines(self._transcript_renderable(), options, pad=False)
        tail = lines[-avail:]
        segs: List[Segment] = []
        for line in tail:
            segs.extend(line)
            segs.append(Segment("\n"))
        transcript = Segments(segs)

        prompt = Text(no_wrap=True, overflow="ellipsis")
        if self.streaming:
            prompt.append(f"{SPINNER[self._tick % len(SPINNER)]} ", style=t.accent)
            prompt.append("thinking…", style=t.dim)
        else:
            prompt.append("❯ ", style=t.accent)
            prompt.append(self.buffer, style="default")
            prompt.append("▏", style=t.accent)

        parts = [transcript, Rule(style=t.border), prompt]
        if self.notice:
            parts.append(Text(self.notice, style=t.dim))
        return Group(*parts)

    def footer_hints(self):
        return [("enter", "send"), ("/new", "reset"), ("/copy", "copy code"),
                ("tab", "agent"), ("esc", "back"), ("^c", "quit")]

    # -- input ------------------------------------------------------------
    def handle_key(self, key: str) -> None:
        if self.streaming:
            return
        if key == K.ESC:
            self.app.pop()
            return
        if key == K.TAB:
            self._cycle_agent()
            return
        if key == K.CTRL_N:
            self._new()
            return
        new, action = edit_text(self.buffer, key)
        if action == "submit":
            self._submit(self.buffer.strip())
            self.buffer = ""
        elif action == "cancel":
            self.app.pop()
        else:
            self.buffer = new
            self.notice = ""

    # -- actions ----------------------------------------------------------
    def _cycle_agent(self):
        order = agentmod.AGENTS
        i = order.index(self.agent)
        self.agent = order[(i + 1) % len(order)]
        self.app.active_agent = self.agent
        self.title = f"Chat · {self.agent.name}"
        self.notice = f"Switched to {self.agent.name}."

    def _new(self):
        self.messages = []
        self.notice = "Started a new conversation."

    def _submit(self, text: str):
        if not text:
            return
        if text.startswith("/"):
            self._command(text)
            return
        self.messages.append({"role": "user", "content": text})
        self.messages.append({"role": "assistant", "content": ""})
        self.streaming = True
        self.notice = ""
        self.app.refresh()
        try:
            asyncio.run(self._stream(text))
        except KeyboardInterrupt:
            self.messages[-1]["content"] += "\n[interrupted]"
        except Exception as e:  # never crash the UI on a provider error
            self.messages[-1]["content"] = f"Error: {e}"
        self.streaming = False
        self.app.refresh()

    async def _stream(self, text: str):
        if self.provider is None:
            self.messages[-1]["content"] = (
                f"No provider available ({self.provider_name}). "
                "Configure one in Settings or set an API key.")
            return
        prompt = self._compose(text)
        got = False
        async for chunk in self.provider.chat(message=prompt, stream=True):
            got = True
            self.messages[-1]["content"] += chunk
            self._tick += 1
            self.app.refresh()
        if not got:
            self.messages[-1]["content"] = "[no response]"

    def _compose(self, text: str) -> str:
        lines = [self.agent.system_prompt, ""]
        # include recent turns (exclude the just-added empty assistant slot)
        for m in self.messages[:-1][-8:]:
            who = "User" if m["role"] == "user" else "Assistant"
            lines.append(f"{who}: {m['content']}")
        lines.append("Assistant:")
        return "\n".join(lines)

    def _command(self, text: str):
        cmd = text.split()[0].lower()
        if cmd in ("/new", "/clear"):
            self._new()
        elif cmd == "/exit":
            self.app.pop()
        elif cmd == "/agent":
            self._cycle_agent()
        elif cmd == "/model":
            parts = text.split(maxsplit=1)
            if len(parts) == 2:
                self.app.set_config("default_model", parts[1].strip())
                self.provider, self.provider_name = build_provider(self.app.config)
                self.notice = f"Model set to {parts[1].strip()}."
            else:
                self.notice = "Usage: /model <name>"
        elif cmd == "/copy":
            self._copy_code()
        elif cmd == "/help":
            self.notice = "/new  /copy  /model <name>  /agent (or Tab)  /exit"
        else:
            self.notice = f"Unknown command {cmd}. Try /help."

    def _copy_code(self):
        blocks = []
        for m in reversed(self.messages):
            if m["role"] == "assistant":
                blocks = re.findall(r"```[^\n]*\n(.*?)```", m["content"], re.DOTALL)
                if blocks:
                    break
        if not blocks:
            self.notice = "No code block to copy."
            return
        code = blocks[-1]
        if self._to_clipboard(code):
            self.notice = "Copied the last code block to the clipboard."
        else:
            self.notice = "No clipboard tool found (pbcopy/xclip/clip)."

    @staticmethod
    def _to_clipboard(text: str) -> bool:
        for cmd in (["pbcopy"], ["xclip", "-selection", "clipboard"], ["wl-copy"], ["clip"]):
            if shutil.which(cmd[0]):
                try:
                    subprocess.run(cmd, input=text, text=True, check=True)
                    return True
                except Exception:
                    continue
        return False
