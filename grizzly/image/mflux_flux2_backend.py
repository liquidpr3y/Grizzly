"""FLUX.2 Klein 4B on Apple Silicon via mflux, with reference images.

Each reference image is VAE-encoded and its tokens are concatenated with the
image being generated, so the model can copy a character's look from their
portrait into a new composition.

mflux's edit variant cannot run without references (it concatenates the
missing reference latents), so shots with nobody in frame go through the
text-to-image variant. Both load the same weights; only one is resident at a
time, and callers should batch shots by `needs_refs` to avoid swapping.
"""

from __future__ import annotations

import gc
import logging
from pathlib import Path

from PIL import Image

from grizzly.memory import release_accelerator_memory

log = logging.getLogger(__name__)


class MfluxFlux2RefModel:
    def __init__(self, model_path: str, steps: int) -> None:
        self.model_path = model_path
        self.steps = steps
        self._kind: str | None = None  # "edit" | "txt2img"
        self.model = None

    def _ensure(self, kind: str) -> None:
        if self._kind == kind:
            return
        from mflux.models.common.config import ModelConfig
        from mflux.models.flux2.variants import Flux2Klein, Flux2KleinEdit

        self.unload()
        log.info("Loading FLUX.2 Klein (%s) from %s (first run downloads it from Hugging Face)", kind, self.model_path)
        cls = Flux2KleinEdit if kind == "edit" else Flux2Klein
        self.model = cls(model_config=ModelConfig.flux2_klein_4b(), model_path=self.model_path)
        self._kind = kind

    def generate(self, prompt: str, seed: int, width: int, height: int, refs: list[Path] | None = None) -> Image.Image:
        self._ensure("edit" if refs else "txt2img")
        kwargs = dict(seed=seed, prompt=prompt, num_inference_steps=self.steps, width=width, height=height)
        if refs:
            kwargs["image_paths"] = [str(p) for p in refs]
        return self.model.generate_image(**kwargs).image

    def unload(self) -> None:
        if self.model is not None:
            self.model = None
            self._kind = None
            gc.collect()
            release_accelerator_memory()
