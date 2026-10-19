from __future__ import annotations

from pathlib import Path
from typing import Protocol

from PIL import Image

from grizzly.config import Profile


class ImageModel(Protocol):
    def generate(self, prompt: str, seed: int, width: int, height: int, refs: list[Path] | None = None) -> Image.Image: ...

    def unload(self) -> None: ...


def create_image_model(profile: Profile) -> ImageModel:
    """Text-only model: character portraits, and shots when references are off."""
    if profile.image_backend == "mflux":
        from grizzly.image.mflux_backend import MfluxImageModel

        return MfluxImageModel(profile.image_model, profile.image_steps)
    if profile.image_backend == "mock":
        from grizzly.image.mock import MockImageModel

        return MockImageModel()
    raise ValueError(f"Unknown image backend {profile.image_backend!r}")


def create_ref_model(profile: Profile) -> ImageModel:
    """Reference-conditioned model: draws shots from the cast's portraits."""
    if profile.ref_backend == "mflux-flux2":
        from grizzly.image.mflux_flux2_backend import MfluxFlux2RefModel

        return MfluxFlux2RefModel(profile.ref_model, profile.ref_steps)
    if profile.ref_backend == "mock":
        from grizzly.image.mock import MockImageModel

        return MockImageModel()
    raise ValueError(f"Unknown reference backend {profile.ref_backend!r}")
