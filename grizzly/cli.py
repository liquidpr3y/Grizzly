"""Command line entry point: `grizzly --help`."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from grizzly.config import PROFILES, load_profile
from grizzly.pipeline import STEPS, Pipeline
from grizzly.store import ProjectStore


def _progress(i: int, n: int, label: str) -> None:
    print(f"  [{i + 1}/{n}] {label}", flush=True)


def _port_free(host: str, port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _exit_with_parent() -> None:
    """Stop when the launching app dies. An app killed outright (e.g. stopped
    from Xcode) never gets to stop its engine, which would otherwise keep
    running and holding model memory and the port."""
    import os
    import signal
    import threading

    parent = os.getppid()

    def watch() -> None:
        while True:
            time.sleep(1)
            if os.getppid() != parent:
                os.kill(os.getpid(), signal.SIGTERM)
                return

    threading.Thread(target=watch, daemon=True).start()


def _models(profile, download: bool, video: bool) -> int:
    from grizzly.weights import GB, WeightStore, specs_for

    specs, notes = specs_for(profile)
    weights = WeightStore(specs)

    def table() -> list[dict]:
        rows = weights.status()
        for m in rows:
            mark = "ok" if m["complete"] else "missing" if m["state"] == "idle" else m["state"]
            size = f"{m['downloaded_bytes'] / GB:.1f}/{m['size_bytes'] / GB:.1f} GB"
            print(f"  {mark:12} {m['id']:10} {size:>15}  {m['repo']}{'' if m['required'] else '  (optional)'}")
        return rows

    print(f"Models for profile {profile.name} in {weights.cache}")
    rows = table()
    for note in notes:
        print(f"  note: {note}")
    if not download:
        return 0 if all(m["complete"] for m in rows if m["required"]) else 1
    ids = [m["id"] for m in rows if not m["complete"] and (m["required"] or video)]
    if not ids:
        print("Nothing to download.")
        return 0
    try:
        weights.download(ids)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    while weights.busy():
        time.sleep(2)
        done = sum(m["downloaded_bytes"] for m in weights.status() if m["id"] in ids)
        total = sum(m["size_bytes"] for m in weights.status() if m["id"] in ids)
        print(f"\r  {done / GB:6.1f} / {total / GB:.1f} GB", end="", flush=True)
    print()
    rows = table()
    return 0 if all(m["complete"] for m in rows if m["id"] in ids) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="grizzly", description="LLM-assisted comics, visual novels and animatics on Apple Silicon.")
    parser.add_argument("--profile", choices=sorted(PROFILES), help="hardware profile (default: $GRIZZLY_PROFILE or m5pro-24gb)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new", help="create a project from a premise")
    p.add_argument("title")
    p.add_argument("premise")
    p.add_argument("--format", choices=["comic", "vn", "film"], default="comic")
    p.add_argument("--seed", type=int, default=1234)

    sub.add_parser("list", help="list projects")

    p = sub.add_parser("show", help="print a project's JSON")
    p.add_argument("project")

    p = sub.add_parser("step", help="run one pipeline step")
    p.add_argument("project")
    p.add_argument("step", choices=STEPS)
    p.add_argument("--force", action="store_true", help="re-render images that already exist")
    p.add_argument("--only", nargs="+", metavar="ID", help="only re-render these shots (images) or characters (portraits)")
    p.add_argument("--reroll", action="store_true", help="draw the --only shots or portraits again with a fresh seed")
    p.add_argument("--scenes", type=int, default=4)
    p.add_argument("--shots", type=int, default=4, help="shots per scene")
    p.add_argument("--characters", type=int, default=None, help="default: as many as the premise needs")
    p.add_argument("--locations", type=int, default=3)

    p = sub.add_parser("run", help="write, render and export everything that is missing")
    p.add_argument("project")
    p.add_argument("--scenes", type=int, default=4)
    p.add_argument("--shots", type=int, default=4)

    p = sub.add_parser("doctor", help="check the machine and load/test each model")
    p.add_argument("--skip-llm", action="store_true")
    p.add_argument("--skip-image", action="store_true")
    p.add_argument("--skip-refs", action="store_true")
    p.add_argument("--video", action="store_true", help="also test image-to-video (downloads ~20GB on first use)")

    p = sub.add_parser("models", help="show which models the profile needs and download them")
    p.add_argument("--download", action="store_true", help="download the required models that are missing")
    p.add_argument("--video", action="store_true", help="with --download, also the optional video model")

    p = sub.add_parser("serve", help="start the local web studio")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8642)
    p.add_argument("--exit-with-parent", action="store_true",
                   help="exit when the launching process dies (used by the Mac app)")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    store = ProjectStore()
    profile = load_profile(args.profile)

    if args.cmd == "new":
        project = store.create(args.title, args.premise, args.format, args.seed)
        print(f"Created {project.id} in {store.root(project.id)}")
        print(f"Next: grizzly run {project.id}")
    elif args.cmd == "list":
        for item in store.list():
            print(f"{item['id']:30} {item['format']:6} {item['title']}")
    elif args.cmd == "show":
        print(json.dumps(json.loads(store.load(args.project).model_dump_json()), indent=2))
    elif args.cmd == "step":
        start = time.time()
        result = Pipeline(profile, store).run(
            args.project, args.step, force=args.force, only=set(args.only) if args.only else None,
            n_scenes=args.scenes, n_shots=args.shots, n_characters=args.characters,
            n_locations=args.locations, progress=_progress, reroll=args.reroll,
        )
        where = result if not hasattr(result, "id") else store.root(args.project) / "project.json"
        print(f"Done {args.step} in {time.time() - start:.0f}s -> {where}")
    elif args.cmd == "run":
        start = time.time()
        pipeline = Pipeline(profile, store)
        out = pipeline.run_all(
            args.project, progress=lambda s: print(f"== {s}", flush=True),
            n_scenes=args.scenes, n_shots=args.shots,
        )
        print(f"Done in {time.time() - start:.0f}s -> {out}")
        print(f"\n{'step':10} {'time':>8} {'peak GPU':>9}  notes")
        for e in pipeline.last_report["steps"]:
            notes = []
            if "count" in e:
                notes.append(f"{e['count']} items, {e['seconds'] / max(e['count'], 1):.1f}s each")
            if e.get("writer_retries"):
                notes.append(f"{e['writer_retries']} writer retries")
            peak = f"{e['peak_gb']}GB" if e["peak_gb"] is not None else "-"
            print(f"{e['step']:10} {e['seconds']:>7.1f}s {peak:>9}  {', '.join(notes)}")
        print(f"Report: {store.root(args.project) / 'run_report.json'}")
    elif args.cmd == "doctor":
        from grizzly.doctor import run_doctor

        return run_doctor(profile, store.base.parent, args.skip_llm, args.skip_image, args.skip_refs, args.verbose, args.video)
    elif args.cmd == "models":
        return _models(profile, args.download, args.video)
    elif args.cmd == "serve":
        try:
            import uvicorn
        except ImportError:
            print("The web studio needs the server extra: pip install -e '.[server]'", file=sys.stderr)
            return 1
        from grizzly.server import create_app

        if not _port_free(args.host, args.port):
            print(
                f"PORT_IN_USE: {args.host}:{args.port} is already in use, most likely by a Grizzly engine "
                f"left running from an earlier session. Find it with: lsof -nP -iTCP:{args.port} -sTCP:LISTEN",
                file=sys.stderr,
            )
            return 3
        if args.exit_with_parent:
            _exit_with_parent()
        print(f"Grizzly studio on http://{args.host}:{args.port} (profile {profile.name})")
        # Clients such as the Mac app keep connections alive; without a
        # graceful-shutdown timeout, SIGTERM waits on them forever.
        uvicorn.run(
            create_app(profile, store), host=args.host, port=args.port, log_level="warning",
            timeout_graceful_shutdown=2,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
