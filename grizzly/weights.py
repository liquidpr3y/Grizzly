"""Model weights: which ones a profile needs, what is on disk, and fetching them.

Weights live in the Hugging Face cache (~/.cache/huggingface/hub), which is
where mlx-lm, mflux and mlx-video look, so a model fetched here is never
fetched again by its loader and models from earlier runs count as installed.
"""

from __future__ import annotations

import logging
import os
import queue
import shutil
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from grizzly.config import Profile

log = logging.getLogger(__name__)

GB = 1_000_000_000

# Shown before Hugging Face has been asked (or when it can't be reached).
KNOWN: dict[str, tuple[str, str, float]] = {
    "mlx-community/Qwen3-8B-4bit": ("Qwen3 8B, 4-bit", "Apache-2.0", 4.6),
    "mlx-community/Qwen3-14B-4bit": ("Qwen3 14B, 4-bit", "Apache-2.0", 8.3),
    "filipstrand/Z-Image-Turbo-mflux-4bit": ("Z-Image Turbo, 4-bit", "see model card", 5.9),
    "mflux-community/flux2-klein-4b-mflux-q4": ("FLUX.2 Klein 4B, 4-bit", "Apache-2.0", 4.6),
    "Anes1032/Wan2.2-TI2V-5B-mlx-q8": ("Wan 2.2 TI2V 5B, 8-bit", "Apache-2.0", 19.6),
}


@dataclass(frozen=True)
class ModelSpec:
    id: str  # the role: writer, portraits, panels, video
    repo: str
    purpose: str
    required: bool = True

    @property
    def title(self) -> str:
        return KNOWN.get(self.repo, (self.repo.split("/")[-1], "", 0.0))[0]


def specs_for(profile: Profile) -> tuple[list[ModelSpec], list[str]]:
    """The models a profile downloads, plus notes on ones it doesn't manage."""
    specs, notes = [], []
    roles = (
        ("writer", profile.llm_backend, profile.llm_model, "Writes the story bible, outline and storyboard", True),
        ("portraits", profile.image_backend, profile.image_model, "Draws character portraits", True),
        ("panels", profile.ref_backend, profile.ref_model, "Draws panels from the cast's portraits", True),
        ("video", profile.video_backend, profile.video_model, "Animates panels into clips (optional)", False),
    )
    for role, backend, repo, purpose, required in roles:
        if not backend:
            continue
        if backend == "ollama":
            notes.append(f"The writer runs in Ollama: install it and run `ollama pull {repo}`.")
        elif backend == "mock":
            specs.append(ModelSpec(role, f"mock/{role}", purpose, required))
        elif Path(repo).expanduser().is_dir():
            notes.append(f"The {role} model is a local folder: {repo}")
        else:
            specs.append(ModelSpec(role, repo, purpose, required))
    return specs, notes


def hub_cache() -> Path:
    try:
        from huggingface_hub import constants

        return Path(constants.HF_HUB_CACHE)
    except ImportError:
        if os.environ.get("HF_HUB_CACHE"):
            return Path(os.environ["HF_HUB_CACHE"])
        return Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"


def repo_dir(cache: Path, repo: str) -> Path:
    return cache / ("models--" + repo.replace("/", "--"))


def local_state(cache: Path, repo: str, weight_files: list[str] | None) -> tuple[int, bool]:
    """(bytes on disk, including partial files; whether all weights are there)."""
    root = repo_dir(cache, repo)
    blobs = [f for f in (root / "blobs").iterdir() if f.is_file()] if (root / "blobs").is_dir() else []
    size = sum(f.stat().st_size for f in blobs)
    snaps = [p for p in (root / "snapshots").iterdir() if p.is_dir()] if (root / "snapshots").is_dir() else []
    if weight_files:
        complete = any(all((s / f).exists() for f in weight_files) for s in snaps)
    else:  # Hugging Face not reachable: trust a snapshot with weights and no partial files
        partial = any(f.name.endswith(".incomplete") for f in blobs)
        complete = not partial and any(next(s.rglob("*.safetensors"), None) for s in snaps)
    return size, complete


@dataclass
class RemoteInfo:
    total_bytes: int
    weight_files: list[str]
    license: str = ""


class Source(Protocol):
    def info(self, repo: str) -> RemoteInfo | None: ...
    def fetch(self, repo: str, cache: Path) -> None: ...


class HubSource:
    """Hugging Face Hub. Downloads resume where they stopped."""

    def info(self, repo: str) -> RemoteInfo | None:
        from huggingface_hub import HfApi

        meta = HfApi().model_info(repo, files_metadata=True, timeout=10)
        files = meta.siblings or []
        card = getattr(meta, "card_data", None) or {}
        return RemoteInfo(
            total_bytes=sum(f.size or 0 for f in files),
            weight_files=[f.rfilename for f in files if f.rfilename.endswith(".safetensors")],
            license=str(card.get("license", "") if hasattr(card, "get") else ""),
        )

    def fetch(self, repo: str, cache: Path) -> None:
        from huggingface_hub import snapshot_download
        from huggingface_hub.utils import disable_progress_bars

        disable_progress_bars()  # the app shows progress; console bars would flood its engine log
        snapshot_download(repo, cache_dir=cache)


class MockSource:
    """Writes a small fake model in the cache layout, slowly enough to watch."""

    size = 4 * 1024 * 1024
    chunks = 8
    delay = 0.1

    def info(self, repo: str) -> RemoteInfo | None:
        return RemoteInfo(self.size, ["model.safetensors"], "mock")

    def fetch(self, repo: str, cache: Path) -> None:
        root = repo_dir(cache, repo)
        (root / "blobs").mkdir(parents=True, exist_ok=True)
        part = root / "blobs" / "mock.incomplete"
        with part.open("wb") as f:
            for _ in range(self.chunks):
                f.write(b"\0" * (self.size // self.chunks))
                f.flush()
                time.sleep(self.delay)
        blob = part.with_suffix("")
        part.rename(blob)
        snap = root / "snapshots" / "mock"
        snap.mkdir(parents=True, exist_ok=True)
        (snap / "model.safetensors").symlink_to(blob)


@dataclass
class _Entry:
    spec: ModelSpec
    state: str = "idle"  # idle | queued | downloading | failed
    error: str | None = None
    remote: RemoteInfo | None = None
    asked: float = 0.0  # when Hugging Face was last asked about it


class WeightStore:
    """Status of a profile's models, and a one-at-a-time download queue."""

    RETRY_INFO = 60.0

    def __init__(self, specs: list[ModelSpec], cache: Path | None = None, source: Source | None = None) -> None:
        self.cache = cache or hub_cache()
        self.hub = source or HubSource()
        self.mock = MockSource()
        self.entries = {s.id: _Entry(s) for s in specs}
        self.lock = threading.Lock()
        self.q: queue.Queue[str] = queue.Queue()
        self._refreshing = False
        threading.Thread(target=self._worker, daemon=True).start()
        self._refresh_soon()

    def _source(self, spec: ModelSpec) -> Source:
        return self.mock if spec.repo.startswith("mock/") else self.hub

    def _refresh_soon(self) -> None:
        """Ask Hugging Face for sizes and file lists in the background: it can
        be slow or offline, and status() is polled by the app."""
        stale = any(e.remote is None and time.time() - e.asked > self.RETRY_INFO for e in self.entries.values())
        with self.lock:
            if not stale or self._refreshing:
                return
            self._refreshing = True

        def run() -> None:
            try:
                for entry in list(self.entries.values()):
                    self._info(entry)
            finally:
                self._refreshing = False

        threading.Thread(target=run, daemon=True).start()

    def _info(self, entry: _Entry) -> RemoteInfo | None:
        if entry.remote is None and time.time() - entry.asked > self.RETRY_INFO:
            entry.asked = time.time()
            try:
                entry.remote = self._source(entry.spec).info(entry.spec.repo)
            except Exception as exc:
                log.info("Could not look up %s: %s", entry.spec.repo, exc)
        return entry.remote

    def status(self) -> list[dict]:
        self._refresh_soon()
        out = []
        for entry in self.entries.values():
            spec, remote = entry.spec, entry.remote
            have, complete = local_state(self.cache, spec.repo, remote.weight_files if remote else None)
            title, license_, approx = KNOWN.get(spec.repo, (spec.title, "", 0.0))
            total = remote.total_bytes if remote else int(approx * GB)
            out.append({
                "id": spec.id, "title": title, "repo": spec.repo, "purpose": spec.purpose,
                "required": spec.required, "license": license_ or (remote.license if remote else ""),
                "size_bytes": total, "downloaded_bytes": total if complete else min(have, total or have),
                "complete": complete, "state": "done" if complete else entry.state, "error": entry.error,
            })
        return out

    def ready(self) -> bool:
        return all(m["complete"] for m in self.status() if m["required"])

    def needed_bytes(self, ids: list[str] | None = None) -> int:
        return sum(
            max(0, m["size_bytes"] - m["downloaded_bytes"])
            for m in self.status()
            if not m["complete"] and (m["id"] in ids if ids is not None else m["required"])
        )

    def download(self, ids: list[str] | None = None) -> None:
        """Queue models (default: the required ones). Raises ValueError if they won't fit."""
        unknown = set(ids or []) - set(self.entries)
        if unknown:
            raise KeyError(", ".join(sorted(unknown)))
        wanted = [m for m in self.status() if not m["complete"] and (m["id"] in ids if ids is not None else m["required"])]
        need = self.needed_bytes([m["id"] for m in wanted])
        free = free_bytes(self.cache)
        if need + GB > free:
            raise ValueError(f"Not enough disk space: these models need {need / GB:.1f} GB plus 1 GB to spare, {free / GB:.1f} GB is free.")
        with self.lock:
            for m in wanted:
                entry = self.entries[m["id"]]
                if entry.state not in ("queued", "downloading"):
                    entry.state, entry.error = "queued", None
                    self.q.put(m["id"])

    def busy(self) -> bool:
        return any(e.state in ("queued", "downloading") for e in self.entries.values())

    def _worker(self) -> None:
        while True:
            entry = self.entries[self.q.get()]
            entry.state = "downloading"
            log.info("Downloading %s", entry.spec.repo)
            try:
                self._source(entry.spec).fetch(entry.spec.repo, self.cache)
                entry.remote = None
                entry.asked = 0.0
                self._info(entry)  # refresh the file list now that it's here
                entry.state = "idle"
            except Exception as exc:
                log.error("Download of %s failed\n%s", entry.spec.repo, traceback.format_exc())
                entry.state, entry.error = "failed", str(exc) or type(exc).__name__


def free_bytes(path: Path) -> int:
    while not path.exists() and path != path.parent:
        path = path.parent
    return shutil.disk_usage(path).free
