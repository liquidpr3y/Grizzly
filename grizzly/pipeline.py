"""Runs pipeline steps against a project, swapping models as needed."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Callable

from grizzly.config import Profile
from grizzly.image import create_image_model, create_ref_model
from grizzly.llm import create_llm
from grizzly.memory import ModelManager, peak_memory_gb
from grizzly.models import Project
from grizzly.render.animatic import build_animatic
from grizzly.render.comic import build_comic
from grizzly.render.vn import build_html_player, build_renpy
from grizzly.store import ProjectStore
from grizzly.visuals import Progress, render_portraits, render_shots
from grizzly.writer import Writer

log = logging.getLogger(__name__)

WRITE_STEPS = ("bible", "outline", "shots")
RENDER_STEPS = ("portraits", "images")
EXPORT_STEPS = ("comic", "vn", "animatic")
STEPS = WRITE_STEPS + RENDER_STEPS + EXPORT_STEPS
DEFAULT_EXPORT = {"comic": "comic", "vn": "vn", "film": "animatic"}


class Pipeline:
    def __init__(self, profile: Profile, store: ProjectStore) -> None:
        self.profile = profile
        self.store = store
        self.models = ModelManager(swap=profile.swap_models)
        self.last_failed_attempts = 0
        self.models.register("llm", lambda: create_llm(profile))
        self.models.register("image", lambda: create_image_model(profile))
        if profile.ref_backend:
            self.models.register("ref_image", lambda: create_ref_model(profile))

    def run(
        self,
        project_id: str,
        step: str,
        *,
        force: bool = False,
        only: set[str] | None = None,
        n_scenes: int = 4,
        n_shots: int = 4,
        n_characters: int = 3,
        n_locations: int = 3,
        progress: Progress | None = None,
        reroll: bool = False,
    ) -> Project | Path:
        project = self.store.load(project_id)
        root = self.store.root(project_id)
        _require(project, step)
        if step in WRITE_STEPS:
            writer = Writer(self.models.acquire("llm"), self.profile)
            self.last_failed_attempts = 0
            if progress:
                progress(0, 1, f"writing {step}")
            if step == "bible":
                project.bible = writer.bible(project, n_characters, n_locations)
                project.outline, project.shots = None, []
            elif step == "outline":
                project.outline = writer.outline(project, n_scenes)
                project.shots = []
            else:
                project.shots = writer.shots(project, n_shots)
            self.last_failed_attempts = writer.failed_attempts
            self.store.save(project)
            return project
        if step in RENDER_STEPS:
            use_refs = bool(self.profile.ref_backend)
            # Shots drawn from references need every portrait first.
            if step == "portraits" or (use_refs and not project.status()["portraits"]):
                model = self.models.acquire("image")
                if step == "portraits":
                    render_portraits(project, root, model, self.profile, force, progress, only=only, reroll=reroll)
                else:
                    render_portraits(project, root, model, self.profile, progress=progress)
                self.store.save(project)
            if step == "images":
                model = self.models.acquire("ref_image" if use_refs else "image")
                render_shots(
                    project, root, model, self.profile, force, only, progress,
                    on_each=lambda: self.store.save(project), use_refs=use_refs, reroll=reroll,
                )
                self.store.save(project)
            return project
        if step == "comic":
            return build_comic(project, root)
        if step == "vn":
            build_renpy(project, root)
            return build_html_player(project, root)
        if step == "animatic":
            return build_animatic(project, root)
        raise ValueError(f"Unknown step {step!r}. Steps: {', '.join(STEPS)}")

    def run_all(self, project_id: str, progress: Callable[[str], None] | None = None, **kw) -> Path:
        """Write and render whatever is missing, then build the format's export.
        Writes a timing/memory report to <project>/run_report.json."""
        project = self.store.load(project_id)
        status = project.status()
        steps = [s for s in WRITE_STEPS + RENDER_STEPS if not status[s]]
        # Earlier steps invalidate later ones, so run everything after the first gap.
        if steps:
            steps = list(WRITE_STEPS + RENDER_STEPS)[list(WRITE_STEPS + RENDER_STEPS).index(steps[0]) :]
        steps.append(DEFAULT_EXPORT[project.format])
        report = {"project": project_id, "profile": self.profile.name, "steps": []}
        started = time.time()
        peak_memory_gb()  # reset the peak counter
        result: Path | Project = project
        for step in steps:
            if progress:
                progress(step)
            t = time.time()
            result = self.run(project_id, step, **kw)
            entry = {"step": step, "seconds": round(time.time() - t, 1), "peak_gb": _round(peak_memory_gb())}
            if step in WRITE_STEPS:
                entry["writer_retries"] = self.last_failed_attempts
            done = self.store.load(project_id)
            if step == "images":
                entry["count"] = len(done.shots)
            elif step == "portraits":
                entry["count"] = len(done.bible.characters)
            report["steps"].append(entry)
        report["total_seconds"] = round(time.time() - started, 1)
        (self.store.root(project_id) / "run_report.json").write_text(json.dumps(report, indent=2))
        self.last_report = report
        return result

def _round(value: float | None) -> float | None:
    return round(value, 1) if value is not None else None


def _require(project: Project, step: str) -> None:
    needs = {
        "outline": ["bible"],
        "shots": ["bible", "outline"],
        "portraits": ["bible"],
        "images": ["bible", "shots"],
        "comic": ["images"],
        "vn": ["images"],
        "animatic": ["images"],
    }
    status = project.status()
    missing = [n for n in needs.get(step, []) if not status[n]]
    if missing:
        raise RuntimeError(f"Step {step!r} needs {', '.join(missing)} first")
