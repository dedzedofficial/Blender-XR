# Blender XR roadmap

Free Blender VR tools by Ded Zed. Versions describe scoped goals, not promises of complete Blender parity. There is no paid feature tier planned.

## v0.3.0: initial basic editing

Implemented:

- Installable Blender 5+ extension with GPL-3.0-or-later source.
- Left/right dominant-hand choice before starting VR.
- Tool menu attached to the non-dominant controller.
- Dominant-controller pointing, object selection, and face selection.
- Extrude, bevel, and inset with controller-driven distance previews.
- Move and rotate an unparented object using the dominant grip.
- Add/remove selected faces by gripping while selecting in face mode.
- Cancel a live operation with the other trigger.
- VR-local undo/redo for the latest 20 tool/move operations.
- Viewer movement with the non-dominant thumbstick and reset view.
- GitHub release check, checksum-verified download, installation rollback, and restart prompt.
- Automated geometry, cancellation, history, packaging, and updater tests.

## v0.4.0: Meta/Valve targets and optional fingers

Implemented:

- Automatic, Meta and Valve/SteamVR controller binding presets.
- Documented Quest, Rift, Index and conditional Steam Frame compatibility targets.
- Opt-in controller finger-touch hold for menu/cancel.
- Experimental external SteamVR skeletal bridge: pinch selection/tool use and finger-curl object grab.
- Loopback-only session-key protocol, bounded packet processing, input freshness and release-before-arming checks.
- Tracking loss cancels unfinished work; estimated skeletal data cannot drive finger tools.

## v0.4.1: fixing update

- Fixed the missing Event.timer access that interrupted the VR modal loop.
- Left thumbstick locomotion independent of dominant-hand choice.
- Either-hand grab-air translation.
- Hand-menu primitive picker and placement preview.
- Primitive creation with VR-local undo/redo.

## v0.4.2: flight and mesh switching

- Unbounded scene flight.
- Left-stick movement, right-stick turning/height and turbo flight.
- Tools, Shapes and Travel menu pages.
- Ray switching between meshes while editing.

## v0.4.3: startup fix, saving and Blender 4.2+

- Fixed unsupported BOOLEAN XR action types.
- Save Blend from the hand menu and desktop sidebar.
- Minimum Blender 4.2.0 with automated 4.2.0, 4.5.0, 5.0.0 and 5.2.2 coverage.

## v0.4.4: easier building

- Ray-picked XYZ movement and extrusion handles.
- Bevel/inset thickness handles.
- Delete selected faces with undo/redo.
- Whole-object scaling.
- Selected-face movement and scaling.
- Distance-aware transform handles.
- Cleaner VR menus with duplicate options removed.

## v0.4.7: UI polish + early v0.5 preview

- Reorganized the desktop sidebar.
- Simplified the hand-menu labels.
- Packaged whole-object scaling, face XYZ movement and face scaling as the first v0.5 preview.
- Added Patreon and Website buttons to the Blender sidebar.
- Preserved save, primitives, travel, editing and local history workflows.

## v0.5.0: vertex, edge and face modeling

Implemented for the v0.5.0 release:

- [x] Vertex, Edge and Face selection modes directly in VR.
- [x] Add/remove multi-selection using grip + trigger.
- [x] Move selected vertices, edges and faces with XYZ gizmos.
- [x] Scale selected vertices, edges and faces.
- [x] Extrude selected vertices, edges and faces.
- [x] Bevel selected vertices/edges and face boundaries.
- [x] Face inset.
- [x] Delete the currently selected geometry type.
- [x] Merge selected vertices.
- [x] Subdivide selected geometry.
- [x] Duplicate selected geometry.
- [x] Recalculate face normals.
- [x] Flip face normals.
- [x] Generalized distance-aware gizmos for edit-mode selections.
- [x] Compact secondary edit page instead of overcrowding the main VR menu.
- [x] Dedicated XR feedback for selected vertices, edges and faces.
- [x] Automated regression coverage across Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2.

## v0.5.2: color + statistics quality-of-life update

Implemented:

- [x] Native Blender color picker / hue wheel for the active mesh object.
- [x] Apply the chosen color to the object's viewport color and active Principled material Base Color.
- [x] Assign a chosen color/material only to selected faces in Edit Mode.
- [x] Reuse matching material slots instead of creating unnecessary duplicate color materials.
- [x] Avoid unexpectedly recoloring other objects by copying shared materials before whole-object changes.
- [x] Scene Statistics area showing visible Objects, Selected Objects, Meshes, Materials, Vertices, Edges, Faces and Triangles.
- [x] Active-object vertex/edge/face/triangle counts.
- [x] Shade Smooth and Shade Flat controls.
- [x] Keep the existing v0.5 mesh editing, axis gizmos, travel, save and local history workflows unchanged.

## v0.5.3: cleanup + stronger foundations

Implemented for the v0.5.3 release:

- [x] Rename the sidebar appearance workflow to a clearer **Materials** section.
- [x] Show active material name and material-slot position.
- [x] Context-aware **Apply to Object** / **Assign to Selected Faces** wording.
- [x] Cache scene statistics instead of fully recounting geometry on every panel redraw.
- [x] Make Scene Statistics collapsible.
- [x] Persist controller, movement, modeling and UI preferences between Blender files.
- [x] Centralize material creation/reuse/face assignment in `materials.py`.
- [x] Centralize vertex/edge/face selection handling in `selection.py` while keeping old APIs compatible.
- [x] Centralize transform helper behavior in `transforms.py` while keeping existing runtime call sites stable.
- [x] Centralize safe Object/Edit mode switching in `modes.py`.
- [x] Centralize short status feedback in `status.py`.
- [x] Move VR menu page definitions out of the GPU renderer into `menus.py`.
- [x] Keep `v052.py` as a small compatibility layer instead of a growing version-specific feature file.
- [x] Standardize gizmo sizing/picking constants without changing the existing controller interaction model.

Still suitable for later v0.5.x modeling polish rather than blocking v0.5.3:

- [ ] Rotate selected mesh geometry with VR gizmos.
- [ ] Loop Cut.
- [ ] Dissolve vertices/edges.
- [ ] Bridge edge loops and fill holes.
- [ ] Separate selected geometry and join meshes.
- [ ] Global / Local / Normal transform orientations.
- [ ] Mesh/grid snapping and more precise transform controls.

# Future roadmap

| Version | Main goal | Ideal features |
| --- | --- | --- |
| **v0.6** | **Materials + UV mapping** | Expand the current basic color/per-face assignment into full material management: create/delete/rename materials and slots; select/assign material slots; Base Color, Metallic, Roughness, Alpha and Emission controls; texture image selection; UV unwrap; Smart UV Project; cube and planar projection; seam marking; move, rotate and scale UV islands; reset/pack UVs; diagnostic checker/direction textures; simple VR UV preview; material preview mode. |
| **v0.7** | **Object transforms + modifiers** | Direct numeric Position X/Y/Z, Rotation X/Y/Z and Scale X/Y/Z; uniform scale; reset and apply transforms; copy/paste transforms; VR transform gizmos; set object origin; Origin to Geometry; Geometry to Origin; snap object to cursor; duplicate and linked duplicate; improved object snapping; Mirror modifier with X/Y/Z, Clipping, Merge and Mirror Object; Array modifier with Count, Relative/Constant Offset, X/Y/Z direction and Object Offset; Solidify modifier; apply/remove modifiers; visibility toggle; reorder supported modifiers. |
| **v0.8** | **Rigging + armatures** | Add armatures and bones; select bones in VR; move, rotate and scale bones; extrude bones; bone parenting; bone naming; mirror bones; Pose Mode; Rest/Pose switching; parent mesh to armature; automatic weights; basic IK; Copy Rotation / Location constraints; armature display controls. |
| **v0.9** | **Weight painting + character tools** | Weight Paint mode; add/remove weights; brush size and strength; bone/vertex-group selection; create, delete and rename vertex groups; assign selected vertices; normalize, mirror and smooth weights; automatic cleanup; visual weight heatmap; test deformation while painting; shape keys/blendshapes; create, rename and delete shape keys; adjust shape-key values. |
| **v1.0** | **Stable complete XR modeling workflow** | Polish all earlier systems; reliable Object/Edit/Pose/Weight/UV/Material switching; unified Undo/Redo; grid, vertex, edge and face snapping; pivot controls; collection and hierarchy controls; common modifier management; better object duplication; transform presets; customizable VR menu; large-scene performance improvements; clearer error feedback; controller accessibility options; direct hand-grab positioning and rotation for objects, vertices, edges and faces while preserving axis gizmos for precision; dominant-thumbstick-click Extrude-to-Hand; full tutorials and documentation; broad Blender-version and OpenXR compatibility testing. |

## v0.7 transform workflow target

v0.7 should translate the most useful parts of Blender's Object Properties and basic Modifier workflow into VR without turning the menu into a desktop UI clone.

### Transform

- Location: X / Y / Z
- Rotation: X / Y / Z
- Scale: X / Y / Z
- Uniform scale
- Reset Location / Rotation / Scale
- Apply Location / Rotation / Scale
- Copy and paste transforms
- Global/local transform handling

### Mirror

- X / Y / Z axes
- Clipping
- Merge
- Mirror Object
- Apply
- Remove

### Array

- Count
- X / Y / Z direction
- Relative Offset
- Constant Offset
- Object Offset
- Apply
- Remove

### Solidify

- Thickness
- Offset
- Even Thickness where supported
- Apply
- Remove

## v1.0 direct-hand interaction target

The precision axis workflow remains available in v1.0. Direct controller manipulation is an additional faster way to model naturally in VR.

- Grab an **object** with the dominant hand and use controller movement/rotation to position and rotate it directly.
- Grab selected **vertices, edges or faces** and move/rotate that selection with the dominant controller pose.
- Keep the existing X/Y/Z and Size gizmos for precise constrained transforms.
- Allow switching between direct-hand manipulation and axis-constrained manipulation without losing the current selection.
- Add **Extrude-to-Hand**: clicking the dominant-hand thumbstick while a vertex/edge/face selection is active starts an extrusion controlled by the dominant hand, with the existing axis-based Extrude remaining available for precision.
- Extrude-to-Hand must use the same safe preview/cancel/Undo history behavior as the existing extrusion tools.

## Beyond v1.0

The following are intentionally outside the initial 1.0 target so the core VR modeling workflow can become stable first:

- Sculpting.
- Full Shader Node editing.
- Geometry Nodes editing.
- Grease Pencil workflows.
- Animation graph editing.
- Video editing and compositing.
- Cloth, fluid and other advanced simulation workflows.
- Advanced retopology systems.

These may be explored in later 1.x releases after the core XR modeling, material, UV, rigging and character workflows are stable.
