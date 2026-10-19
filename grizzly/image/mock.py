"""Placeholder art: a seeded gradient with the prompt written on it."""

from __future__ import annotations

import random
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw

from grizzly.render.fonts import font


class MockImageModel:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate(self, prompt: str, seed: int, width: int, height: int, refs: list[Path] | None = None) -> Image.Image:
        rng = random.Random(seed)
        a = [rng.randint(40, 200) for _ in range(3)]
        b = [rng.randint(40, 200) for _ in range(3)]
        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)
        for y in range(height):
            t = y / max(1, height - 1)
            draw.line([(0, y), (width, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
        text = "\n".join(textwrap.wrap(prompt, width=max(20, width // 14))[:14])
        draw.multiline_text((16, 16), text, font=font(18), fill=(255, 255, 255))
        # Show references as thumbnails along the bottom edge.
        x = 8
        for ref in refs or []:
            thumb = Image.open(ref).convert("RGB")
            thumb.thumbnail((height // 4, height // 4))
            img.paste(thumb, (x, height - thumb.height - 8))
            x += thumb.width + 8
        self.calls.append({"prompt": prompt, "refs": [str(r) for r in refs or []]})
        return img

    def unload(self) -> None:
        pass
