"""GET /api/llm/status — active LLM provider information."""

import os

from fastapi import APIRouter

from core.llm import get_llm_provider

router = APIRouter(tags=["llm"])

_AVAILABLE_PROVIDERS = ["claude", "openai", "gemini", "ollama", "azure"]

_KEY_VARS: dict[str, str | None] = {
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "ollama": None,
    "azure": "AZURE_OPENAI_KEY",
}


@router.get("/llm/status")
async def llm_status() -> dict:
    provider_name = os.environ.get("LLM_PROVIDER", "claude").lower()
    key_var = _KEY_VARS.get(provider_name)
    configured = key_var is None or bool(os.environ.get(key_var))

    try:
        provider = get_llm_provider()
        model = provider.model
    except ValueError:
        model = "unknown"
        configured = False

    return {
        "provider": provider_name,
        "model": model,
        "configured": configured,
        "available_providers": _AVAILABLE_PROVIDERS,
    }
