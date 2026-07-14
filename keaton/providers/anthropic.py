"""
Anthropic provider for Keaton CLI.

Talks to the public Anthropic Messages API (https://api.anthropic.com/v1).
"""
import os
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from .base import AIProvider, Conversation, Model


class AnthropicProvider(AIProvider):
    """Anthropic AI provider."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = "https://api.anthropic.com/v1"
        self.default_model = config.get("model", "claude-3-haiku-20240307")

    @property
    def display_name(self) -> str:
        return "Anthropic"

    @property
    def needs_auth(self) -> bool:
        return True

    async def login(self) -> bool:
        return await self.is_authenticated()

    async def logout(self) -> bool:
        self.api_key = None
        return True

    async def is_authenticated(self) -> bool:
        """Authenticated when an API key is present."""
        return bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    async def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        model: Optional[str] = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[str]:
        if not await self.is_authenticated():
            yield "Error: Anthropic API key not configured (set ANTHROPIC_API_KEY)."
            return

        data = {
            "model": model or self.default_model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": message}],
            "stream": stream,
        }
        try:
            async with httpx.AsyncClient() as client:
                if stream:
                    async with client.stream(
                        "POST", f"{self.base_url}/messages",
                        headers=self._headers(), json=data, timeout=60.0,
                    ) as response:
                        if response.status_code != 200:
                            yield f"Error: {response.status_code} - {await response.aread()}"
                            return
                        async for line in response.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            try:
                                import json
                                event = json.loads(line[6:])
                                if event.get("type") == "content_block_delta":
                                    text = event.get("delta", {}).get("text", "")
                                    if text:
                                        yield text
                            except Exception:
                                continue
                else:
                    response = await client.post(
                        f"{self.base_url}/messages",
                        headers=self._headers(), json=data, timeout=60.0,
                    )
                    if response.status_code != 200:
                        yield f"Error: {response.status_code} - {await response.aread()}"
                        return
                    blocks = response.json().get("content", [])
                    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
                    yield text or "Error: No response from Anthropic."
        except Exception as e:
            yield f"Error: {str(e)}"

    async def models(self) -> List[Model]:
        """Anthropic has no public models list endpoint; return a known set."""
        if not await self.is_authenticated():
            return []
        return [
            Model(id="claude-3-opus-20240229", name="Claude 3 Opus",
                  description="Most powerful Claude 3 model", owned_by="anthropic"),
            Model(id="claude-3-sonnet-20240229", name="Claude 3 Sonnet",
                  description="Balanced Claude 3 model", owned_by="anthropic"),
            Model(id="claude-3-haiku-20240307", name="Claude 3 Haiku",
                  description="Fastest Claude 3 model", owned_by="anthropic"),
        ]

    async def conversations(self) -> List[Conversation]:
        return []

    async def health_check(self) -> bool:
        if not await self.is_authenticated():
            return False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self._headers(),
                    json={
                        "model": self.default_model,
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "ping"}],
                    },
                    timeout=5.0,
                )
                return response.status_code == 200
        except Exception:
            return False
