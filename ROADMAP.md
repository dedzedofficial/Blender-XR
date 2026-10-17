# Mesh XR roadmap

Mesh XR is a free controller-first OpenXR modeling extension for Blender by Ded Zed. This roadmap describes scoped goals rather than promises of full Blender parity. Shipped release history is kept in [CHANGELOG.md](CHANGELOG.md); this file tracks completed milestones and future direction.

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

- [x] Create, delete, rename and duplicate materials.
- [x] Create/remove/cycle material slots.
- [x] Assign the active slot to selected faces and select faces using the active slot.
- [x] Base Color, Metallic, Roughness, Alpha and Emission controls.
- [x] Material Preview toggle.
- [x] Dedicated Materials hub in VR.
- [x] Advanced Materials + Textures desktop panel.

### Textures

- [x] Select and cycle Blender images from VR.
- [x] Load texture images using Blender's desktop file picker.
- [x] Apply/clear Base Color image textures without deleting image datablocks.
- [x] Built-in numbered checker, directional UV and color-grid diagnostics.
- [x] Pack generated diagnostic images into the `.blend`.

### UV mapping + editing

- [x] Standard UV Unwrap.
- [x] Smart UV Project.
- [x] Cube and Planar projection.
- [x] Mark/Clear seams.
- [x] Move, rotate and scale UV islands.
- [x] Reset UVs and Pack Islands.
- [x] Simple VR UV wireframe preview.
- [x] Desktop UV Mapping panel and configurable move step.
- [x] Deterministic projection/packing fallbacks for restricted Blender contexts.

### v0.6 engineering + release quality

- [x] Separate material/UV modules instead of growing the core runtime indefinitely.
- [x] Preserve the HSL color workflow inside the Materials hub.
- [x] Dedicated material/texture/UV regression suite.
- [x] Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2 automated coverage.
- [x] Block release publishing unless release validation passes.
- [x] Blender Extensions-compliant naming/support/update behavior.
- [x] No packaged `threading` / `queue` imports.
- [x] Bundled and verified OpenVR Python wheel for the optional external SteamVR skeletal bridge.

## v0.6.5 — modeling + icon UI — complete

v0.6.5 focuses on making the established modeling workflow faster to understand and filling several practical modeling gaps.

### Icon-first interface

- [x] Replace long primary Object/Edit labels with compact pictogram icons.
- [x] Raycast hover highlighting.
- [x] Delayed hover tooltips with tool name and explanation.
- [x] Blender-style Object Mode / Edit Mode selector.
- [x] Dedicated Vertex / Edge / Face selection icons.
- [x] Restore Inset Faces directly to the primary Edit toolbar.
- [x] Keep secondary commands grouped so the main toolbar stays compact.
- [x] Provide an `ICON_GUIDE.md` reference for icons and controls.

### Loop Cut

- [x] Detect a continuous quad edge ring from the selected edge.
- [x] Preview the target ring before applying.
- [x] 1–16 cuts.
- [x] Adjustable position for a single cut from 5% to 95%.
- [x] Even spacing for multiple cuts.
- [x] Reject invalid/non-quad rings with a clear message.
- [x] Session-local Undo/Redo integration.

### Object deletion

- [x] Dedicated Delete Object action in Object Mode.
- [x] Keep Delete Geometry as a separate Edit Mode operation.
- [x] Restore deleted mesh objects with Mesh XR Undo.
- [x] Redo object deletion.

### v0.6.5 quality

- [x] Dedicated v0.6.5 modeling/UI regression coverage.
- [x] Run v0.6.5 validation in release CI before GitHub/Blender Extensions publishing.
- [x] Update current README, changelog, testing guide, icon guide, release notes and roadmap.

## Modeling polish backlog

These are useful modeling improvements that remain open after v0.6.5 and can be scheduled alongside later transform/modeling work.

- [ ] Rotate selected mesh geometry with VR gizmos.
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

## v0.7 — object transforms + modifiers

### Transform

- [ ] Location X / Y / Z.
- [ ] Rotation X / Y / Z.
- [ ] Scale X / Y / Z and uniform scale.
- [ ] Reset/apply Location, Rotation and Scale.
- [ ] Copy/paste transforms.
- [ ] Global/local transform handling.
- [ ] Set object origin, Origin to Geometry and Geometry to Origin.
- [ ] Snap object to cursor.
- [ ] Duplicate and linked duplicate.
- [ ] Improved object snapping.

### Mirror

- [ ] X / Y / Z axes.
- [ ] Clipping and Merge.
- [ ] Mirror Object.
- [ ] Apply/remove Mirror.

### Array

- [ ] Count and X / Y / Z direction.
- [ ] Relative Offset, Constant Offset and Object Offset.
- [ ] Apply/remove Array.

### Solidify

- [ ] Thickness and Offset.
- [ ] Even Thickness where supported.
- [ ] Apply/remove Solidify.

### Modifier management

- [ ] Toggle supported modifier viewport visibility.
- [ ] Reorder, apply and remove supported modifiers.

## v0.8 — rigging + weight painting

v0.8 should take a mesh from an unrigged state through a usable weighted armature without forcing the user to leave XR.

### Armatures + bones

- [ ] Add armatures and bones.
- [ ] Select/multi-select, move, rotate, scale and extrude bones.
- [ ] Parent/unparent, rename, mirror, duplicate and delete bones.
- [ ] Armature and bone display controls.

### Pose workflow

- [ ] Enter Pose Mode from VR.
- [ ] Switch Rest/Pose position.
- [ ] Select and transform pose bones.
- [ ] Reset individual/full pose.
- [ ] Test mesh deformation while posing.

### Parenting + vertex groups

- [ ] Parent mesh to armature with automatic weights or empty groups.
- [ ] Clear armature parenting safely.
- [ ] Recalculate automatic weights.
- [ ] Create/delete/rename/select vertex groups.
- [ ] Assign/remove/select/deselect vertices by group.

### Weight Painting

- [ ] Enter Weight Paint Mode from VR.
- [ ] Choose active bone/group.
- [ ] Add/remove/set weight.
- [ ] Brush size and strength.
- [ ] Normalize, mirror, smooth, clean and limit influences.
- [ ] Visual weight heatmap.
- [ ] Pose while testing deformation.

### Rig constraints

- [ ] Basic IK creation/target/chain length.
- [ ] Copy Rotation and Copy Location.
- [ ] Enable/disable/remove supported constraints.

## v0.9 — deformation + animation

### Shape Keys / Blendshapes

- [ ] Create Basis/new shape keys.
- [ ] Delete, rename, duplicate and select shape keys.
- [ ] Adjust/reset values and compare against Basis.
- [ ] Mirror/copy/clear deformation.
- [ ] Edit active shape keys with VR mesh tools.
- [ ] Live preview and multi-key deformation testing.

### Corrective deformation + simplified drivers

- [ ] Create corrective shape keys from poses.
- [ ] Associate corrective targets with supported bone transforms.
- [ ] Preview/reset corrective deformation.
- [ ] Connect shape-key values to supported transforms/properties.
- [ ] Configure driver axis/input/output ranges.
- [ ] Enable/disable/remove simple drivers.

### Timeline + keyframing

- [ ] Current-frame display and scrubbing.
- [ ] Previous/next frame and keyframe.
- [ ] Play/pause and playback range.
- [ ] Insert/delete keys.
- [ ] Key object, pose-bone and shape-key transforms/values.
- [ ] Show keyed-state feedback.

### Pose and shape-key animation

- [ ] Create keyed poses across frames.
- [ ] Preview armature animation in XR.
- [ ] Key and preview shape-key animation.
- [ ] Mix pose and shape-key animation.

### Pose presets / library

- [ ] Save, load, rename, delete and mirror poses.
- [ ] Reset to rest pose from the pose-library workflow.

## v1.0 — stable complete XR modeling workflow

The precision axis workflow remains available; direct controller manipulation is an additional faster modeling path.

- [ ] Polish all earlier systems into one consistent workflow.
- [ ] Reliable Object/Edit/Pose/Weight/UV/Material mode switching.
- [ ] Unified Undo/Redo across supported XR operations.
- [ ] Grid, vertex, edge and face snapping.
- [ ] Pivot, collection and hierarchy controls.
- [ ] Common modifier management and better duplication.
- [ ] Transform presets and customizable VR menu.
- [ ] Large-scene performance improvements.
- [ ] Clearer error feedback and controller accessibility options.
- [ ] Grab objects or selected vertices/edges/faces and transform them directly with controller pose.
- [ ] Keep X/Y/Z and Size gizmos for precision-constrained transforms.
- [ ] Switch between direct-hand and constrained manipulation without losing selection.
- [ ] Extrude-to-Hand from the dominant-hand thumbstick.
- [ ] Keep axis-based Extrude for precision.
- [ ] Apply the same preview/cancel/Undo safety to direct-hand extrusion.
- [ ] Full tutorials and documentation.
- [ ] Broad Blender-version and OpenXR runtime/controller compatibility testing.

## Beyond v1.0

The following remain outside the initial 1.0 target so the core XR modeling workflow can stabilize first:

- Sculpting.
- Full Shader Node editing.
- Geometry Nodes editing.
- Grease Pencil workflows.
- Advanced Graph Editor / animation-curve editing beyond practical v0.9 controls.
- Video editing and compositing.
- Cloth, fluid and other advanced simulation workflows.
- Advanced retopology systems.

These may be explored in later 1.x releases after the core XR modeling, materials, UV, rigging, weighting, deformation and animation workflows are stable.
