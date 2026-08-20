from __future__ import annotations

from typing import Any

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from app.config import Settings

APP_NAME = "ai-marketing-copilot"
USER_ID = "seller"


def build_llm(settings: Settings) -> LiteLlm:
    """Build LiteLlm for an OpenAI-compatible endpoint (e.g. 9Router).

    Kwargs are passed straight to litellm.completion: api_base + api_key + max_tokens.
    A model without "/" is prefixed with "openai/" so litellm routes it through api_base
    (the bare model name is still sent in the request body).
    """
    kwargs: dict[str, Any] = {
        "api_base": settings.llm_base_url,
        "api_key": settings.llm_api_key,
        "max_tokens": settings.llm_max_tokens,
        "temperature": 0.3,
        "drop_params": True,
    }
    model = settings.llm_model
    if "/" not in model:
        model = f"openai/{model}"
    return LiteLlm(model=model, **kwargs)


async def run_agent(agent: Agent, prompt: str, session_id: str = "default") -> str:
    """Run an ADK agent once (in-memory session); return all generated text."""
    session_service = InMemorySessionService()
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)
    message = genai_types.Content(role="user", parts=[genai_types.Part(text=prompt)])

    parts: list[str] = []
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=message
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                text = getattr(part, "text", None)
                if text:
                    parts.append(text)
    return "\n".join(parts).strip()
