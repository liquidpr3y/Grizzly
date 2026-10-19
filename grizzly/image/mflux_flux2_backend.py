"""FLUX.2 Klein 4B on Apple Silicon via mflux, with reference images.

Each reference image is VAE-encoded and its tokens are concatenated with the
image being generated, so the model can copy a character's look from their
portrait into a new composition. With no references it is plain
text-to-image, so one model draws every shot and the style stays uniform.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

log = logging.getLogger(__name__)


class MfluxFlux2RefModel:
    def __init__(self, model_path: str, steps: int) -> None:
        from mflux.models.common.config import ModelConfig
        from mflux.models.flux2.variants import Flux2KleinEdit

        log.info("Loading reference model %s (first run downloads it from Hugging Face)", model_path)
        self.steps = steps
        self.model = Flux2KleinEdit(model_config=ModelConfig.flux2_klein_4b(), model_path=model_path)

    def generate(self, prompt: str, seed: int, width: int, height: int, refs: list[Path] | None = None) -> Image.Image:
        result = self.model.generate_image(
            seed=seed,
            prompt=prompt,
            num_inference_steps=self.steps,
            width=width,
            height=height,
            image_paths=[str(p) for p in refs] if refs else None,
        )
        return result.image

    def unload(self) -> None:
        self.model = None
