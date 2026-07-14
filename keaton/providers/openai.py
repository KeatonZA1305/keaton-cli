"""
OpenAI provider for Keaton CLI.
"""
import os
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from .base import AIProvider, Conversation, Message, Model


class OpenAIProvider(AIProvider):
    """OpenAI AI provider."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY")
        self.base_url = "https://api.openai.com/v1"
        self.default_model = config.get("model", "gpt-3.5-turbo")

    async def _ensure_authenticated(self) -> bool:
        """Ensure we have an API key."""
        return bool(self.api_key)

    @property
    def display_name(self) -> str:
        return "OpenAI"

    @property
    def needs_auth(self) -> bool:
        return True

    async def login(self) -> bool:
        """OpenAI doesn't have a login; we just check for API key."""
        return await self.is_authenticated()

    async def logout(self) -> bool:
        """OpenAI doesn't have a logout; we just clear the API key."""
        self.api_key = None
        return True

    async def is_authenticated(self) -> bool:
        """Check if we have an API key."""
        return bool(self.api_key)

    async def models(self) -> List[Model]:
        """Get available models from OpenAI."""
        if not await self.is_authenticated():
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    models = []
                    for item in data.get("data", []):
                        models.append(
                            Model(
                                id=item["id"],
                                name=item["id"],
                                description=item.get("owned_by", ""),
                            )
                        )
                    return models
        except Exception:
            pass
        return []

    async def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        stream: bool = False,
    ) -> AsyncIterator[str]:
        """Send a message to OpenAI and get a response."""
        if not await self.is_authenticated():
            yield "Error: OpenAI API key not configured."
            return

        # For simplicity, we're not implementing conversation persistence here.
        # In a full implementation, we would use conversation_id to maintain context.
        messages = [{"role": "user", "content": message}]

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST"
                    if stream
                    else "POST",  # OpenAI uses POST for both streaming and non-streaming
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.default_model,
                        "messages": messages,
                        "stream": stream,
                    },
                    timeout=30.0,
                ) as response:
                    if response.status_code != 200:
                        yield f"Error: {response.status_code} - {await response.aread()}"
                        return

                    if stream:
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]":
                                    break
                                try:
                                    import json

                                    data_json = json.loads(data)
                                    if "choices" in data_json and len(data_json["choices"]) > 0:
                                        delta = data_json["choices"][0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            yield content
                                except Exception:
                                    pass
                    else:
                        # Non-streaming response
                        data = await response.json()
                        if "choices" in data and len(data["choices"]) > 0:
                            content = data["choices"][0].get("message", {}).get("content", "")
                            yield content
                        else:
                            yield "Error: No response from OpenAI."
        except Exception as e:
            yield f"Error: {str(e)}"

    async def conversations(self) -> List[Conversation]:
        """OpenAI doesn't provide a conversations API in the same way; we return empty list."""
        return []

    async def health_check(self) -> bool:
        """Check if OpenAI API is reachable."""
        if not await self.is_authenticated():
            return False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=5.0,
                )
                return response.status_code == 200
        except Exception:
            return False