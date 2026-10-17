# Mesh XR changelog

This file records shipped user-facing changes. Planned work belongs in [ROADMAP.md](ROADMAP.md).

## v0.6.5 — modeling tools + icon-first VR UI

### Added

- Icon-first Object/Edit VR toolbars designed to reduce reliance on language-specific labels.
- Raycast hover highlighting plus delayed tooltips that show a tool name and short explanation.
- Blender-style Object Mode / Edit Mode selector as the first primary toolbar control.
- Dedicated Vertex / Edge / Face selection icons in Edit Mode.
- Loop Cut with continuous quad-ring detection, orange preview, 1–16 cuts and adjustable single-cut position.
- Dedicated Object Mode **Delete Object** command, separate from Edit Mode **Delete Geometry**.
- `ICON_GUIDE.md` documenting the current icon set, hover behavior and controls.
- v0.6.5 automated modeling/UI regression coverage in CI and release validation.

### Changed

- Restored **Inset Faces** directly to the primary Edit toolbar.
- Kept secondary modeling operations under More Edit so the main toolbar remains compact.
- Updated current documentation and release notes to Mesh XR v0.6.5.

### Safety / Undo

- Loop Cut rejects invalid/non-quad edge rings instead of applying an unpredictable cut.
- Loop Cut participates in Mesh XR session-local Undo/Redo.
- Deleted mesh objects can be restored with Mesh XR Undo and removed again with Redo.
- Whole-object deletion and selected-geometry deletion remain intentionally separate operations.

## v0.6.4 — Blender Extensions packaging + Mesh XR naming

### Added

- Bundled `openvr==2.12.1401` as Blender Extension wheel metadata for the optional SteamVR skeletal hand bridge.
- Build-time download of the unchanged upstream PyPI wheel with the published SHA-256 pinned and verified before packaging.
- Package validation that fails if the declared OpenVR wheel is absent from the final extension ZIP.
- Clean-profile CI coverage that imports the bundled `openvr` module after installing the generated extension package.

### Changed

- Current extension/add-on branding changed from **XR Mesh** to **Mesh XR**.
- Kept the stable `blender_xr` extension ID and operator namespace for compatibility with the existing Blender Extensions entry and saved workflows.
- SteamVR hand-helper startup now relaunches the external helper with the extension's installed `site-packages` supplied through `PYTHONPATH`, without modifying Blender's module search path.
- Release archives and GitHub workflow/artifact naming now use `mesh-xr-v<version>.zip` / Mesh XR branding.

### Fixed

- Removed the hand helper's manual `pip install openvr` requirement.
- Fixed Blender Extensions review failure caused by importing a Python library that was not shipped with the extension.

## v0.6.1 — Materials + UV mapping

### Added

- VR Materials hub with dedicated material properties, slots, textures and UV pages.
- Material create, duplicate, delete and VR auto-name controls.
- Desktop custom material rename dialog.
- Material slot add/remove/cycle, selected-face assignment and select-faces-by-slot.
- Principled Base Color, Metallic, Roughness, Alpha and Emission controls.
- Desktop texture-image file loading plus VR image cycling/apply/clear.
- Built-in numbered checker, directional UV and color-grid diagnostic textures.
- UV Unwrap, Smart Project, Cube Project and Planar Project.
- Mark/Clear seams.
- UV U/V movement, rotation and scale.
- Reset UVs and Pack Islands.
- Compact in-headset UV wireframe preview.
- Material Preview toggle.
- Desktop Advanced Materials + Textures and UV Mapping panels.
- Dedicated v0.6 automated regression suite on Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2.

### Changed

- Main Object/Edit VR pages now route through the Materials hub; the existing HSL color workflow remains available inside it.
- Material/UV code is split into focused `material_uv.py`, `uv_tools.py` and `v060.py` modules.
- Extension file permission text now explicitly covers loading texture images as well as saving Blender projects.
- Build validation requires the v0.6 modules/runtime wiring and menu routes to remain packaged.

### Fixed

- Fixed a cross-version UV transform failure caused by accumulating 2D UV coordinates into a default 3D vector.
- Updated older v0.5.6 regression expectations to remain valid under the v0.6 Materials hub.

## v0.6.0 — Blender Extensions compliance + runtime wiring

### Changed

- Public extension name changed from **Blender XR** to **XR Mesh** while retaining the internal `blender_xr` extension/operator identifiers for compatibility.
- Support/Report Issues now points to the public GitHub Issues tracker.
- Removed the in-extension updater/update panel and funding UI; updates are managed by Blender Extensions.
- Build validation rejects packaged `threading` and `queue` imports.
- GitHub release/workflow branding changed to XR Mesh.

### Fixed

- Activated the v0.5.6 runtime patch during normal startup, making the shipped HSL sliders, continuous dragging, selected Move/Scale and per-face color history active in installed builds.

## v0.5.6 — HSL and selected-edit workflow

- Added full-width Hue, Saturation and Lightness controls in VR.
- Added continuous trigger dragging, Pick/Apply and optional color presets.
- Added selected-face material color history without topology snapshots.
- Clarified Move Sel and Scale Sel behavior and kept Object Mode scale separate.
- Added Edit-page Undo and More Edit Redo.
- Standardized version/package checks.

## v0.5.3 — Cleanup + foundations

- Reorganized the Materials/sidebar workflow and cached Scene Statistics.
- Persisted controller, movement, modeling and UI preferences.
- Split material, selection, transform, mode, status and menu responsibilities into focused modules while retaining compatibility wrappers.

## v0.5.2 — Colors + statistics

- Added Blender color picker integration, whole-object color application and selected-face material assignment.
- Added material reuse/shared-material protection, Shade Smooth/Flat and scene/object statistics.

## v0.5.0 — Vertex/edge/face modeling

- Added VR Vertex, Edge and Face selection modes and additive selection.
- Added selected-geometry Move/Scale, Extrude, Bevel, Inset, Delete, Merge, Subdivide, Duplicate and normals operations.
- Added edit-selection feedback and multi-version regression coverage.

## v0.4.x — Navigation, primitives, saving and compatibility

- Added Meta/Valve controller targets and experimental finger-input paths.
- Added primitives, flight/walk, turbo, snap/smooth turning, grab-air navigation and mesh switching.
- Added Save Blend, Blender 4.2+ support and axis/size handles.
- Added whole-object and selected-face movement/scaling and deletion.
- Earlier self-update code/UI existed during this development line; it was removed in v0.6.0 for Blender Extensions compliance.

## v0.3.0 — Initial VR editing

- Initial installable VR mesh-editing workflow with controller menu, object/face selection, Extrude/Bevel/Inset, object grab, additive face selection, cancellation, local Undo/Redo and basic viewer movement.
