# XR Mesh roadmap

XR Mesh is a free controller-first OpenXR modeling extension for Blender by Ded Zed. This roadmap describes scoped goals, not promises of full Blender parity. Shipped release history is kept in [CHANGELOG.md](CHANGELOG.md); this file focuses on completed milestones and future direction.

## Shipped foundation

### v0.3–v0.4

Implemented the initial VR edit loop, controller menu, face selection, Extrude/Bevel/Inset, object grabbing, local Undo/Redo, navigation, controller profiles, experimental finger input, primitives, flight, mesh switching, Save Blend, Blender 4.2+ support, axis/size handles and selected-face transforms.

### v0.5 — vertex/edge/face modeling

- [x] Vertex, Edge and Face selection modes directly in VR.
- [x] Add/remove multi-selection using grip + trigger.
- [x] Move and scale selected vertices, edges and faces.
- [x] Extrude selected vertices, edges and faces.
- [x] Bevel selected vertices/edges and face boundaries.
- [x] Face inset.
- [x] Delete the currently selected geometry type.
- [x] Merge selected vertices.
- [x] Subdivide selected geometry.
- [x] Duplicate selected geometry.
- [x] Recalculate and flip face normals.
- [x] Distance-aware edit-mode gizmos and dedicated selection feedback.
- [x] Native Blender color picker plus object/selected-face material colors.
- [x] HSL controls, presets, Pick/Apply and lightweight face-color Undo/Redo.
- [x] Shade Smooth / Flat and cached scene/object statistics.
- [x] Persistent controller, movement, modeling and UI preferences.
- [x] Purpose-based material, selection, transform, mode, status and menu modules.
- [x] Automated Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2 regression coverage.

## v0.6.1 — Materials + UV mapping — complete

The original v0.6 Materials + UV target is implemented and covered by the automated Blender matrix.

### Materials

- [x] Create materials.
- [x] Delete materials.
- [x] Rename materials.
- [x] Duplicate materials. *(Added during v0.6 implementation.)*
- [x] Create and remove material slots.
- [x] Cycle the active material slot in VR. *(Added during v0.6 implementation.)*
- [x] Select and assign material slots to selected faces.
- [x] Select faces that use the active material slot. *(Added during v0.6 implementation.)*
- [x] Base Color control.
- [x] Metallic control.
- [x] Roughness control.
- [x] Alpha control.
- [x] Emission control.
- [x] Material Preview toggle.
- [x] Dedicated Materials hub in VR. *(Added during v0.6 implementation.)*
- [x] Advanced Materials + Textures desktop panel. *(Added during v0.6 implementation.)*

### Textures

- [x] Select texture images.
- [x] Cycle available Blender images from VR. *(Added during v0.6 implementation.)*
- [x] Load a texture image from disk using Blender's desktop file picker. *(Added during v0.6 implementation.)*
- [x] Apply the selected image to the active material Base Color.
- [x] Clear the XR Mesh image texture without deleting the image datablock. *(Added during v0.6 implementation.)*
- [x] Built-in numbered checker diagnostic texture.
- [x] Built-in directional UV diagnostic texture.
- [x] Built-in color-grid diagnostic texture.
- [x] Pack generated diagnostic images into the `.blend`. *(Added during v0.6 implementation.)*

### UV mapping + editing

- [x] Standard UV Unwrap.
- [x] Smart UV Project.
- [x] Cube projection.
- [x] Planar projection.
- [x] Mark seams.
- [x] Clear seams.
- [x] Move UV islands on U/V.
- [x] Rotate UV islands.
- [x] Scale UV islands.
- [x] Reset UVs.
- [x] Pack UV islands.
- [x] Simple VR UV wireframe preview.
- [x] Desktop UV Mapping panel. *(Added during v0.6 implementation.)*
- [x] Configurable desktop UV movement step. *(Added during v0.6 implementation.)*
- [x] Deterministic UV projection/packing fallbacks for restricted Blender contexts. *(Added during v0.6 implementation.)*

### v0.6 engineering + release quality

- [x] Separate `material_uv.py`, `uv_tools.py` and `v060.py` instead of growing the core runtime.
- [x] Preserve the existing HSL color workflow inside the new Materials hub.
- [x] Dedicated v0.6 material/texture/UV regression suite.
- [x] Run v0.6 tests on Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2.
- [x] Block release publishing unless the v0.6 suite passes on Blender 5.2.2.
- [x] Build guards for v0.6 runtime/module/menu wiring.
- [x] Blender Extensions-compliant name/support/update behavior and no packaged `threading`/`queue` imports.
- [x] File permission description covers texture loading and project saving.

## Modeling polish backlog

These were previously listed as later v0.5.x polish. They remain useful, but are not part of the completed v0.6 Materials + UV milestone and can be scheduled alongside later transform/modeling work.

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
| **v0.7** | **Object transforms + modifiers** | Numeric transforms, origins, snapping, duplication and a focused set of common modifiers. |
| **v0.8** | **Rigging + Weight Painting** | Armatures, bones, posing, vertex groups, weighting, deformation testing and basic rig constraints in one complete rigging workflow. |
| **v0.9** | **Deformation + Animation** | Shape keys/blendshapes, corrective deformation, pose presets, basic drivers and practical keyframe animation tools in VR. |
| **v1.0** | **Stable complete XR modeling workflow** | Polish all earlier systems and make the complete workflow stable, performant and VR-native, including direct-hand manipulation and Extrude-to-Hand. |

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
