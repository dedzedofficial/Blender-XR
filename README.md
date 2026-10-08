# Blender XR v0.3

**Free basic VR modeling inside Blender, by Ded Zed.**

Choose your dominant hand before entering VR. The other hand holds a small tool menu; the dominant controller points, selects, edits, and moves objects.

**Initial development release:** geometry and updater tests pass in Blender 5.0.0 and 5.2.2. Physical Quest 3 and Windows runtime testing is still pending. Air Link, SteamVR, and Virtual Desktop are intended OpenXR connection paths, not yet certified combinations.

[Download v0.3 installer](dist/blender-xr-v0.3.0.zip) · [Latest releases](https://github.com/dedzedofficial/Blender-XR/releases/latest) · [Roadmap](ROADMAP.md)

## Install

1. Download `blender-xr-v0.3.0.zip` from this repository's `dist` folder or Releases. Open the file and click **Download raw file** if GitHub shows its file page. Do not install GitHub's entire source-code ZIP.
2. In Blender, open **Edit > Preferences > Add-ons**, open the menu at the upper right, and select **Install from Disk**.
3. Select the installer ZIP and enable **Blender XR**.
4. In the 3D viewport, press **N** and open the **Blender XR** tab.
5. Choose **Right** or **Left** as your dominant hand before clicking **Start VR**.

No subscription or activation key. Source is GPL-3.0-or-later. This repository is private, so users need repository access to download until the owner makes it public. Repository privacy is separate from the free software license.

## Connect Quest 3 / PCVR

Blender runs on the PC. This add-on uses Blender's OpenXR support rather than a standalone Quest application. Only one OpenXR runtime should be active for the session.

| Connection | Setup to try |
| --- | --- |
| Quest Link / Air Link | Connect to the PC, enter Link, and set Meta Quest Link as the active OpenXR runtime. |
| SteamVR | Connect the headset to the PC, start SteamVR, and select SteamVR as the current OpenXR runtime in its settings. |
| Virtual Desktop | Connect through the Virtual Desktop PC streamer and choose VDXR as its OpenXR runtime, or use its SteamVR route with SteamVR active. |

Set the runtime before starting Blender; restart Blender if you change it. Hold both controllers awake/tracked before pressing **Start VR**. The add-on cannot establish Air Link or Virtual Desktop for you. Other PCVR controllers have preliminary action bindings, but physical testing is pending.

Requires Blender 5+ with OpenXR, a PC capable of running VR, and two tracked controllers. Blender 5.0.1 is blocked due to a known VR crash; 5.0.0 and 5.2.2 were used for automated checks. Later versions need testing before being added to the compatibility matrix.

## Controls

| Control | Action |
| --- | --- |
| Dominant trigger, pointing at menu | Choose a tool or menu command. |
| Dominant trigger with SELECT | Select an object; in face edit mode, select a face. |
| MODE menu button | Switch the selected mesh between object mode and face edit mode. |
| Grip + trigger with SELECT in face mode | Add or remove a face from the selection. |
| Trigger with EXTRUDE / BEVEL / INSET | Hold and move the controller to preview the amount; release to apply. |
| Dominant grip with MOVE in object mode | Move and rotate the selected object; release to apply. |
| Non-dominant trigger | Toggle the hand menu, or cancel an active edit/move. |
| Non-dominant thumbstick | Move the viewer horizontally while no tool operation is active. |
| LESS / MORE menu buttons | Halve or double the starting tool distance. |
| UNDO / REDO | Undo/redo the latest 20 Blender XR edits and object moves during the current session. |
| RESET VIEW | Reset viewer navigation to the starting location. |
| STOP VR, desktop Stop VR, or ESC | Stop the session and cancel unfinished work. |

### First edit

1. Start with a cube or another simple mesh. Place the 3D cursor near your workspace; it sets the starting VR origin.
2. Enter VR, point at the mesh, and select it with **SELECT**.
3. Click **MODE**, then use **SELECT** to pick the face you want.
4. Choose **EXTRUDE**, **BEVEL**, or **INSET** on the other hand.
5. Point away from the menu, hold the trigger, and move the dominant controller. Release to commit; press the other trigger to cancel.

Extrusion follows the area-weighted average selected face normal. Moving along that normal changes depth. Bevel and inset use sideways controller movement. A short trigger click uses the default distance, initially 0.03 in local mesh units. Bevel segment count is set before entering VR. The menu floats above the other hand and faces your head for readability.

## Update from GitHub

The sidebar includes **Check** and **Download & Install** buttons.

1. Stop VR and enable **Allow Online Access** in Blender preferences.
2. For this private repository, supply a fine-grained GitHub token with **Contents: Read** access to **dedzedofficial/Blender-XR** in the password field. An environment variable, `BLENDER_XR_GITHUB_TOKEN`, is also supported.
3. Click **Check**, or **Download & Install** to fetch and install a newer release.
4. Restart Blender when prompted.

The token is held for the current Blender session, with `SKIP_SAVE`; it is not stored in the scene, saved preferences, or repository. Do not commit tokens. Public repository downloads will not need a token. The updater targets stable GitHub Releases, not arbitrary commits. Network requests run in a background thread. ZIP and checksum files are verified before installation, and changed files are restored if installation fails.

The first release must exist on GitHub for update checks to work. Release automation creates it after validation. A 404 can mean missing private-repository access or no release yet.

## v0.3 limits

- One local mesh at a time. Shared mesh data, linked mesh data, shape keys, and zero-scale objects are refused for topology edits.
- Face selection and editing operate on the base mesh cage. Evaluated modifiers may make its displayed surface differ; disable those modifiers while using v0.3 tools.
- Movement supports local unparented objects without constraints. Scaling, vertices/edges, sculpting, UVs, painting, nodes, and multi-object editing are future work.
- Use the VR-local history buttons during a session. History clears on stop. Desktop edits/native undo during VR can invalidate history; finish VR before using the desktop workflow.
- Some controller tracking/runtime failures cannot be detected through Blender's Python API. Stop VR if tracking becomes unreliable.
- This is not a replacement for all Blender desktop tools.

## Development and releases

Run `python scripts/build.py` to generate the installable ZIP and SHA-256 file. Source files live in `blender_xr/`; installer files sit at the root of the extension ZIP.

Run tests using a Blender binary:

```sh
blender --background --factory-startup --python-exit-code 1 --python tests/test_blender.py
blender --background --factory-startup --python-exit-code 1 --python tests/test_updater.py
```

GitHub Actions validates on Blender 5.0.0 and 5.2.2. The release workflow validates on 5.2.2 and publishes a version once. For the next release, update the manifest, `bl_info`, updater `VERSION`, documentation, and release notes together. Existing release assets are never silently replaced. A private repository must have GitHub Actions enabled for automated publishing.

See [TESTING.md](TESTING.md) for automated results and headset checks, and [ROADMAP.md](ROADMAP.md) for future scope.

Independent project by Ded Zed. Not affiliated with the Blender Foundation, Freebird XR, or the earlier MARUI BlenderXR project.
