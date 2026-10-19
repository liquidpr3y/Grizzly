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
from grizzly.memory import release_accelerator_memory


def _ok(label: str, detail: str = "") -> None:
    print(f"  OK    {label}{'  ' + detail if detail else ''}")


def _fail(label: str, exc: BaseException, verbose: bool) -> None:
    print(f"  FAIL  {label}: {type(exc).__name__}: {exc}")
    if verbose:
        traceback.print_exc()


def _peak_gb() -> str:
    try:
        import mlx.core as mx
    except ImportError:
        return ""
    get = getattr(mx, "get_peak_memory", None) or getattr(getattr(mx, "metal", None), "get_peak_memory", None)
    reset = getattr(mx, "reset_peak_memory", None) or getattr(getattr(mx, "metal", None), "reset_peak_memory", None)
    if not get:
        return ""
    peak = get() / 1e9
    if reset:
        reset()
    return f"peak {peak:.1f}GB"


def run_doctor(
    profile: Profile, out_dir: Path, skip_llm: bool = False, skip_image: bool = False, skip_refs: bool = False, verbose: bool = False
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

    print("All checks passed." if not failures else f"{failures} check(s) failed. Re-run with -v for tracebacks.")
    return 1 if failures else 0
