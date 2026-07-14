"""
Gemini provider for Keaton CLI.

Talks to Google's Generative Language API
(https://generativelanguage.googleapis.com/v1beta).
"""
import os
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from .base import AIProvider, Conversation, Model


class GeminiProvider(AIProvider):
    """Google Gemini AI provider."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("GEMINI_API_KEY")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.default_model = config.get("model", "gemini-1.5-flash")

    @property
    def display_name(self) -> str:
        return "Gemini"

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

    async def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        model: Optional[str] = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[str]:
        if not await self.is_authenticated():
            yield "Error: Gemini API key not configured (set GEMINI_API_KEY)."
            return

        model_name = model or self.default_model
        url = f"{self.base_url}/models/{model_name}:generateContent"
        params = {"key": self.api_key}
        data = {
            "contents": [{"parts": [{"text": message}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048},
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, params=params, json=data, timeout=60.0)
                if response.status_code != 200:
                    yield f"Error: {response.status_code} - {await response.aread()}"
                    return
                candidates = response.json().get("candidates", [])
                if not candidates:
                    yield "Error: No response from Gemini."
                    return
                parts = candidates[0].get("content", {}).get("parts", [])
                yield "".join(p.get("text", "") for p in parts) or "Error: Empty response."
        except Exception as e:
            yield f"Error: {str(e)}"

    async def models(self) -> List[Model]:
        if not await self.is_authenticated():
            return []
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{self.base_url}/models",
                                     params={"key": self.api_key}, timeout=10.0)
                if r.status_code != 200:
                    return []
                out = []
                for m in r.json().get("models", []):
                    mid = m.get("name", "").replace("models/", "")
                    out.append(Model(id=mid, name=m.get("displayName", mid),
                                     description=m.get("description", ""), owned_by="google"))
                return out
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
                                     params={"key": self.api_key}, timeout=5.0)
                return r.status_code == 200
        except Exception:
            return False
