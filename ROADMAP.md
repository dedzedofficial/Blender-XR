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

Still suitable for later v0.5.x modeling polish rather than blocking v0.5.0:

- [ ] Rotate selected mesh geometry with VR gizmos.
- [ ] Loop Cut.
- [ ] Dissolve vertices/edges.
- [ ] Bridge edge loops and fill holes.
- [ ] Separate selected geometry and join meshes.
- [ ] Shade Smooth / Flat controls.
- [ ] Global / Local / Normal transform orientations.
- [ ] Mesh/grid snapping and more precise transform controls.

# Future roadmap

| Version | Main goal | Ideal features |
| --- | --- | --- |
| **v0.6** | **Materials + UV mapping** | Create and delete materials; material slots; assign materials to selected faces; Base Color, Metallic, Roughness, Alpha and Emission controls; texture image selection; UV unwrap; Smart UV Project; cube and planar projection; move, rotate and scale UVs; reset UVs; simple VR UV preview; material preview mode. |
| **v0.7** | **Object transforms + modifiers** | Direct numeric Position X/Y/Z, Rotation X/Y/Z and Scale X/Y/Z; uniform scale; reset and apply transforms; copy/paste transforms; VR transform gizmos; set object origin; Origin to Geometry; Geometry to Origin; snap object to cursor; duplicate and linked duplicate; improved object snapping; Mirror modifier with X/Y/Z, Clipping, Merge and Mirror Object; Array modifier with Count, Relative/Constant Offset, X/Y/Z direction and Object Offset; Solidify modifier; apply/remove modifiers; visibility toggle; reorder supported modifiers. |
| **v0.8** | **Rigging + armatures** | Add armatures and bones; select bones in VR; move, rotate and scale bones; extrude bones; bone parenting; bone naming; mirror bones; Pose Mode; Rest/Pose switching; parent mesh to armature; automatic weights; basic IK; Copy Rotation / Location constraints; armature display controls. |
| **v0.9** | **Weight painting + character tools** | Weight Paint mode; add/remove weights; brush size and strength; bone/vertex-group selection; create, delete and rename vertex groups; assign selected vertices; normalize, mirror and smooth weights; automatic cleanup; visual weight heatmap; test deformation while painting; shape keys/blendshapes; create, rename and delete shape keys; adjust shape-key values. |
| **v1.0** | **Stable complete XR modeling workflow** | Polish all earlier systems; reliable Object/Edit/Pose/Weight/UV/Material switching; unified Undo/Redo; grid, vertex, edge and face snapping; pivot controls; collection and hierarchy controls; common modifier management; better object duplication; transform presets; customizable VR menu; large-scene performance improvements; clearer error feedback; controller accessibility options; full tutorials and documentation; broad Blender-version and OpenXR compatibility testing. |

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
