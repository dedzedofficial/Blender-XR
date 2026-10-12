# XR Mesh v0.6.1

v0.6.1 completes the planned **Materials + UV mapping** scope for v0.6 and keeps the Blender Extensions compliance work introduced in v0.6.0.

## Materials

- Added a dedicated headset **Materials** hub available from Object and Edit modes.
- Create, duplicate, delete and auto-rename materials from VR; custom-name materials from the desktop panel.
- Add, remove and cycle material slots.
- Assign the active material slot to selected faces and select faces that use the active slot.
- Edit Principled **Base Color, Metallic, Roughness, Alpha and Emission**.
- Toggle Material Preview from XR Mesh.
- Existing HSL color sliders, presets, Pick/Apply and lightweight per-face color history remain available from the Materials hub.

## Textures

- Load image textures from disk in the desktop panel.
- Cycle Blender images, apply the selected image to the active material and clear the XR Mesh image texture from VR.
- Added built-in **numbered checker**, **directional UV** and **color-grid** diagnostic textures.
- Generated diagnostic images are packed into the Blender project so they do not depend on external files.

## UV mapping

- Standard UV Unwrap.
- Smart UV Project.
- Cube projection.
- Planar projection.
- Mark and Clear seams.
- Move UVs on U/V, rotate and scale selected UV islands.
- Reset UVs and pack seam-delimited islands.
- Added a compact in-headset UV wireframe preview.
- Native Blender UV operators are used where their context is available; deterministic fallbacks keep the core workflow usable in restricted/background contexts.

## Desktop workflow

- Added collapsed **Advanced Materials + Textures** and **UV Mapping** panels under the XR Mesh sidebar.
- Desktop image loading and custom material naming complement the controller-first headset workflow where text/file dialogs are impractical.

## Quality and compatibility

- Split v0.6 logic into focused `material_uv.py`, `uv_tools.py` and `v060.py` modules rather than expanding the core runtime further.
- Added a dedicated v0.6 regression suite covering materials, slots, shader properties, textures, diagnostics, UV projection/editing and VR page routing.
- The normal CI matrix runs that suite on Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**.
- Release publishing is blocked unless the v0.6 suite passes on Blender 5.2.2.
- Build validation now checks that the v0.6 runtime layer and material/UV modules are packaged and still rejects `threading` or `queue` imports.
- Fixed a cross-version UV transform bug caused by mixing Blender's 2D UV vectors with a default 3D vector accumulator.
- Updated the file permission description to cover loading texture images as well as saving `.blend` projects.

## Blender Extensions compliance retained from v0.6.0

- Public extension name is **XR Mesh**.
- Support/Report Issues points directly to the public GitHub Issues tracker.
- No in-extension updater or funding controls.
- The add-on itself contains no Python `threading` or `queue` imports.
- The optional SteamVR hand helper stays external and uses the existing `subprocess`/authenticated loopback-socket path.

## Existing modeling workflow retained

Vertex/edge/face selection, Move/Scale Selected, extrude, bevel, inset, delete, merge, subdivide, duplicate, normals, whole-object movement/scaling, primitives, flight/navigation, save, session Undo/Redo, HSL colors, per-face colors, shading and scene statistics remain available.

## Compatibility

Automated validation targets Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**. Blender 5.0.1 remains blocked because of its known VR crash. Physical headset/runtime validation is still separate from background Blender automation.
