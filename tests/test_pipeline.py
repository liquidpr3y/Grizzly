import shutil
import subprocess
from pathlib import Path

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


def test_shots_are_drawn_from_character_portraits(store, pipeline):
    project = store.create("Lighthouse", "premise", "comic")
    for step in ("bible", "outline", "shots"):
        pipeline.run(project.id, step, n_scenes=1, n_shots=3)
    # The images step renders missing portraits itself before the shots.
    pipeline.run(project.id, "images")
    project = store.load(project.id)
    root = store.root(project.id)
    assert all(c.portrait for c in project.bible.characters)
    calls = pipeline.models.acquire("ref_image").calls
    assert len(calls) == 3
    for shot, call in zip(project.shots, calls):
        assert len(call["refs"]) == len(shot.character_ids)
        for i, ref in enumerate(call["refs"]):
            assert (root / "images" / "refs").samefile(Path(ref).parent)
            assert f"image {i + 1}" in call["prompt"]
    # References are downscaled to the profile's limit.
    from PIL import Image

    ref = Image.open(calls[0]["refs"][0])
    assert max(ref.size) <= pipeline.profile.ref_max_side


def test_refs_can_be_switched_off(store, monkeypatch):
    from grizzly.config import load_profile
    from grizzly.pipeline import Pipeline

    monkeypatch.setenv("GRIZZLY_REFS", "off")
    profile = load_profile("mock")
    assert profile.ref_backend == ""
    pipeline = Pipeline(profile, store)
    project = store.create("Lighthouse", "premise", "comic")
    pipeline.run_all(project.id, n_scenes=1, n_shots=2)
    assert all(not c["refs"] for c in pipeline.models.acquire("image").calls)


def test_reroll_redraws_one_portrait_with_a_new_seed(store, pipeline):
    project = store.create("Lighthouse", "premise", "comic")
    pipeline.run(project.id, "bible")
    pipeline.run(project.id, "portraits")
    root = store.root(project.id)
    before = {c.id: (root / c.portrait).read_bytes() for c in store.load(project.id).bible.characters}
    pipeline.run(project.id, "portraits", only={"mara"}, reroll=True)
    after = store.load(project.id).bible
    assert after.character("mara").portrait_seed == 1
    assert (root / after.character("mara").portrait).read_bytes() != before["mara"]
    assert (root / after.character("old_tom").portrait).read_bytes() == before["old_tom"]


def test_shots_with_references_render_first(store, pipeline):
    project = store.create("Lighthouse", "premise", "comic")
    for step in ("bible", "outline", "shots"):
        pipeline.run(project.id, step, n_scenes=1, n_shots=3)
    data = store.load(project.id)
    data.shots[0].character_ids = []
    data.shots[0].action = "a gull on a railing"
    store.save(data)
    pipeline.run(project.id, "images")
    calls = pipeline.models.acquire("ref_image").calls
    assert [bool(c["refs"]) for c in calls] == [True, True, False]


def test_failed_shot_clears_its_image_and_blocks_export(store, pipeline):
    project = store.create("Lighthouse", "premise", "comic")
    pipeline.run_all(project.id, n_scenes=1, n_shots=3)
    model = pipeline.models.acquire("ref_image")
    original = model.generate

    def flaky(prompt, seed, w, h, refs=None):
        if not refs:
            raise RuntimeError("boom")
        return original(prompt, seed, w, h, refs)

    model.generate = flaky
    data = store.load(project.id)
    data.shots[0].character_ids = []
    data.shots[0].action = "a gull on a railing"
    store.save(data)
    with pytest.raises(RuntimeError, match="1 shot\\(s\\) failed"):
        pipeline.run(project.id, "images", force=True)
    after = store.load(project.id)
    assert after.shots[0].image is None and all(s.image for s in after.shots[1:])
    with pytest.raises(RuntimeError, match="needs images"):
        pipeline.run(project.id, "comic")
