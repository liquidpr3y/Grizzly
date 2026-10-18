from __future__ import annotations

from typing import Protocol

from PIL import Image

from grizzly.config import Profile


class ImageModel(Protocol):
    def generate(self, prompt: str, seed: int, width: int, height: int) -> Image.Image: ...

    def unload(self) -> None: ...


def create_image_model(profile: Profile) -> ImageModel:
    if profile.image_backend == "mflux":
        from grizzly.image.mflux_backend import MfluxImageModel

        return MfluxImageModel(profile.image_model, profile.image_steps)
    if profile.image_backend == "mock":
        from grizzly.image.mock import MockImageModel

        return MockImageModel()
    raise ValueError(f"Unknown image backend {profile.image_backend!r}")
