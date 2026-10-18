"""In-process LLM on Apple Silicon via mlx-lm (Metal, unified memory)."""

from __future__ import annotations

import logging

from grizzly.llm.base import Message, strip_reasoning

log = logging.getLogger(__name__)


class MLXLLM:
    def __init__(self, model: str) -> None:
        from mlx_lm import load

        log.info("Loading LLM %s (first run downloads it from Hugging Face)", model)
        self.model_name = model
        self.model, self.tokenizer = load(model)

    def chat(self, messages: list[Message], max_tokens: int, temperature: float) -> str:
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        prompt = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=False,
            # Qwen3 and similar: answer directly instead of spending tokens on a
            # hidden reasoning trace. Ignored by templates that don't use it.
            enable_thinking=False,
        )
        text = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            sampler=make_sampler(temp=temperature, top_p=0.9),
            verbose=False,
        )
        return strip_reasoning(text)

    def unload(self) -> None:
        self.model = None
        self.tokenizer = None
