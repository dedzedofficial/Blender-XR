# XR Mesh v0.6.1

**Free VR mesh modeling and scene building inside Blender, by Ded Zed.**

XR Mesh adds a controller-first OpenXR modeling workflow to Blender. One hand carries a compact tool menu while the other points, selects, edits, transforms, places primitives, manages materials and textures, edits UVs, and moves around the scene.

[Latest Release](https://github.com/dedzedofficial/Blender-XR/releases/latest) · [Report Issues](https://github.com/dedzedofficial/Blender-XR/issues) · [Roadmap](ROADMAP.md) · [Changelog](CHANGELOG.md) · [Testing](TESTING.md)

## v0.6.1 highlights

v0.6.1 completes the planned v0.6 **Materials + UV mapping** milestone.

- Material hub in VR plus advanced desktop material/texture controls.
- Create, duplicate, delete and rename materials; manage material slots and selected-face assignments.
- Principled Base Color, Metallic, Roughness, Alpha and Emission controls.
- Load/cycle/apply/clear texture images.
- Built-in numbered checker, directional UV and color-grid diagnostic textures.
- UV Unwrap, Smart Project, Cube and Planar projection.
- Mark/Clear seams; move, rotate and scale UVs; Reset and Pack Islands.
- Compact in-headset UV wireframe preview and Material Preview toggle.
- Dedicated regression coverage for the full v0.6 workflow across Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2.

The v0.6.0 Blender Extensions compliance changes remain in place: the public name is **XR Mesh**, support links to GitHub Issues, updater/funding UI is removed, and the packaged add-on contains no `threading` or `queue` imports.

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
- Clear the XR Mesh image texture without deleting the Blender image datablock.
- Built-in numbered checker, directional and color-grid diagnostics.

Generated diagnostic images are packed into the `.blend` so they are self-contained.

## UV mapping

UV tools operate on selected mesh faces in Edit Mode:

- Unwrap, Smart Project, Cube Project and Planar Project.
- Mark and Clear seams.
- Move U/V, rotate and scale UVs.
- Reset UVs and Pack Islands.
- Open a compact VR UV wireframe preview.

XR Mesh uses Blender's native UV operators where their context is available and falls back to deterministic projection/packing behavior where needed, including restricted/background contexts.

The desktop **UV Mapping** panel exposes the same practical operations with buttons and an adjustable UV move step.

## Mesh editing

Enter **Edit Mode** from the VR menu and choose **VERT**, **EDGE** or **FACE**. The main edit page includes Select, Move Sel, Scale Sel, Extrude, Bevel, Materials, Undo and More. More Edit contains Inset, Delete, Merge, Subdivide, Duplicate, Recalculate Normals, Flip Normals and Redo.

## Scene building and movement

Use **Shapes** to add cube, sphere, cylinder, cone, torus or plane meshes directly in VR. A placement preview appears before creation.

Use **Travel** for Fly/Walk, Turbo, Faster/Slower, Snap/Smooth turning and Reset View. The left stick controls movement and the right stick handles turning and vertical travel.

## Saving

Use **Save Blend** from the VR menu or desktop sidebar.

- Existing projects save to their current file.
- Unsaved projects default to a timestamped file in `Documents/BlenderXR` for backwards-compatible storage paths.
- A custom first-save path can be chosen before starting VR.
- Private XR Mesh session-history snapshots are not stored in the `.blend` file.

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

## Experimental finger input

Finger-touch shortcuts and the optional SteamVR skeletal bridge remain experimental and are not required for standard controller use. The helper is launched outside Blender's Python process; the add-on itself stays free of `threading` and `queue`.

## Current limits

- One local editable mesh at a time for topology work.
- Shared/linked mesh data and shape-key meshes are rejected for topology edits.
- Editing operates on the base mesh cage, not evaluated modifier geometry.
- Scene Statistics reports base-mesh geometry rather than evaluated modifier output.
- VR Undo/Redo is session-local; not every material/UV operation is currently part of that lightweight history.
- Texture management currently targets a practical single Base Color image workflow rather than arbitrary shader-node authoring.
- Custom text naming and browsing arbitrary files use Blender's desktop dialogs; VR provides auto-name and image cycling instead.
- Rigging, weight painting, animation and advanced modifier workflows remain future roadmap features.
- Physical headset/runtime behavior can vary even when automated Blender tests pass.

## Development

Build the extension with:

```sh
python scripts/build.py
```

The build verifies manifest/version/package metadata, public name/support URL, the v0.5.6 and v0.6 runtime layers, the material/UV modules and menu routing, and rejects packaged imports of `threading` or `queue`.

The GitHub test matrix validates XR Mesh against Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2, including a clean-profile install of the generated extension ZIP and the complete v0.6 material/UV regression suite.

See [TESTING.md](TESTING.md), [ROADMAP.md](ROADMAP.md) and [CHANGELOG.md](CHANGELOG.md).

Independent project by Ded Zed. Not affiliated with the Blender Foundation, Freebird XR or the earlier MARUI BlenderXR project.
