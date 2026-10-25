# Mesh XR roadmap

## v0.7.6 — shipped baseline (25 October 2026)

- [x] Compact seven-workspace native-icon desktop UI.
- [x] One contextual Select tool (no separate Select Mesh / Select Armature buttons), vertex/edge/face and bone grabbing/transforms, and Mesh XR Undo/Redo.
- [x] Freeform armature creation, bone edit tools, native Blender parenting, Weight Paint Mode and controller brush with group management basics.
- [x] Automated install/compatibility matrix for Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2; GitHub v0.7.6 release published.
- [ ] Full **physical-headset** acceptance for real controller interactions and Weight Paint remains unverified. This is a v0.8 release gate, not proof of a failed automated test.

**Next target:** [Mesh XR v0.8 — VR-first workflow and rigging completion plan](V0_8_PLAN.md) and [Deep System Audit / Hands / Finger Tracking / Radial Menu](V0_8_SYSTEM_AUDIT_AND_INPUT_PLAN.md).

Shipped details: [CHANGELOG.md](CHANGELOG.md). Version 0.8 and later items are **proposals**, not completed features.

## v0.7.5 — workflow expansion (development)

- [x] PC View Mode toggle for Blender's live OpenXR viewport mirror, independent of VR session start/stop.
- [x] Optional precision snapping for controller-driven geometry tools and axis translation.
- [x] Two-controller object scaling with midpoint-aware transforms and XR-local Undo/Redo.
- [x] Optional OpenXR haptic pulses after completed geometry edits and object transforms, guarded by a preference and safe fallback.
- [x] Read-only asset readiness audit for topology, UVs, material slots, modifier counts, base triangles and evaluated modifier triangles when available.
- [x] Distinguish open boundary edges from true non-manifold edges and test both cases.
- [x] Restore selection and clean up partial starter rigs on failure; harden weight-tool selection/mode recovery.
- [x] Restore the regular desktop viewport and clean up Mesh XR promptly when an XR session ends unexpectedly.
- [x] Add regression coverage for evaluated triangle counts, two-hand scaling pivot math and rig-preflight failure recovery.
- [x] Starter humanoid armature creation, automatic-weight binding, weight normalization/cleanup and Weight Paint entry.
- [x] Collapsible desktop Workflow panel for asset checks, rigging and controller-modeling guidance.
- [ ] Complete CI validation for the final commit across Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2 before release.
- [ ] Manually validate headset mirroring and controller interactions on physical OpenXR hardware.
- [ ] Future follow-up: broader controller-direct vertex/edge manipulation, full custom wrist/radial workspace, and rig-aware VR weight painting.

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

## v0.7.5 — PC View Mode development

- [x] Add a desktop toggle for normal viewport versus live OpenXR session mirror where Blender supports it.
- [x] Keep view switching independent from starting/stopping the VR session.
- [x] Disable mirroring until the XR session is running and show a clear unsupported-build message.
- [ ] Validate physical headset/runtime mirror behavior across the supported Blender matrix before release.

## v0.7.1 — advanced modeling and stability improvements

- [x] World-axis incremental object rotation, grid snapping and reset world rotation.
- [x] Object duplication with retained object settings and XR history.
- [x] Selected mesh rotation, dissolve, fill holes and bridge loops.
- [x] Mesh XR-managed Mirror, Array and Solidify controls with reversible settings.
- [x] UV editing and face material-slot assignment integrated with session-local history.
- [x] Full Blender-version release gating and immutable GitHub release tags.
- [ ] Continuous direct controller geometry manipulation, two-handed scale and haptics.
- [ ] Numeric transform entry, full local/global/normal gizmos, modifier apply/reorder.
- [ ] Complete physical headset compatibility and stability verification.

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
| **v0.8** | **VR usability + production rigging + selected VR tools** | Consolidated input, precision modelling, native Weight Eyedropper, reversible Isolation/X-Ray, direct IK posing, conditional Curve Draw and non-destructive Cleanup/Repair. **No asset browser or sculpt mode.** [Detailed plan](V0_8_PLAN.md). |
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

## v0.8 — VR-first workflow + rigging completion (proposed)

**Full requirements, stages, scope limits and headset acceptance:** [V0_8_PLAN.md](V0_8_PLAN.md). New tools complement existing v0.7.6 features rather than duplicate them.

- [ ] **Research gate — before implementation:** investigate existing balls/controller visuals; hand overlay drawing; Quest 3/OpenXR and SteamVR joint capabilities; thumbstick input conflicts; radial UX; full risk matrix. [Technical design](V0_8_SYSTEM_AUDIT_AND_INPUT_PLAN.md).
- [ ] **P0:** Replace sphere-style controller pointers with lightweight, user-optional 3D hands; animate estimated controller fingers and upgrade SteamVR joint feed where supported. Optical tracking remains capability-gated.
- [ ] **P0/P1:** Replace the ray-only grid with a **non-dominant-hand radial menu**: hold the non-dominant Trigger, select with that same hand's thumbstick, release to activate or recenter to cancel. Capture both sticks to prevent movement/turning while open; provide correct left-hand/right-hand reversal and legacy ray-grid fallback.
- [ ] **P0:** Unify controller action routing, context-sensitive Select and all gesture/transform handling; no duplicate selection buttons.
- [ ] **P0:** Blender-native modes, correct Undo/Redo/cancel, reliable weight strokes, robust session startup/shutdown and physical Quest 3 acceptance.
- [ ] **P1:** One compact contextual wrist UI, X/Y/Z constraints, precision bubble, snapping, numeric input and box/lasso/brush selection.
- [ ] **P1:** **Isolation and X-Ray** for targeted meshes, rigs and through-surface selection; independently controlled, reversible and non-destructive.
- [ ] **P1:** **Weight Eyedropper** for precise read-only weight sampling and brush value matching, plus better group tools, bone-to-group picking, symmetry and weight cleanup.
- [ ] **P1:** **Direct Posing** with controller-grabbed endpoints, small IK chains, pose reset and live mesh deformation without changing rest bones.
- [ ] **P1:** **Cleanup/Repair** tools: Merge by Distance, loose/degenerate geometry, normals, non-manifold inspection, broken rig mappings and safe weight cleanup with preview and Undo.
- [ ] **P2 / conditional:** **Draw Curves in 3D** with controller stroke preview, jitter reduction, editable native Blender splines, thickness/bevel, curve-point edits and optional conversion to mesh. Delay to v0.8.x if core stability/performance gates are not met.
- [ ] **P0:** Profile OpenXR/Quest 3 PC-VR workloads, cache expensive pick structures, test Blender 4.2/4.5/5.0/5.2 and finish headset-based release QA.
- [ ] **Excluded:** VR asset browser, sculpt mode, full character animation and automatic full-body posing.

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
