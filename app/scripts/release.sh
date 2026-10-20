#!/bin/bash
# Builds, signs, notarises and packages Grizzly for distribution:
# build/Grizzly-<version>.dmg, which opens on any Apple silicon Mac without
# Gatekeeper warnings. One-time setup is in RELEASING.md.
#
#   GRIZZLY_SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" scripts/release.sh [--reuse]
#
# --reuse skips rebuilding the engine. $GRIZZLY_NOTARY_PROFILE names the
# notarytool keychain profile (default grizzly-notary); $GRIZZLY_VERSION sets
# the version (default: Info.plist's).
set -euo pipefail

cd "$(dirname "$0")/.."
IDENTITY="${GRIZZLY_SIGN_IDENTITY:-}"
PROFILE="${GRIZZLY_NOTARY_PROFILE:-grizzly-notary}"

if [[ "$IDENTITY" != "Developer ID Application:"* ]]; then
    echo "Set GRIZZLY_SIGN_IDENTITY to your Developer ID Application identity. Yours:" >&2
    security find-identity -v -p codesigning | grep "Developer ID Application" >&2 || echo "  (none: see RELEASING.md)" >&2
    exit 1
fi
if ! xcrun notarytool history --keychain-profile "$PROFILE" >/dev/null 2>&1; then
    echo "No notarytool credentials named '$PROFILE'. Create them once with:" >&2
    echo "  xcrun notarytool store-credentials $PROFILE --apple-id you@example.com --team-id TEAMID" >&2
    exit 1
fi

# Submits a file to Apple's notary service and waits; prints Apple's log and
# stops if it is rejected.
notarise() {
    local file="$1" out id status
    echo "==> Notarising $(basename "$file") (uploads $(du -sh "$file" | cut -f1); usually 5-20 minutes)"
    out="$(mktemp)"
    # A rejection exits non-zero; read the result either way to show Apple's log.
    xcrun notarytool submit "$file" --keychain-profile "$PROFILE" --wait --output-format plist > "$out" || true
    id="$(/usr/libexec/PlistBuddy -c 'Print :id' "$out" 2>/dev/null || true)"
    status="$(/usr/libexec/PlistBuddy -c 'Print :status' "$out" 2>/dev/null || true)"
    rm -f "$out"
    if [ -z "$id" ]; then
        echo "The upload to Apple's notary service failed; see the error above." >&2
        exit 1
    fi
    if [ "$status" != "Accepted" ]; then
        echo "Notarisation $status (submission $id). Apple's log:" >&2
        xcrun notarytool log "$id" --keychain-profile "$PROFILE" >&2
        exit 1
    fi
    echo "    accepted ($id)"
}

GRIZZLY_SIGN_IDENTITY="$IDENTITY" scripts/make-app.sh "$@"
APP=build/Grizzly.app
VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist")"
BUILD="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$APP/Contents/Info.plist")"

echo "==> Checking signatures"
codesign --verify --deep --strict --verbose=2 "$APP"
DETAILS="$(codesign --display --verbose=2 "$APP" 2>&1)"
if ! grep -q "Authority=Developer ID Application" <<<"$DETAILS" || ! grep -q "flags=.*runtime" <<<"$DETAILS"; then
    echo "The app is not signed with a Developer ID and the hardened runtime:" >&2
    echo "$DETAILS" >&2
    exit 1
fi

# The app is notarised and stapled on its own, so it also opens offline
# after being copied out of the disk image.
ZIP=build/Grizzly-notarise.zip
rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"
notarise "$ZIP"
rm -f "$ZIP"
xcrun stapler staple "$APP"

echo "==> Disk image"
DMG="build/Grizzly-$VERSION.dmg"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
ditto "$APP" "$STAGE/Grizzly.app"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"
hdiutil create -quiet -volname "Grizzly" -srcfolder "$STAGE" -format ULFO -ov "$DMG"
codesign --force --sign "$IDENTITY" --timestamp "$DMG"
notarise "$DMG"
xcrun stapler staple "$DMG"

echo "==> Gatekeeper"
spctl --assess --type execute --verbose=2 "$APP"
spctl --assess --type open --context context:primary-signature --verbose=2 "$DMG"

echo "Released Grizzly $VERSION ($BUILD): $DMG ($(du -sh "$DMG" | cut -f1))"
