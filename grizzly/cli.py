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
    p.add_argument("--characters", type=int, default=3)
    p.add_argument("--locations", type=int, default=3)

    p = sub.add_parser("run", help="write, render and export everything that is missing")
    p.add_argument("project")
    p.add_argument("--scenes", type=int, default=4)
    p.add_argument("--shots", type=int, default=4)

    p = sub.add_parser("doctor", help="check the machine and load/test each model")
    p.add_argument("--skip-llm", action="store_true")
    p.add_argument("--skip-image", action="store_true")
    p.add_argument("--skip-refs", action="store_true")

    p = sub.add_parser("serve", help="start the local web studio")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8642)

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
        out = Pipeline(profile, store).run_all(
            args.project, progress=lambda s: print(f"== {s}", flush=True),
            n_scenes=args.scenes, n_shots=args.shots,
        )
        print(f"Done in {time.time() - start:.0f}s -> {out}")
    elif args.cmd == "doctor":
        from grizzly.doctor import run_doctor

        return run_doctor(profile, store.base.parent, args.skip_llm, args.skip_image, args.skip_refs, args.verbose)
    elif args.cmd == "serve":
        try:
            import uvicorn
        except ImportError:
            print("The web studio needs the server extra: pip install -e '.[server]'", file=sys.stderr)
            return 1
        from grizzly.server import create_app

        print(f"Grizzly studio on http://{args.host}:{args.port} (profile {profile.name})")
        uvicorn.run(create_app(profile, store), host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
