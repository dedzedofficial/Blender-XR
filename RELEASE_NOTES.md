# XR Mesh v0.5.6

v0.5.6 completes the headset-side edit/color workflow and closes several version/UI gaps found while auditing every previously shipped update.

## Edit Mode fixes

- Renamed the VR edit transforms to **Move Sel** and **Scale Sel** so they clearly operate on the current vertex/edge/face selection rather than the whole object.
- Keeps Object Mode **Scale** as a separate whole-object uniform scale tool.
- Adds **Undo** directly to the main Edit page and **Redo** to More Edit so mesh edits can be corrected without leaving Edit Mode.
- Keeps vertex, edge and face selection, additive grip+trigger selection, extrusion, bevel, inset, delete, merge, subdivide, duplicate and normal tools intact.

## VR colors

- **Colors now opens directly to three full-width HSL sliders: Hue, Saturation and Lightness.**
- Point anywhere on a slider and hold the trigger to drag it continuously.
- The Hue bar shows the full spectrum; Saturation and Lightness bars update from the currently selected HSL color.
- The headset shows the current H/S/L values alongside the live color swatch.
- **Pick** reads the active object material or the selected Edit Mode face color back into the sliders.
- **Apply** recolors the active object in Object Mode.
- In Edit Mode, **Apply requires Face selection and changes only the selected faces**, allowing different faces on the same mesh to keep different colors.
- Face-color changes remain in XR Mesh's lightweight session-local Undo / Redo history without creating temporary topology snapshots.
- Re-applying an unchanged face color does not waste an Undo history entry.
- White and Black change Lightness while retaining the selected Hue/Saturation, so moving Lightness back restores the chosen color family.
- Red, Orange, Yellow, Green, Cyan, Blue, Purple and Pink remain available on an optional **Presets** page.
- VR material changes invalidate cached scene statistics so material counts stay current.
- The existing desktop Blender hue-wheel picker, per-face material assignment, material-slot reuse and Shade Smooth / Flat controls remain available.

## Version and package consistency

- Adds a shared Python version source for v0.5.6.
- The Blender add-on metadata, XR Mesh sidebar title and in-headset footer all report v0.5.6 from that shared source.
- Replaces the stale packaged README that still identified itself as v0.5.3.
- The build fails if the manifest, Python version source, sidebar metadata, VR version source or packaged README drift apart again.

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
- Native Blender launch paths from the XR Mesh sidebar and the 3D Viewport View menu.
- Blender 5.2-safe deferred preference restore when Scene writes are forbidden during UI drawing.
- Clean-profile installation/enablement testing of the actual built extension ZIP.
- Patreon/website links and the experimental finger-input paths.

## Branding

- The user-facing software name is now **XR Mesh**.
- The existing `Blender-XR` repository, `blender_xr` extension ID and package filename are retained for update and install compatibility.

## Compatibility

Automated validation targets Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**. Blender 5.0.1 remains blocked because of its known VR crash.
