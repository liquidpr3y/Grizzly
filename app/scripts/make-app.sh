#!/bin/sh
# Builds Grizzly.app from the Swift package: a double-clickable app that
# starts the Python engine from your Grizzly checkout (set in Settings).
# Ad-hoc signed for local use; distribution needs a Developer ID and notarisation.
set -eu

cd "$(dirname "$0")/.."
swift build -c release --product Grizzly

APP=build/Grizzly.app
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$(swift build -c release --show-bin-path)/Grizzly" "$APP/Contents/MacOS/Grizzly"
cp Support/Info.plist "$APP/Contents/Info.plist"
codesign --force --sign - "$APP"

echo "Built $APP"
echo "Run it with: open $APP"
