"""Animate rendered panels into short clips (image-to-video).

Each clip starts from the shot's panel, so the characters keep the look the
reference portraits gave them; the prompt only has to describe motion.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from PIL import Image, ImageChops, ImageStat

from grizzly.config import Profile
from grizzly.models import Project, Shot
from grizzly.video import VideoModel
from grizzly.visuals import Progress, shot_cast, stable_seed

log = logging.getLogger(__name__)

CAMERA = {
    "wide": "slow cinematic camera drift across the scene",
    "medium": "gentle camera push-in",
    "close-up": "very slight camera push-in, shallow depth of field",
}


# Mean absolute pixel change between first and last frame, as a fraction of
# full scale. Below this a clip reads as a still image.
STATIC_THRESHOLD = 0.02


def clip_motion(path: Path) -> float:
    """How much a clip changes from its first frame to its last (0..1)."""
    with tempfile.TemporaryDirectory() as tmp:
        first, last = Path(tmp) / "first.png", Path(tmp) / "last.png"
        for args, out in ((["-i", str(path)], first), (["-sseof", "-0.1", "-i", str(path)], last)):
            subprocess.run(
                ["ffmpeg", "-y", *args, "-frames:v", "1", "-update", "1", str(out)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
        a = Image.open(first).convert("L")
        b = Image.open(last).convert("L").resize(a.size)
        return ImageStat.Stat(ImageChops.difference(a, b)).mean[0] / 255


def motion_prompt(project: Project, shot: Shot) -> str:
    bible = project.bible
    names = ", ".join(c.name for c in shot_cast(bible, shot))
    parts = [
        bible.art_style,
        shot.action,
        f"{names} move naturally with small, believable gestures and expressions" if names else "ambient motion in the environment",
        CAMERA.get(shot.framing, CAMERA["medium"]),
        "one continuous shot, consistent characters and lighting, smooth motion",
    ]
    if bible.tone:
        parts.append(f"mood: {bible.tone}")
    return ". ".join(p.strip().rstrip(".") for p in parts if p) + "."


def render_videos(
    project: Project,
    root: Path,
    model: VideoModel,
    profile: Profile,
    force: bool = False,
    only: set[str] | None = None,
    reroll: bool = False,
    progress: Progress | None = None,
    on_each: Callable[[], None] | None = None,
) -> None:
    out = root / "video"
    todo = [
        s
        for s in project.shots
        if s.image
        and (only is None or s.id in only)
        and (force or only is not None or not (s.video and (root / s.video).exists()))
    ]
    w, h = profile.video_size
    failed: list[tuple[str, Exception]] = []
    for i, shot in enumerate(todo):
        if progress:
            progress(i, len(todo), f"clip {shot.id}")
        if reroll:
            shot.video_take += 1
        key = f"{shot.id}:video" if not shot.video_take else f"{shot.id}:video:{shot.video_take}"
        prompt = motion_prompt(project, shot)
        log.info("Animating %s (%dx%d, %d frames): %s", shot.id, w, h, profile.video_frames, prompt[:160])
        path = out / f"{shot.id}.mp4"
        try:
            model.generate(prompt, root / shot.image, stable_seed(project, key), w, h, profile.video_frames, path)
        except Exception as exc:
            log.error("Clip %s failed: %s", shot.id, exc, exc_info=True)
            failed.append((shot.id, exc))
            shot.video = None
        else:
            shot.video = str(path.relative_to(root))
            score = clip_motion(path)
            if score < STATIC_THRESHOLD:
                log.warning("Clip %s barely moves (motion %.3f); try a larger size or --reroll", shot.id, score)
            else:
                log.info("Clip %s motion %.3f", shot.id, score)
        if on_each:
            on_each()
    if failed:
        ids = ", ".join(sid for sid, _ in failed)
        raise RuntimeError(f"{len(failed)} clip(s) failed ({ids}); first error: {failed[0][1]!r}")
