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
