"""
Base provider interface for Keaton CLI.
Defines the common interface that all AI providers must implement.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncIterator, Optional
from dataclasses import dataclass


@dataclass
class Model:
    """Represents an AI model."""
    id: str
    name: str
    description: str = ""
    owned_by: str = ""  # e.g., "openai", "anthropic", "ollama"


@dataclass
class Conversation:
    """Represents a conversation/chat session."""
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


@dataclass
class Message:
    """Represents a message in a conversation."""
    id: str
    role: str  # "user", "assistant", "system"
    content: str
    created_at: str


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__.lower().replace("provider", "")

    @abstractmethod
    async def login(self) -> bool:
        """Log in to the provider. Returns True if successful."""
        pass

    @abstractmethod
    async def logout(self) -> bool:
        """Log out from the provider. Returns True if successful."""
        pass

    @abstractmethod
    async def is_authenticated(self) -> bool:
        """Check if the user is authenticated with the provider."""
        pass

    @abstractmethod
    async def chat(self, message: str, conversation_id: Optional[str] = None,
                   model: Optional[str] = None, stream: bool = True,
                   **kwargs) -> AsyncIterator[str]:
        """
        Send a message and get a response stream.
        
        Args:
            message: The user's message
            conversation_id: Optional ID of existing conversation
            model: Optional model to use
            stream: Whether to stream the response
            **kwargs: Provider-specific parameters
            
        Yields:
            Chunks of the response
        """
        pass

    @abstractmethod
    async def models(self) -> List[Model]:
        """Get list of available models for this provider."""
        pass

    @abstractmethod
    async def conversations(self) -> List[Conversation]:
        """Get list of conversations for this provider."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider service is healthy."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name of the provider."""
        pass

    @property
    @abstractmethod
    def needs_auth(self) -> bool:
        """Whether this provider requires authentication."""
        pass