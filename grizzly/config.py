"""Hardware profiles and runtime settings.

A profile pins which backends and models to use. The default targets a
MacBook Pro M5 Pro with 24GB unified memory: macOS lets the GPU wire roughly
two thirds of RAM (~16GB), so we keep exactly one heavy model resident at a
time and swap between the writer (LLM) and the illustrator (diffusion).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path


@dataclass(frozen=True)
class Profile:
    name: str
    llm_backend: str  # "mlx" | "ollama" | "mock"
    llm_model: str
    image_backend: str  # "mflux" | "mock"
    image_model: str
    image_steps: int
    # Unload the LLM before loading the image model (and vice versa).
    swap_models: bool = True
    llm_max_tokens: int = 3072
    llm_temperature: float = 0.7
    ollama_url: str = "http://127.0.0.1:11434"
    # Reference-conditioned shot renderer: draws each shot with the portraits
    # of the characters in frame as reference images. "" disables it (shots
    # then use the text-only image model).
    ref_backend: str = ""  # "mflux-flux2" | "mock" | ""
    ref_model: str = ""
    ref_steps: int = 4
    # Portraits are downscaled to this longest side before use as references;
    # every reference adds tokens, so smaller is faster and lighter.
    ref_max_side: int = 512
    # Image-to-video: animates a rendered panel into a short clip. Slow on
    # laptops, so it is its own step rather than part of `run`.
    video_backend: str = ""  # "mlx-video-wan" | "mock" | ""
    video_model: str = ""
    video_size: tuple[int, int] = (832, 480)  # multiples of 32, ~16:9
    video_frames: int = 49  # 4n+1; ~2s at 24fps
    video_steps: int = 30
    # Shot sizes per framing, kept to multiples of 16 for the diffusion VAE.
    sizes: dict[str, tuple[int, int]] = field(
        default_factory=lambda: {
            "wide": (1344, 768),
            "medium": (1024, 1024),
            "close-up": (896, 1152),
            "film": (1280, 720),
            "portrait": (896, 1152),
        }
    )


# FLUX.2 Klein 4B (Apache-2.0), pre-quantised to 4-bit: ~4.6GB, 4 steps.
_KLEIN_REFS = dict(ref_backend="mflux-flux2", ref_model="mflux-community/flux2-klein-4b-mflux-q4")
# Wan 2.2 TI2V-5B (Apache-2.0), 8-bit, via mlx-video: ~20GB download. The
# 11GB text encoder is freed before the video model loads.
_WAN_VIDEO = dict(video_backend="mlx-video-wan", video_model="Anes1032/Wan2.2-TI2V-5B-mlx-q8")

PROFILES: dict[str, Profile] = {
    # ~5GB LLM + ~7GB diffusion (both 4-bit), swapped. Leaves headroom for
    # activations at ~1MP and for macOS itself.
    "m5pro-24gb": Profile(
        name="m5pro-24gb",
        llm_backend="mlx",
        llm_model="mlx-community/Qwen3-8B-4bit",
        image_backend="mflux",
        image_model="filipstrand/Z-Image-Turbo-mflux-4bit",
        image_steps=9,
        **_KLEIN_REFS,
        **_WAN_VIDEO,
    ),
    # Same machine, but the writer runs in an existing Ollama install.
    "m5pro-24gb-ollama": Profile(
        name="m5pro-24gb-ollama",
        llm_backend="ollama",
        llm_model="qwen3:8b",
        image_backend="mflux",
        image_model="filipstrand/Z-Image-Turbo-mflux-4bit",
        image_steps=9,
        **_KLEIN_REFS,
        **_WAN_VIDEO,
    ),
    # Machines with 48GB+ can keep both models loaded and use a bigger writer.
    "mac-48gb": Profile(
        name="mac-48gb",
        llm_backend="mlx",
        llm_model="mlx-community/Qwen3-14B-4bit",
        image_backend="mflux",
        image_model="filipstrand/Z-Image-Turbo-mflux-4bit",
        image_steps=9,
        **_KLEIN_REFS,
        **_WAN_VIDEO,
        swap_models=False,
    ),
    # No ML at all: canned writer, placeholder art. Runs anywhere (CI, Linux).
    "mock": Profile(
        name="mock",
        llm_backend="mock",
        llm_model="mock",
        image_backend="mock",
        image_model="mock",
        image_steps=1,
        ref_backend="mock",
        ref_model="mock",
        ref_max_side=128,
        video_backend="mock",
        video_model="mock",
        video_size=(320, 192),
        video_frames=13,
        sizes={
            "wide": (672, 384),
            "medium": (512, 512),
            "close-up": (448, 576),
            "film": (640, 360),
            "portrait": (448, 576),
        },
    ),
}

DEFAULT_PROFILE = "m5pro-24gb"


def load_profile(name: str | None = None) -> Profile:
    """Resolve a profile, applying GRIZZLY_* environment overrides."""
    name = name or os.environ.get("GRIZZLY_PROFILE", DEFAULT_PROFILE)
    if name not in PROFILES:
        raise ValueError(f"Unknown profile {name!r}. Choose from: {', '.join(PROFILES)}")
    profile = PROFILES[name]
    overrides = {}
    for env, key, cast in (
        ("GRIZZLY_LLM_MODEL", "llm_model", str),
        ("GRIZZLY_IMAGE_MODEL", "image_model", str),
        ("GRIZZLY_IMAGE_STEPS", "image_steps", int),
        ("GRIZZLY_OLLAMA_URL", "ollama_url", str),
        ("GRIZZLY_VIDEO_MODEL", "video_model", str),
        ("GRIZZLY_VIDEO_FRAMES", "video_frames", int),
        ("GRIZZLY_VIDEO_STEPS", "video_steps", int),
    ):
        if os.environ.get(env):
            overrides[key] = cast(os.environ[env])
    if os.environ.get("GRIZZLY_REFS", "").lower() in ("0", "off", "false", "no"):
        overrides["ref_backend"] = ""
    return replace(profile, **overrides) if overrides else profile


def projects_dir() -> Path:
    path = Path(os.environ.get("GRIZZLY_HOME", Path.home() / "Grizzly")) / "projects"
    path.mkdir(parents=True, exist_ok=True)
    return path
