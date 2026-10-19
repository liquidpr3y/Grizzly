"""Local HTTP API + web studio.

The same API is what a SwiftUI front end (or a hosted SaaS front end) would
talk to. Jobs run one at a time on a single worker thread because the GPU is
the bottleneck and models are swapped in and out of unified memory.
"""

from __future__ import annotations

import logging
import queue
import threading
import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from grizzly.config import Profile
from grizzly.models import Format, Project
from grizzly.pipeline import STEPS, Pipeline
from grizzly.store import ProjectStore

log = logging.getLogger(__name__)
WEB = Path(__file__).parent / "web"


class NewProject(BaseModel):
    title: str
    premise: str
    format: Format = "comic"
    seed: int = 1234


class StepRequest(BaseModel):
    force: bool = False
    only: list[str] | None = None
    scenes: int = 4
    shots: int = 4
    characters: int = 3
    locations: int = 3
    reroll: bool = False


class Jobs:
    def __init__(self, pipeline: Pipeline) -> None:
        self.pipeline = pipeline
        self.jobs: dict[str, dict] = {}
        self.q: queue.Queue = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()

    def submit(self, project_id: str, step: str, req: StepRequest) -> dict:
        job = {"id": uuid.uuid4().hex[:12], "project": project_id, "step": step, "state": "queued", "progress": "", "result": None, "error": None}
        self.jobs[job["id"]] = job
        self.q.put((job, req))
        return job

    def _worker(self) -> None:
        while True:
            job, req = self.q.get()
            job["state"] = "running"

            def progress(i: int, n: int, label: str, job=job) -> None:
                job["progress"] = f"{i + 1}/{n} {label}"

            try:
                kw = dict(n_scenes=req.scenes, n_shots=req.shots)
                if job["step"] == "all":
                    out = self.pipeline.run_all(job["project"], progress=lambda s, job=job: job.update(progress=s), **kw)
                else:
                    out = self.pipeline.run(
                        job["project"], job["step"], force=req.force, only=set(req.only) if req.only else None,
                        n_characters=req.characters, n_locations=req.locations, progress=progress,
                        reroll=req.reroll, **kw,
                    )
                if isinstance(out, Path):
                    job["result"] = str(out.relative_to(self.pipeline.store.root(job["project"])))
                job["state"] = "done"
            except Exception as exc:  # surfaced to the UI
                log.error("Job %s failed\n%s", job["id"], traceback.format_exc())
                job["state"], job["error"] = "failed", str(exc)


def create_app(profile: Profile, store: ProjectStore) -> FastAPI:
    app = FastAPI(title="Grizzly")
    jobs = Jobs(Pipeline(profile, store))

    def load(pid: str) -> Project:
        try:
            return store.load(pid)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, f"No project {pid!r}")

    @app.get("/")
    def index():
        return FileResponse(WEB / "index.html")

    @app.get("/api/info")
    def info():
        return {"profile": profile.name, "llm": profile.llm_model, "image": profile.image_model, "steps": STEPS}

    @app.get("/api/projects")
    def list_projects():
        return store.list()

    @app.post("/api/projects")
    def new_project(body: NewProject):
        return store.create(body.title, body.premise, body.format, body.seed)

    @app.get("/api/projects/{pid}")
    def get_project(pid: str):
        project = load(pid)
        return {"project": project, "status": project.status()}

    @app.put("/api/projects/{pid}")
    def put_project(pid: str, project: Project):
        load(pid)
        if project.id != pid:
            raise HTTPException(400, "Project id cannot change")
        store.save(project)
        return {"project": project, "status": project.status()}

    @app.post("/api/projects/{pid}/steps/{step}")
    def run_step(pid: str, step: str, req: StepRequest | None = None):
        load(pid)
        if step not in STEPS and step != "all":
            raise HTTPException(400, f"Unknown step {step!r}")
        return jobs.submit(pid, step, req or StepRequest())

    @app.get("/api/jobs")
    def list_jobs():
        return list(jobs.jobs.values())

    @app.get("/api/jobs/{jid}")
    def get_job(jid: str):
        if jid not in jobs.jobs:
            raise HTTPException(404, "No such job")
        return jobs.jobs[jid]

    app.mount("/files", StaticFiles(directory=store.base), name="files")
    return app
