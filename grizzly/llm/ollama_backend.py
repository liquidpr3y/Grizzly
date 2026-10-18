"""Use a running Ollama server as the writer. No extra dependencies."""

from __future__ import annotations

import json
import urllib.request

from grizzly.llm.base import Message, strip_reasoning


class OllamaLLM:
    def __init__(self, model: str, url: str) -> None:
        self.model = model
        self.url = url.rstrip("/")

    def chat(self, messages: list[Message], max_tokens: int, temperature: float) -> str:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,
            "format": "json",
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        req = urllib.request.Request(
            f"{self.url}/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.load(resp)
        return strip_reasoning(data["message"]["content"])

    def unload(self) -> None:
        # Ask Ollama to evict the model so the diffusion model gets the memory.
        body = json.dumps({"model": self.model, "keep_alive": 0}).encode()
        req = urllib.request.Request(
            f"{self.url}/api/generate", data=body, headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(req, timeout=30).close()
        except OSError:
            pass
