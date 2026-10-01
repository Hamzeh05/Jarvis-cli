import os
from dataclasses import dataclass, field

from langchain_openai import ChatOpenAI

from harness.config import (
    DEFAULT_MAIN_MODEL,
    LITELLM_API_KEY_ENV,
    LITELLM_URL,
)


@dataclass(frozen=True)
class ModelSpec:

    model_id: str
    provider: str
    base_url: str
    api_key: str
    description: str
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    fallback: str | None = None


MODELS = {

    "gemma4-31b": ModelSpec(
        model_id="gemma4-31b",
        provider="LiteLLM",
        base_url=LITELLM_URL,
        api_key=os.getenv(LITELLM_API_KEY_ENV, ""),
        description="Large general-purpose model.",
        capabilities=(
            "general",
            "analysis",
            "coding",
            "tools",
        ),
        fallback="qwen3-35b",
    ),

    "gemma4-31b-thinking": ModelSpec(
        model_id="gemma4-31b-thinking",
        provider="LiteLLM",
        base_url=LITELLM_URL,
        api_key=os.getenv(LITELLM_API_KEY_ENV, ""),
        description="Reasoning-focused Gemma model.",
        capabilities=(
            "reasoning",
            "analysis",
            "complex_tasks",
            "coding",
        ),
        fallback="gemma4-31b",
    ),

    "qwen3-35b": ModelSpec(
        model_id="qwen3-35b",
        provider="LiteLLM",
        base_url=LITELLM_URL,
        api_key=os.getenv(LITELLM_API_KEY_ENV, ""),
        description="Large Qwen general-purpose model.",
        capabilities=(
            "general",
            "coding",
            "tools",
            "reasoning",
            "analysis",
        ),
        fallback="gemma4-31b",
    ),

    "qwen3-35b-thinking": ModelSpec(
        model_id="qwen3-35b-thinking",
        provider="LiteLLM",
        base_url=LITELLM_URL,
        api_key=os.getenv(LITELLM_API_KEY_ENV, ""),
        description="Reasoning-focused Qwen model.",
        capabilities=(
            "reasoning",
            "complex_tasks",
            "analysis",
            "coding",
            "tools",
        ),
        fallback="qwen3-35b",
    ),
}


def get_model(model_id: str) -> ModelSpec:
    if model_id not in MODELS:
        raise ValueError(f"Unknown model: {model_id}")

    return MODELS[model_id]


def list_models() -> list[ModelSpec]:
    return list(MODELS.values())


def model_exists(model_id: str) -> bool:
    return model_id in MODELS


def create_llm(model_id: str) -> ChatOpenAI:
    spec = get_model(model_id)

    return ChatOpenAI(
        base_url=spec.base_url,
        api_key=spec.api_key,
        model=spec.model_id,
        temperature=0,
    )


def get_default_model() -> str:
    return DEFAULT_MAIN_MODEL
