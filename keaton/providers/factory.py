"""Single source of truth for building a provider from config.

Both the classic CLI (`keaton chat`) and the TUI use this, so provider wiring
lives in exactly one place.
"""
from __future__ import annotations

import importlib
import os
from typing import Dict, List, Optional, Tuple

_SPECS: Dict[str, Tuple[str, str]] = {
    "base44": ("keaton.providers.base44", "Base44Provider"),
    "openai": ("keaton.providers.openai", "OpenAIProvider"),
    "anthropic": ("keaton.providers.anthropic", "AnthropicProvider"),
    "ollama": ("keaton.providers.ollama", "OllamaProvider"),
    "gemini": ("keaton.providers.gemini", "GeminiProvider"),
    "openrouter": ("keaton.providers.openrouter", "OpenRouterProvider"),
    "lmstudio": ("keaton.providers.lmstudio", "LMStudioProvider"),
    "local": ("keaton.providers.local", "LocalProvider"),
}

_ENV_KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

PROVIDER_NAMES: List[str] = list(_SPECS)


def get_provider_class(name: str):
    spec = _SPECS.get(name)
    if not spec:
        return None
    module_path, class_name = spec
    return getattr(importlib.import_module(module_path), class_name)


def provider_config(config: dict, name: str) -> dict:
    cfg = {
        "app_id": config.get("app_id"),
        "agent_name": config.get("agent_name"),
        "agent_id": config.get("agent_id"),
        "model": config.get("default_model"),
    }
    env_key = _ENV_KEYS.get(name)
    if env_key:
        cfg["api_key"] = os.getenv(env_key)
    return cfg


def build_provider(config: dict, name: Optional[str] = None):
    """Return (provider_instance, provider_name), or (None, name) on failure."""
    name = name or config.get("provider", "base44")
    cls = get_provider_class(name)
    if cls is None:
        return None, name
    try:
        return cls(provider_config(config, name)), name
    except Exception:
        return None, name
