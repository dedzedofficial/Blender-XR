# Blender XR v0.4.4

**Free basic VR modeling inside Blender, by Ded Zed.**

Choose your dominant hand before entering VR. The other hand holds a small tool menu; the dominant controller points, selects, edits, and moves objects.

**v0.4.4 fixing update:** fixes the unsupported BOOLEAN action type that prevented VR startup, adds Save Blend, and lowers the minimum Blender version to 4.2.0. Full-scene flight, right-stick turning, ray switching and basic modeling remain included. Automated checks use Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2. Physical headset and Windows testing remains pending.

[Download v0.4.4 installer](dist/blender-xr-v0.4.4.zip) · [Latest releases](https://github.com/dedzedofficial/Blender-XR/releases/latest) · [Roadmap](ROADMAP.md)

## Install

1. Download `blender-xr-v0.4.4.zip` from this repository's `dist` folder or Releases. Open the file and click **Download raw file** if GitHub shows its file page. Do not install GitHub's entire source-code ZIP.
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

Requires Blender 4.2+ with OpenXR, a PC capable of running VR, and two tracked controllers. Blender 5.0.1 is blocked due to a known VR crash; 4.2.0, 4.5.0, 5.0.0 and 5.2.2 are used for automated checks. Later versions need testing before being added to the compatibility matrix.

## Controls

| Control | Action |
| --- | --- |
| Dominant trigger, pointing at menu | Choose a tool or menu command. |
| Dominant trigger with SELECT | Select a mesh or face; point at another mesh to switch the active edit target. |
| MODE menu button | Switch the selected mesh between object mode and face edit mode. |
| Grip + trigger with SELECT in face mode | Add or remove a face from the selection. |
| Trigger with EXTRUDE / BEVEL / INSET | Hold and move the controller to preview the amount; release to apply. |
| Dominant grip with MOVE in object mode | Point at a mesh, grip to move and rotate it; release to apply. |
| Non-dominant trigger | Toggle the hand menu, or cancel an active edit/move. |
| Left thumbstick | Fly in head direction, including head pitch; works regardless of dominant hand. Walk mode keeps movement level. |
| Right thumbstick left/right | Turn the viewer. Default: 30-degree snap per deflection; return the stick to centre before the next turn. Smooth turning is optional. |
| Right thumbstick up/down | Fly vertically. |
| Hold left thumbstick click | Four-times turbo flight. |
| TRAVEL menu | Set flight/walk, turbo, faster/slower, snap/smooth, reset view and tool distance. |
| Either grip, ray pointing into empty space | Hold and pull your hand to move the viewer in 3D; release to stop. Works with controller grips and the experimental finger-curl bridge. |
| SHAPES | Choose cube, sphere, cylinder, cone, torus or plane, point away from the menu, then trigger to place. |
| LESS / MORE menu buttons | Halve or double the starting tool distance. |
| UNDO / REDO | Undo/redo the latest 20 Blender XR edits, object moves and primitive creations during the current session. |
| RESET VIEW | Reset viewer navigation to the starting location. |
| SAVE BLEND (Tools or Travel) | Save the current project, or create a timestamped .blend file if unsaved. |
| STOP VR, desktop Stop VR, or ESC | Stop the session and cancel unfinished work. |

### First edit

1. Start with a cube or another simple mesh. Place the 3D cursor near your workspace; it sets the starting VR origin.
2. Enter VR, point at the mesh, and select it with **SELECT**.
3. Click **MODE**, then use **SELECT** to pick the face you want.
4. Open **Edit Tools** on the other hand and choose **EXTRUDE**, **BEVEL**, or **INSET**.
5. Point away from the menu, hold the trigger, and move the dominant controller. Release to commit; press the other trigger to cancel.

Extrusion follows the area-weighted average selected face normal. Moving along that normal changes depth. Bevel and inset use sideways controller movement. A short trigger click uses the default distance, initially 0.03 in local mesh units. Bevel segment count is set before entering VR. The menu floats above the other hand and faces your head for readability.

### Build from primitives

Open **SHAPES** on the hand menu, choose a primitive and point at its intended location. A green wireframe box shows the placement bounds. Trigger places an ordinary Blender mesh and selects MOVE so you can point at it and grip to position it. Use MODE to edit its faces with Blender XR tools. UNDO removes a new primitive; REDO restores it in object mode.

Shapes land on the ray-hit surface, offset by half their size (plane has no offset). In empty space they appear at **Placement distance**, initially 1.5 VR metres. Set **Shape size**, **Placement distance**, **Flight speed** and **Grab empty space to move** in the sidebar. The empty-space grip gesture translates the viewer; it does not rotate or scale the scene.

If v0.4 raised the `Event has no attribute timer` error, stop VR and restart Blender before updating. v0.4.1 handles TIMER events using the session clock and never reads that missing attribute.

### Fly and switch meshes

Left moves, right turns, independent of which hand edits. Default flight speed is 3 VR metres/second with no scene boundary. Look up or down to fly in that direction, or use the right stick vertically for altitude. Hold the left stick click for 4x speed, or use **Travel > Faster** to double base speed up to 1000 VR metres/second. **Slower** halves it. **Turbo** keeps the 4x boost on without holding a button. High speeds help cross large scenes; use Slower for precise work. Saved scenes can retain an older speed setting.

The right stick snaps 30 degrees by default, with one turn per deflection. **Travel > Snap/Smooth** changes to continuous turning. Snap angle and smooth turn speed are adjustable in the sidebar. Turning pivots around your head, including when the starting 3D cursor is away from the origin. Navigation pauses during live edits, object grabs and grab-air movement.

The menu separates **Tools**, **Edit Tools**, **Shapes** and **Travel**, with larger labels, active-tool/turbo highlights, selected mesh name and control hints. A green ray and bounds identify the mesh under the pointer. In SELECT, trigger another mesh to switch targets. If you were face editing, the old mesh leaves edit mode and the new mesh enters it with the hit face selected. A linked/shared mesh, shape-key mesh or zero-scale target is refused before leaving the current edit target. Finish or cancel live work before switching.

## Save your Blender project

Use **Save Blend** on the **Tools** or **Travel** hand menu, or the desktop sidebar. The button writes a normal `.blend` file with your scene and committed mesh edits. Finish or cancel any live edit/move first. Saving preserves the current session's VR undo history and excludes its private mesh snapshots from the saved project.

- Existing project: save back to its current filepath, using Blender's normal save behavior and backup preferences.
- Unsaved project: create `BlenderXR-YYYYMMDD-HHMMSS.blend` in your home **Documents/BlenderXR** folder. An occupied timestamp gets a numbered filename.
- Optional first-save location: choose an absolute **Blend save path** in the sidebar before VR. An existing file at that first-save path is refused; open it in Blender if you want to work on it.

The chosen path appears in the sidebar and the hand menu confirms the saved filename. Saved projects can be reopened and edited normally in Blender. VR undo is session-local and is not restored when reopening the file.

## Update from GitHub

The sidebar has one **Update Blender XR** button. Stop VR, enable **Allow Online Access** in Blender preferences, then click it to download and install the latest stable release. No GitHub account, key or token is required. Restart Blender when prompted.

The updater verifies the installer ZIP and checksum before installation, runs network requests in a background thread, and restores changed files if installation fails. Release automation verifies the new installer before removing older releases and installer downloads.

## Optional finger features

**Finger-touch shortcuts** work with Touch/Index controller touch sensors, not a full hand skeleton. Enable before starting VR. Hold a finger on the trigger and a thumb on the thumbstick for 0.7 seconds: the non-dominant hand toggles the menu (or cancels a live edit); the dominant hand cancels a live edit. Lift the fingers to rearm. The option defaults off, because some resting grips naturally touch both sensors. Other profiles simply lack this shortcut.

**Finger bridge (experimental)** reads partial/full SteamVR skeletal tracking. It does not add native controller-free hand tracking to Blender or Air Link. It requires SteamVR as the OpenXR runtime plus two tracked controller/hand poses. Virtual Desktop hand tracking must be configured to supply SteamVR skeletal input and compatible controller poses. VDXR alone does not feed this bridge. SteamVR's estimated, button-derived skeleton is rejected.

1. Install the optional free helper dependency into **system Python**, using `python -m pip install openvr==2.12.1401` (Windows: `py -m pip install openvr==2.12.1401`). No dependency is installed into Blender.
2. Choose **Finger bridge (experimental)** before **Start VR**. Keep SteamVR running and the hands/controllers tracked.
3. Click **Copy Hand Bridge Command** in the desktop sidebar and paste into a terminal. It launches the included helper with this VR session's key and loopback port.
4. Release both hands to arm. Thumb/index pinch replaces the trigger: select, menu clicks, or hold/release a tool preview. Close the dominant middle/ring/pinky fingers to grab in MOVE, then open to release. Pinch the other hand to toggle the menu or cancel.
5. Stop the helper with Ctrl+C. Stale input after 0.25 seconds cancels unfinished work; release both hands after reconnection. Stop VR before returning to controller input.

Skeletal pinch accuracy, simultaneous background SteamVR input and controller-free emulation need real headset testing. If SteamVR does not expose active partial/full skeletal actions, the mode waits rather than edits. Use SteamVR Input to bind the helper's two skeleton actions if the automatic bindings are unavailable. Finger mode uses either-hand finger curl in empty space for grab-air movement; it has no thumbstick locomotion.

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
blender --background --factory-startup --python-exit-code 1 --python tests/test_controls.py
blender --background --factory-startup --python-exit-code 1 --python tests/test_flight.py
blender --background --factory-startup --python-exit-code 1 --python tests/test_save.py
blender --background --factory-startup --python-exit-code 1 --python tests/test_updater.py
```

GitHub Actions validates on Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2. The release workflow validates on 5.2.2 and publishes a version once. For the next release, update the manifest, `bl_info`, updater `VERSION`, documentation, and release notes together. Existing release assets are never silently replaced. A private repository must have GitHub Actions enabled for automated publishing.

See [TESTING.md](TESTING.md) for automated results and headset checks, and [ROADMAP.md](ROADMAP.md) for future scope.

Independent project by Ded Zed. Not affiliated with the Blender Foundation, Freebird XR, or the earlier MARUI BlenderXR project.

## Ray-draggable axis handles

Choose **MOVE** in object mode to show red **X**, green **Y** and blue **Z** handles. Aim the dominant-hand ray at a handle, hold the trigger and sweep the ray along that axis. Release to apply. In face edit mode, select faces, open **Edit Tools**, and choose **EXTRUDE** for the same XYZ handles. Extrusion can travel in either direction on the chosen axis. **BEVEL** and **INSET** use a yellow SIZE handle because they change thickness rather than translate geometry. Aim across a handle; pointing directly along its axis makes dragging ambiguous and retains the last valid amount. The off-hand trigger cancels a drag. Undo and Redo restore committed changes.

Choose **DEL FACES** in Edit Tools to delete selected faces. Undo restores them.

For free movement across the entire scene, the physical left thumbstick moves sideways and forward/backward; the physical right thumbstick moves up/down and turns left/right. All three spatial axes are accessible regardless of which hand is dominant. Travel provides speed, turbo and flight controls; gripping empty air lets you pull the scene.
