import pytest

from grizzly.jsonutil import extract_json
from grizzly.llm.base import strip_reasoning
from grizzly.memory import ModelManager
from grizzly.models import Shot
from grizzly.render.comic import _rows
from grizzly.render.vn import _rpy_str


def test_extract_json_from_fenced_and_chatty_output():
    assert extract_json('Sure!\n```json\n{"a": [1, 2,]}\n```') == {"a": [1, 2]}
    assert extract_json('noise {"a": "b}"} trailing {') == {"a": "b}"}
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_strip_reasoning():
    assert strip_reasoning("<think>hmm</think>\n{}") == "{}"
    assert strip_reasoning('{"x": 1}<think>unfinished') == '{"x": 1}'


def test_framing_normalisation():
    assert Shot(id="a", scene_id="s", action="x", framing="Close Up").framing == "close-up"
    assert Shot(id="a", scene_id="s", action="x", framing="closeup").framing == "close-up"
    assert Shot(id="a", scene_id="s", action="x", framing="establishing").framing == "wide"


def test_comic_rows_pair_non_wide_shots():
    shots = [Shot(id=str(i), scene_id="s", action="x", framing=f) for i, f in enumerate(["wide", "medium", "close-up", "medium", "wide", "medium"])]
    assert [[s.id for s in row] for row in _rows(shots)] == [["0"], ["1", "2"], ["3"], ["4"], ["5"]]


def test_renpy_escaping():
    assert _rpy_str('He said "hi" [x] {b}') == '"He said \\"hi\\" [[x] {{b}"'


def test_model_manager_swaps():
    events = []

    class Fake:
        def __init__(self, name):
            self.name = name
            events.append(f"load {name}")

        def unload(self):
            events.append(f"unload {self.name}")

    mm = ModelManager(swap=True)
    mm.register("llm", lambda: Fake("llm"))
    mm.register("image", lambda: Fake("image"))
    mm.acquire("llm")
    mm.acquire("llm")
    mm.acquire("image")
    assert events == ["load llm", "unload llm", "load image"]


def test_doctor_with_mock_profile(tmp_path):
    from grizzly.config import load_profile
    from grizzly.doctor import run_doctor

    assert run_doctor(load_profile("mock"), tmp_path) == 0
    assert (tmp_path / "doctor_512x512.png").exists()


def test_pillow_typing_module_imports():
    # mflux imports PIL._typing at runtime; Pillow 13.0 fails there on Python <3.15.
    import PIL._typing  # noqa: F401


def test_paginate_balances_rows():
    from grizzly.render.comic import _paginate

    assert [len(p) for p in _paginate(list(range(4)))] == [2, 2]
    assert [len(p) for p in _paginate(list(range(5)))] == [3, 2]
    assert [len(p) for p in _paginate(list(range(6)))] == [3, 3]
    assert [len(p) for p in _paginate(list(range(7)))] == [3, 2, 2]


def test_shot_prompt_adds_unlisted_characters_and_head_count():
    from grizzly.models import Character, Location, StoryBible
    from grizzly.visuals import shot_prompt

    bible = StoryBible(
        title="t", logline="l", art_style="ink",
        characters=[
            Character(id="whiskers", name="Whiskers", appearance="black cat, monocle"),
            Character(id="pudding", name="Mrs. Pudding", appearance="red cloak"),
            Character(id="bumble", name="Lord Bumblewick", appearance="powdered wig"),
        ],
        locations=[Location(id="market", name="Market", description="stalls")],
    )
    shot = Shot(id="a", scene_id="s", action="Whiskers inspects the key while Bumblewick watches", character_ids=[])
    prompt = shot_prompt(bible, shot)
    assert "black cat, monocle" in prompt and "powdered wig" in prompt
    assert "red cloak" not in prompt  # "Mrs." alone must not match
    assert "exactly 2 main figures (Whiskers and Lord Bumblewick)" in prompt
    solo = shot_prompt(bible, Shot(id="b", scene_id="s", action="a cat on a wall", character_ids=["whiskers"]))
    assert "exactly one main figure (Whiskers)" in solo
    empty = shot_prompt(bible, Shot(id="c", scene_id="s", action="a hand drops a key into a crate"))
    assert "no main characters in frame" in empty
    wide = shot_prompt(bible, Shot(id="d", scene_id="s", action="x", framing="wide", character_ids=["whiskers"]))
    assert "full bodies" not in wide


def test_flux2_backend_switches_variant_by_references(monkeypatch, tmp_path):
    """Exercise the real backend class against a fake mflux, since mflux's
    edit variant crashes without references (it concatenates None)."""
    import sys
    import types

    from PIL import Image

    loads, calls = [], []

    class FakeModel:
        def __init__(self, model_config, model_path):
            loads.append(type(self).__name__)

        def generate_image(self, **kw):
            calls.append((type(self).__name__, kw.get("image_paths")))
            return types.SimpleNamespace(image=Image.new("RGB", (8, 8)))

    variants = types.ModuleType("mflux.models.flux2.variants")
    variants.Flux2KleinEdit = type("Flux2KleinEdit", (FakeModel,), {})
    variants.Flux2Klein = type("Flux2Klein", (FakeModel,), {})
    config = types.ModuleType("mflux.models.common.config")
    config.ModelConfig = types.SimpleNamespace(flux2_klein_4b=lambda: "cfg")
    monkeypatch.setitem(sys.modules, "mflux.models.flux2.variants", variants)
    monkeypatch.setitem(sys.modules, "mflux.models.common.config", config)

    from grizzly.image.mflux_flux2_backend import MfluxFlux2RefModel

    model = MfluxFlux2RefModel("repo", 4)
    ref = tmp_path / "r.png"
    model.generate("a", 1, 64, 64, refs=[ref])
    model.generate("b", 1, 64, 64, refs=[ref])
    model.generate("c", 1, 64, 64, refs=[])
    assert loads == ["Flux2KleinEdit", "Flux2Klein"]
    assert calls == [("Flux2KleinEdit", [str(ref)]), ("Flux2KleinEdit", [str(ref)]), ("Flux2Klein", None)]


def test_cast_size_follows_the_premise_unless_fixed():
    from grizzly.prompts import character_count

    assert character_count(4) == "exactly 4 characters"
    assert "every role it names" in character_count(None)


def test_reference_shots_warn_against_duplicates():
    from grizzly.models import Character, Location, StoryBible
    from grizzly.visuals import shot_prompt

    bible = StoryBible(
        title="t", logline="l", art_style="ink",
        characters=[Character(id="a", name="Ann", appearance="red coat"), Character(id="b", name="Ben", appearance="goggles")],
        locations=[Location(id="x", name="X", description="deck")],
    )
    shot = Shot(id="s", scene_id="s", action="Ann and Ben on deck", character_ids=["a", "b"], framing="wide")
    assert "never two copies" in shot_prompt(bible, shot, ref_ids=["a", "b"])
    assert "never two copies" not in shot_prompt(bible, shot)


def test_wan_backend_passes_the_panel_and_settings_to_mlx_video(monkeypatch, tmp_path):
    import sys
    import types

    calls = []
    gen = types.ModuleType("mlx_video.models.wan_2.generate")
    gen.generate_video = lambda **kw: calls.append(kw)
    monkeypatch.setitem(sys.modules, "mlx_video", types.ModuleType("mlx_video"))
    monkeypatch.setitem(sys.modules, "mlx_video.models", types.ModuleType("mlx_video.models"))
    monkeypatch.setitem(sys.modules, "mlx_video.models.wan_2", types.ModuleType("mlx_video.models.wan_2"))
    monkeypatch.setitem(sys.modules, "mlx_video.models.wan_2.generate", gen)

    from grizzly.video.mlx_wan import MlxWanVideoModel

    model_dir = tmp_path / "wan"
    model_dir.mkdir()
    out = MlxWanVideoModel(str(model_dir), 30).generate("p", tmp_path / "s.png", 5, 832, 480, 49, tmp_path / "v" / "s.mp4")
    assert out == tmp_path / "v" / "s.mp4" and out.parent.exists()
    kw = calls[0]
    assert kw["model_dir"] == str(model_dir) and kw["image"] == str(tmp_path / "s.png")
    assert (kw["width"], kw["height"], kw["num_frames"], kw["steps"], kw["seed"]) == (832, 480, 49, 30, 5)
    # Wan constraints: sizes divisible by 32, frames of the form 4n+1.
    from grizzly.config import load_profile

    p = load_profile("m5pro-24gb")
    assert p.video_size[0] % 32 == 0 and p.video_size[1] % 32 == 0 and (p.video_frames - 1) % 4 == 0
