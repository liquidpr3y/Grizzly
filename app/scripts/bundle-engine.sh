#!/bin/bash
# Builds a self-contained Grizzly engine: a relocatable CPython
# (python-build-standalone, fetched by uv), Grizzly and its MLX dependencies
# installed into it, and a static ffmpeg. make-app.sh copies the result into
# Grizzly.app/Contents/Resources/engine, so customers need no terminal, uv or
# Homebrew. Needs uv on the build machine only.
#
#   app/scripts/bundle-engine.sh [OUT]       (default: app/build/engine)
#
# GRIZZLY_EXTRAS picks the extras (default mac,server,video).
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$APP_DIR/.." && pwd)"
OUT="${1:-$APP_DIR/build/engine}"
EXTRAS="${GRIZZLY_EXTRAS:-mac,server,video}"
PYTHON_VERSION="${GRIZZLY_PYTHON:-$(cat "$REPO/.python-version")}"

command -v uv >/dev/null || { echo "uv is needed to build the engine: https://docs.astral.sh/uv/" >&2; exit 1; }

rm -rf "$OUT"
mkdir -p "$OUT"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "==> Python $PYTHON_VERSION (python-build-standalone)"
uv python install "$PYTHON_VERSION" --install-dir "$STAGE/pythons" --no-bin --quiet
SRC="$(find "$STAGE/pythons" -mindepth 1 -maxdepth 1 -type d -name 'cpython-*' | head -1)"
[ -n "$SRC" ] || { echo "uv did not install a CPython" >&2; exit 1; }
cp -R "$SRC" "$OUT/python"
PY="$OUT/python/bin/python3"
# uv marks its Pythons as externally managed; this copy is ours to install into.
find "$OUT/python/lib" -maxdepth 2 -name EXTERNALLY-MANAGED -delete

echo "==> Grizzly [$EXTRAS] and dependencies"
# A regular (non-editable) install, so the engine does not depend on this checkout.
uv pip install --python "$PY" --no-cache --quiet "$REPO[$EXTRAS]"

echo "==> ffmpeg"
mkdir -p "$OUT/bin"
FFMPEG="$("$PY" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"
ln -s "$("$PY" -c 'import os, sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$FFMPEG" "$OUT/bin")" "$OUT/bin/ffmpeg"
"$OUT/bin/ffmpeg" -hide_banner -version | head -1

echo "==> Trimming"
STDLIB="$(echo "$OUT"/python/lib/python3.*)"
rm -rf "$STDLIB"/{test,idlelib,tkinter,turtledemo,ensurepip,lib2to3} "$OUT/python/share" "$OUT/python/include"
find "$OUT/python/lib" -maxdepth 1 -name "tcl8*" -exec rm -rf {} + 2>/dev/null || true
find "$OUT/python/lib" -maxdepth 1 \( -name 'libtcl*' -o -name 'libtk*' \) -delete
# The app bundle is read-only and signed: compile everything now, in a form
# Python trusts without comparing source timestamps, which copying changes.
"$PY" -m compileall -q -f -j 0 --invalidation-mode unchecked-hash "$OUT/python/lib" || true

echo "==> Smoke test"
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 "$PY" -s -m grizzly --help >/dev/null
PATH="$OUT/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 "$PY" -s -c 'from grizzly.tools import ffmpeg; print("    ffmpeg:", ffmpeg())'

VERSION="$(cd "$REPO" && git describe --always --dirty 2>/dev/null || echo unknown)"
echo "$VERSION" > "$OUT/VERSION"
echo "Engine $VERSION in $OUT ($(du -sh "$OUT" | cut -f1))"
