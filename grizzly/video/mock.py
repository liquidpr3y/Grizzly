"""Stand-in clip: a slow zoom on the source image, made with ffmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path


class MockVideoModel:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate(self, prompt: str, image: Path, seed: int, width: int, height: int, frames: int, out: Path) -> Path:
        out.parent.mkdir(parents=True, exist_ok=True)
        vf = (
            f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,crop={width * 2}:{height * 2},"
            f"zoompan=z='1+0.1*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps=24,"
            "format=yuv420p"
        )
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(image), "-vf", vf, "-frames:v", str(frames), "-c:v", "libx264", str(out)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        self.calls.append({"prompt": prompt, "image": str(image), "seed": seed})
        return out

    def unload(self) -> None:
        pass
