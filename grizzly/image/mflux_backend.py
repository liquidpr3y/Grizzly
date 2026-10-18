"""Z-Image Turbo on Apple Silicon via mflux (MLX).

The default checkpoint is pre-quantised to 4-bit (~6-7GB resident), which is
what makes it comfortable on a 24GB machine. Turbo is guidance-distilled, so
there is no negative prompt and ~9 steps is enough.
"""

from __future__ import annotations

import logging

from PIL import Image

log = logging.getLogger(__name__)


class MfluxImageModel:
    def __init__(self, model_path: str, steps: int) -> None:
        from mflux.models.common.config import ModelConfig
        from mflux.models.z_image import ZImage

        log.info("Loading image model %s (first run downloads it from Hugging Face)", model_path)
        self.steps = steps
        self.model = ZImage(model_config=ModelConfig.z_image_turbo(), model_path=model_path)

    def generate(self, prompt: str, seed: int, width: int, height: int) -> Image.Image:
        result = self.model.generate_image(
            seed=seed,
            prompt=prompt,
            num_inference_steps=self.steps,
            width=width,
            height=height,
        )
        return result.image

    def unload(self) -> None:
        self.model = None
