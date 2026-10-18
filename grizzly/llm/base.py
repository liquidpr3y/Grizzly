from __future__ import annotations

import re
from typing import Protocol, TypedDict


class Message(TypedDict):
    role: str  # "system" | "user" | "assistant"
    content: str


class LLM(Protocol):
    def chat(self, messages: list[Message], max_tokens: int, temperature: float) -> str: ...

    def unload(self) -> None: ...


_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_reasoning(text: str) -> str:
    """Drop <think> blocks emitted by reasoning models such as Qwen3."""
    text = _THINK.sub("", text)
    # An unterminated block means the model ran out of tokens mid-thought.
    if "<think>" in text:
        text = text.split("<think>", 1)[0]
    return text.strip()
