"""`grizzly doctor`: check the machine and each backend in isolation, with timings."""

from __future__ import annotations

import platform
import shutil
import sys
import time
import traceback
from pathlib import Path

from grizzly.config import Profile
from grizzly.jsonutil import extract_json
from grizzly.memory import peak_memory_gb, release_accelerator_memory


def _ok(label: str, detail: str = "") -> None:
    print(f"  OK    {label}{'  ' + detail if detail else ''}")


def _fail(label: str, exc: BaseException, verbose: bool) -> None:
    print(f"  FAIL  {label}: {type(exc).__name__}: {exc}")
    if verbose:
        traceback.print_exc()


def _peak_gb() -> str:
    peak = peak_memory_gb()
    return f"peak {peak:.1f}GB" if peak is not None else ""


def run_doctor(
    profile: Profile, out_dir: Path, skip_llm: bool = False, skip_image: bool = False, skip_refs: bool = False, verbose: bool = False,
    video: bool = False,
) -> int:
    failures = 0
    print(f"Grizzly doctor - profile {profile.name}")
    print("Environment")
    print(f"  ..    Python {sys.version.split()[0]} on {platform.system()} {platform.machine()}")
    if platform.system() == "Darwin" and platform.machine() != "arm64":
        print("  WARN  Not running natively on Apple Silicon (Rosetta Python?). MLX needs an arm64 Python.")
    for tool in ("ffmpeg", "say"):
        if shutil.which(tool):
            _ok(tool)
        else:
            print(f"  WARN  {tool} not found ({'brew install ffmpeg' if tool == 'ffmpeg' else 'macOS only; animatic will be silent'})")

    if profile.llm_backend == "mlx" or profile.image_backend == "mflux":
        try:
            import mlx.core as mx

            info = getattr(mx, "device_info", None) or getattr(getattr(mx, "metal", None), "device_info", None)
            details = info() if info else {}
            mem = details.get("memory_size") or 0
            wired = details.get("max_recommended_working_set_size") or 0
            _ok("MLX", f"{mx.__version__}, device {mx.default_device()}, RAM {mem / 1e9:.0f}GB, GPU working set {wired / 1e9:.1f}GB")
        except Exception as exc:
            _fail("MLX", exc, verbose)
            failures += 1

    if not skip_llm:
        print(f"Writer: {profile.llm_backend} {profile.llm_model}")
        try:
            from grizzly.llm import create_llm

            t = time.time()
            llm = create_llm(profile)
            _ok("load", f"{time.time() - t:.1f}s")
            t = time.time()
            raw = llm.chat(
                [
                    {"role": "system", "content": 'TASK: ping\nReply with ONLY JSON: {"title": "...", "logline": "..."}'},
                    {"role": "user", "content": "A cat detective in Victorian London."},
                ],
                max_tokens=200,
                temperature=0.7,
            )
            data = extract_json(raw)
            _ok("generate JSON", f"{time.time() - t:.1f}s {_peak_gb()}  -> {data.get('title', data)!s:.60}")
            llm.unload()
            del llm
            release_accelerator_memory()
        except Exception as exc:
            _fail("writer", exc, verbose)
            failures += 1

    if not skip_image:
        print(f"Illustrator: {profile.image_backend} {profile.image_model} ({profile.image_steps} steps)")
        try:
            from grizzly.image import create_image_model

            t = time.time()
            model = create_image_model(profile)
            _ok("load", f"{time.time() - t:.1f}s")
            for w, h in dict.fromkeys([(512, 512), profile.sizes["medium"]]):
                t = time.time()
                img = model.generate("ink and watercolour comic art, a cat detective in a deerstalker hat on a foggy London street, gas lamps", 42, w, h)
                out_dir.mkdir(parents=True, exist_ok=True)
                path = out_dir / f"doctor_{w}x{h}.png"
                img.save(path)
                _ok(f"{w}x{h}", f"{time.time() - t:.1f}s {_peak_gb()}  -> {path}")
            model.unload()
            release_accelerator_memory()
        except Exception as exc:
            _fail("illustrator", exc, verbose)
            failures += 1

    if profile.ref_backend and not skip_refs:
        print(f"Reference renderer: {profile.ref_backend} {profile.ref_model} ({profile.ref_steps} steps)")
        ref = out_dir / "doctor_512x512.png"
        if not ref.exists():
            print("  SKIP  needs doctor_512x512.png from the illustrator check; run without --skip-image once")
        else:
            try:
                from grizzly.image import create_ref_model

                t = time.time()
                model = create_ref_model(profile)
                _ok("load", f"{time.time() - t:.1f}s")
                for refs, label in (([], "no reference"), ([ref], "1 reference")):
                    t = time.time()
                    img = model.generate(
                        "ink and watercolour comic art, wide shot: the cat detective from image 1 crouches on a rooftop "
                        "at night, full figure, London skyline and moon behind",
                        7, 1024, 1024, refs=refs,
                    )
                    path = out_dir / f"doctor_ref_{len(refs)}.png"
                    img.save(path)
                    _ok(f"1024x1024 {label}", f"{time.time() - t:.1f}s {_peak_gb()}  -> {path}")
                model.unload()
                release_accelerator_memory()
            except Exception as exc:
                _fail("reference renderer", exc, verbose)
                failures += 1

    if video:
        print(f"Video: {profile.video_backend} {profile.video_model} ({profile.video_steps} steps)")
        src = out_dir / "doctor_512x512.png"
        if not profile.video_backend:
            print("  SKIP  this profile has no video model")
        elif not src.exists():
            print("  SKIP  needs doctor_512x512.png from the illustrator check; run without --skip-image once")
        else:
            try:
                from grizzly.video import create_video_model

                model = create_video_model(profile)
                # Native size (smaller sizes freeze), but few frames to keep it short.
                (w, h), frames = profile.video_size, 17
                peak_memory_gb()
                t = time.time()
                path = model.generate(
                    "ink and watercolour comic art, the cat detective turns his head and looks around, "
                    "fog drifting past the gas lamps, gentle camera push-in",
                    src, 7, w, h, frames, out_dir / "doctor_video.mp4",
                )
                secs = time.time() - t
                _ok(f"{w}x{h} x {frames} frames", f"{secs:.0f}s {_peak_gb()}  -> {path}")
                from grizzly.motion import STATIC_THRESHOLD, clip_motion

                score = clip_motion(path)
                if score < STATIC_THRESHOLD:
                    print(f"  WARN  motion {score:.3f}: the clip is essentially a still image")
                else:
                    _ok("motion", f"{score:.3f} (first vs last frame)")
                w2, h2 = profile.video_size
                scale = (w2 * h2 * profile.video_frames) / (w * h * frames)
                print(f"  ..    rough estimate for a {w2}x{h2} x {profile.video_frames}-frame clip: "
                      f"{secs * scale / 60:.0f} min (includes model loading, so likely an overestimate)")
            except Exception as exc:
                _fail("video", exc, verbose)
                failures += 1

    print("All checks passed." if not failures else f"{failures} check(s) failed. Re-run with -v for tracebacks.")
    return 1 if failures else 0
