"""External binaries. ffmpeg comes from PATH, $GRIZZLY_FFMPEG, or the static
build shipped in the imageio-ffmpeg wheel, so the Mac app needs no Homebrew."""

from __future__ import annotations

import functools
import os
import re
import shutil
import subprocess
from pathlib import Path


@functools.cache
def ffmpeg() -> str:
    """Path to an ffmpeg binary, or raise with an install hint."""
    found = os.environ.get("GRIZZLY_FFMPEG") or shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # not installed, or no binary for this platform
        raise RuntimeError("ffmpeg not found. Install it with: brew install ffmpeg") from exc


def has_ffmpeg() -> bool:
    try:
        ffmpeg()
        return True
    except RuntimeError:
        return False


_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def media_duration(path: Path) -> float:
    """Seconds of audio or video, read from ffmpeg's banner (no ffprobe needed)."""
    out = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = _DURATION.search(out.stderr)
    if not m:
        return 0.0
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)
