# Releasing Grizzly

`scripts/release.sh` turns the source into a disk image that opens on any Apple silicon Mac running macOS 14 or later, without Gatekeeper warnings. It builds the app and its engine, then signs every binary with your Developer ID and the hardened runtime. Apple then notarises the app, which is stapled, and the same happens to the disk image.

## One-time setup

You need Xcode (not just the Command Line Tools) and a paid Apple Developer Program membership.

1. **Developer ID certificate.** Open Xcode → Settings → Accounts, add your Apple ID, select your team and click **Manage Certificates…**. Click **+** and choose **Developer ID Application**. Check that it is in your keychain:

   ```sh
   security find-identity -v -p codesigning
   ```

   You should see a line like `"Developer ID Application: Your Name (AB12CD34EF)"`. The part in brackets is your Team ID.

2. **App-specific password.** Sign in at [account.apple.com](https://account.apple.com) and go to Sign-In and Security → App-Specific Passwords. Create one called "Grizzly notary".

3. **Store the notary credentials** in your keychain, so the script never sees the password:

   ```sh
   xcrun notarytool store-credentials grizzly-notary \
       --apple-id you@example.com --team-id AB12CD34EF
   ```

   When it asks, paste the app-specific password.

## Each release

```sh
cd ~/Grizzly && git pull
GRIZZLY_VERSION=0.2.0 \
GRIZZLY_SIGN_IDENTITY="Developer ID Application: Your Name (AB12CD34EF)" \
    app/scripts/release.sh
```

The output is `app/build/Grizzly-0.2.0.dmg`. The two notarisation uploads are about 1 GB each. Expect around 20–40 minutes in total, mostly waiting on Apple. `--reuse` skips rebuilding the engine when only the Swift app changed.

If Apple rejects a submission, the script prints Apple's log. That log names each file that failed and why, usually an unsigned binary or a missing timestamp.

## What to check on another Mac

Download the disk image, drag Grizzly to Applications and open it. There should be no "unidentified developer" or "damaged" dialog. If there is one, run `spctl --assess --type execute -vv /Applications/Grizzly.app` and send the output.

## Notes

- **Entitlements.** `Support/Engine.entitlements` holds the hardened-runtime exceptions for the engine's Python and ffmpeg executables: JIT and library validation. The Swift app itself needs none.
- **Nothing may write inside the app once it is signed,** or Gatekeeper reports it as damaged. Python bytecode is precompiled and numba's cache goes to `~/Library/Caches/app.grizzly.studio`. `BundledEngineTests` checks that a story run leaves the engine folder untouched.
- **Bundle identifier.** It is `app.grizzly.studio`. Change it in `Support/Info.plist` before the first public release if you will use a domain you own; changing it later makes macOS treat the app as a different app.
- **Version numbers.** `GRIZZLY_VERSION` sets the version users see. The build number is the commit count, so it always increases.
