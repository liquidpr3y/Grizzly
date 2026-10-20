"""Local HTTP API + web studio.

The same API is what a SwiftUI front end (or a hosted SaaS front end) would
talk to. Jobs run one at a time on a single worker thread because the GPU is
the bottleneck and models are swapped in and out of unified memory.
"""

from __future__ import annotations

import logging
import queue
import shutil
import threading
import time
import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from grizzly.config import Profile
from grizzly import __version__
from grizzly.models import DialogueLine, Format, Project
from grizzly.pipeline import STEPS, Pipeline
from grizzly.store import ProjectStore
from grizzly.system import system_info
from grizzly.weights import WeightStore, specs_for

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
    characters: int | None = None
    locations: int = 3
    reroll: bool = False


class BiblePatch(BaseModel):
    title: str | None = None
    logline: str | None = None
    tone: str | None = None
    art_style: str | None = None


class CharacterPatch(BaseModel):
    name: str | None = None
    personality: str | None = None
    appearance: str | None = None
    voice: str | None = None


class ShotPatch(BaseModel):
    action: str | None = None
    framing: str | None = None
    narration: str | None = None
    dialogue: list[DialogueLine] | None = None
    duration: float | None = None


class DownloadRequest(BaseModel):
    # None: every required model that isn't downloaded yet.
    models: list[str] | None = None


class Jobs:
    def __init__(self, pipeline: Pipeline) -> None:
        self.pipeline = pipeline
        self.jobs: dict[str, dict] = {}
        self.q: queue.Queue = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()

    def submit(self, project_id: str, step: str, req: StepRequest) -> dict:
        job = {
            "id": uuid.uuid4().hex[:12], "project": project_id, "step": step, "state": "queued",
            "stage": step, "progress": "", "result": None, "error": None, "created": time.time(), "finished": None,
        }
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
                    out = self.pipeline.run_all(
                        job["project"], progress=lambda s, job=job: job.update(stage=s, progress=""),
                        step_progress=progress, **kw,
                    )
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
            job["finished"] = time.time()

    def busy(self, project_id: str) -> bool:
        return any(j["project"] == project_id and j["state"] in ("queued", "running") for j in self.jobs.values())


def create_app(profile: Profile, store: ProjectStore, weights: WeightStore | None = None) -> FastAPI:
    app = FastAPI(title="Grizzly")
    jobs = Jobs(Pipeline(profile, store))
    app.state.jobs = jobs
    specs, notes = specs_for(profile)
    # The mock profile's stand-in models stay out of the real Hugging Face cache.
    weights = weights or WeightStore(specs, cache=store.base.parent / "mock-models" if profile.name == "mock" else None)
    app.state.weights = weights

    def load(pid: str) -> Project:
        try:
            return store.load(pid)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, f"No project {pid!r}")

    @app.get("/")
    def index():
        return FileResponse(WEB / "index.html")

    def editable(pid: str) -> Project:
        project = load(pid)
        # The render worker saves its own copy as it goes; an edit made now
        # would be overwritten, so refuse it until the job finishes.
        if jobs.busy(pid):
            raise HTTPException(409, "A job is running on this project; edit when it finishes")
        return project

    def summary(project: Project) -> dict:
        cover = next((s.image for s in project.shots if s.image and s.framing == "wide"), None) or next(
            (s.image for s in project.shots if s.image), None
        )
        if not cover and project.bible:
            cover = next((c.portrait for c in project.bible.characters if c.portrait), None)
        return {
            "id": project.id, "title": project.title, "format": project.format, "created": project.created,
            "logline": project.bible.logline if project.bible else "", "cover": cover,
            "shots": len(project.shots), "status": project.status(), "busy": jobs.busy(project.id),
        }

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": __version__, "profile": profile.name}

    @app.get("/api/info")
    def info():
        return {
            "profile": profile.name, "llm": profile.llm_model, "image": profile.image_model,
            "ref": profile.ref_model, "video": profile.video_model, "steps": STEPS,
            # Lets a native front end reveal exports in Finder.
            "projects_dir": str(store.base.resolve()),
        }

    def setup_status() -> dict:
        models = weights.status()
        missing = sum(max(0, m["size_bytes"] - m["downloaded_bytes"]) for m in models if m["required"] and not m["complete"])
        return {
            "profile": profile.name,
            "system": system_info(weights.cache, missing),
            "models": models,
            "notes": notes,
            "ready": all(m["complete"] for m in models if m["required"]),
            "downloading": weights.busy(),
            "cache_dir": str(weights.cache),
        }

    @app.get("/api/setup")
    def setup():
        """First-launch state: the hardware check and which models are installed."""
        return setup_status()

    @app.post("/api/setup/download")
    def download(req: DownloadRequest | None = None):
        try:
            weights.download((req or DownloadRequest()).models)
        except KeyError as exc:
            raise HTTPException(404, f"No model {exc.args[0]!r} in profile {profile.name}")
        except ValueError as exc:
            raise HTTPException(507, str(exc))
        return setup_status()

    @app.get("/api/projects")
    def list_projects():
        items = []
        for item in store.list():
            try:
                items.append(summary(store.load(item["id"])))
            except Exception:  # a damaged project should not hide the rest
                log.exception("Could not load project %s", item["id"])
        return sorted(items, key=lambda p: p["created"], reverse=True)

    @app.post("/api/projects")
    def new_project(body: NewProject):
        return store.create(body.title, body.premise, body.format, body.seed)

    @app.get("/api/projects/{pid}")
    def get_project(pid: str):
        project = load(pid)
        return {"project": project, "status": project.status(), "busy": jobs.busy(pid)}

    @app.put("/api/projects/{pid}")
    def put_project(pid: str, project: Project):
        editable(pid)
        if project.id != pid:
            raise HTTPException(400, "Project id cannot change")
        store.save(project)
        return {"project": project, "status": project.status(), "busy": False}

    @app.delete("/api/projects/{pid}")
    def delete_project(pid: str):
        editable(pid)
        shutil.rmtree(store.root(pid))
        return {"deleted": pid}

    @app.patch("/api/projects/{pid}/bible")
    def patch_bible(pid: str, body: BiblePatch):
        project = editable(pid)
        if not project.bible:
            raise HTTPException(409, "No story bible yet")
        for key, value in body.model_dump(exclude_none=True).items():
            setattr(project.bible, key, value)
        store.save(project)
        return {"project": project, "status": project.status(), "busy": False}

    @app.patch("/api/projects/{pid}/characters/{cid}")
    def patch_character(pid: str, cid: str, body: CharacterPatch):
        project = editable(pid)
        character = project.bible.character(cid) if project.bible else None
        if not character:
            raise HTTPException(404, f"No character {cid!r}")
        for key, value in body.model_dump(exclude_none=True).items():
            setattr(character, key, value)
        store.save(project)
        return {"project": project, "status": project.status(), "busy": False}

    @app.patch("/api/projects/{pid}/shots/{sid}")
    def patch_shot(pid: str, sid: str, body: ShotPatch):
        project = editable(pid)
        shot = next((s for s in project.shots if s.id == sid), None)
        if not shot:
            raise HTTPException(404, f"No shot {sid!r}")
        data = body.model_dump(exclude_none=True)
        if "framing" in data:
            # Reuse the model's normalisation ("Close Up" -> "close-up").
            data["framing"] = type(shot)(id="x", scene_id="x", action="x", framing=data["framing"]).framing
        for key, value in data.items():
            setattr(shot, key, value)
        store.save(project)
        return {"project": project, "status": project.status(), "busy": False}

    @app.get("/api/projects/{pid}/exports")
    def exports(pid: str):
        load(pid)
        root = store.root(pid)

        def rel(path: Path) -> str | None:
            return str(path.relative_to(root)) if path.exists() else None

        comic = root / "exports" / "comic"
        return {
            "comic": {
                "pdf": rel(comic / f"{pid}.pdf"),
                "pages": sorted(str(p.relative_to(root)) for p in comic.glob("page_*.png")),
            },
            "vn": {"html": rel(root / "exports" / "vn_html" / "index.html"), "renpy": rel(root / "exports" / "renpy" / "game" / "script.rpy")},
            "animatic": {"mp4": rel(root / "exports" / "animatic" / f"{pid}.mp4")},
        }

    @app.post("/api/projects/{pid}/steps/{step}")
    def run_step(pid: str, step: str, req: StepRequest | None = None):
        load(pid)
        if step not in STEPS and step != "all":
            raise HTTPException(400, f"Unknown step {step!r}")
        return jobs.submit(pid, step, req or StepRequest())

    @app.get("/api/jobs")
    def list_jobs(project: str | None = None):
        return [j for j in jobs.jobs.values() if project is None or j["project"] == project]

    @app.get("/api/jobs/{jid}")
    def get_job(jid: str):
        if jid not in jobs.jobs:
            raise HTTPException(404, "No such job")
        return jobs.jobs[jid]

    app.mount("/files", StaticFiles(directory=store.base), name="files")
    return app
