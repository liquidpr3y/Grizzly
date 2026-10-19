"""Turn shots into image prompts and render them.

Consistency strategy: every prompt repeats the global art style, each visible
character's fixed appearance text and the location description, with seeds
derived from stable ids. When the profile has a reference renderer, each shot
is also drawn from the portraits of the characters in frame, which pins down
details text alone drifts on (which eye the monocle is on, glasses vs monocle).
"""

from __future__ import annotations

import logging
import re
import zlib
from pathlib import Path
from typing import Callable

from PIL import Image

from grizzly.config import Profile
from grizzly.image import ImageModel
from grizzly.models import Character, Project, Shot, StoryBible

log = logging.getLogger(__name__)

FRAMING_PHRASES = {
    "wide": "wide establishing shot, full figure visible, environment visible",
    "medium": "medium shot from the waist up",
    "close-up": "close-up on the face, expressive detail",
}
NO_TEXT = "clean illustration with no text, no lettering, no speech bubbles, no watermark"
# Each reference adds image tokens (time and memory); a panel rarely needs more.
MAX_REFS = 3


def stable_seed(project: Project, key: str) -> int:
    return (project.seed + zlib.crc32(key.encode())) % (2**31)


def portrait_prompt(bible: StoryBible, c: Character) -> str:
    return (
        f"{bible.art_style}. Full-body character reference of {c.name}: {c.appearance}. "
        f"Single figure, standing, three-quarter view, whole outfit and accessories clearly visible, "
        f"plain light background, even lighting. {NO_TEXT}."
    )


_TITLES = {"mr", "mrs", "ms", "miss", "lord", "lady", "sir", "dr", "doctor", "captain", "the", "old", "young"}


def _mentions(text: str, c: Character) -> bool:
    words = set(re.findall(r"[a-z0-9']+", text.lower()))
    names = [w for w in re.findall(r"[a-z0-9']+", c.name.lower()) if w not in _TITLES and len(w) >= 3]
    return c.name.lower() in text.lower() or any(n in words for n in names)


def shot_cast(bible: StoryBible, shot: Shot) -> list[Character]:
    """Characters listed for the shot, plus any the action describes but the
    writer forgot to list. Without this their appearance text is missing and
    the model invents a different-looking character."""
    cast = [c for c in (bible.character(cid) for cid in shot.character_ids) if c]
    for c in bible.characters:
        if c not in cast and _mentions(shot.action, c):
            cast.append(c)
    return cast


def shot_prompt(bible: StoryBible, shot: Shot, film: bool = False, ref_ids: list[str] | None = None) -> str:
    """ref_ids: ids of the characters whose portraits are passed as reference
    images, in order, so the prompt can say which image shows whom."""
    parts = [bible.art_style, FRAMING_PHRASES.get(shot.framing, ""), shot.action]
    cast = shot_cast(bible, shot)
    ref_ids = ref_ids or []
    for c in cast:
        if c.id in ref_ids:
            parts.append(f"{c.name} looks exactly like the character in image {ref_ids.index(c.id) + 1}: {c.appearance}")
        else:
            parts.append(f"{c.name}: {c.appearance}")
    # Diffusion models duplicate characters in wide shots and invent them in
    # empty ones. They don't know character names, so give a numeric count.
    if not cast:
        parts.append("no main characters in frame")
    elif len(cast) == 1:
        parts.append(f"exactly one main figure ({cast[0].name}), appearing only once, no duplicates")
    else:
        names = " and ".join(c.name for c in cast)
        parts.append(f"exactly {len(cast)} main figures ({names}), each appearing only once, no duplicates")
    if ref_ids:
        # With several references the model sometimes draws one character
        # twice (Kyler appeared twice in 3 of 16 heist panels).
        parts.append(
            "each reference image shows one different character; draw every one of them exactly once, "
            "never two copies of the same person"
        )
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


def render_portraits(
    project: Project,
    root: Path,
    model: ImageModel,
    profile: Profile,
    force: bool = False,
    progress: Progress | None = None,
    only: set[str] | None = None,
    reroll: bool = False,
) -> None:
    """Draw missing portraits. `only` limits to those character ids (and
    re-draws them); `reroll` also moves them to a fresh seed."""
    out = root / "images" / "characters"
    out.mkdir(parents=True, exist_ok=True)
    chars = [c for c in project.bible.characters if only is None or c.id in only]
    for i, c in enumerate(chars):
        if reroll:
            c.portrait_seed += 1
        if c.portrait and (root / c.portrait).exists() and not (force or only or reroll):
            continue
        if progress:
            progress(i, len(chars), f"portrait {c.name}")
        w, h = profile.sizes["portrait"]
        key = c.id if not c.portrait_seed else f"{c.id}:{c.portrait_seed}"
        img = model.generate(portrait_prompt(project.bible, c), stable_seed(project, key), w, h)
        path = out / f"{c.id}.png"
        img.save(path)
        c.portrait = str(path.relative_to(root))


def reference_images(project: Project, root: Path, profile: Profile, shot: Shot) -> list[tuple[str, Path]]:
    """(character id, downscaled portrait) for the characters in frame that
    have a portrait, at most MAX_REFS, in cast order."""
    out = root / "images" / "refs"
    refs: list[tuple[str, Path]] = []
    for c in shot_cast(project.bible, shot)[:MAX_REFS]:
        if not c.portrait or not (root / c.portrait).exists():
            continue
        src, dst = root / c.portrait, out / f"{c.id}.png"
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            out.mkdir(parents=True, exist_ok=True)
            img = Image.open(src).convert("RGB")
            img.thumbnail((profile.ref_max_side, profile.ref_max_side), Image.LANCZOS)
            img.save(dst)
        refs.append((c.id, dst))
    return refs


def render_shots(
    project: Project,
    root: Path,
    model: ImageModel,
    profile: Profile,
    force: bool = False,
    only: set[str] | None = None,
    progress: Progress | None = None,
    on_each: Callable[[], None] | None = None,
    use_refs: bool = False,
    reroll: bool = False,
) -> None:
    out = root / "images" / "shots"
    out.mkdir(parents=True, exist_ok=True)
    todo = [
        s
        for s in project.shots
        if (only is None or s.id in only) and (force or only is not None or not (s.image and (root / s.image).exists()))
    ]
    plan = [(s, reference_images(project, root, profile, s) if use_refs else []) for s in todo]
    # Shots with references first: the reference backend swaps variants
    # between with- and without-reference shots, so group them.
    plan.sort(key=lambda item: not item[1])
    failed: list[tuple[str, Exception]] = []
    for i, (shot, refs) in enumerate(plan):
        if progress:
            progress(i, len(plan), f"shot {shot.id}")
        if reroll:
            shot.seed_offset += 1
        w, h = shot_size(profile, project, shot)
        prompt = shot_prompt(project.bible, shot, film=project.format != "comic", ref_ids=[cid for cid, _ in refs])
        log.info("Rendering %s (%dx%d, %d refs): %s", shot.id, w, h, len(refs), prompt[:160])
        key = shot.id if not shot.seed_offset else f"{shot.id}:{shot.seed_offset}"
        try:
            img = model.generate(prompt, stable_seed(project, key), w, h, refs=[p for _, p in refs])
        except Exception as exc:
            # Keep going, but drop the stale image so exports can't silently
            # use the previous version of this shot.
            log.error("Shot %s failed: %s", shot.id, exc, exc_info=True)
            failed.append((shot.id, exc))
            shot.image = None
        else:
            path = out / f"{shot.id}.png"
            img.save(path)
            shot.image = str(path.relative_to(root))
        if on_each:
            on_each()
    if failed:
        ids = ", ".join(sid for sid, _ in failed)
        raise RuntimeError(f"{len(failed)} shot(s) failed ({ids}); first error: {failed[0][1]!r}")
