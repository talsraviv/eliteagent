"""Model provider wiring for pydantic-ai.

Supports switching between OpenAI GPT-5, Anthropic Claude 4.5 Sonnet,
and Grok Code Fast via OpenRouter.

Environment variables:
- OPENAI_API_KEY
- ANTHROPIC_API_KEY
- OPENROUTER_API_KEY

Model names (IDs):
- openai:gpt-5
- anthropic:claude-4.5-sonnet
- openrouter:x-ai/grok-code-fast-1

Note: GPT-5 is hypothetical; ensure correct model IDs for your account.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Literal

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

# OpenRouter compatibility via OpenAI-compatible provider
from pydantic_ai.models.openai import OpenAIChatModel as OpenRouterModel
from pydantic_ai.providers.openai import OpenAIProvider as OpenRouterProvider


ModelName = Literal[
    "gpt-5",
    "claude-4.5-sonnet",
    "grok-code-fast-1",
]


@dataclass
class ModelConfig:
    name: ModelName
    display: str


SYSTEM_PROMPT = (
    "You are an AI coding agent.\n"
    "Your goal is to act on the user's request to complete a given task.\n"
    "You operate in a loop, repeatedly calling tools until the task is finished.\n"
    "You must explain your thought process and the steps you plan to take to solve the problem.\n"
    "You must use the provided tools to interact with the environment, specifically the file system.\n"
)


def build_model(model_name: ModelName):
    """Return a pydantic-ai Model instance for the given logical name.

    We construct explicit provider instances to allow custom base URLs and API keys.
    """
    if model_name == "gpt-5":
        # OpenAI provider (replace 'gpt-5' with a valid model for your account if needed)
        api_key = os.environ.get("OPENAI_API_KEY")
        provider = OpenAIProvider(api_key=api_key)
        return OpenAIChatModel("gpt-5", provider=provider)

    if model_name == "claude-4.5-sonnet":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        provider = AnthropicProvider(api_key=api_key)
        return AnthropicModel("claude-4.5-sonnet", provider=provider)

    if model_name == "grok-code-fast-1":
        # OpenRouter: use OpenAI-compatible endpoint
        api_key = os.environ.get("OPENROUTER_API_KEY")
        base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        provider = OpenRouterProvider(api_key=api_key, base_url=base_url)
        # OpenRouter model ids look like "openrouter/x-ai/grok-code-fast-1" for some SDKs;
        # with OpenAI-compatible endpoints, use the raw provider's model id.
        return OpenRouterModel("x-ai/grok-code-fast-1", provider=provider)

    raise ValueError(f"Unknown model: {model_name}")


def build_agent(model_name: ModelName) -> Agent:
    """Create an Agent with our system prompt for the selected model.

    The agent expects tools to be registered by the caller, since tool
    behavior depends on CLI-provided dependencies (approval, UI, etc.).
    """
    model = build_model(model_name)
    # Tools will be attached by the CLI using .override or passing tools here.
    return Agent(model, system_prompt=SYSTEM_PROMPT)
