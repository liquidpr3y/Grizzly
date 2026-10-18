"""Runs pipeline steps against a project, swapping models as needed."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from grizzly.config import Profile
from grizzly.image import create_image_model
from grizzly.llm import create_llm
from grizzly.memory import ModelManager
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
        self.models.register("llm", lambda: create_llm(profile))
        self.models.register("image", lambda: create_image_model(profile))

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
    ) -> Project | Path:
        project = self.store.load(project_id)
        root = self.store.root(project_id)
        _require(project, step)
        if step in WRITE_STEPS:
            writer = Writer(self.models.acquire("llm"), self.profile)
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
            self.store.save(project)
            return project
        if step in RENDER_STEPS:
            model = self.models.acquire("image")
            if step == "portraits":
                render_portraits(project, root, model, self.profile, force, progress)
            else:
                render_shots(project, root, model, self.profile, force, only, progress, on_each=lambda: self.store.save(project))
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
        """Write and render whatever is missing, then build the format's export."""
        project = self.store.load(project_id)
        status = project.status()
        for step in WRITE_STEPS + RENDER_STEPS:
            if not status[step]:
                if progress:
                    progress(step)
                self.run(project_id, step, **kw)
                # Later steps depend on the earlier ones, so rerun them all.
                status = {k: (False if k in STEPS[STEPS.index(step) + 1 :] else v) for k, v in status.items()}
        export = DEFAULT_EXPORT[project.format]
        if progress:
            progress(export)
        return self.run(project_id, export)


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
