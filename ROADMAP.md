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

| Version | Main goal | Ideal direction |
| --- | --- | --- |
| **v0.6** | **Materials + UV mapping** | Full material management, textures, UV unwrapping, UV editing and diagnostic texture tools. |
| **v0.7** | **Object transforms + modifiers** | Numeric transforms, origins, snapping, duplication and a focused set of common modifiers. |
| **v0.8** | **Rigging + Weight Painting** | Armatures, bones, posing, vertex groups, weighting, deformation testing and basic rig constraints in one complete rigging workflow. |
| **v0.9** | **Deformation + Animation** | Shape keys/blendshapes, corrective deformation, pose presets, basic drivers and practical keyframe animation tools in VR. |
| **v1.0** | **Stable complete XR modeling workflow** | Polish all earlier systems and make the complete workflow stable, performant and VR-native, including direct-hand manipulation and Extrude-to-Hand. |

## v0.6 materials + UV mapping target

- [ ] Create materials.
- [ ] Delete materials.
- [ ] Rename materials.
- [ ] Create and remove material slots.
- [ ] Select and assign material slots to selected faces.
- [ ] Base Color control.
- [ ] Metallic control.
- [ ] Roughness control.
- [ ] Alpha control.
- [ ] Emission control.
- [ ] Select texture images.
- [ ] Standard UV unwrap.
- [ ] Smart UV Project.
- [ ] Cube projection.
- [ ] Planar projection.
- [ ] Mark seams.
- [ ] Clear seams.
- [ ] Move UV islands.
- [ ] Rotate UV islands.
- [ ] Scale UV islands.
- [ ] Reset UVs.
- [ ] Pack UV islands.
- [ ] Built-in numbered checker diagnostic texture.
- [ ] Built-in directional UV diagnostic texture.
- [ ] Built-in color-grid diagnostic texture.
- [ ] Simple VR UV preview.
- [ ] Material preview mode.

## v0.7 object transforms + modifiers target

### Transform

- [ ] Location X / Y / Z.
- [ ] Rotation X / Y / Z.
- [ ] Scale X / Y / Z.
- [ ] Uniform scale.
- [ ] Reset Location.
- [ ] Reset Rotation.
- [ ] Reset Scale.
- [ ] Apply Location.
- [ ] Apply Rotation.
- [ ] Apply Scale.
- [ ] Copy transforms.
- [ ] Paste transforms.
- [ ] Global/local transform handling.
- [ ] Set object origin.
- [ ] Origin to Geometry.
- [ ] Geometry to Origin.
- [ ] Snap object to cursor.
- [ ] Duplicate object.
- [ ] Linked duplicate.
- [ ] Improved object snapping.

### Mirror

- [ ] X / Y / Z axes.
- [ ] Clipping.
- [ ] Merge.
- [ ] Mirror Object.
- [ ] Apply Mirror.
- [ ] Remove Mirror.

### Array

- [ ] Count.
- [ ] X / Y / Z direction.
- [ ] Relative Offset.
- [ ] Constant Offset.
- [ ] Object Offset.
- [ ] Apply Array.
- [ ] Remove Array.

### Solidify

- [ ] Thickness.
- [ ] Offset.
- [ ] Even Thickness where supported.
- [ ] Apply Solidify.
- [ ] Remove Solidify.

### Modifier management

- [ ] Toggle supported modifier viewport visibility.
- [ ] Reorder supported modifiers.
- [ ] Apply supported modifiers.
- [ ] Remove supported modifiers.

## v0.8 rigging + weight painting target

Rigging and weighting belong in the same workflow, so v0.8 should take a mesh from an unrigged state through a usable weighted armature without forcing the user to leave XR.

### Armatures + bones

- [ ] Add a new armature.
- [ ] Add bones.
- [ ] Select bones in VR.
- [ ] Multi-select bones.
- [ ] Move bones.
- [ ] Rotate bones.
- [ ] Scale bones.
- [ ] Extrude bones.
- [ ] Parent bones.
- [ ] Unparent bones.
- [ ] Rename bones.
- [ ] Mirror bones.
- [ ] Duplicate bones.
- [ ] Delete bones.
- [ ] Armature display controls.
- [ ] Bone display controls.

### Pose workflow

- [ ] Enter Pose Mode from VR.
- [ ] Switch between Rest Position and Pose Position.
- [ ] Select pose bones.
- [ ] Move pose bones.
- [ ] Rotate pose bones.
- [ ] Scale pose bones.
- [ ] Reset individual bone transforms.
- [ ] Reset the full pose.
- [ ] Test mesh deformation while posing.

### Mesh parenting + automatic weights

- [ ] Parent a mesh to an armature.
- [ ] Parent with automatic weights.
- [ ] Parent with empty groups.
- [ ] Clear armature parenting safely.
- [ ] Recalculate automatic weights when requested.

### Vertex groups

- [ ] Create vertex groups.
- [ ] Delete vertex groups.
- [ ] Rename vertex groups.
- [ ] Select the active vertex group.
- [ ] Assign selected vertices to a group.
- [ ] Remove selected vertices from a group.
- [ ] Select vertices belonging to a group.
- [ ] Deselect vertices belonging to a group.

### Weight Painting

- [ ] Enter Weight Paint Mode from VR.
- [ ] Choose the active bone / vertex group while painting.
- [ ] Add weight.
- [ ] Remove weight.
- [ ] Adjust brush size.
- [ ] Adjust brush strength.
- [ ] Set exact weight values where useful.
- [ ] Normalize weights.
- [ ] Normalize all weights.
- [ ] Mirror weights.
- [ ] Smooth weights.
- [ ] Clean very small / unused weights.
- [ ] Limit total influences per vertex.
- [ ] Visual weight heatmap.
- [ ] Pose bones while testing weight deformation.
- [ ] Quickly return to the active weight-paint bone.

### Rig constraints

- [ ] Basic IK constraint creation.
- [ ] Basic IK target assignment.
- [ ] IK chain-length control.
- [ ] Copy Rotation constraint.
- [ ] Copy Location constraint.
- [ ] Enable / disable supported constraints.
- [ ] Remove supported constraints.

## v0.9 deformation + animation target

v0.9 should build on the completed v0.8 rigging workflow and add shape-based deformation plus practical animation tools without trying to recreate the entire desktop Graph Editor in VR.

### Shape Keys / Blendshapes

- [ ] Create Basis shape key.
- [ ] Create new shape keys.
- [ ] Delete shape keys.
- [ ] Rename shape keys.
- [ ] Duplicate shape keys.
- [ ] Select the active shape key.
- [ ] Adjust shape-key value from 0 to 1.
- [ ] Reset an individual shape-key value.
- [ ] Reset all shape-key values.
- [ ] Compare active shape key against Basis.
- [ ] Mirror a shape key.
- [ ] Copy deformation from another shape key.
- [ ] Clear a shape key back toward Basis.
- [ ] Edit the active shape key directly in VR using vertex/edge/face tools.
- [ ] Preview shape-key deformation live while editing.
- [ ] Combine multiple shape-key values for deformation testing.

### Corrective deformation

- [ ] Pose a bone and create a corrective shape key for that pose.
- [ ] Capture the current deformed mesh as a corrective target where safe.
- [ ] Associate a corrective shape key with a bone transform.
- [ ] Preview corrective deformation while moving the driving bone.
- [ ] Reset corrective preview safely.

### Simplified drivers

- [ ] Connect a shape-key value to a bone transform.
- [ ] Connect a shape-key value to another supported property.
- [ ] Choose a driver axis/property.
- [ ] Set driver minimum input.
- [ ] Set driver maximum input.
- [ ] Set driven minimum output.
- [ ] Set driven maximum output.
- [ ] Enable / disable a simple driver.
- [ ] Remove a simple driver.

### Timeline + playback

- [ ] Show the current frame in VR.
- [ ] Set current frame.
- [ ] Scrub the timeline.
- [ ] Previous frame.
- [ ] Next frame.
- [ ] Previous keyframe.
- [ ] Next keyframe.
- [ ] Play animation.
- [ ] Pause animation.
- [ ] Set animation start frame.
- [ ] Set animation end frame.
- [ ] Loop playback toggle.

### Keyframing

- [ ] Insert keyframe.
- [ ] Delete keyframe.
- [ ] Key object Location.
- [ ] Key object Rotation.
- [ ] Key object Scale.
- [ ] Key object Location + Rotation + Scale together.
- [ ] Key pose-bone Location.
- [ ] Key pose-bone Rotation.
- [ ] Key pose-bone Scale.
- [ ] Key pose-bone Location + Rotation + Scale together.
- [ ] Key shape-key values.
- [ ] Show whether the current property/frame already has a key.

### Pose animation

- [ ] Pose a bone in VR and key the pose.
- [ ] Move to another frame and create another pose key.
- [ ] Preview keyed armature animation inside XR.
- [ ] Reset a pose without deleting its animation keys.

### Shape-key animation

- [ ] Set a shape-key value and key it.
- [ ] Animate multiple shape keys together.
- [ ] Preview shape-key animation in XR.
- [ ] Mix pose animation and shape-key animation during playback.

### Pose presets / Pose Library

- [ ] Save the current pose as a preset.
- [ ] Load a saved pose.
- [ ] Rename a pose preset.
- [ ] Delete a pose preset.
- [ ] Mirror a pose preset.
- [ ] Reset to rest pose from the pose library workflow.

### Deformation testing

- [ ] Test armature deformation and shape keys together.
- [ ] Quickly switch between Rest, Pose and animated states.
- [ ] Temporarily mute shape keys for comparison.
- [ ] Temporarily mute armature deformation for comparison.
- [ ] One-click reset of pose and shape-key preview values without deleting data.

## v1.0 stable complete XR modeling workflow target

The precision axis workflow remains available in v1.0. Direct controller manipulation is an additional faster way to model naturally in VR.

- [ ] Polish all earlier systems into one consistent workflow.
- [ ] Reliable Object/Edit/Pose/Weight/UV/Material mode switching.
- [ ] Unified Undo/Redo across supported XR operations.
- [ ] Grid snapping.
- [ ] Vertex snapping.
- [ ] Edge snapping.
- [ ] Face snapping.
- [ ] Pivot controls.
- [ ] Collection controls.
- [ ] Hierarchy controls.
- [ ] Common modifier management.
- [ ] Better object duplication.
- [ ] Transform presets.
- [ ] Customizable VR menu.
- [ ] Large-scene performance improvements.
- [ ] Clearer error feedback.
- [ ] Controller accessibility options.
- [ ] Grab an **object** with the dominant hand and use controller movement/rotation to position and rotate it directly.
- [ ] Grab selected **vertices** and move/rotate them with the dominant controller pose.
- [ ] Grab selected **edges** and move/rotate them with the dominant controller pose.
- [ ] Grab selected **faces** and move/rotate them with the dominant controller pose.
- [ ] Keep the existing X/Y/Z and Size gizmos for precise constrained transforms.
- [ ] Switch between direct-hand manipulation and axis-constrained manipulation without losing the current selection.
- [ ] **Extrude-to-Hand** by clicking the dominant-hand thumbstick while a vertex/edge/face selection is active.
- [ ] Extrude-to-Hand follows the dominant hand while the operation is active.
- [ ] Keep the existing axis-based Extrude available for precision.
- [ ] Extrude-to-Hand uses the same preview/cancel/Undo safety as the existing extrusion tools.
- [ ] Full tutorials and documentation.
- [ ] Broad Blender-version compatibility testing.
- [ ] Broad OpenXR runtime/controller compatibility testing.

## Beyond v1.0

The following are intentionally outside the initial 1.0 target so the core VR workflow can become stable first:

- Sculpting.
- Full Shader Node editing.
- Geometry Nodes editing.
- Grease Pencil workflows.
- Advanced Graph Editor / animation-curve editing beyond the practical v0.9 animation controls.
- Video editing and compositing.
- Cloth, fluid and other advanced simulation workflows.
- Advanced retopology systems.

These may be explored in later 1.x releases after the core XR modeling, materials, UV, rigging, weighting, deformation and animation workflows are stable.
