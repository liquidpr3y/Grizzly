#!/bin/bash
# Builds Grizzly.app from the Swift package, with the engine inside it
# (Contents/Resources/engine, built by bundle-engine.sh) so it runs on a Mac
# with no Python, uv or Homebrew.
#
#   scripts/make-app.sh               app + bundled engine (first build ~5 min)
#   scripts/make-app.sh --reuse       reuse build/engine from the last run
#   scripts/make-app.sh --no-engine   app only; it runs the engine from your checkout
#
# Signs with $GRIZZLY_SIGN_IDENTITY (default "-", ad hoc, for this Mac only).
# With a "Developer ID Application" identity it signs for distribution:
# hardened runtime, secure timestamps, Support/Engine.entitlements on the
# engine's executables. scripts/release.sh then notarises and packages it.
# $GRIZZLY_VERSION sets the marketing version (default: Info.plist's).
set -euo pipefail

cd "$(dirname "$0")/.."

# From the macOS 27 SDK, SwiftUI's @State is a macro whose plugin ships with
# Xcode; the Command Line Tools alone fail with "plugin for module
# 'SwiftUIMacros' not found".
if [[ "$(xcode-select -p 2>/dev/null)" == *CommandLineTools* ]]; then
    echo "Building Grizzly needs Xcode, not just the Command Line Tools." >&2
    echo "Install Xcode from the App Store, then run:" >&2
    echo "  sudo xcode-select -s /Applications/Xcode.app/Contents/Developer && sudo xcodebuild -license accept" >&2
    exit 1
fi
MODE="${1:-}"
IDENTITY="${GRIZZLY_SIGN_IDENTITY:--}"

swift build -c release --product Grizzly

APP=build/Grizzly.app
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$(swift build -c release --show-bin-path)/Grizzly" "$APP/Contents/MacOS/Grizzly"
cp Support/Info.plist "$APP/Contents/Info.plist"
# Build number: commits on this branch, so every release counts up.
plutil -replace CFBundleVersion -string "$(git rev-list --count HEAD 2>/dev/null || echo 1)" "$APP/Contents/Info.plist"
if [ -n "${GRIZZLY_VERSION:-}" ]; then
    plutil -replace CFBundleShortVersionString -string "$GRIZZLY_VERSION" "$APP/Contents/Info.plist"
fi

SIGN=(codesign --force --sign "$IDENTITY")
if [ "$IDENTITY" != "-" ]; then
    # Notarisation requires the hardened runtime and a secure timestamp.
    SIGN+=(--options runtime --timestamp)
fi

if [ "$MODE" != "--no-engine" ]; then
    if [ "$MODE" != "--reuse" ] || [ ! -x build/engine/python/bin/python3 ]; then
        scripts/bundle-engine.sh build/engine
    fi
    echo "==> Copying engine into the app"
    cp -R build/engine "$APP/Contents/Resources/engine"
    # Every Mach-O file is signed on its own: codesign --deep does not reach
    # code under Contents/Resources, and notarisation rejects unsigned code.
    # Extended attributes (quarantine, Finder info) make codesign refuse files.
    xattr -cr "$APP"
    echo "==> Signing engine binaries"
    # `file` on every file finds Mach-O code whatever it is named. Executables
    # get the engine entitlements; libraries cannot carry entitlements.
    COUNT=0
    while IFS='|' read -r f kind; do
        if [[ "$kind" == *executable* ]]; then
            "${SIGN[@]}" --entitlements Support/Engine.entitlements "$f"
        else
            "${SIGN[@]}" "$f"
        fi
        COUNT=$((COUNT + 1))
    done < <(find "$APP/Contents/Resources/engine" -type f -print0 | xargs -0 file -F '|' | grep 'Mach-O' | grep -v '(for architecture' | sed 's/| */|/')
    echo "    signed $COUNT binaries"
fi

"${SIGN[@]}" "$APP"
codesign --verify --deep --strict "$APP"

echo "Built $APP ($(du -sh "$APP" | cut -f1))"
echo "Run it with: open $APP"
