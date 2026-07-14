"""
OpenRouter provider for Keaton CLI.

OpenRouter exposes an OpenAI-compatible Chat Completions API, so this provider
speaks that dialect against https://openrouter.ai/api/v1.
"""
import os
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from .base import AIProvider, Conversation, Model


class OpenRouterProvider(AIProvider):
    """OpenRouter AI provider (OpenAI-compatible)."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1"
        self.default_model = config.get("model", "openai/gpt-3.5-turbo")

    @property
    def display_name(self) -> str:
        return "OpenRouter"

    @property
    def needs_auth(self) -> bool:
        return True

    async def login(self) -> bool:
        return await self.is_authenticated()

    async def logout(self) -> bool:
        self.api_key = None
        return True

    async def is_authenticated(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
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
            yield "Error: OpenRouter API key not configured (set OPENROUTER_API_KEY)."
            return

        data = {
            "model": model or self.default_model,
            "messages": [{"role": "user", "content": message}],
            "stream": stream,
        }
        try:
            async with httpx.AsyncClient() as client:
                if stream:
                    async with client.stream(
                        "POST", f"{self.base_url}/chat/completions",
                        headers=self._headers(), json=data, timeout=60.0,
                    ) as response:
                        if response.status_code != 200:
                            yield f"Error: {response.status_code} - {await response.aread()}"
                            return
                        async for line in response.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            payload = line[len("data: "):].strip()
                            if payload == "[DONE]":
                                break
                            try:
                                import json
                                chunk = json.loads(payload)
                                content = chunk["choices"][0].get("delta", {}).get("content", "")
                                if content:
                                    yield content
                            except Exception:
                                continue
                else:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(), json=data, timeout=60.0,
                    )
                    if response.status_code != 200:
                        yield f"Error: {response.status_code} - {await response.aread()}"
                        return
                    choices = response.json().get("choices", [])
                    yield choices[0].get("message", {}).get("content", "") if choices \
                        else "Error: No response from OpenRouter."
        except Exception as e:
            yield f"Error: {str(e)}"

    async def models(self) -> List[Model]:
        if not await self.is_authenticated():
            return []
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{self.base_url}/models",
                                     headers=self._headers(), timeout=10.0)
                if r.status_code != 200:
                    return []
                return [
                    Model(id=i["id"], name=i.get("name", i["id"]),
                          description=i.get("description", ""), owned_by="openrouter")
                    for i in r.json().get("data", [])
                ]
        except Exception:
            return []

    async def conversations(self) -> List[Conversation]:
        return []

    async def health_check(self) -> bool:
        if not await self.is_authenticated():
            return False
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{self.base_url}/models",
                                     headers=self._headers(), timeout=5.0)
                return r.status_code == 200
        except Exception:
            return False
