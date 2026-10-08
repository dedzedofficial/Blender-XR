# Blender XR v0.4

**Free basic VR modeling inside Blender, by Ded Zed.**

Choose your dominant hand before entering VR. The other hand holds a small tool menu; the dominant controller points, selects, edits, and moves objects.

**Development release:** geometry and updater tests pass in Blender 5.0.0 and 5.2.2. Physical Quest 3 and Windows runtime testing is still pending. Air Link, SteamVR, and Virtual Desktop are intended OpenXR connection paths, not yet certified combinations.

[Download v0.4 installer](dist/blender-xr-v0.4.0.zip) · [Latest releases](https://github.com/dedzedofficial/Blender-XR/releases/latest) · [Roadmap](ROADMAP.md)

## Install

1. Download `blender-xr-v0.4.0.zip` from this repository's `dist` folder or Releases. Open the file and click **Download raw file** if GitHub shows its file page. Do not install GitHub's entire source-code ZIP.
2. In Blender, open **Edit > Preferences > Add-ons**, open the menu at the upper right, and select **Install from Disk**.
3. Select the installer ZIP and enable **Blender XR**.
4. In the 3D viewport, press **N** and open the **Blender XR** tab.
5. Choose **Right** or **Left** as your dominant hand before clicking **Start VR**.

No subscription or activation key. Source is GPL-3.0-or-later. The repository is public. GitHub downloads need no account or token.

## Meta and Valve PCVR targets

Blender runs on the PC. This add-on uses Blender's OpenXR support rather than a standalone Quest application. Only one OpenXR runtime should be active for the session.

| Connection | Setup to try |
| --- | --- |
| Quest Link / Air Link | Connect to the PC, enter Link, and set Meta Quest Link as the active OpenXR runtime. |
| SteamVR | Connect the headset to the PC, start SteamVR, and select SteamVR as the current OpenXR runtime in its settings. |
| Virtual Desktop | Connect through the Virtual Desktop PC streamer and choose VDXR as its OpenXR runtime, or use its SteamVR route with SteamVR active. |

Set the runtime before starting Blender; restart Blender if you change it. Hold both controllers awake/tracked before pressing **Start VR**. The add-on cannot establish Air Link or Virtual Desktop for you. Choose **Automatic**, **Meta**, or **Valve / SteamVR** in the sidebar before entering VR. Bindings cover Oculus Touch, Valve Index, Vive and simple controllers. Touch Pro/Plus and newer controllers depend on the runtime supplying a compatible profile; unsupported native profiles are not enabled by this extension.

| Headset family | v0.4 target and limits |
| --- | --- |
| Meta Quest 1, 2, 3, 3S and Pro | PC-connected OpenXR with two tracked Touch-compatible controllers. Link availability varies by headset/software; use a supported PCVR connection. |
| Meta Rift CV1 / Rift S | PC OpenXR runtime with tracked Touch controllers. |
| Valve Index | SteamVR OpenXR with Index controller bindings. Optional skeletal finger bridge. |
| Valve Steam Frame | SteamVR OpenXR when its controllers are exposed through compatible bindings. Its native controller extension is not enabled by Blender XR; physical validation pending. |
| Future Meta/Valve headsets | Conditional on PCVR OpenXR support, compatible controller profiles and two tracked hand poses. |
| Meta Go / Gear VR | Unsupported: this editing system needs positional tracking and two tracked hand poses. |

This is a compatibility target matrix, not a completed physical test matrix. It cannot make every Meta or Valve device compatible regardless of its runtime capabilities.

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
2. Public releases need no token. If the repository is private, supply a fine-grained GitHub token with **Contents: Read** access to **dedzedofficial/Blender-XR** in the password field. An environment variable, `BLENDER_XR_GITHUB_TOKEN`, is also supported.
3. Click **Check**, or **Download & Install** to fetch and install a newer release.
4. Restart Blender when prompted.

The token is held for the current Blender session, with `SKIP_SAVE`; it is not stored in the scene, saved preferences, or repository. Do not commit tokens. Public repository downloads will not need a token. The updater targets stable GitHub Releases, not arbitrary commits. Network requests run in a background thread. ZIP and checksum files are verified before installation, and changed files are restored if installation fails.

Release automation publishes each version after validation. A 404 can mean missing private-repository access or no release yet.

## Optional finger features

**Finger-touch shortcuts** work with Touch/Index controller touch sensors, not a full hand skeleton. Enable before starting VR. Hold a finger on the trigger and a thumb on the thumbstick for 0.7 seconds: the non-dominant hand toggles the menu (or cancels a live edit); the dominant hand cancels a live edit. Lift the fingers to rearm. The option defaults off, because some resting grips naturally touch both sensors. Other profiles simply lack this shortcut.

**Finger bridge (experimental)** reads partial/full SteamVR skeletal tracking. It does not add native controller-free hand tracking to Blender or Air Link. It requires SteamVR as the OpenXR runtime plus two tracked controller/hand poses. Virtual Desktop hand tracking must be configured to supply SteamVR skeletal input and compatible controller poses. VDXR alone does not feed this bridge. SteamVR's estimated, button-derived skeleton is rejected.

1. Install the optional free helper dependency into **system Python**, using `python -m pip install openvr==2.12.1401` (Windows: `py -m pip install openvr==2.12.1401`). No dependency is installed into Blender.
2. Choose **Finger bridge (experimental)** before **Start VR**. Keep SteamVR running and the hands/controllers tracked.
3. Click **Copy Hand Bridge Command** in the desktop sidebar and paste into a terminal. It launches the included helper with this VR session's key and loopback port.
4. Release both hands to arm. Thumb/index pinch replaces the trigger: select, menu clicks, or hold/release a tool preview. Close the dominant middle/ring/pinky fingers to grab in MOVE, then open to release. Pinch the other hand to toggle the menu or cancel.
5. Stop the helper with Ctrl+C. Stale input after 0.25 seconds cancels unfinished work; release both hands after reconnection. Stop VR before returning to controller input.

Skeletal pinch accuracy, simultaneous background SteamVR input and controller-free emulation need real headset testing. If SteamVR does not expose active partial/full skeletal actions, the mode waits rather than edits. Use SteamVR Input to bind the helper's two skeleton actions if the automatic bindings are unavailable. No automatic viewer movement is enabled in finger mode.

## v0.4 limits

- One local mesh at a time. Shared mesh data, linked mesh data, shape keys, and zero-scale objects are refused for topology edits.
- Face selection and editing operate on the base mesh cage. Evaluated modifiers may make its displayed surface differ; disable those modifiers while using v0.4 tools.
- Movement supports local unparented objects without constraints. Scaling, vertices/edges, sculpting, UVs, painting, nodes, and multi-object editing are future work.
- Use the VR-local history buttons during a session. History clears on stop. Desktop edits/native undo during VR can invalidate history; finish VR before using the desktop workflow.
- Some controller tracking/runtime failures cannot be detected through Blender's Python API. Stop VR if tracking becomes unreliable.
- This is not a replacement for all Blender desktop tools.

## Development and releases

Run `python scripts/build.py` to generate the installable ZIP and SHA-256 file. Source files live in `blender_xr/`; installer files sit at the root of the extension ZIP.

Run `python tests/test_gestures.py` for finger/protocol/profile checks. Run the remaining tests using a Blender binary:

```sh
blender --background --factory-startup --python-exit-code 1 --python tests/test_blender.py
blender --background --factory-startup --python-exit-code 1 --python tests/test_updater.py
```

GitHub Actions validates on Blender 5.0.0 and 5.2.2. The release workflow validates on 5.2.2 and publishes a version once. For the next release, update the manifest, `bl_info`, updater `VERSION`, documentation, and release notes together. Existing release assets are never silently replaced. A private repository must have GitHub Actions enabled for automated publishing.

See [TESTING.md](TESTING.md) for automated results and headset checks, and [ROADMAP.md](ROADMAP.md) for future scope.

Independent project by Ded Zed. Not affiliated with the Blender Foundation, Freebird XR, or the earlier MARUI BlenderXR project.
