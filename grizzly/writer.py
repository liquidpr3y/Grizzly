"""LLM-assisted writing: premise -> story bible -> scene outline -> shot list."""

from __future__ import annotations

import json
import logging
from typing import Callable, TypeVar

from pydantic import BaseModel, ValidationError

from grizzly import prompts
from grizzly.config import Profile
from grizzly.jsonutil import extract_json
from grizzly.llm.base import LLM, Message
from grizzly.models import Outline, Project, Shot, StoryBible

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class Writer:
    def __init__(self, llm: LLM, profile: Profile, retries: int = 3) -> None:
        self.llm = llm
        self.profile = profile
        self.retries = retries

    def _ask(self, system: str, user: str, model: type[T], fix: Callable[[dict], dict] = lambda d: d) -> T:
        messages: list[Message] = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        error = ""
        for attempt in range(1, self.retries + 1):
            raw = self.llm.chat(messages, self.profile.llm_max_tokens, self.profile.llm_temperature)
            try:
                return model.model_validate(fix(extract_json(raw)))
            except (ValueError, ValidationError) as exc:
                error = str(exc)
                log.warning("Attempt %d produced invalid %s: %s", attempt, model.__name__, error[:300])
                # Show the model its own output and the error, and ask again.
                messages = messages[:2] + [
                    {"role": "assistant", "content": raw[:4000]},
                    {"role": "user", "content": f"That was not valid. Error: {error[:800]}\nReply again with ONLY the corrected JSON."},
                ]
        raise RuntimeError(f"Writer could not produce a valid {model.__name__}: {error}")

    def bible(self, project: Project, n_characters: int = 3, n_locations: int = 3) -> StoryBible:
        system = prompts.BIBLE_SYSTEM.format(
            format_note=prompts.FORMAT_NOTES[project.format],
            n_characters=n_characters,
            n_locations=n_locations,
        )
        def fix(data: dict) -> dict:
            if not data.get("characters") or not data.get("locations"):
                raise ValueError("bible needs at least one character and one location")
            return data

        bible = self._ask(system, prompts.bible_user(project.premise), StoryBible, fix)
        for c in bible.characters:
            c.portrait = None
        return bible

    def outline(self, project: Project, n_scenes: int = 4) -> Outline:
        bible = project.bible
        system = prompts.OUTLINE_SYSTEM.format(n_scenes=n_scenes)

        def fix(data: dict) -> dict:
            for i, scene in enumerate(data.get("scenes", [])):
                scene["id"] = f"s{i + 1}"
                loc = bible.location(str(scene.get("location_id", "")))
                scene["location_id"] = loc.id if loc else bible.locations[0].id
                scene["character_ids"] = _resolve_characters(bible, scene.get("character_ids", []))
            return data

        return self._ask(system, prompts.outline_user(_bible_json(bible)), Outline, fix)

    def shots(self, project: Project, n_shots: int = 4) -> list[Shot]:
        bible, outline = project.bible, project.outline
        system = prompts.SHOTS_SYSTEM.format(format_note=prompts.FORMAT_NOTES[project.format], n_shots=n_shots)
        all_shots: list[Shot] = []
        previous = ""
        for scene in outline.scenes:

            def fix(data: dict, scene=scene) -> dict:
                for i, shot in enumerate(data.get("shots", [])):
                    shot["id"] = f"{scene.id}_{i + 1:02d}"
                    shot["scene_id"] = scene.id
                    shot["location_id"] = scene.location_id
                    shot["character_ids"] = _resolve_characters(bible, shot.get("character_ids", []))
                    for line in shot.get("dialogue") or []:
                        c = bible.character(str(line.get("speaker", "")))
                        line["speaker"] = c.id if c else "narrator"
                    shot["narration"] = shot.get("narration") or ""
                return data

            class _Shots(BaseModel):
                shots: list[Shot]

            result = self._ask(system, prompts.shots_user(_bible_json(bible), scene.model_dump_json(), previous), _Shots, fix)
            all_shots.extend(result.shots)
            previous = scene.summary
            log.info("Scene %s: %d shots", scene.id, len(result.shots))
        return all_shots


def _resolve_characters(bible: StoryBible, refs: list) -> list[str]:
    ids: list[str] = []
    for ref in refs if isinstance(refs, list) else []:
        c = bible.character(str(ref))
        if c and c.id not in ids:
            ids.append(c.id)
    return ids


def _bible_json(bible: StoryBible) -> str:
    data = bible.model_dump(exclude={"characters": {"__all__": {"portrait", "voice"}}})
    return json.dumps(data, ensure_ascii=False)
