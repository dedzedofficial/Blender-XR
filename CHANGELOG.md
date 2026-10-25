# Mesh XR changelog

## v0.8.0 — alpha cross-platform follow-up

- Extended Blender extension manifest to all five desktop platform tags: Windows x64/ARM64, macOS Intel/ARM64, Linux x64.
- Added OS-aware XR support diagnostics to the Session UI and Start VR operator, with Blender 5.1+ macOS experimental XR gate and Intel Mac version guidance.
- Added cross-platform packaging/unit/ZIP integrity regression checks on native Windows/macOS CI hosts, retaining Blender 4.2/4.5/5.0/5.2 Linux CI matrix.
- Separated headset/runtime support from add-on installability; mobile iOS/iPadOS and standalone Android/Quest are **not** native Blender extension hosts. Documented an optional secure desktop companion route.

## v0.8.0 — alpha 1 (development, Quest 3 physical testing outstanding)

### Input and menu
- Implemented an eight-direction thumbstick radial menu driven **entirely by the non-dominant hand**. Hold that hand's Trigger, tilt its thumbstick to choose, recenter to cancel, release Trigger to apply. Recenter on a highlighted menu category to enter its submenu without dropping the Trigger.
- Added center/deadzone hysteresis, paging and a capture path that temporarily stops locomotion, turning and modelling actions while the menu is open.
- Retained the classic controller-ray menu for users who prefer it and as a fallback when thumbstick input is unavailable or the SteamVR hand-only bridge is active.

### 3D hands and skeletal data
- Added lightweight, non-scene 3D XR hand geometry (palm, wrist, thumb and articulated fingers) drawn with Blender's XR GPU overlay rather than the old controller markers; hand size is configurable.
- Trigger and Grip animate **estimated** finger curls on ordinary Touch controllers. This is not optical individual-joint hand tracking.
- Updated the authenticated, loopback-only SteamVR skeletal bridge to version 2 with independent five-finger curl readings and 26 local joint positions per hand when supplied by compatible hardware. Version 1 pinch/curl packets remain supported.
- Added tracking-data size/sequence/finite-value validation and stale-packet cleanup. Animated hand fingers use v2 individual curls when available.
- Added preference options for animated Hands, Native controllers, Pointers only, radial/classic menus, and adjustable hand scale.

### Quality and compatibility
- Added radial 8-way input unit tests including deadzones, boundary hysteresis, submenu recentering, cancellation, one-time selection and paging.
- Added Blender-based hand-geometry/add-on-settings regression tests, plus SteamVR v2 protocol validation and original modelling/rigging tests.
- CI succeeded on Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2** and built a valid installable extension ZIP in [run #40204941450](https://github.com/dedzedofficial/Blender-XR/actions/runs/40204941450).

**Limitations:** Physical Quest 3 PC-VR controller feel, stereo alignment, real tracking quality, optical hand input and radial selection comfort have not been verified. Full 0.8 modelling features (Isolation/X-Ray, Weight Eyedropper, direct IK posing, Curve Draw and Cleanup/Repair) are subsequent milestones, not yet shipped.

## v0.7.6 — Unified VR modelling, freeform armatures and native Weight Paint

*Compared with v0.7.5. Merged into `main` on 25 October 2026 via [PR #18](https://github.com/dedzedofficial/Blender-XR/pull/18); the [v0.7.6 GitHub release](https://github.com/dedzedofficial/Blender-XR/releases/tag/v0.7.6) and installer ZIP were published shortly afterward. Blender Extensions publication status has not been separately verified.*

### Blender-style VR selection and transforms

- Consolidated mesh and armature picking into **one context-sensitive Select tool**. Depending on Blender mode, it can select objects, mesh vertices/edges/faces, edit bones or pose bones. Removed redundant Select Mesh / Select Rig buttons.
- Improved controller-ray picking of armatures inside meshes and nearby or loose vertices and edges that may not intersect a polygon.
- Enabled controller **Grip** to grab and move selected geometry or objects, and **Trigger** with Move / Scale / Rotate tools to manipulate objects, vertices, edges, faces, armatures and bones.
- Added controller scale and rotation for edit bones, and a compact Pose Bones workspace with Select, Move, Scale, Rotate and Finish Pose.
- Extended session-local Undo/Redo to controller mesh-element, edit-bone and pose-bone transforms; cancelling a transform restores its original state.
- Preserved existing mesh Edit Mode operations, multi-selection and mesh-to-mesh switching.

### Freeform rigging and armature editing

- Replaced the proportion-restricted humanoid starter rig with normal Blender armatures that work with **any mesh shape**, including wide or flat models, and can be created without a mesh.
- Added Create Armature, Edit Bones, Add Bone and Finish Bones workflows; bones can be picked and manipulated using VR controllers.
- Exposed armature selection, parenting, extrusion, duplication, subdivision, symmetry, roll, visibility, naming and other native edit actions through organized tools and Blender's original menus.
- Remembered the relationship between an armature and its source mesh through Object, Edit, Pose and Weight Paint modes, without requiring redundant selection buttons.

### Weight Paint as a native Blender mode

- Added **Weight Paint** alongside Object and Edit in the standard headset **Mode** selector. Selecting it activates Blender's actual `WEIGHT_PAINT` mode and displays dedicated painting controls.
- Added controller-ray Paint / Erase on actual Blender vertex groups, including group switching and adjustable brush strength and radius.
- Improved painting on armature-deformed and low-poly meshes by using evaluated mesh hits when available, falling back to the nearest vertex where appropriate.
- Refreshes mesh data after painting and shows **NO SURFACE HIT** feedback when the controller misses the mesh, instead of appearing unresponsive.
- Automatically selects a valid active vertex group and supports independent mesh weight painting without silently changing parenting.
- Avoids resetting existing painted weights when binding again or adding bone-named groups.

### Blender-style parenting

- Added **Rigging → Parent** with standard Blender Ctrl+P options: Automatic Weights, Empty Groups, Envelope Weights, Armature Deform and Object Parent.
- Added **Clear Parent (Keep Transform)** and the same parenting controls in Blender's Model and Workflow panels.
- Prioritizes an explicitly selected mesh and armature over a previously remembered pairing; guards repeated parenting from overwriting painted weights.

### Interface and compatibility

- Redesigned the desktop Blender XR sidebar into seven compact icon-led workspaces: **Session, Model, Material, UV, Travel, Project and Help**.
- Added official Blender icon coverage, hover guidance and a fallback for headset icons that cannot be loaded.
- Kept advanced Materials, UV and Workflow controls available in collapsible panels without removing existing modelling functions.
- Expanded regression coverage for menu duplicates, selection, transformation, rig creation, mode switching, parenting, vertex weights, undo/redo and installable extension packaging.
- The final merge candidate passed CI packaging and Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2** in [workflow run #40147094901](https://github.com/dedzedofficial/Blender-XR/actions/runs/40147094901).

**Validation note:** Automated Blender tests and packaging passed. Real OpenXR headset ergonomics, controller ray accuracy and tracked-device painting behaviour cannot be established by those tests alone.

## v0.7.5 — PC View Mode (development)

- Added a PC View Mode toggle in the Mesh XR sidebar to switch the current 3D View between normal desktop display and Blender's live XR session mirror.
- Kept mirroring separate from session lifecycle: toggling the view does not start or stop the headset session.
- Disabled the control until Mesh XR's XR session is active and show a compatibility message when Blender does not expose the native mirror property.
- Added documentation and build validation for the mirror toggle.
- Added optional controller precision snapping based on the configured tool step.
- Added two-controller object scaling, with midpoint-aware scaling and XR-local Undo/Redo when either grip is released.
- Added optional OpenXR haptic pulses after completed geometry edits and object transforms, with safe fallback when unsupported.
- Added a read-only asset audit for topology health, UV availability, material slots, triangle count and modifiers, with a configurable triangle-budget warning.
- Distinguished open boundary edges from true non-manifold edges shared by three or more faces in audit reports.
- Used clearer humanoid starter-rig bone names and persisted the Precision Snap, Haptic Feedback and Triangle Budget settings.
- Added a starter humanoid armature workflow, automatic-weight binding, weight normalization/cleanup, and Weight Paint entry.
- Added separate source/evaluated triangle counts so the triangle budget accounts for viewport modifier output when available.
- Hardened rigging and weight-tool failure recovery, and improved XR shutdown cleanup so unexpected session termination restores the normal PC view.
- Added regression tests for evaluated modifier counts, two-hand scaling pivot math and failed rig creation state restoration.
- Added a collapsible Workflow panel that groups asset, rigging and controller-modeling tools.

## v0.7.1 — advanced modeling and release safety

- Added Object Tools for world-axis incremental rotation, snap-to-grid, reset rotation and reversible object duplication.
- Added Geometry Tools for selected geometry rotation, dissolve vertices/edges, fill holes, bridge loops and normals recalculation.
- Added Mesh XR-managed Mirror, Array and Solidify modifiers with adjustable settings and session-local history.
- Added XR-local Undo/Redo for UV actions and selected-face material-slot assignment.
- Fixed unsafe material-name access after deletion; improved quad-ring validation and controller-hover cleanup.
- Added v0.7.1 regression coverage; versioned the Blender extension at 0.7.1.
- Changed release automation to require the four-version validation matrix before publishing, stop force-moving release tags and avoid overwriting a published version.

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
