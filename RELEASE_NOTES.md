# Mesh XR v0.6.5

v0.6.5 is a modeling and usability update that builds on the completed Materials + UV workflow and the Blender Extensions packaging fixes from v0.6.4.

## Icon-first VR interface

- Replaces long primary Object/Edit toolbar labels with compact pictogram icons.
- Adds immediate raycast hover highlighting.
- Adds delayed hover tooltips with the tool name and a short explanation.
- Adds a Blender-style Object Mode / Edit Mode selector as the first primary toolbar control.
- Keeps dedicated Vertex, Edge and Face selection icons in Edit Mode.
- Restores Inset Faces directly to the main Edit toolbar.
- Keeps secondary modeling commands grouped so the main toolbar remains compact.
- Includes `ICON_GUIDE.md` with an icon-by-icon usage reference.

## Loop Cut

- Adds Loop Cut for valid continuous quad edge rings.
- The detected ring is previewed in orange before applying the operation.
- Supports 1–16 cuts.
- A single cut can be positioned from 5% to 95% in 5% steps.
- Multiple cuts are evenly distributed.
- Invalid/non-quad rings are rejected cleanly instead of producing an unpredictable result.
- Loop Cut participates in Mesh XR session-local Undo/Redo.

## Delete Object

- Adds a dedicated Delete Object operation in Object Mode.
- Keeps Edit Mode Delete Geometry as a separate operation so selected mesh elements cannot accidentally remove the whole object.
- Deleted mesh objects can be restored with Mesh XR Undo and removed again with Redo.

## Existing v0.6 workflow retained

Mesh XR continues to include:

- Vertex, edge and face selection/editing.
- Move/Scale Selection, Extrude, Bevel, Inset, Merge, Subdivide, Duplicate and normals tools.
- HSL and per-face color workflows.
- Material creation, duplication, deletion, slots and Principled controls.
- Texture image loading/cycling plus built-in diagnostic textures.
- UV Unwrap, Smart/Cube/Planar projection, seams, transform tools, Pack Islands and VR UV preview.
- Object movement/scaling, primitives, travel/navigation, Save Blend and session Undo/Redo.

## Blender Extensions compatibility

- Keeps the stable `blender_xr` extension ID and operator namespace for install/update compatibility.
- Bundles `openvr==2.12.1401` as the declared platform-independent Python wheel required by the optional SteamVR skeletal hand bridge.
- Verifies the upstream wheel SHA-256 before packaging.
- Keeps SteamVR polling in the external helper process.
- Contains no packaged Python `threading` or `queue` imports.
- Contains no in-extension updater; updates are managed through Blender Extensions.

## Validation

- Automated validation covers Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2.
- Release validation runs the v0.6 Materials/UV and v0.6.5 modeling/UI regression coverage before publishing.
- Clean-profile installation checks verify the generated extension package and bundled OpenVR dependency.
- Blender 5.0.1 remains blocked because of its known VR crash.

## Compatibility

Requires Blender 4.2+ with OpenXR support. Standard controller operation does not depend on OpenVR; the bundled OpenVR wheel is used only by the optional experimental SteamVR skeletal hand bridge.

See `README.md` for installation/use, `ICON_GUIDE.md` for the current VR controls, `CHANGELOG.md` for shipped history, `ROADMAP.md` for future work and `TESTING.md` for validation coverage.
