"""Deterministic stand-in writer so the whole pipeline runs without a model."""

from __future__ import annotations

import json
import re

from grizzly.jsonutil import extract_json
from grizzly.llm.base import Message

_BIBLE = {
    "title": "The Lighthouse Signal",
    "logline": "A young keeper discovers the lighthouse beam is answering something beneath the sea.",
    "genre": "mystery",
    "tone": "eerie, hopeful",
    "art_style": "ink and watercolour comic art, bold linework, muted teal and amber palette",
    "characters": [
        {
            "id": "mara",
            "name": "Mara",
            "role": "protagonist",
            "personality": "curious, stubborn",
            "appearance": "19-year-old woman, short copper hair, freckles, yellow oilskin coat, brass compass necklace",
            "voice": "",
        },
        {
            "id": "old_tom",
            "name": "Old Tom",
            "role": "mentor",
            "personality": "gruff, secretive",
            "appearance": "70-year-old man, white beard, navy fisherman's sweater, flat cap, eyepatch over left eye",
            "voice": "",
        },
    ],
    "locations": [
        {"id": "lighthouse", "name": "The Lighthouse", "description": "stone lighthouse on a cliff at night, rotating amber beam, storm clouds"},
        {"id": "harbour", "name": "Harbour", "description": "small fishing harbour at dawn, wooden boats, gulls, wet cobbles"},
    ],
}


class MockLLM:
    def chat(self, messages: list[Message], max_tokens: int, temperature: float) -> str:
        system = messages[0]["content"]
        task = re.match(r"TASK: (\w+)", system).group(1)
        if task == "ping":
            return json.dumps({"title": "Mock Title", "logline": "A mock logline."})
        if task == "bible":
            return "Here is the bible:\n```json\n" + json.dumps(_BIBLE) + "\n```"
        if task == "outline":
            n = int(re.search(r"exactly (\d+) scenes", system).group(1))
            scenes = [
                {
                    "id": f"s{i + 1}",
                    "title": f"Scene {i + 1}",
                    "summary": f"Mara and Old Tom investigate the signal, part {i + 1}.",
                    "location_id": "lighthouse" if i % 2 == 0 else "harbour",
                    "character_ids": ["mara", "old_tom"],
                }
                for i in range(n)
            ]
            return json.dumps({"scenes": scenes})
        if task == "shots":
            n = int(re.search(r"exactly (\d+) shots", system).group(1))
            scene = extract_json(messages[-1]["content"].split("Scene to storyboard:", 1)[1])
            framings = ["wide", "medium", "close-up", "medium"]
            shots = []
            for i in range(n):
                speaker = scene["character_ids"][i % len(scene["character_ids"])]
                shots.append(
                    {
                        "framing": framings[i % len(framings)],
                        "action": f"{speaker} looks out towards the sea, beam sweeping overhead (beat {i + 1})",
                        "character_ids": scene["character_ids"][: 1 + i % 2],
                        "dialogue": [{"speaker": speaker, "text": f"Did you see that? Line {i + 1}."}] if i % 2 else [],
                        "narration": f"{scene['title']}." if i == 0 else "",
                    }
                )
            return json.dumps({"shots": shots})
        raise ValueError(f"MockLLM has no response for task {task!r}")

    def unload(self) -> None:
        pass
