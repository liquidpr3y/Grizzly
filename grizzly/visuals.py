"""Turn shots into image prompts and render them.

Consistency strategy for the prototype: every prompt repeats the global art
style, each visible character's fixed appearance text and the location
description, with seeds derived from stable ids. Next steps (see README) are
per-character LoRAs and reference-image conditioning.
"""

from __future__ import annotations

import logging
import zlib
from pathlib import Path
from typing import Callable

from grizzly.config import Profile
from grizzly.image import ImageModel
from grizzly.models import Character, Project, Shot, StoryBible

log = logging.getLogger(__name__)

FRAMING_PHRASES = {
    "wide": "wide establishing shot, full bodies, environment visible",
    "medium": "medium shot from the waist up",
    "close-up": "close-up on the face, expressive detail",
}
NO_TEXT = "clean illustration with no text, no lettering, no speech bubbles, no watermark"


def stable_seed(project: Project, key: str) -> int:
    return (project.seed + zlib.crc32(key.encode())) % (2**31)


def portrait_prompt(bible: StoryBible, c: Character) -> str:
    return (
        f"{bible.art_style}. Character reference portrait of {c.name}: {c.appearance}. "
        f"Three-quarter view, neutral plain background, even lighting. {NO_TEXT}."
    )


def shot_prompt(bible: StoryBible, shot: Shot, film: bool = False) -> str:
    parts = [bible.art_style, FRAMING_PHRASES.get(shot.framing, ""), shot.action]
    cast = [bible.character(cid) for cid in shot.character_ids]
    for c in filter(None, cast):
        parts.append(f"{c.name}: {c.appearance}")
    loc = bible.location(shot.location_id) if shot.location_id else None
    if loc:
        parts.append(f"Setting: {loc.description}")
    if bible.tone:
        parts.append(f"Mood: {bible.tone}")
    if film:
        parts.append("cinematic 16:9 composition")
    parts.append(NO_TEXT)
    return ". ".join(p.strip().rstrip(".") for p in parts if p and p.strip()) + "."


def shot_size(profile: Profile, project: Project, shot: Shot) -> tuple[int, int]:
    if project.format in ("film", "vn"):
        return profile.sizes["film"]
    return profile.sizes.get(shot.framing, profile.sizes["medium"])


Progress = Callable[[int, int, str], None]


def render_portraits(project: Project, root: Path, model: ImageModel, profile: Profile, force: bool = False, progress: Progress | None = None) -> None:
    out = root / "images" / "characters"
    out.mkdir(parents=True, exist_ok=True)
    chars = project.bible.characters
    for i, c in enumerate(chars):
        if c.portrait and (root / c.portrait).exists() and not force:
            continue
        if progress:
            progress(i, len(chars), f"portrait {c.name}")
        w, h = profile.sizes["portrait"]
        img = model.generate(portrait_prompt(project.bible, c), stable_seed(project, c.id), w, h)
        path = out / f"{c.id}.png"
        img.save(path)
        c.portrait = str(path.relative_to(root))


def render_shots(
    project: Project,
    root: Path,
    model: ImageModel,
    profile: Profile,
    force: bool = False,
    only: set[str] | None = None,
    progress: Progress | None = None,
    on_each: Callable[[], None] | None = None,
) -> None:
    out = root / "images" / "shots"
    out.mkdir(parents=True, exist_ok=True)
    todo = [
        s
        for s in project.shots
        if (only is None or s.id in only) and (force or only is not None or not (s.image and (root / s.image).exists()))
    ]
    for i, shot in enumerate(todo):
        if progress:
            progress(i, len(todo), f"shot {shot.id}")
        w, h = shot_size(profile, project, shot)
        prompt = shot_prompt(project.bible, shot, film=project.format != "comic")
        log.info("Rendering %s (%dx%d): %s", shot.id, w, h, prompt[:160])
        img = model.generate(prompt, stable_seed(project, shot.id), w, h)
        path = out / f"{shot.id}.png"
        img.save(path)
        shot.image = str(path.relative_to(root))
        if on_each:
            on_each()
