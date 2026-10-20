"""Animatic: Ken Burns moves over each shot, voiced with macOS `say`, plus subtitles.

This is the prototype's "film" output. A real image-to-video model can later
replace `_shot_clip` per shot without changing the rest of the assembly.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from grizzly.models import Project, Shot

FPS = 24
W, H = 1280, 720


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip() or 0)


def _lines(project: Project, shot: Shot) -> list[tuple[str, str]]:
    """(voice, text) pairs in reading order."""
    out = [("", shot.narration)] if shot.narration else []
    for d in shot.dialogue:
        c = project.bible.character(d.speaker)
        out.append((c.voice if c else "", d.text))
    return out


def _voice(lines: list[tuple[str, str]], work: Path, shot_id: str) -> tuple[Path | None, list[float]]:
    """Synthesize each line with `say`; return combined audio and per-line durations."""
    if not lines or not shutil.which("say"):
        return None, []
    parts, durs = [], []
    for i, (voice, text) in enumerate(lines):
        part = work / f"{shot_id}_{i}.aiff"
        cmd = ["say", "-o", str(part)] + (["-v", voice] if voice else []) + [text]
        try:
            _run(cmd)
        except subprocess.CalledProcessError:
            # Unknown voice name: fall back to the system voice.
            _run(["say", "-o", str(part), text])
        parts.append(part)
        durs.append(_duration(part) + 0.3)
    combined = work / f"{shot_id}.wav"
    inputs = sum((["-i", str(p)] for p in parts), [])
    chain = "".join(f"[{i}:a]aresample=44100,apad=pad_dur=0.3[a{i}];" for i in range(len(parts)))
    chain += "".join(f"[a{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[out]"
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", chain, "-map", "[out]", "-ac", "2", str(combined)])
    return combined, durs


def _shot_clip(image: Path, audio: Path | None, duration: float, index: int, out: Path) -> None:
    frames = max(1, round(duration * FPS))
    zoom = f"1+0.12*on/{frames}" if index % 2 == 0 else f"1.12-0.12*on/{frames}"
    vf = (
        f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
        f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},"
        "format=yuv420p"
    )
    audio_in = ["-i", str(audio)] if audio else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    _run([
        "ffmpeg", "-y", "-i", str(image), *audio_in,
        "-filter_complex", f"[0:v]{vf}[v];[1:a]apad,aresample=44100[a]",
        "-map", "[v]", "-map", "[a]", "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS),
        "-c:a", "aac", "-ar", "44100", "-ac", "2", str(out),
    ])


def _video_clip(video: Path, audio: Path | None, duration: float, out: Path) -> None:
    """Use a generated clip; hold its last frame if the voice-over runs longer."""
    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
        f"tpad=stop_mode=clone:stop_duration={duration:.3f},format=yuv420p"
    )
    audio_in = ["-i", str(audio)] if audio else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    _run([
        "ffmpeg", "-y", "-i", str(video), *audio_in,
        "-filter_complex", f"[0:v]{vf}[v];[1:a]apad,aresample=44100[a]",
        "-map", "[v]", "-map", "[a]", "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS),
        "-c:a", "aac", "-ar", "44100", "-ac", "2", str(out),
    ])


def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_animatic(project: Project, root: Path) -> Path:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found. Install it with: brew install ffmpeg")
    out = root / "exports" / "animatic"
    work = out / "_work"
    work.mkdir(parents=True, exist_ok=True)
    clips, srt, t, n = [], [], 0.0, 1
    for i, shot in enumerate(s for s in project.shots if s.image and (root / s.image).exists()):
        lines = _lines(project, shot)
        audio, durs = _voice(lines, work, shot.id)
        duration = max(shot.duration, sum(durs) + 0.5)
        clip = work / f"{shot.id}.mp4"
        if shot.video and (root / shot.video).exists():
            _video_clip(root / shot.video, audio, duration, clip)
        else:
            _shot_clip(root / shot.image, audio, duration, i, clip)
        clips.append(clip)
        if lines:
            durs = durs or [duration / len(lines)] * len(lines)
            start = t
            for (_, text), d in zip(lines, durs):
                srt.append(f"{n}\n{_ts(start)} --> {_ts(start + d)}\n{text}\n")
                start += d
                n += 1
        t += duration
    if not clips:
        raise RuntimeError("No rendered shots to assemble. Run the render step first.")
    concat = work / "clips.txt"
    concat.write_text("".join(f"file '{c.name}'\n" for c in clips))
    joined = work / "joined.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(joined)])
    final = out / f"{project.id}.mp4"
    subs = out / f"{project.id}.srt"
    subs.write_text("\n".join(srt))
    if not srt:
        shutil.copy(joined, final)
        return final
    _run([
        "ffmpeg", "-y", "-i", str(joined), "-i", str(subs),
        "-map", "0", "-map", "1", "-c", "copy", "-c:s", "mov_text", str(final),
    ])
    return final
