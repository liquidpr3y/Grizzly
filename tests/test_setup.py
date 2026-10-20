"""First-launch setup: model status in the Hugging Face cache, downloads, hardware check."""

import time
from dataclasses import replace

import pytest

from grizzly.config import load_profile
from grizzly.system import recommended_profile, system_info
from grizzly.weights import GB, MockSource, ModelSpec, RemoteInfo, WeightStore, local_state, repo_dir, specs_for


def fake_hub_model(cache, repo, files, partial=False):
    """Lay out a repo the way huggingface_hub does: blobs plus a snapshot."""
    root = repo_dir(cache, repo)
    (root / "blobs").mkdir(parents=True)
    snap = root / "snapshots" / "abc123"
    for i, (name, size) in enumerate(files.items()):
        blob = root / "blobs" / (f"b{i}.incomplete" if partial else f"b{i}")
        blob.write_bytes(b"\0" * size)
        if not partial:
            (snap / name).parent.mkdir(parents=True, exist_ok=True)
            (snap / name).symlink_to(blob)


def test_specs_follow_the_profile():
    specs, notes = specs_for(load_profile("m5pro-24gb"))
    assert [(s.id, s.required) for s in specs] == [("writer", True), ("portraits", True), ("panels", True), ("video", False)]
    assert specs[0].repo == "mlx-community/Qwen3-8B-4bit" and not notes
    specs, notes = specs_for(load_profile("m5pro-24gb-ollama"))
    assert "writer" not in [s.id for s in specs] and "ollama pull qwen3:8b" in notes[0]
    specs, _ = specs_for(replace(load_profile("m5pro-24gb"), ref_backend="", video_backend=""))
    assert [s.id for s in specs] == ["writer", "portraits"]


def test_local_state_reads_the_hub_cache(tmp_path):
    fake_hub_model(tmp_path, "org/done", {"transformer/0.safetensors": 300, "config.json": 10})
    fake_hub_model(tmp_path, "org/partial", {"model.safetensors": 200}, partial=True)
    assert local_state(tmp_path, "org/done", ["transformer/0.safetensors"]) == (310, True)
    assert local_state(tmp_path, "org/done", ["transformer/0.safetensors", "transformer/1.safetensors"])[1] is False
    assert local_state(tmp_path, "org/done", None) == (310, True)  # offline: trust a snapshot with weights
    assert local_state(tmp_path, "org/partial", None) == (200, False)
    assert local_state(tmp_path, "org/missing", None) == (0, False)


class FakeHub:
    def __init__(self):
        self.fetched = []

    def info(self, repo):
        return RemoteInfo(1000, ["model.safetensors"], "Apache-2.0")

    def fetch(self, repo, cache):
        self.fetched.append(repo)
        if repo == "org/broken":
            raise RuntimeError("connection reset")
        fake_hub_model(cache, repo, {"model.safetensors": 1000})


def wait_idle(store, timeout=10):
    end = time.time() + timeout
    while store.busy():
        assert time.time() < end, "download did not finish"
        time.sleep(0.05)


def test_downloads_queue_required_models_and_report_failures(tmp_path):
    hub = FakeHub()
    specs = [ModelSpec("writer", "org/writer", "w"), ModelSpec("portraits", "org/broken", "p"), ModelSpec("video", "org/video", "v", required=False)]
    fake_hub_model(tmp_path, "org/video", {"model.safetensors": 1000})  # fetched in an earlier run
    store = WeightStore(specs, cache=tmp_path, source=hub)
    time.sleep(0.2)  # background size lookup
    assert not store.ready()
    status = {m["id"]: m for m in store.status()}
    assert status["video"]["complete"] and status["video"]["state"] == "done"
    assert status["writer"]["size_bytes"] == 1000 and status["writer"]["license"] == "Apache-2.0"

    store.download()
    wait_idle(store)
    assert hub.fetched == ["org/writer", "org/broken"]  # required only, video already there
    status = {m["id"]: m for m in store.status()}
    assert status["writer"]["complete"] and status["writer"]["downloaded_bytes"] == 1000
    assert status["portraits"]["state"] == "failed" and "connection reset" in status["portraits"]["error"]
    assert not store.ready()
    with pytest.raises(KeyError):
        store.download(["nope"])


def test_downloads_refuse_to_fill_the_disk(tmp_path, monkeypatch):
    import grizzly.weights as weights

    monkeypatch.setattr(weights, "free_bytes", lambda path: GB // 2)
    store = WeightStore([ModelSpec("writer", "org/writer", "w")], cache=tmp_path, source=FakeHub())
    with pytest.raises(ValueError, match="Not enough disk space"):
        store.download()


def test_mock_models_download_in_visible_steps(tmp_path, monkeypatch):
    monkeypatch.setattr(MockSource, "delay", 0.05)
    store = WeightStore([ModelSpec("writer", "mock/writer", "w")], cache=tmp_path)
    store.download()
    seen = set()
    while store.busy():
        seen.add(store.status()[0]["downloaded_bytes"])
        time.sleep(0.01)
    assert store.ready() and len(seen) > 2  # progress moved in between


def test_system_check(tmp_path):
    info = system_info(tmp_path, needed_bytes=10 * GB)
    assert {c["id"] for c in info["checks"]} == {"chip", "macos", "memory", "disk"}
    assert all(c["status"] in ("ok", "warn", "fail") for c in info["checks"])
    assert info["memory_bytes"] > 0 and info["disk_free_bytes"] > 0
    assert recommended_profile(24 * GB) == "m5pro-24gb" and recommended_profile(64 * GB) == "mac-48gb"


def test_setup_api(store, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from grizzly.server import create_app

    monkeypatch.setattr(MockSource, "delay", 0.01)
    client = TestClient(create_app(load_profile("mock"), store))
    setup = client.get("/api/setup").json()
    assert setup["profile"] == "mock" and not setup["ready"]
    assert [m["id"] for m in setup["models"]] == ["writer", "portraits", "panels", "video"]
    assert setup["system"]["checks"] and "recommended_profile" in setup["system"]
    assert setup["cache_dir"].endswith("mock-models")

    assert client.post("/api/setup/download", json={"models": ["nope"]}).status_code == 404
    assert client.post("/api/setup/download", json={}).json()["downloading"]
    end = time.time() + 10
    while client.get("/api/setup").json()["downloading"]:
        assert time.time() < end
        time.sleep(0.05)
    setup = client.get("/api/setup").json()
    assert setup["ready"]
    assert {m["id"] for m in setup["models"] if m["complete"]} == {"writer", "portraits", "panels"}  # video is optional
