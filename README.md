# Mesh XR v0.7.5

**Free VR mesh modeling and scene building inside Blender, by Ded Zed.**

Mesh XR adds a controller-first OpenXR modeling workflow to Blender. One hand carries a compact tool menu while the other points, selects, edits, transforms, places primitives, manages materials and textures, edits UVs, and moves around the scene.

[Latest Release](https://github.com/dedzedofficial/Blender-XR/releases/latest) · [Blender Extensions](https://extensions.blender.org/add-ons/blender-xr/) · [Report Issues](https://github.com/dedzedofficial/Blender-XR/issues) · [Icon Guide](ICON_GUIDE.md) · [Roadmap](ROADMAP.md) · [Changelog](CHANGELOG.md) · [Testing](TESTING.md)

## v0.7.5 development highlights

- **PC View Mode:** Toggle the active desktop 3D View between the normal Blender viewport and the live OpenXR headset mirror, without ending the VR session. Requires Blender's `mirror_xr_session` viewport support.
- **Precision Snap:** Optional controller-driven move/tool quantization using the configured tool step.
- **Two-handed object scaling:** Grab an object with one controller, grab it with the other, then move your hands apart or together to scale it. Releasing either grip commits the change to XR Undo/Redo. The pivot math is regression-tested.
- **Optional haptic feedback:** Short controller pulses after completed geometry edits and object transforms when enabled and supported by the OpenXR runtime.
- **Rigging starter workflow:** Create a proportion-based humanoid armature, bind selected meshes with Blender automatic weights, enter Weight Paint, and normalize/clean groups. Failed setup steps restore the original selection and report the error.
- **Asset readiness audit:** Read-only report for non-manifold/boundary edges, loose geometry, degenerate faces, UV availability, material slots, source and modifier-evaluated triangle counts, with a configurable budget checked against the evaluated mesh.
- **Workflow workspace:** A collapsible Mesh XR Workflow panel groups asset checks, rigging, weight painting and controller-modeling guidance.

## v0.7.1 highlights

- **Object Tools:** Rotate objects in 15° increments around world X/Y/Z, reset world rotation, snap to the current step grid, and duplicate local objects with XR Undo/Redo.
- **Geometry Tools:** Rotate selected vertices, edges or faces around their selection center on local X/Y/Z; dissolve geometry, fill boundary holes, bridge selected edge loops and recalculate normals.
- **Modifiers:** Add and manage Mesh XR Mirror (X/Y/Z), Array and Solidify modifiers. Adjust Array count or Solidify thickness, toggle viewport display and remove the most recently managed modifier, with XR-local Undo/Redo.
- **Undo improvements:** UV projection/transform/seam edits and selected-face material-slot assignment now use mesh snapshots for XR-local Undo/Redo.
- **Reliability:** Safer material deletion, explicit quad-ring validation, tracking-loss tooltip cleanup and full Blender version matrix gating for releases.
- **Blender Extensions:** Verified new versions are submitted through the official API. Updates on users' computers remain managed by Blender's built-in Extensions preferences.

Open **Mode > Object Tools** in Object Mode, **More Edit > Geometry Tools** in Edit Mode, or **Object Tools > Modifiers** for the new commands.

## v0.6.5 highlights

v0.6.5 introduced a modeling and usability update built on the complete v0.6 Materials + UV workflow and the v0.6.4 Blender Extensions packaging fixes.

- Replaces long main-toolbar labels with a compact **icon-first VR interface**.
- Adds **raycast hover highlighting** plus delayed tooltips with the tool name and explanation.
- Adds a Blender-style **Object Mode / Edit Mode selector** at the start of the toolbar.
- Keeps dedicated **Vertex / Edge / Face** selection icons in Edit Mode.
- Restores **Inset Faces** directly to the main Edit toolbar.
- Adds **Loop Cut** with quad-ring detection, orange preview, 1–16 cuts and adjustable single-cut position.
- Adds a dedicated **Delete Object** operation in Object Mode while keeping **Delete Geometry** separate in Edit Mode.
- Loop Cut and Delete Object participate in Mesh XR session Undo/Redo.
- Includes `ICON_GUIDE.md` with an icon-by-icon explanation of the current VR controls.
- Retains the bundled verified `openvr==2.12.1401` wheel required by the optional SteamVR skeletal hand bridge.

## Launch

Mesh XR can be started from either:

- **3D Viewport > Sidebar (`N`) > Mesh XR > Start VR**
- **3D Viewport > View > Start Mesh XR**

Blender's separate **VR Scene Inspection** extension provides Blender's own Start VR Session control; Mesh XR does not remove or replace it.

## VR interface

The main Object/Edit controls use pictogram icons so the interface is easier to understand without relying on language-specific button text.

Point the menu ray at an icon to highlight it. Keep the ray on that control for roughly half a second to show its tool name and short explanation.

The first control switches between **Object Mode** and **Edit Mode**. Edit Mode then exposes **Vertex**, **Edge** and **Face** selection directly.

See [ICON_GUIDE.md](ICON_GUIDE.md) for the current icon and tooltip reference.

## Core modeling features

- Vertex, edge and face selection in VR.
- Add/remove from the selection with grip + trigger.
- Move and scale selected vertices, edges and faces.
- Extrude vertices, edges and faces.
- Bevel vertex/edge selections and face boundaries.
- Inset selected faces.
- Loop Cut across valid continuous quad rings with preview and configurable cut count.
- Delete selected geometry without confusing it with whole-object deletion.
- Delete whole mesh objects from Object Mode with Undo/Redo support.
- Merge, subdivide and duplicate selected geometry.
- Recalculate and flip face normals.
- Object movement and uniform scaling.
- Distance-aware X/Y/Z and Size gizmos.
- Primitive placement: cube, sphere, cylinder, cone, torus and plane.
- Full-scene flight, snap/smooth turning and grab-air navigation.
- Session Undo / Redo and Save Blend from VR.

## Materials, colors and textures

Open **Materials** from Object Mode or Edit Mode. The headset hub provides Base Color/HSL, material properties, material slots, textures, UV tools and Material Preview.

The color page keeps the full-width **Hue**, **Saturation** and **Lightness** sliders, Pick/Apply controls, White/Black lightness shortcuts and optional color presets. In Edit Mode, Face selection allows different faces on one mesh to retain different materials/colors.

Material tools include:

- Create, duplicate and delete materials in VR.
- Auto-name materials in VR or enter a custom name from the desktop panel.
- Add/remove/cycle material slots.
- Assign the active slot to selected faces or select faces that use the active slot.
- Base Color, Metallic, Roughness, Alpha and Emission controls.
- Load an image from disk on desktop, then cycle/apply available Blender images in VR.
- Clear the managed image texture without deleting the Blender image datablock.
- Built-in numbered checker, directional and color-grid diagnostics.

Generated diagnostic images are packed into the `.blend` so they are self-contained.

## UV mapping

UV tools operate on selected mesh faces in Edit Mode:

- Unwrap, Smart Project, Cube Project and Planar Project.
- Mark and Clear seams.
- Move U/V, rotate and scale UVs.
- Reset UVs and Pack Islands.
- Open a compact VR UV wireframe preview.

Mesh XR uses Blender's native UV operators where their context is available and falls back to deterministic projection/packing behavior where needed, including restricted/background contexts.

The desktop **UV Mapping** panel exposes the same practical operations with buttons and an adjustable UV move step.

## Mesh editing

Switch to **Edit Mode** from the mode icon and choose **VERT**, **EDGE** or **FACE**.

The primary edit toolbar exposes selection, Move Selection, Scale Selection, Extrude, Bevel, Inset Faces and Materials. Secondary commands such as Loop Cut, Delete Geometry, Merge, Subdivide, Duplicate, normals tools and Redo remain grouped where appropriate to keep the main toolbar compact.

Loop Cut detects a continuous quad edge ring from the selected edge. The ring is previewed in orange before applying. You can choose 1–16 cuts; a single cut can be positioned from 5% to 95% in 5% steps, while multiple cuts are evenly distributed. Invalid/non-quad rings are rejected instead of applying an unpredictable cut.

## Scene building and movement

Use **Shapes** to add cube, sphere, cylinder, cone, torus or plane meshes directly in VR. A placement preview appears before creation.

Object Mode includes a dedicated **Delete Object** action. This is intentionally separate from Edit Mode's Delete Geometry operation.

Use **Travel** for Fly/Walk, Turbo, Faster/Slower, Snap/Smooth turning and Reset View. The left stick controls movement and the right stick handles turning and vertical travel.

## Saving

Use **Save Blend** from the VR menu or desktop sidebar.

- Existing projects save to their current file.
- Unsaved projects default to a timestamped file in `Documents/BlenderXR` for backwards-compatible storage paths.
- A custom first-save path can be chosen before starting VR.
- Private Mesh XR session-history snapshots are not stored in the `.blend` file.

## Install

### Blender Extensions

Install/update Mesh XR from the official Blender Extensions listing:

https://extensions.blender.org/add-ons/blender-xr/

### GitHub package

1. Open [Latest Releases](https://github.com/dedzedofficial/Blender-XR/releases/latest).
2. Download `mesh-xr-v0.7.1.zip`.
3. In Blender open **Edit > Preferences > Add-ons / Extensions**.
4. Choose **Install from Disk** and select the ZIP.
5. Enable **Mesh XR**.
6. In the 3D Viewport press **N** and open the **Mesh XR** tab, or open the **View** menu.
7. Pick your dominant hand and press **Start VR**.

The extension is free, open source and licensed under **GPL-3.0-or-later**.

## Requirements

- Blender **4.2+** with OpenXR support.
- PCVR-capable hardware.
- Two tracked controllers for the standard controller workflow.
- One active OpenXR runtime.

Automated validation covers Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**. Blender 5.0.1 remains blocked because of its known VR crash.

## Experimental finger input

Finger-touch shortcuts and the optional SteamVR skeletal bridge remain experimental and are not required for standard controller use. Standard controller operation does not depend on OpenVR.

Mesh XR ships the required OpenVR Python wheel inside the Blender Extension package. The helper runs as a separate system-Python process so SteamVR polling remains outside Blender's Python process, while reusing the dependency installed with Mesh XR. The add-on itself remains free of `threading` and `queue`.

## Current limits

- Loop Cut currently requires a valid continuous quad ring.
- One local editable mesh at a time for topology work.
- Shared/linked mesh data and shape-key meshes are rejected for topology edits.
- Editing operates on the base mesh cage, not evaluated modifier geometry.
- Scene Statistics reports base-mesh geometry rather than evaluated modifier output.
- VR Undo/Redo is session-local. UV operations, slot assignments, mesh changes, transforms, duplication and Mesh XR-managed modifier changes are tracked; not every material or texture edit has its own history entry.
- Texture management currently targets a practical single Base Color image workflow rather than arbitrary shader-node authoring.
- Custom text naming and browsing arbitrary files use Blender's desktop dialogs; VR provides auto-name and image cycling instead.
- Rigging, weight painting, animation, full numeric transforms, direct controller edit manipulation and generic third-party modifier management remain future roadmap features.
- Physical headset/runtime behavior can vary even when automated Blender tests pass.

## Development

Build the extension with:

```sh
python scripts/build.py
```

The build verifies manifest/version/package metadata, Mesh XR branding, runtime/modeling layers, material/UV modules and menu routing, checks the pinned OpenVR wheel against its published SHA-256, verifies the wheel is present in the final ZIP, and rejects packaged imports of `threading` or `queue`.

The GitHub test matrix validates Mesh XR against Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2, including a clean-profile install of the generated extension ZIP, bundled OpenVR import, v0.6 material/UV regression coverage and v0.6.5 modeling/UI regression coverage.

See [TESTING.md](TESTING.md), [ROADMAP.md](ROADMAP.md), [ICON_GUIDE.md](ICON_GUIDE.md) and [CHANGELOG.md](CHANGELOG.md).

Independent project by Ded Zed. Not affiliated with the Blender Foundation, Freebird XR or the earlier MARUI BlenderXR project.
