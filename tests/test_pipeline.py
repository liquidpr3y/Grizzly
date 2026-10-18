import shutil
import subprocess

import pytest

from grizzly.visuals import shot_prompt


def test_full_comic_pipeline(store, pipeline):
    project = store.create("Lighthouse", "A keeper hears the sea answer back.", "comic")
    pdf = pipeline.run_all(project.id, n_scenes=2, n_shots=4)
    assert pdf.exists() and pdf.suffix == ".pdf"
    project = store.load(project.id)
    assert len(project.shots) == 8
    assert all(project.status().values())
    root = store.root(project.id)
    assert all((root / s.image).exists() for s in project.shots)
    assert all((root / c.portrait).exists() for c in project.bible.characters)
    # cover + 8 shots laid out as wide / pair / single rows over two pages
    assert len(list((root / "exports" / "comic").glob("page_*.png"))) == 3


def test_prompts_carry_character_and_style(store, pipeline):
    project = store.create("Lighthouse", "premise", "comic")
    for step in ("bible", "outline", "shots"):
        pipeline.run(project.id, step, n_scenes=1, n_shots=2)
    project = store.load(project.id)
    shot = project.shots[0]
    prompt = shot_prompt(project.bible, shot)
    assert project.bible.art_style.rstrip(".") in prompt
    for cid in shot.character_ids:
        assert project.bible.character(cid).appearance in prompt


def test_rerender_single_shot(store, pipeline):
    project = store.create("Lighthouse", "premise", "vn")
    pipeline.run_all(project.id, n_scenes=1, n_shots=2)
    target = store.load(project.id).shots[1]
    before = (store.root(project.id) / target.image).stat().st_mtime_ns
    pipeline.run(project.id, "images", only={target.id})
    after = (store.root(project.id) / target.image).stat().st_mtime_ns
    assert after > before


def test_vn_exports(store, pipeline):
    project = store.create("Lighthouse", "premise", "vn")
    player = pipeline.run_all(project.id, n_scenes=1, n_shots=2)
    assert player.name == "index.html" and "beats" in player.read_text()
    script = (store.root(project.id) / "exports" / "renpy" / "game" / "script.rpy").read_text()
    assert "label start:" in script and "define c_mara" in script


def test_steps_enforce_order(store, pipeline):
    project = store.create("Lighthouse", "premise")
    with pytest.raises(RuntimeError, match="needs bible"):
        pipeline.run(project.id, "outline")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_animatic(store, pipeline):
    project = store.create("Lighthouse", "premise", "film")
    mp4 = pipeline.run_all(project.id, n_scenes=1, n_shots=2)
    assert mp4.exists()
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(mp4)],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert {"video", "audio", "subtitle"} <= set(out)
