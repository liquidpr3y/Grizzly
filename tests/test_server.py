import time

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from grizzly.config import load_profile  # noqa: E402
from grizzly.server import create_app  # noqa: E402


def wait(client, jid, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        job = client.get(f"/api/jobs/{jid}").json()
        if job["state"] in ("done", "failed"):
            return job
        time.sleep(0.1)
    raise TimeoutError(jid)


def test_studio_api_end_to_end(store):
    client = TestClient(create_app(load_profile("mock"), store))
    assert "Grizzly Studio" in client.get("/").text
    pid = client.post("/api/projects", json={"title": "Test", "premise": "p", "format": "comic"}).json()["id"]

    job = wait(client, client.post(f"/api/projects/{pid}/steps/all", json={"scenes": 1, "shots": 2}).json()["id"])
    assert job["state"] == "done", job["error"]
    assert job["result"].endswith(".pdf")
    assert client.get(f"/files/{pid}/{job['result']}").status_code == 200

    # Edit a shot and re-render only that one.
    data = client.get(f"/api/projects/{pid}").json()["project"]
    data["shots"][0]["action"] = "a gull lands on the railing"
    assert client.put(f"/api/projects/{pid}", json=data).status_code == 200
    job = wait(client, client.post(f"/api/projects/{pid}/steps/images", json={"only": [data["shots"][0]["id"]]}).json()["id"])
    assert job["state"] == "done"
    assert client.get(f"/api/projects/{pid}").json()["project"]["shots"][0]["action"] == "a gull lands on the railing"

    assert client.get("/api/projects/..%2F..").status_code == 404
    assert client.post(f"/api/projects/{pid}/steps/bogus").status_code == 400


def test_app_api_summaries_patches_exports_and_edit_lock(store):
    client = TestClient(create_app(load_profile("mock"), store))
    assert client.get("/api/health").json()["ok"] is True
    pid = client.post("/api/projects", json={"title": "App", "premise": "p", "format": "comic"}).json()["id"]
    assert wait(client, client.post(f"/api/projects/{pid}/steps/all", json={"scenes": 1, "shots": 2}).json()["id"])["state"] == "done"

    item = next(p for p in client.get("/api/projects").json() if p["id"] == pid)
    assert item["cover"] and item["shots"] == 2 and item["status"]["images"] and item["logline"]

    shot = client.get(f"/api/projects/{pid}").json()["project"]["shots"][0]
    r = client.patch(f"/api/projects/{pid}/shots/{shot['id']}", json={"action": "a gull lands", "framing": "Close Up"})
    patched = next(s for s in r.json()["project"]["shots"] if s["id"] == shot["id"])
    assert patched["action"] == "a gull lands" and patched["framing"] == "close-up"
    assert patched["image"] == shot["image"]  # untouched fields survive

    r = client.patch(f"/api/projects/{pid}/characters/mara", json={"appearance": "silver coat"})
    assert r.json()["project"]["bible"]["characters"][0]["appearance"] == "silver coat"
    assert client.patch(f"/api/projects/{pid}/bible", json={"art_style": "woodcut"}).json()["project"]["bible"]["art_style"] == "woodcut"
    assert client.patch(f"/api/projects/{pid}/shots/nope", json={"action": "x"}).status_code == 404

    ex = client.get(f"/api/projects/{pid}/exports").json()
    assert ex["comic"]["pdf"] and ex["comic"]["pages"] and ex["animatic"]["mp4"] is None

    # Edits are refused while a job runs on the project.
    queue = client.app.state.jobs.jobs
    queue["busy"] = {"id": "busy", "project": pid, "state": "running"}
    assert client.patch(f"/api/projects/{pid}/bible", json={"tone": "x"}).status_code == 409
    assert client.delete(f"/api/projects/{pid}").status_code == 409
    assert next(p for p in client.get("/api/projects").json() if p["id"] == pid)["busy"] is True
    del queue["busy"]
    job = wait(client, client.post(f"/api/projects/{pid}/steps/comic").json()["id"])
    assert [j["id"] for j in client.get(f"/api/jobs?project={pid}").json()][-1] == job["id"]

    assert client.delete(f"/api/projects/{pid}").json() == {"deleted": pid}
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_jobs_report_their_stage(store):
    client = TestClient(create_app(load_profile("mock"), store))
    pid = client.post("/api/projects", json={"title": "Stages", "premise": "p", "format": "comic"}).json()["id"]
    job = wait(client, client.post(f"/api/projects/{pid}/steps/all", json={"scenes": 1, "shots": 3}).json()["id"])
    # A full run ends on its export step; single steps report their own name.
    assert job["state"] == "done" and job["stage"] == "comic"
    assert wait(client, client.post(f"/api/projects/{pid}/steps/vn").json()["id"])["stage"] == "vn"


def test_video_settings_reach_the_video_model_and_the_animatic(store):
    from grizzly import tools

    if not tools.has_ffmpeg():
        pytest.skip("ffmpeg not installed")
    app = create_app(load_profile("mock"), store)
    client = TestClient(app)
    pid = client.post("/api/projects", json={"title": "Vid", "premise": "p", "format": "film"}).json()["id"]
    r = client.patch(f"/api/projects/{pid}/settings", json={
        "video": {"aspect": "9:16", "clip_seconds": 1.0, "steps": 12, "negative_prompt": "blurry, warped hands"}, "animatic": {"fps": 30},
    })
    assert r.status_code == 200 and r.json()["project"]["video"]["aspect"] == "9:16"
    assert client.patch(f"/api/projects/{pid}/settings", json={"video": {"aspect": "5:4"}}).status_code == 422
    assert wait(client, client.post(f"/api/projects/{pid}/steps/all", json={"scenes": 1, "shots": 2}).json()["id"])["state"] == "done"

    shots = client.get(f"/api/projects/{pid}").json()["project"]["shots"]
    job = client.post(f"/api/projects/{pid}/steps/video", json={"only": [shots[0]["id"]], "video": {"steps": 4}}).json()
    assert wait(client, job["id"])["state"] == "done"
    call = app.state.jobs.pipeline.models.acquire("video").calls[-1]
    w, h = call["size"]
    assert h > w and call["frames"] == 25 and call["steps"] == 4  # request beats project
    assert call["negative_prompt"] == "blurry, warped hands"

    # A shot's own options beat the project's; its motion note joins the prompt.
    r = client.patch(f"/api/projects/{pid}/shots/{shots[0]['id']}", json={
        "video_options": {"clip_seconds": 2.0, "steps": 6, "motion": "the gull takes off"},
    })
    assert r.json()["project"]["shots"][0]["video_options"]["steps"] == 6
    job = client.post(f"/api/projects/{pid}/steps/video", json={"only": [shots[0]["id"]]}).json()
    assert wait(client, job["id"])["state"] == "done"
    call = app.state.jobs.pipeline.models.acquire("video").calls[-1]
    assert call["frames"] == 49 and call["steps"] == 6 and "the gull takes off" in call["prompt"]

    # The seed used is recorded; a reroll moves to a new one unless the seed is locked.
    sid = shots[0]["id"]

    def animate(**body):
        assert wait(client, client.post(f"/api/projects/{pid}/steps/video", json={"only": [sid], **body}).json()["id"])["state"] == "done"
        shot = client.get(f"/api/projects/{pid}").json()["project"]["shots"][0]
        assert shot["video_seed"] == app.state.jobs.pipeline.models.acquire("video").calls[-1]["seed"]
        return shot["video_seed"]

    first = animate()
    assert animate() == first
    rerolled = animate(reroll=True)
    assert rerolled != first
    client.patch(f"/api/projects/{pid}/shots/{sid}", json={"video_options": {"seed": first}})
    assert animate(reroll=True) == first
    assert animate(video={"seed": 42}) == 42

    from PIL import Image

    root = store.root(pid)
    panel = Image.open(root / shots[0]["image"])
    assert panel.height > panel.width  # panels are drawn at the clip's shape
    job = wait(client, client.post(f"/api/projects/{pid}/steps/animatic").json()["id"])
    assert job["state"] == "done", job["error"]
