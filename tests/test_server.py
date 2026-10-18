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
