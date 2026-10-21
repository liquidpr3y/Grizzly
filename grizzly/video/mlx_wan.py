"""Image-to-video with Wan 2.2 TI2V-5B on Apple Silicon via mlx-video.

mlx-video loads the UMT5 text encoder, encodes the prompt, frees it, then
loads the video model, so peak memory is roughly the larger of the two
rather than their sum. It does this per clip, so each call pays the load
time; generation itself dominates at these sizes.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


class MlxWanVideoModel:
    def __init__(self, repo: str, steps: int) -> None:
        self.repo = repo
        self.steps = steps
        self._model_dir: str | None = None

    def _ensure_downloaded(self) -> str:
        if self._model_dir is None:
            path = Path(self.repo).expanduser()
            if path.is_dir():
                self._model_dir = str(path)
            else:
                from huggingface_hub import snapshot_download

                log.info("Fetching video model %s (first run downloads ~20GB)", self.repo)
                self._model_dir = snapshot_download(self.repo)
        return self._model_dir

    def generate(
        self, prompt: str, image: Path, seed: int, width: int, height: int, frames: int, out: Path, **options
    ) -> Path:
        from mlx_video.models.wan_2.generate import generate_video

        out.parent.mkdir(parents=True, exist_ok=True)
        generate_video(
            model_dir=self._ensure_downloaded(),
            prompt=prompt,
            image=str(image),
            width=width,
            height=height,
            num_frames=frames,
            steps=options.get("steps") or self.steps,
            seed=seed,
            output_path=str(out),
            tiling="auto",
        )
        return out

    def unload(self) -> None:
        # Nothing stays resident between clips.
        pass
