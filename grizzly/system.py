"""Hardware check for first launch: can this Mac run Grizzly, and with which profile?"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from grizzly.weights import GB, free_bytes

MIN_MACOS = (14, 0)


def _sysctl(name: str) -> str:
    try:
        return subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def memory_bytes() -> int:
    raw = _sysctl("hw.memsize")
    if raw.isdigit():
        return int(raw)
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        return 0


def recommended_profile(memory: int) -> str:
    return "mac-48gb" if memory >= 44 * GB else "m5pro-24gb"


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in text.split(".") if p.isdigit())


def system_info(cache: Path, needed_bytes: int) -> dict:
    """What this machine is, plus pass / warn / fail checks the app shows."""
    system, arch = platform.system(), platform.machine()
    macos = platform.mac_ver()[0] if system == "Darwin" else ""
    memory = memory_bytes()
    free = free_bytes(cache)
    chip = _sysctl("machdep.cpu.brand_string") or platform.processor() or arch
    mem_gb = memory / GB

    def check(id: str, label: str, status: str, detail: str) -> dict:
        return {"id": id, "label": label, "status": status, "detail": detail}

    apple_silicon = system == "Darwin" and arch == "arm64"
    checks = [
        check(
            "chip", "Apple silicon", "ok" if apple_silicon else "fail",
            chip if apple_silicon else f"{chip} ({system} {arch}): the models run on Apple silicon GPUs (MLX).",
        ),
        check(
            "macos", "macOS 14 or later",
            "ok" if macos and _version(macos) >= MIN_MACOS else "fail",
            f"macOS {macos}" if macos else f"{system} {platform.release()}",
        ),
        check(
            "memory", "Memory",
            "ok" if mem_gb >= 23 else "warn" if mem_gb >= 15 else "fail",
            f"{mem_gb:.0f} GB" + (
                "" if mem_gb >= 23 else
                ": stories will work, but slowly, and video clips probably won't fit." if mem_gb >= 15 else
                ": Grizzly needs at least 16 GB."
            ),
        ),
        check(
            "disk", "Space for models",
            "ok" if free >= needed_bytes + 5 * GB else "warn" if free >= needed_bytes + GB else "fail",
            f"{free / GB:.0f} GB free, {needed_bytes / GB:.1f} GB still to download",
        ),
    ]
    return {
        "chip": chip, "arch": arch, "macos": macos, "memory_bytes": memory, "disk_free_bytes": free,
        "checks": checks, "recommended_profile": recommended_profile(memory),
        "supported": all(c["status"] != "fail" for c in checks if c["id"] != "disk"),
    }
