"""Animatic: Ken Burns moves over each shot, voiced with macOS `say`, plus subtitles.

This is the prototype's "film" output. A real image-to-video model can later
replace `_shot_clip` per shot without changing the rest of the assembly.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from grizzly.models import Project, Shot
from grizzly.tools import ffmpeg, media_duration
from grizzly.video_settings import aspect_ratio

# Short side of the film per resolution; the long side follows the aspect.
SHORT_SIDE = {"720p": 720, "1080p": 1080}


def frame_size(aspect: str, resolution: str = "720p") -> tuple[int, int]:
    """Output size for `aspect`, with even sides for H.264."""
    r, short = aspect_ratio(aspect), SHORT_SIDE[resolution]
    if r >= 1:
        return round(short * r / 2) * 2, short
    return short, round(short / r / 2) * 2


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


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
        durs.append(media_duration(part) + 0.3)
    combined = work / f"{shot_id}.wav"
    inputs = sum((["-i", str(p)] for p in parts), [])
    chain = "".join(f"[{i}:a]aresample=44100,apad=pad_dur=0.3[a{i}];" for i in range(len(parts)))
    chain += "".join(f"[a{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[out]"
    _run([ffmpeg(), "-y", *inputs, "-filter_complex", chain, "-map", "[out]", "-ac", "2", str(combined)])
    return combined, durs


def _shot_clip(
    image: Path, audio: Path | None, duration: float, index: int, out: Path, size: tuple[int, int], fps: int
) -> None:
    w, h = size
    frames = max(1, round(duration * fps))
    zoom = f"1+0.12*on/{frames}" if index % 2 == 0 else f"1.12-0.12*on/{frames}"
    vf = (
        f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
        f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps},"
        "format=yuv420p"
    )
    audio_in = ["-i", str(audio)] if audio else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    _run([
        ffmpeg(), "-y", "-i", str(image), *audio_in,
        "-filter_complex", f"[0:v]{vf}[v];[1:a]apad,aresample=44100[a]",
        "-map", "[v]", "-map", "[a]", "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(fps),
        "-c:a", "aac", "-ar", "44100", "-ac", "2", str(out),
    ])


def _video_clip(video: Path, audio: Path | None, duration: float, out: Path, size: tuple[int, int], fps: int) -> None:
    """Use a generated clip; hold its last frame if the voice-over runs longer."""
    w, h = size
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},"
        f"tpad=stop_mode=clone:stop_duration={duration:.3f},format=yuv420p"
    )
    audio_in = ["-i", str(audio)] if audio else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    _run([
        ffmpeg(), "-y", "-i", str(video), *audio_in,
        "-filter_complex", f"[0:v]{vf}[v];[1:a]apad,aresample=44100[a]",
        "-map", "[v]", "-map", "[a]", "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(fps),
        "-c:a", "aac", "-ar", "44100", "-ac", "2", str(out),
    ])


def _crossfade(clips: list[Path], lengths: list[float], fade: float, fps: int, out: Path) -> None:
    """Join clips, dissolving picture and sound over `fade` seconds at each cut."""
    inputs = sum((["-i", str(c)] for c in clips), [])
    chain = [f"[{i}:v]settb=AVTB,fps={fps},format=yuv420p[v{i}];" for i in range(len(clips))]
    v, a, offset = "v0", "0:a", 0.0
    for i in range(1, len(clips)):
        offset += lengths[i - 1] - fade
        chain.append(f"[{v}][v{i}]xfade=transition=fade:duration={fade:.3f}:offset={offset:.3f}[x{i}];")
        chain.append(f"[{a}][{i}:a]acrossfade=d={fade:.3f}[y{i}];")
        v, a = f"x{i}", f"y{i}"
    _run([
        ffmpeg(), "-y", *inputs, "-filter_complex", "".join(chain).rstrip(";"),
        "-map", f"[{v}]", "-map", f"[{a}]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(fps),
        "-c:a", "aac", "-ar", "44100", "-ac", "2", str(out),
    ])


def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_animatic(project: Project, root: Path) -> Path:
    ffmpeg()  # fail early with an install hint
    out = root / "exports" / "animatic"
    work = out / "_work"
    work.mkdir(parents=True, exist_ok=True)
    settings = project.animatic
    size, fps = frame_size(project.video.aspect, settings.resolution), settings.fps
    shots = [s for s in project.shots if s.image and (root / s.image).exists()]
    # A dissolve overlaps two shots, so keep it well inside the shortest one.
    fade = min([settings.crossfade] + [0.4 * s.duration for s in shots]) if len(shots) > 1 else 0.0
    clips, lengths, srt, t, n = [], [], [], 0.0, 1
    for i, shot in enumerate(shots):
        lines = _lines(project, shot)
        audio, durs = _voice(lines, work, shot.id)
        duration = max(shot.duration, sum(durs) + 0.5)
        clip = work / f"{shot.id}.mp4"
        if shot.video and (root / shot.video).exists():
            _video_clip(root / shot.video, audio, duration, clip, size, fps)
        else:
            _shot_clip(root / shot.image, audio, duration, i, clip, size, fps)
        clips.append(clip)
        lengths.append(duration)
        if lines:
            durs = durs or [duration / len(lines)] * len(lines)
            start = t
            for (_, text), d in zip(lines, durs):
                srt.append(f"{n}\n{_ts(start)} --> {_ts(start + d)}\n{text}\n")
                start += d
                n += 1
        t += duration - fade
    if not clips:
        raise RuntimeError("No rendered shots to assemble. Run the render step first.")
    joined = work / "joined.mp4"
    if fade > 0:
        _crossfade(clips, lengths, fade, fps, joined)
    else:
        concat = work / "clips.txt"
        concat.write_text("".join(f"file '{c.name}'\n" for c in clips))
        _run([ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(joined)])
    final = out / f"{project.id}.mp4"
    subs = out / f"{project.id}.srt"
    subs.write_text("\n".join(srt))
    if not srt or not settings.subtitles:
        shutil.copy(joined, final)
        return final
    _run([
        ffmpeg(), "-y", "-i", str(joined), "-i", str(subs),
        "-map", "0", "-map", "1", "-c", "copy", "-c:s", "mov_text", str(final),
    ])
    return final
