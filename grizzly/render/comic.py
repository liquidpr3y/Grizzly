"""Lay shots out as comic pages with panels, captions and speech bubbles."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from grizzly.models import Project, Shot
from grizzly.render.fonts import font

PAGE_W, PAGE_H = 1800, 2700
MARGIN, GUTTER, BORDER = 70, 28, 6
ROWS_PER_PAGE = 3
TEXT_SIZE, NAME_SIZE = 30, 22


def _rows(shots: list[Shot]) -> list[list[Shot]]:
    """Wide shots take a full row; everything else pairs up two per row."""
    rows: list[list[Shot]] = []
    pending: list[Shot] = []
    for shot in shots:
        if shot.framing == "wide":
            if pending:
                rows.append(pending)
                pending = []
            rows.append([shot])
        else:
            pending.append(shot)
            if len(pending) == 2:
                rows.append(pending)
                pending = []
    if pending:
        rows.append(pending)
    return rows


def _wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _caption(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str) -> int:
    x0, y0, x1, _ = box
    fnt = font(TEXT_SIZE - 4)
    pad = 14
    lines = _wrap(draw, text, fnt, int((x1 - x0) * 0.7) - 2 * pad)
    lh = fnt.size + 6
    w = max(draw.textlength(ln, font=fnt) for ln in lines) + 2 * pad
    h = lh * len(lines) + 2 * pad
    rect = (x0 + 12, y0 + 12, x0 + 12 + w, y0 + 12 + h)
    draw.rectangle(rect, fill=(255, 236, 160), outline="black", width=3)
    for i, ln in enumerate(lines):
        draw.text((rect[0] + pad, rect[1] + pad + i * lh), ln, font=fnt, fill="black")
    return int(rect[3])


def _bubble(draw: ImageDraw.ImageDraw, box, y: int, name: str, text: str, right: bool) -> int:
    x0, _, x1, y1 = box
    fnt, nfnt = font(TEXT_SIZE), font(NAME_SIZE, bold=True)
    pad = 18
    max_w = int((x1 - x0) * 0.55)
    lines = _wrap(draw, text, fnt, max_w - 2 * pad)
    lh = fnt.size + 6
    w = max([draw.textlength(ln, font=fnt) for ln in lines] + [draw.textlength(name, font=nfnt)]) + 2 * pad
    h = nfnt.size + 6 + lh * len(lines) + 2 * pad
    if y + h + 40 > y1:  # out of room in this panel
        return y
    bx0 = x1 - 20 - w if right else x0 + 20
    rect = (bx0, y, bx0 + w, y + h)
    tail_x = rect[0] + w * (0.7 if right else 0.3)
    draw.polygon([(tail_x - 14, rect[3] - 4), (tail_x + 14, rect[3] - 4), (tail_x + (10 if right else -10), rect[3] + 30)], fill="white", outline="black")
    draw.rounded_rectangle(rect, radius=28, fill="white", outline="black", width=3)
    # Re-cover the tail's top edge so the bubble and tail read as one shape.
    draw.line([(tail_x - 11, rect[3] - 2), (tail_x + 11, rect[3] - 2)], fill="white", width=4)
    draw.text((rect[0] + pad, rect[1] + pad - 4), name.upper(), font=nfnt, fill=(90, 90, 90))
    for i, ln in enumerate(lines):
        draw.text((rect[0] + pad, rect[1] + pad + nfnt.size + 6 + i * lh), ln, font=fnt, fill="black")
    return int(rect[3]) + 40


def _panel(page: Image.Image, root: Path, project: Project, shot: Shot, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    if shot.image and (root / shot.image).exists():
        art = Image.open(root / shot.image).convert("RGB")
        page.paste(ImageOps.fit(art, (x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
    draw = ImageDraw.Draw(page)
    y = y0 + 16
    if shot.narration:
        y = _caption(draw, box, shot.narration) + 16
    for i, line in enumerate(shot.dialogue):
        c = project.bible.character(line.speaker) if line.speaker != "narrator" else None
        y = _bubble(draw, box, y, c.name if c else "", line.text, right=i % 2 == 1)
    draw.rectangle(box, outline="black", width=BORDER)


def _cover(project: Project, root: Path) -> Image.Image:
    page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    hero = next((s for s in project.shots if s.image and s.framing == "wide"), None) or next(
        (s for s in project.shots if s.image), None
    )
    if hero:
        art = Image.open(root / hero.image).convert("RGB")
        page.paste(ImageOps.fit(art, (PAGE_W, PAGE_H), Image.LANCZOS), (0, 0))
    draw = ImageDraw.Draw(page)
    title_font = font(130, bold=True)
    lines = _wrap(draw, project.bible.title.upper(), title_font, PAGE_W - 2 * MARGIN)
    band_h = len(lines) * 150 + 160
    draw.rectangle((0, 120, PAGE_W, 120 + band_h), fill=(15, 15, 15))
    for i, ln in enumerate(lines):
        draw.text((MARGIN, 170 + i * 150), ln, font=title_font, fill="white")
    draw.text((MARGIN, 120 + band_h - 70), project.bible.logline[:110], font=font(34), fill=(220, 220, 220))
    return page


def build_comic(project: Project, root: Path) -> Path:
    out = root / "exports" / "comic"
    out.mkdir(parents=True, exist_ok=True)
    pages = [_cover(project, root)]
    rows = _rows(project.shots)
    row_h = (PAGE_H - 2 * MARGIN - GUTTER * (ROWS_PER_PAGE - 1)) // ROWS_PER_PAGE
    for start in range(0, len(rows), ROWS_PER_PAGE):
        page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
        for r, row in enumerate(rows[start : start + ROWS_PER_PAGE]):
            y0 = MARGIN + r * (row_h + GUTTER)
            col_w = (PAGE_W - 2 * MARGIN - GUTTER * (len(row) - 1)) // len(row)
            for c, shot in enumerate(row):
                x0 = MARGIN + c * (col_w + GUTTER)
                _panel(page, root, project, shot, (x0, y0, x0 + col_w, y0 + row_h))
        pages.append(page)
    for i, page in enumerate(pages):
        page.save(out / f"page_{i:02d}.png")
    pdf = out / f"{project.id}.pdf"
    pages[0].save(pdf, save_all=True, append_images=pages[1:], resolution=150)
    return pdf
