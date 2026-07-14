"""
Base44 provider for Keaton CLI.
"""
import json
import os
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from .base import AIProvider, Conversation, Message, Model


class Base44Provider(AIProvider):
    """Base44 AI provider."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.app_id = config.get("app_id")
        self.agent_name = config.get("agent_name")
        self.agent_id = config.get("agent_id")
        self.base_url = "https://api.base44.com"
        self.token: Optional[str] = None

    async def _ensure_authenticated(self, interactive: bool = False) -> bool:
        """Return whether we are authenticated with Base44.

        A plain status check (``interactive=False``) never launches a login —
        that would block on the browser flow and hang commands like
        ``keaton doctor``. Only the explicit chat/login paths pass
        ``interactive=True`` to trigger the CLI login when a token is missing.
        """
        config_path = Path.home() / ".base44" / "config.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                    self.token = config.get("token")
                    if not self.app_id:
                        self.app_id = config.get("appId")
            except (json.JSONDecodeError, IOError):
                pass

        if self.token:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.base_url}/v1/apps/{self.app_id}/auth/me",
                        headers={"Authorization": f"Bearer {self.token}"},
                        timeout=10.0,
                    )
                    if response.status_code == 200:
                        return True
            except Exception:
                pass

        if not interactive:
            # Pure status check: don't trigger a blocking login.
            return bool(self.token)

        from ..auth import login
        if login():
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        config = json.load(f)
                        self.token = config.get("token")
                        if not self.app_id:
                            self.app_id = config.get("appId")
                except (json.JSONDecodeError, IOError):
                    pass
            return bool(self.token)
        return False

    @property
    def display_name(self) -> str:
        return "Base44"

    @property
    def needs_auth(self) -> bool:
        return True

    async def login(self) -> bool:
        """Log in to Base44."""
        from ..auth import login
        return login()

    async def logout(self) -> bool:
        """Log out from Base44."""
        from ..auth import logout
        success = logout()
        if success:
            self.token = None
        return success

    async def is_authenticated(self) -> bool:
        """Check if authenticated with Base44."""
        return await self._ensure_authenticated()

    async def models(self) -> List[Model]:
        """Get available models for Base44.
        Base44 uses agents, not models in the traditional sense.
        We'll return a placeholder model representing the agent.
        """
        if not await self.is_authenticated():
            return []

        # If we have an agent name or ID, we can try to get it
        if self.agent_name or self.agent_id:
            try:
                agent = await self._get_agent()
                if agent:
                    return [
                        Model(
                            id=agent.get("id", ""),
                            name=agent.get("name", "Unknown Agent"),
                            description=agent.get(
                                "description", "Base44 AI Agent"
                            ),
                            owned_by="base44",
                        )
                    ]
            except Exception:
                pass

        # Fallback: return a generic model
        return [
            Model(
                id="base44-agent",
                name="Base44 Agent",
                description="Interact with your Base44 AI Agent",
                owned_by="base44",
            )
        ]

    async def conversations(self) -> List[Conversation]:
        """Get conversations for Base44.
        Note: Base44 doesn't have a direct conversations API in the public SDK.
        We'll return an empty list for now.
        """
        # This would require accessing conversation history via the agent
        # For now, we return an empty list
        return []

    async def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        model: Optional[str] = None,
        stream: bool = True,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Send a message to the Base44 agent and stream the response."""
        if not await self.is_authenticated():
            yield "Error: Not authenticated with Base44. Please run 'keaton login'."
            return

        try:
            agent = await self._get_agent()
            if not agent:
                yield "Error: Could not find agent. Please configure agent_id or agent_name."
                return

            # For now, we'll simulate streaming by getting the full response and yielding it in chunks
            # In a real implementation, we would use the agent's streaming chat method
            response = await self._chat_with_agent(agent, message)
            if response:
                # Simulate streaming by yielding chunks of text
                words = response.split(" ")
                for i, word in enumerate(words):
                    if i == 0:
                        yield word
                    else:
                        yield " " + word
                    # Small delay to simulate streaming
                    # In a real implementation, we would yield actual tokens from the stream
            else:
                yield "Error: No response from agent."

        except Exception as e:
            yield f"Error communicating with Base44 agent: {str(e)}"

    async def _get_agent(self) -> Optional[Dict[str, Any]]:
        """Get the agent by ID or name."""
        if not self.app_id:
            return None

        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {self.token}"}
            # Try to get agent by ID if we have it
            if self.agent_id:
                response = await client.get(
                    f"{self.base_url}/v1/apps/{self.app_id}/agents/{self.agent_id}",
                    headers=headers,
                    timeout=10.0,
                )
                if response.status_code == 200:
                    return response.json()
            # Otherwise, try to get by name
            if self.agent_name:
                response = await client.get(
                    f"{self.base_url}/v1/apps/{self.app_id}/agents",
                    headers=headers,
                    params={"name": self.agent_name},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    agents = response.json()
                    if isinstance(agents, list) and len(agents) > 0:
                        return agents[0]
            # If we don't have agent name or ID, or search failed, try to get the first agent
            response = await client.get(
                f"{self.base_url}/v1/apps/{self.app_id}/agents",
                headers=headers,
                limit=1,
                timeout=10.0,
            )
            if response.status_code == 200:
                agents = response.json()
                if isinstance(agents, list) and len(agents) > 0:
                    return agents[0]
        return None

    async def _chat_with_agent(
        self, agent: Dict[str, Any], message: str
    ) -> Optional[str]:
        """Send a message to the agent and get the response."""
        agent_id = agent.get("id")
        if not agent_id:
            return None

        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            payload = {
                "message": message,
                # Add any additional parameters from kwargs
                **{
                    k: v
                    for k, v in self.config.items()
                    if k not in ["app_id", "agent_name", "agent_id"]
                },
            }
            response = await client.post(
                f"{self.base_url}/v1/apps/{self.app_id}/agents/{agent_id}/chat",
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            if response.status_code == 200:
                result = response.json()
                return result.get("text") or result.get("message") or str(result)
            else:
                # Try to get error message
                try:
                    error_data = response.json()
                    return f"Error: {error_data.get('message', 'Unknown error')}"
                except Exception:
                    return f"Error: HTTP {response.status_code}"

    async def health_check(self) -> bool:
        """Check if the Base44 service is healthy."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/health", timeout=10.0)
                return response.status_code == 200
        except Exception:
            return False
