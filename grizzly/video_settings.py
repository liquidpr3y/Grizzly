"""How a clip gets made: the project's video settings, a shot's overrides and
a one-off request, resolved down to what the video model is called with.

Precedence, highest first: the run's request, the shot, the project, then
the video model's own defaults (today the hardware profile's video_* fields).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from grizzly.config import Profile
from grizzly.models import ASPECTS, Project, Shot, VideoOverride

# Wan 2.2 TI2V-5B renders at 24fps; clip length in seconds converts at this rate.
MODEL_FPS = 24
# Pixel budget per quality, relative to the model's default size. For Wan
# that default is its training size (1280x704) and "draft" is its 480p
# (832x480); well below that its clips come out frozen.
QUALITY_SCALE = {"draft": 832 * 480 / (1280 * 704), "standard": 1.0}
# Wan needs 4n+1 frames; 121 (~5s) is the longest it was trained on.
MIN_FRAMES, MAX_FRAMES = 17, 121


def aspect_ratio(aspect: str) -> float:
    w, h = ASPECTS.get(aspect, ASPECTS["16:9"])
    return w / h


def size_for(aspect: str, area: int, multiple: int) -> tuple[int, int]:
    """Width and height near `area` pixels at `aspect`, snapped to `multiple`."""
    r = aspect_ratio(aspect)
    w, h = math.sqrt(area * r), math.sqrt(area / r)
    return max(multiple, round(w / multiple) * multiple), max(multiple, round(h / multiple) * multiple)


def video_size(aspect: str, quality: str | None, default: tuple[int, int]) -> tuple[int, int]:
    if quality is None and aspect == "16:9":
        return default
    area = default[0] * default[1] * QUALITY_SCALE.get(quality or "", 1.0)
    return size_for(aspect, round(area), 32)


def frames_for(seconds: float) -> int:
    """Nearest 4n+1 frame count for `seconds` of clip, within what Wan handles."""
    n = round(seconds * MODEL_FPS / 4)
    return min(MAX_FRAMES, max(MIN_FRAMES, n * 4 + 1))


@dataclass(frozen=True)
class ResolvedVideo:
    width: int
    height: int
    frames: int
    steps: int
    negative_prompt: str | None
    # Fixed seed from the request or the shot; None = the shot's take seed.
    seed: int | None
    guidance: float | None


def model_defaults(profile: Profile) -> dict:
    """The active video model's defaults. The model registry replaces this."""
    return {"size": list(profile.video_size), "frames": profile.video_frames, "steps": profile.video_steps}


def resolve_video_settings(
    project: Project, shot: Shot, request: VideoOverride | None, profile: Profile
) -> ResolvedVideo:
    defaults = model_defaults(profile)
    project_video = project.video
    req = request or VideoOverride()

    def pick(*values):
        return next((v for v in values if v is not None), None)

    aspect = pick(req.aspect, project_video.aspect)
    quality = pick(req.quality, project_video.quality)
    width, height = video_size(aspect, quality, tuple(defaults["size"]))
    shot_video = shot.video_options
    seconds = pick(req.clip_seconds, shot_video.clip_seconds, project_video.clip_seconds)
    frames = frames_for(seconds) if seconds is not None else defaults["frames"]
    steps = pick(req.steps, shot_video.steps, project_video.steps, defaults["steps"])
    negative = project_video.negative_prompt.strip() or None
    seed = pick(req.seed, shot_video.seed)
    guidance = pick(req.guidance, project_video.guidance)
    return ResolvedVideo(width, height, frames, steps, negative, seed, guidance)
