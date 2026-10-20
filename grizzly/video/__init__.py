from __future__ import annotations

from pathlib import Path
from typing import Protocol

from grizzly.config import Profile


class VideoModel(Protocol):
    def generate(
        self, prompt: str, image: Path, seed: int, width: int, height: int, frames: int, out: Path
    ) -> Path: ...

    def unload(self) -> None: ...


def create_video_model(profile: Profile) -> VideoModel:
    if profile.video_backend == "mlx-video-wan":
        from grizzly.video.mlx_wan import MlxWanVideoModel

        return MlxWanVideoModel(profile.video_model, profile.video_steps)
    if profile.video_backend == "mock":
        from grizzly.video.mock import MockVideoModel

        return MockVideoModel()
    raise ValueError(f"Unknown video backend {profile.video_backend!r}")
