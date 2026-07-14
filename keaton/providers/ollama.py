"""
Ollama provider for Keaton CLI.
"""
import os
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from .base import AIProvider, Conversation, Message, Model


class OllamaProvider(AIProvider):
    """Ollama AI provider for local models."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.default_model = config.get("model", "llama2")

    async def _ensure_authenticated(self) -> bool:
        """Ollama doesn't require authentication, but we check if the service is available."""
        return await self.is_authenticated()

    @property
    def display_name(self) -> str:
        return "Ollama"

    @property
    def needs_auth(self) -> bool:
        return False

    async def login(self) -> bool:
        """Ollama doesn't have a login; we just check if the service is available."""
        return await self.is_authenticated()

    async def logout(self) -> bool:
        """Ollama doesn't have a logout."""
        return True

    async def is_authenticated(self) -> bool:
        """Check if Ollama service is available."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/tags", timeout=5.0)
                return response.status_code == 200
        except Exception:
            return False

    async def models(self) -> List[Model]:
        """Get available models from Ollama."""
        if not await self.is_authenticated():
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/tags", timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    models = []
                    for item in data.get("models", []):
                        models.append(
                            Model(
                                id=item["name"],
                                name=item["name"],
                                description=f"Ollama model: {item['name']}",
                                owned_by="ollama",
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
        """Send a message to Ollama and get a response."""
        if not await self.is_authenticated():
            yield "Error: Ollama service not available."
            return

        # For simplicity, we're not implementing conversation persistence here.
        # In a full implementation, we would use conversation_id to maintain context.
        
        # Prepare the request
        url = f"{self.base_url}/api/generate"
        
        data = {
            "model": self.default_model,
            "prompt": message,
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
                            if line.strip():
                                try:
                                    import json
                                    data_json = json.loads(line)
                                    if "response" in data_json:
                                        yield data_json["response"]
                                    if data_json.get("done", False):
                                        break
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
                    if "response" in result:
                        yield result["response"]
                    else:
                        yield "Error: No response from Ollama."
        except Exception as e:
            yield f"Error: {str(e)}"

    async def conversations(self) -> List[Conversation]:
        """Ollama doesn't provide a conversations API in the same way; we return empty list."""
        return []

    async def health_check(self) -> bool:
        """Check if Ollama service is reachable."""
        return await self.is_authenticated()