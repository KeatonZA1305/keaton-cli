"""
LM Studio provider for Keaton CLI.
"""
import os
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from .base import AIProvider, Conversation, Message, Model


class LMStudioProvider(AIProvider):
    """LM Studio AI provider for local models served via LM Studio."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url") or os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234")
        self.default_model = config.get("model", "local-model")  # LM Studio doesn't require a specific model name in the same way

    async def _ensure_authenticated(self) -> bool:
        """LM Studio doesn't require authentication, but we check if the service is available."""
        return await self.is_authenticated()

    @property
    def display_name(self) -> str:
        return "LM Studio"

    @property
    def needs_auth(self) -> bool:
        return False

    async def login(self) -> bool:
        """LM Studio doesn't have a login; we just check if the service is available."""
        return await self.is_authenticated()

    async def logout(self) -> bool:
        """LM Studio doesn't have a logout."""
        return True

    async def is_authenticated(self) -> bool:
        """Check if LM Studio service is available."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/v1/models", timeout=5.0)
                return response.status_code == 200
        except Exception:
            return False

    async def models(self) -> List[Model]:
        """Get available models from LM Studio."""
        if not await self.is_authenticated():
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/v1/models", timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    models = []
                    for item in data.get("data", []):
                        models.append(
                            Model(
                                id=item["id"],
                                name=item.get("id", "unknown"),
                                description=f"LM Studio model: {item['id']}",
                                owned_by="lmstudio",
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
        """Send a message to LM Studio and get a response."""
        if not await self.is_authenticated():
            yield "Error: LM Studio service not available."
            return

        # For simplicity, we're not implementing conversation persistence here.
        # In a full implementation, we would use conversation_id to maintain context.
        
        # Prepare the request
        url = f"{self.base_url}/v1/chat/completions"
        
        data = {
            "model": self.default_model,
            "messages": [{"role": "user", "content": message}],
            "stream": stream,
        }

        try:
            async with httpx.AsyncClient() as client:
                if stream:
                    # Streaming response
                    async with client.stream(
                        "POST",
                        url,
                        json=data,
                        timeout=60.0,
                    ) as response:
                        if response.status_code != 200:
                            yield f"Error: {response.status_code} - {await response.aread()}"
                            return

                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                try:
                                    import json
                                    data_json = json.loads(line[6:])
                                    if data_json == "[DONE]":
                                        break
                                    if "choices" in data_json and len(data_json["choices"]) > 0:
                                        delta = data_json["choices"][0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            yield content
                                except Exception:
                                    pass
                else:
                    # Non-streaming response
                    response = await client.post(
                        url,
                        json=data,
                        timeout=60.0,
                    )
                    if response.status_code != 200:
                        yield f"Error: {response.status_code} - {await response.aread()}"
                        return
                    
                    result = await response.json()
                    if "choices" in result and len(result["choices"]) > 0:
                        content = result["choices"][0].get("message", {}).get("content", "")
                        yield content
                    else:
                        yield "Error: No response from LM Studio."
        except Exception as e:
            yield f"Error: {str(e)}"

    async def conversations(self) -> List[Conversation]:
        """LM Studio doesn't provide a conversations API in the same way; we return empty list."""
        return []

    async def health_check(self) -> bool:
        """Check if LM Studio service is reachable."""
        return await self.is_authenticated()