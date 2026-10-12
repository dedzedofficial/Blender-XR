# XR Mesh v0.6.0

**Free VR mesh modeling and scene building inside Blender, by Ded Zed.**

XR Mesh adds a controller-first OpenXR modeling workflow to Blender. One hand carries a compact tool menu while the other points, selects, edits, transforms, places primitives, assigns colors and moves around the scene.

[Latest Release](https://github.com/dedzedofficial/Blender-XR/releases/latest) · [Report Issues](https://github.com/dedzedofficial/Blender-XR/issues) · [Roadmap](ROADMAP.md) · [Testing](TESTING.md)

## v0.6.0

This release is the Blender Extensions review/compliance pass and a runtime wiring fix.

- Public extension name changed from **Blender XR** to **XR Mesh**.
- Manifest Support/Report Issues now points directly to the public GitHub Issues tracker.
- Removed the in-extension updater box and Patreon/funding controls.
- The packaged add-on contains no `threading` or `queue` imports; the build fails if either is added in the future.
- The optional SteamVR hand helper remains external and uses the existing `subprocess`/loopback bridge path.
- The v0.5.6 runtime layer is now applied during normal extension startup, activating the shipped HSL sliders, continuous trigger dragging, selected-geometry transforms and face-color history in installed builds.

## Launch

XR Mesh can be started from either:

- **3D Viewport > Sidebar (`N`) > XR Mesh > Start VR**
- **3D Viewport > View > Start XR Mesh**

Blender's separate **VR Scene Inspection** extension provides Blender's own Start VR Session control; XR Mesh does not remove or replace it.

## Core modeling features

- Vertex, edge and face selection in VR.
- Add/remove from the selection with grip + trigger.
- Move and scale selected vertices, edges and faces.
- Extrude vertices, edges and faces.
- Bevel vertex/edge selections and face boundaries.
- Inset selected faces.
- Delete, merge, subdivide and duplicate selected geometry.
- Recalculate and flip face normals.
- Object movement and uniform scaling.
- Distance-aware X/Y/Z and Size gizmos.
- Primitive placement: cube, sphere, cylinder, cone, torus and plane.
- Full-scene flight, snap/smooth turning and grab-air navigation.
- Session Undo / Redo and Save Blend from VR.
- HSL color sliders and per-face material assignment in VR.

## Install

1. Open [Latest Releases](https://github.com/dedzedofficial/Blender-XR/releases/latest).
2. Download the current extension ZIP.
3. In Blender open **Edit > Preferences > Add-ons / Extensions**.
4. Choose **Install from Disk** and select the ZIP.
5. Enable **XR Mesh**.
6. In the 3D Viewport press **N** and open the **XR Mesh** tab, or open the **View** menu.
7. Pick your dominant hand and press **Start VR**.

The extension is free, open source and licensed under **GPL-3.0-or-later**.

## Requirements

- Blender **4.2+** with OpenXR support.
- PCVR-capable hardware.
- Two tracked controllers for the standard controller workflow.
- One active OpenXR runtime.

Automated validation covers Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**. Blender 5.0.1 is blocked because of a known VR crash.

## Materials and color

Choose **Colors** from Object Mode or Edit Mode. XR Mesh opens three full-width **Hue**, **Saturation** and **Lightness** sliders. Point anywhere on a bar and hold the dominant trigger to drag continuously.

**Pick** reads the active material color back into the sliders. **Apply** commits the current color. White and Black set Lightness to its extremes without discarding the chosen Hue/Saturation. Red, Orange, Yellow, Green, Cyan, Blue, Purple and Pink remain available as optional presets.

In **Object Mode**, Apply recolors the active object. In **Edit Mode**, switch to Face selection first; Apply assigns the chosen color only to the selected faces so different faces can keep different material colors.

The desktop sidebar uses Blender's normal color picker / hue wheel and also provides Shade Smooth / Flat.

## Mesh editing

Enter **Edit Mode** from the VR menu and choose one of the selection modes:

- **VERT** selects vertices.
- **EDGE** selects edges.
- **FACE** selects faces.

The main edit page includes Select, Move Sel, Scale Sel, Extrude, Bevel, Colors, Undo and More. More Edit contains Inset, Delete, Merge, Subdivide, Duplicate, Recalculate Normals, Flip Normals and Redo.

## Scene building and movement

Use **Shapes** to add cube, sphere, cylinder, cone, torus or plane meshes directly in VR. A placement preview appears before creation.

Use **Travel** for Fly/Walk, Turbo, Faster/Slower, Snap/Smooth turning and Reset View. The left stick controls movement and the right stick handles turning and vertical travel.

## Saving

Use **Save Blend** from the VR menu or desktop sidebar.

- Existing projects save to their current file.
- Unsaved projects default to a timestamped file in `Documents/BlenderXR` for backwards-compatible storage paths.
- A custom first-save path can be chosen before starting VR.
- Private XR Mesh session history snapshots are not stored in the `.blend` file.

## Experimental finger input

Finger-touch shortcuts and the optional SteamVR skeletal bridge remain experimental and are not required for standard controller use. The helper is launched outside Blender's Python process; the add-on itself stays free of `threading` and `queue`.

## Current limits

- One local editable mesh at a time for topology work.
- Shared/linked mesh data and shape-key meshes are rejected for topology edits.
- Editing operates on the base mesh cage, not evaluated modifier geometry.
- Scene Statistics reports base-mesh geometry rather than evaluated modifier output.
- VR Undo/Redo is session-local.
- VR color controls cover normal material color assignment, not full shader-node authoring.
- UV mapping, rigging and weight painting remain roadmap features.
- Physical headset/runtime behavior can vary even when automated Blender tests pass.

## Development

Build the extension with:

```sh
python scripts/build.py
```

The build verifies the manifest/version/package metadata, checks the public name/support URL, verifies the v0.5.6 runtime layer is enabled, and rejects packaged imports of `threading` or `queue`.

The GitHub test matrix validates XR Mesh against Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2, including a clean-profile install of the generated extension ZIP.

See [TESTING.md](TESTING.md) for validation details and [ROADMAP.md](ROADMAP.md) for upcoming features.

Independent project by Ded Zed. Not affiliated with the Blender Foundation, Freebird XR or the earlier MARUI BlenderXR project.
