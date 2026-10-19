"""Keeps at most one heavy model resident when the profile asks for swapping.

On a 24GB machine an 8B writer and a 6B diffusion model fit individually but
leave little room for activations together, so the pipeline asks for a model
through `acquire()` and anything else loaded gets released first.
"""

from __future__ import annotations

import gc
import logging
from typing import Callable, Protocol

log = logging.getLogger(__name__)


class Unloadable(Protocol):
    def unload(self) -> None: ...


def release_accelerator_memory() -> None:
    gc.collect()
    try:
        import mlx.core as mx
    except ImportError:
        return
    clear = getattr(mx, "clear_cache", None) or getattr(getattr(mx, "metal", None), "clear_cache", None)
    if clear:
        clear()


def peak_memory_gb(reset: bool = True) -> float | None:
    """Peak MLX (GPU) memory since the last reset, or None without MLX."""
    try:
        import mlx.core as mx
    except ImportError:
        return None
    get = getattr(mx, "get_peak_memory", None) or getattr(getattr(mx, "metal", None), "get_peak_memory", None)
    clear = getattr(mx, "reset_peak_memory", None) or getattr(getattr(mx, "metal", None), "reset_peak_memory", None)
    if not get:
        return None
    peak = get() / 1e9
    if reset and clear:
        clear()
    return peak


class ModelManager:
    def __init__(self, swap: bool = True) -> None:
        self.swap = swap
        self._slots: dict[str, Unloadable] = {}
        self._factories: dict[str, Callable[[], Unloadable]] = {}

    def register(self, kind: str, factory: Callable[[], Unloadable]) -> None:
        self._factories[kind] = factory

    def acquire(self, kind: str):
        if self.swap:
            for other in [k for k in self._slots if k != kind]:
                log.info("Unloading %s to make room for %s", other, kind)
                self._slots.pop(other).unload()
                release_accelerator_memory()
        if kind not in self._slots:
            self._slots[kind] = self._factories[kind]()
        return self._slots[kind]

    def release_all(self) -> None:
        for model in self._slots.values():
            model.unload()
        self._slots.clear()
        release_accelerator_memory()
