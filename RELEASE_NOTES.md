# Blender XR v0.5.6

v0.5.6 completes the headset-side edit/color workflow and closes several version/UI gaps found while auditing every previously shipped update.

## Edit Mode fixes

- Renamed the VR edit transforms to **Move Sel** and **Scale Sel** so they clearly operate on the current vertex/edge/face selection rather than the whole object.
- Keeps Object Mode **Scale** as a separate whole-object uniform scale tool.
- Adds **Undo** directly to the main Edit page and **Redo** to More Edit so mesh edits can be corrected without leaving Edit Mode.
- Keeps vertex, edge and face selection, additive grip+trigger selection, extrusion, bevel, inset, delete, merge, subdivide, duplicate and normal tools intact.

## VR colors

- Adds **Colors** to both Object Mode and Edit Mode VR menus.
- Adds quick Red, Orange, Yellow, Green, Cyan, Blue, Purple and Pink presets.
- Adds **Pick** and **Apply** directly in VR.
- Adds an **Adjust** page with hue, saturation and brightness controls plus White and Black.
- Object Mode Apply recolors the active object's material.
- Edit Mode Apply requires Face selection and assigns the chosen color only to the selected faces.
- Edit-mode face color assignment is stored in Blender XR's session-local Undo / Redo history.
- Keeps the existing desktop Blender hue-wheel picker, per-face material assignment, material-slot reuse and Shade Smooth / Flat controls.

## Version and package consistency

- Adds a shared Python version source for v0.5.6.
- The Blender add-on metadata, sidebar title and in-headset footer now all report v0.5.6 from that shared source.
- Replaces the stale packaged README that still identified itself as v0.5.3.
- The build now fails if the manifest, Python version source, sidebar metadata, VR version source or packaged README drift apart again.

## Previous-update audit

The v0.5.6 audit confirmed that the following previously released systems remain present and covered:

- Vertex / edge / face VR selection and additive selection.
- Selected-geometry move, scale, extrude, bevel, inset, delete, merge, subdivide and duplicate.
- Recalculate / flip normals.
- Whole-object movement and uniform scaling.
- Distance-aware X/Y/Z and Size gizmos.
- Six VR primitives and creation Undo / Redo.
- Fly/Walk movement, turbo, snap/smooth turning and grab-air navigation.
- Save Blend with in-memory local history snapshots excluded from saved projects.
- Desktop material color picker, shared-material copy protection, selected-face material assignment and shading controls.
- Cached scene/object statistics.
- Persistent controller, movement, modeling and UI preferences.
- Native Blender launch paths from the Blender XR sidebar and the 3D Viewport View menu.
- Blender 5.2-safe deferred preference restore when Scene writes are forbidden during UI drawing.
- Clean-profile installation/enablement testing of the actual built extension ZIP.
- Patreon/website links and the experimental finger-input paths.

## Compatibility

Automated validation targets Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**. Blender 5.0.1 remains blocked because of its known VR crash.
