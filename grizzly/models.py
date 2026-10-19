"""Story data model. Everything the pipeline produces is plain, editable JSON."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Format = Literal["comic", "vn", "film"]
FRAMINGS = ("wide", "medium", "close-up")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "item"


class Character(BaseModel):
    id: str
    name: str
    role: str = ""
    personality: str = ""
    # Fixed visual description, injected verbatim into every image prompt so
    # the character looks the same from shot to shot.
    appearance: str
    # macOS `say` voice for animatic narration, e.g. "Daniel". Empty = default.
    voice: str = ""
    portrait: str | None = None
    # Bumped to re-draw ("reroll") the portrait with a fresh seed. The portrait
    # is the reference every shot copies, so it is worth getting right.
    portrait_seed: int = 0

    @field_validator("id", mode="before")
    @classmethod
    def _slug_id(cls, v: str) -> str:
        return slugify(str(v))


class Location(BaseModel):
    id: str
    name: str
    description: str

    @field_validator("id", mode="before")
    @classmethod
    def _slug_id(cls, v: str) -> str:
        return slugify(str(v))


class StoryBible(BaseModel):
    title: str
    logline: str
    genre: str = ""
    tone: str = ""
    # Global art direction prepended to every image prompt.
    art_style: str
    characters: list[Character]
    locations: list[Location]

    def character(self, ref: str) -> Character | None:
        key = slugify(ref)
        for c in self.characters:
            if c.id == key or slugify(c.name) == key:
                return c
        return None

    def location(self, ref: str) -> Location | None:
        key = slugify(ref)
        for loc in self.locations:
            if loc.id == key or slugify(loc.name) == key:
                return loc
        return None


class SceneOutline(BaseModel):
    id: str
    title: str
    summary: str
    location_id: str
    character_ids: list[str] = Field(default_factory=list)


class Outline(BaseModel):
    scenes: list[SceneOutline]


class DialogueLine(BaseModel):
    speaker: str  # character id, or "narrator"
    text: str


class Shot(BaseModel):
    id: str
    scene_id: str
    framing: str = "medium"
    # What the camera sees. Visual only: no dialogue, no text.
    action: str
    character_ids: list[str] = Field(default_factory=list)
    location_id: str = ""
    dialogue: list[DialogueLine] = Field(default_factory=list)
    narration: str = ""
    duration: float = 4.0
    image: str | None = None

    @field_validator("framing", mode="before")
    @classmethod
    def _norm_framing(cls, v: str) -> str:
        v = str(v).lower().replace("_", "-").replace(" ", "-")
        if v in ("closeup", "close", "extreme-close-up", "portrait"):
            return "close-up"
        if v in ("establishing", "long", "wide-shot", "full", "panorama"):
            return "wide"
        return v if v in FRAMINGS else "medium"


class Project(BaseModel):
    id: str
    title: str
    premise: str
    format: Format = "comic"
    seed: int = 1234
    created: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    bible: StoryBible | None = None
    outline: Outline | None = None
    shots: list[Shot] = Field(default_factory=list)

    def status(self) -> dict[str, bool]:
        return {
            "bible": self.bible is not None,
            "outline": self.outline is not None,
            "shots": bool(self.shots),
            "portraits": bool(self.bible) and all(c.portrait for c in self.bible.characters),
            "images": bool(self.shots) and all(s.image for s in self.shots),
        }
