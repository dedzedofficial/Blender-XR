# Mesh XR — local validation and manual publishing

GitHub Actions workflows were removed from `main` on **18 November 2026** to
avoid unattended runner usage. Mesh XR is a native Blender desktop extension,
not a GitHub-hosted service. Commits and pull requests do **not** automatically
validate or publish an installer. Do not restore the deleted workflows merely
to fix a draft pull-request conflict.

## Build and validate locally

On Windows, from the repository root in PowerShell:

```powershell
.\dev-local.ps1 -Build -BlenderPath 'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe'
```

`-Build` compiles the Python sources, runs the hardware-free regressions,
builds the versioned extension ZIP and verifies its contents/checksum.
`-BlenderPath` runs every Blender-dependent `tests/test_*.py` script in a
fresh, isolated Blender process. The command fails on the first failing test.
You can omit either parameter for a quicker partial check, but a partial check
does not establish release readiness.

Repeat the Blender integration suite using supported Blender versions 4.2,
4.5, 5.0 and 5.2, and verify packaging on Windows, Linux and both macOS
architectures where applicable. Test Mac OpenXR capability separately from
desktop installability. Record the exact Blender binary/version, platform,
result and any failures. See `TESTING.md` for full hardware acceptance.

## Stable-release gate

Version 0.8.5 currently has `RELEASE_CHANNEL = "development"`. Before
publishing anything marked stable:

1. Resolve code conflicts, finish release-scoped features and run the local
   source, package and supported-version checks.
2. Install the built ZIP into a clean Blender profile, then verify registration
   and representative modeling, material, rigging, and scene data round trips.
3. Obtain real Quest 3/SteamVR controller sign-off, including interrupted edits,
   tracking-loss rollback and spatial UI accuracy.
4. Only then explicitly set the release channel to `stable` and run
   `python scripts/check_release_ready.py`. Do not bypass its guard.
5. Build the final ZIP and verify its `.sha256` file; manually create a
   versioned GitHub release using those exact artifacts. Never overwrite an
   existing release tag or asset in place.
6. Submit the exact release ZIP to Blender Extensions using the publisher
   account's approved manual upload procedure. Submission does not mean
   moderation approval.

The official Blender extension ID remains `blender_xr`; user updates are
managed by Blender **Preferences > Get Extensions > Check for Updates**.
The extension must not self-update behind Blender's built-in mechanism.

## Credentials and troubleshooting

If the Blender Extensions publishing API is used manually, create its API
token in the publishing account and supply it only to that local submission
process. Do not store credentials in Git, tickets, logs or artifacts. An old
repository `BLENDER_EXTENSIONS_TOKEN` Actions secret no longer triggers
publication, because the Actions workflows are absent.

- If a Blender test fails, fix the underlying code and repeat that version's
  suite rather than publishing an unvalidated package.
- If the ZIP check fails, regenerate the icons/build and check the manifest,
  OpenVR wheel hash and version consistency.
- If a release version already exists, use a new correctly incremented
  version after validation, not a force-updated tag.
- If the Extensions website/API rejects a submission, verify account
  permissions, extension ID, version and moderation status before retrying.
