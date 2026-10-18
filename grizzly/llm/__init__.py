from __future__ import annotations

from grizzly.config import Profile
from grizzly.llm.base import LLM, Message


def create_llm(profile: Profile) -> LLM:
    if profile.llm_backend == "mlx":
        from grizzly.llm.mlx_backend import MLXLLM

        return MLXLLM(profile.llm_model)
    if profile.llm_backend == "ollama":
        from grizzly.llm.ollama_backend import OllamaLLM

        return OllamaLLM(profile.llm_model, profile.ollama_url)
    if profile.llm_backend == "mock":
        from grizzly.llm.mock import MockLLM

        return MockLLM()
    raise ValueError(f"Unknown LLM backend {profile.llm_backend!r}")


__all__ = ["LLM", "Message", "create_llm"]
