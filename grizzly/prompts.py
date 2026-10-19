"""Prompt templates for the writer.

Written for small local models (7-14B): one job per call, an explicit JSON
shape, and short instructions. Each system prompt starts with a TASK tag so
logs (and the mock backend) can tell the calls apart.
"""

FORMAT_NOTES = {
    "comic": "a comic book. Favour striking visual moments and short, punchy dialogue (max ~20 words per line).",
    "vn": "a visual novel. Dialogue can be longer and more conversational; scenes are mostly character conversations.",
    "film": "a short animated film / animatic. Favour cinematic camera framing and narration that can be read aloud.",
}

BIBLE_SYSTEM = """TASK: bible
You are a story developer. From the user's premise, create a story bible for {format_note}
Reply with ONLY a JSON object of this exact shape:
{{
  "title": "string",
  "logline": "one sentence",
  "genre": "string",
  "tone": "string",
  "art_style": "medium, technique and palette ONLY, e.g. 'ink and watercolour comic art, bold linework, muted palette'. Never mention characters, animals, species or places here: this text is added to every image",
  "characters": [
    {{"id": "short_snake_case", "name": "string", "role": "protagonist/antagonist/...",
      "personality": "string",
      "appearance": "fixed visual description used in every illustration, starting with what they are (species if not human): age, build, face, hair or fur, clothing, colours, one distinctive feature"}}
  ],
  "locations": [
    {{"id": "short_snake_case", "name": "string", "description": "visual description: setting, lighting, key props"}}
  ]
}}
Create {n_characters} characters and {n_locations} locations. Appearance must be concrete and visual, not personality."""

OUTLINE_SYSTEM = """TASK: outline
You are a story editor. Break the story into exactly {n_scenes} scenes with a clear beginning, middle and end.
Reply with ONLY a JSON object of this exact shape:
{{"scenes": [{{"id": "s1", "title": "string", "summary": "2-3 sentences of what happens",
  "location_id": "one of the location ids", "character_ids": ["character ids present"]}}]}}"""

SHOTS_SYSTEM = """TASK: shots
You are a storyboard artist adapting a scene into {format_note}
Break the scene into exactly {n_shots} shots. For each shot:
- "framing": one of "wide", "medium", "close-up"
- "action": what the camera SEES, purely visual: poses, expressions, composition, lighting. Never include dialogue or written text.
  Describe only what IS visible. Image models draw whatever you name, so avoid negations like "empty", "missing", "without" or "no":
  write "a fish tank of still, clear water" rather than "an empty fish tank".
- "character_ids": ids of characters visible in the shot
- "dialogue": spoken lines in this shot, [{{"speaker": "character id", "text": "..."}}], may be empty
- "narration": caption / voice-over text, may be empty
Reply with ONLY a JSON object: {{"shots": [{{"framing": "...", "action": "...", "character_ids": [], "dialogue": [], "narration": ""}}]}}"""


def bible_user(premise: str) -> str:
    return f"Premise:\n{premise}"


def outline_user(bible_json: str) -> str:
    return f"Story bible:\n{bible_json}"


def shots_user(bible_json: str, scene_json: str, previous: str) -> str:
    prev = f"\nThe previous scene ended with: {previous}" if previous else ""
    return f"Story bible:\n{bible_json}\n\nScene to storyboard:\n{scene_json}{prev}"
