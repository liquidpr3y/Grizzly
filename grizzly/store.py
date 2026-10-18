"""Projects live in folders: project.json plus images/ and exports/."""

from __future__ import annotations

import json
import os
from pathlib import Path

from grizzly.config import projects_dir
from grizzly.models import Format, Project, slugify


class ProjectStore:
    def __init__(self, base: Path | None = None) -> None:
        self.base = base or projects_dir()
        self.base.mkdir(parents=True, exist_ok=True)

    def root(self, project_id: str) -> Path:
        path = (self.base / project_id).resolve()
        if path.parent != self.base.resolve():
            raise ValueError(f"Invalid project id {project_id!r}")
        return path

    def create(self, title: str, premise: str, format: Format = "comic", seed: int = 1234) -> Project:
        pid = slugify(title)
        n = 2
        while (self.base / pid).exists():
            pid = f"{slugify(title)}_{n}"
            n += 1
        project = Project(id=pid, title=title, premise=premise, format=format, seed=seed)
        self.save(project)
        return project

    def load(self, project_id: str) -> Project:
        return Project.model_validate_json((self.root(project_id) / "project.json").read_text())

    def save(self, project: Project) -> None:
        root = self.root(project.id)
        root.mkdir(parents=True, exist_ok=True)
        tmp = root / "project.json.tmp"
        tmp.write_text(project.model_dump_json(indent=2))
        os.replace(tmp, root / "project.json")

    def list(self) -> list[dict]:
        items = []
        for p in sorted(self.base.glob("*/project.json")):
            data = json.loads(p.read_text())
            items.append({"id": data["id"], "title": data["title"], "format": data["format"], "created": data["created"]})
        return items
