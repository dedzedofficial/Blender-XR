# XR Mesh v0.6.0

v0.6.0 is the Blender Extensions review/compliance release and also fixes one runtime wiring issue found during the audit.

## Blender Extensions review changes

- Public extension name changed from **Blender XR** to **XR Mesh**.
- The manifest Support/Report Issues link now points directly to the public GitHub Issues tracker.
- Removed the in-extension **Updates** box. Updates are handled by Blender Extensions rather than by the add-on.
- Removed the in-extension Patreon/funding controls from the add-on UI.
- The extension contains no Python `threading` or `queue` imports.
- The build now parses every packaged Python file and fails if `threading` or `queue` is introduced later.
- The existing SteamVR hand-helper command remains on the supported `subprocess` path and communicates with the add-on through the existing authenticated loopback-only socket bridge.

## Runtime fix

- The v0.5.6 runtime patch is now applied during normal add-on startup after the base v0.5 runtime patch.
- This makes the already-shipped **Hue / Saturation / Lightness sliders**, continuous trigger dragging, selected-geometry Move/Scale workflow and face-color history active in the normal installed extension rather than only when the v0.5.6 module is imported directly by tests.

## Existing v0.5.6 features retained

- Vertex / edge / face VR selection and additive grip+trigger selection.
- Move/Scale Selected, extrude, bevel, inset, delete, merge, subdivide and duplicate.
- Recalculate / flip normals.
- Whole-object movement and uniform scaling.
- Distance-aware X/Y/Z and Size gizmos.
- Six VR primitives and creation Undo / Redo.
- Fly/Walk movement, turbo, snap/smooth turning and grab-air navigation.
- Save Blend with in-memory session history excluded from saved projects.
- HSL color controls, material Pick/Apply and per-face material assignment.
- Desktop material color picker, shared-material copy protection and Shade Smooth / Flat.
- Cached scene/object statistics.
- Persistent controller, movement, modeling and UI preferences.
- Native desktop launch paths from the **XR Mesh** sidebar and the 3D Viewport View menu.
- Blender 5.2-safe deferred preference restore when Scene writes are forbidden during UI drawing.

## Compatibility

Automated validation targets Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**. Blender 5.0.1 remains blocked because of its known VR crash.
