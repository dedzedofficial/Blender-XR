# XR Mesh v0.6.0

v0.6.0 completes the public rename to **XR Mesh** while preserving the existing repository and extension identifiers for compatibility.

## Public name and extension metadata

- Renames the user-facing extension from **Blender XR** to **XR Mesh**.
- Keeps the repository at `dedzedofficial/Blender-XR` and the extension ID as `blender_xr` so existing links and update paths continue to work.
- Uses the public GitHub Issues tracker for Report Issues / Support.
- Updates the Blender sidebar, native View menu, in-headset menu header, release titles and documentation to use XR Mesh consistently.
- Adds build checks so the manifest, packaged README, Blender panel and in-headset branding cannot silently drift apart again.

## Blender Extensions compliance

- Keeps the add-on free of Python `threading` and `queue`; the build rejects either import if introduced later.
- The optional SteamVR hand helper remains on the existing subprocess/loopback-socket path.
- Extension updates continue through Blender Extensions rather than a custom updater.

## VR editing and colors

The v0.5.6 modeling and color workflow remains available in v0.6.0:

- Vertex / edge / face selection and additive selection.
- Move and scale the current geometry selection.
- Extrude, bevel, inset, delete, merge, subdivide and duplicate.
- Recalculate / flip normals.
- Whole-object movement and scaling.
- Distance-aware X/Y/Z and Size gizmos.
- Six VR primitives and session Undo / Redo.
- Full Hue / Saturation / Lightness controls in VR with continuous dragging, Pick and Apply.
- Per-face material assignment so different faces on one mesh can keep different colors.
- Desktop color picker and Shade Smooth / Flat controls.
- Fly/Walk movement, turbo, snap/smooth turning and grab-air navigation.
- Save Blend with session-local history kept out of saved projects.

## Compatibility

Automated validation targets Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**. Blender 5.0.1 remains blocked because of its known VR crash.
