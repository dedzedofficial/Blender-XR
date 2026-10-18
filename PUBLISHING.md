# Mesh XR — GitHub and Blender Extensions publishing

## Automated workflow

On a new main-branch version, `.github/workflows/release.yml` calls the complete
four-version Blender validation matrix before packaging. If any check fails,
publication stops. When validation passes, the workflow creates an immutable
versioned GitHub release and submits the exact version to Blender Extensions.
Existing release tags and assets are not force-updated.

Blender Extensions uses the stable extension ID `blender_xr`. The add-on itself
does not contain an updater, as this is prohibited by the official platform.

## One-time secret setup (required)

1. On the Blender Extensions website, create a publishing API token in the account
   that maintains Mesh XR.
2. In **this repository** open **Settings > Secrets and variables > Actions**.
3. Add a **repository secret** named exactly `BLENDER_EXTENSIONS_TOKEN`.
4. Paste the token as its value. Do **not** commit it to source code, issues,
   logs, build artifacts or documentation.

A secret in `CubeZ-Auto` or another GitHub repository is **not** automatically
available to Blender-XR workflows. Each repository must be granted access.

## Retry an already released version

If a GitHub release succeeds but the Blender Extensions submission fails due
to a missing token or API error:

1. Add/fix `BLENDER_EXTENSIONS_TOKEN`.
2. Open **Actions > Package and release Mesh XR > Run workflow**.
3. Choose branch `main` and enable `publish_existing_to_blender`.
4. Run the workflow and inspect **Publish to Blender Extensions** for success.

The workflow will rebuild and verify the current manifest version without
overwriting the existing GitHub release or force-moving its tag.

## Review and user updates

A successful API upload means *submitted*, not necessarily *approved*.
Check the Mesh XR version history on Blender Extensions for moderation status.
Users of the official Blender extension repository still use Blender's
**Preferences > Get Extensions > Check for Updates** feature to find updates;
the extension must not self-update behind Blender's back.

## Troubleshooting

- **Missing token:** the upload step must fail with an explicit error; configure
  the secret in this repository, then retry manually.
- **Compatibility test fails:** fix the failed Blender version first. Do not
  bypass or delete a failing test solely to publish.
- **Version already exists:** bump the manifest and Python version for a genuinely
  new release; never rewrite an approved release tag.
- **API responds with an error:** read its returned response body and check
  the extension ID, account permissions, package version and upload status.
