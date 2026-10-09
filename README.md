# Blender XR v0.4.7

**Free VR mesh editing and scene building inside Blender, by Ded Zed.**

Blender XR brings a simple controller-first modeling workflow into Blender using OpenXR. One hand holds a compact tool menu while the dominant controller points, selects, edits, transforms, places primitives and navigates the scene.

[Download the latest release](https://github.com/dedzedofficial/Blender-XR/releases/latest) · [Roadmap](ROADMAP.md) · [Testing](TESTING.md) · [Website](https://fishhwb.github.io/)

## What v0.4.7 includes

- Object selection, movement and uniform scaling in VR.
- Face selection, movement and scaling.
- Extrude, bevel, inset and delete-face tools.
- Ray-draggable X, Y and Z transform handles.
- Distance-aware gizmos that stay usable farther from the mesh.
- Primitive placement for cubes, spheres, cylinders, cones, toruses and planes.
- Left-stick flight, right-stick turning and vertical movement.
- Grab-empty-space locomotion.
- VR-local Undo / Redo.
- Save Blend directly from VR or the desktop sidebar.
- Cleaner desktop and VR menus with duplicate options removed.
- Patreon and Website buttons in the Blender sidebar.
- Built-in public release updater with checksum verification.

The v0.5 roadmap expands this into fuller mesh modeling, including vertex and edge workflows. See [ROADMAP.md](ROADMAP.md) for the planned path through materials, UV mapping, modifiers, rigging, weight painting and v1.0.

## Requirements

- Blender **4.2+** with OpenXR support.
- A PC capable of running Blender in VR.
- Two tracked controllers for the normal controller workflow.
- One active OpenXR runtime for the session.

Automated validation currently covers Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**. Blender 5.0.1 is blocked because of a known VR crash. Physical headset/runtime testing is still an ongoing part of development.

## Install

1. Open [Latest Releases](https://github.com/dedzedofficial/Blender-XR/releases/latest).
2. Download the current `blender-xr-vX.X.X.zip` installer asset. Do not install GitHub's automatic source-code ZIP.
3. In Blender, open **Edit > Preferences > Add-ons**.
4. Open the menu in the upper-right and choose **Install from Disk**.
5. Select the downloaded ZIP and enable **Blender XR**.
6. In the 3D Viewport, press **N** and open the **Blender XR** tab.
7. Choose your dominant hand and click **Start VR**.

No subscription, activation key or GitHub account is required.

## PCVR setup

Blender XR uses Blender's OpenXR support. Configure the OpenXR runtime before starting Blender.

| Connection | Setup |
| --- | --- |
| **Quest Link / Air Link** | Connect to the PC and use Meta Quest Link as the active OpenXR runtime. |
| **SteamVR** | Start SteamVR and select SteamVR as the current OpenXR runtime. |
| **Virtual Desktop** | Use VDXR when supported, or route through SteamVR with SteamVR active. |

Controller bindings target Touch-compatible controllers, Valve Index, Vive and simple OpenXR controller profiles. Actual compatibility depends on the runtime exposing suitable controller actions.

## Quick controls

| Control | Action |
| --- | --- |
| Dominant trigger on menu | Choose a tool or command. |
| Dominant trigger with Select | Select a mesh or selected edit-mode face. |
| Grip in Move | Grab and position an object. |
| Trigger on X/Y/Z handle | Drag the selected transform along that axis. |
| Trigger on Size handle | Scale the selected object or face. |
| Other trigger | Toggle the hand menu or cancel live work. |
| Left thumbstick | Move / fly. |
| Right thumbstick left/right | Turn. |
| Right thumbstick up/down | Move vertically. |
| Hold left-stick click | Turbo flight. |
| Grip empty space | Pull yourself through the scene. |
| Undo / Redo | Restore recent Blender XR edits for the current session. |
| Save Blend | Save the current project. |
| Stop VR / ESC | Stop the session and cancel unfinished work. |

## Basic modeling workflow

1. Start with a mesh or add one from **Shapes**.
2. Point at the object and select it.
3. Use **Move** or **Scale** for whole-object transforms.
4. Enter **Face Mode** for edit tools.
5. Select a face and choose **Move**, **Scale**, **Extrude**, **Bevel**, **Inset** or **Delete**.
6. Aim at the transform handle, hold the trigger, drag and release to apply.
7. Use **Undo** if needed and **Save Blend** when finished.

The gizmo grows with viewing distance so its handles remain easier to raycast from farther away.

## Scene navigation

- **Left stick:** forward/backward and sideways movement.
- **Right stick:** turn and move vertically.
- **Turbo:** hold the left-stick click or enable Turbo from Travel.
- **Fly / Walk:** choose whether head pitch affects forward movement.
- **Grab air:** grip empty space and pull your hand to reposition yourself.
- **Reset View:** return to the starting navigation position.

Movement is designed for full Blender scenes rather than a small fixed VR play area.

## Saving

Use **Save Blend** from the desktop sidebar or VR menu.

- Existing projects save back to their current file.
- Unsaved projects default to a timestamped `.blend` in `Documents/BlenderXR`.
- You can set a first-save path in the sidebar before entering VR.
- Private Blender XR undo snapshots are excluded from the saved project.

## Updating

The sidebar includes **Update Blender XR**.

1. Stop VR.
2. Enable **Allow Online Access** in Blender preferences.
3. Click **Update Blender XR**.
4. Restart Blender when prompted.

The updater downloads the current public release, checks its checksum, validates the extension archive and rolls back file replacement if installation fails.

## Experimental finger features

Controller finger-touch shortcuts and the optional SteamVR skeletal hand bridge remain experimental. They are not required for normal controller use.

The SteamVR bridge uses an external helper and `openvr` in system Python. See the source and testing documentation before relying on it for production work.

## Current limitations

- One local editable mesh at a time for topology editing.
- Shared/linked meshes, shape-key meshes and zero-scale targets are rejected for topology changes.
- Editing operates on the base mesh cage; evaluated modifiers can visually differ from it.
- Full vertex/edge modeling, UV editing, materials, rigging and weight painting are roadmap features rather than complete v0.4.7 systems.
- VR Undo / Redo is session-local.
- Physical headset behavior can vary between OpenXR runtimes and controller profiles.
- Blender XR is not intended to replace every desktop Blender tool.

## Development

Build the installable extension with:

```sh
python scripts/build.py
```

Run the standard Python checks with:

```sh
python tests/test_gestures.py
python tests/test_prune.py
```

The remaining regression tests run through Blender in GitHub Actions. The project validates against Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2 before release.

Source is licensed under **GPL-3.0-or-later**.

See [TESTING.md](TESTING.md) for validation details and [ROADMAP.md](ROADMAP.md) for the planned feature path.

---

## Support Development

Blender XR is free and open source. If you find the project useful and want to help support continued development, testing and future VR modeling features, you can support Ded Zed on Patreon.

**[Support Blender XR development on Patreon](https://www.patreon.com/cw/DedZed)**

Patreon support is completely optional. There is no paid feature tier and development remains focused on keeping Blender XR freely available.

**[FISHHWB Website](https://fishhwb.github.io/)**

Independent project by Ded Zed. Not affiliated with the Blender Foundation, Freebird XR or the earlier MARUI BlenderXR project.
