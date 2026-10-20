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
