# Mesh XR — creator capability development plan

**Re-audited:** 9 November 2026  
**Status:** Proposed implementation backlog, not a claim of completed features  
**Source branch:** `main` at `1a115135ae500f66451c658a5f0c67be571936bb`  
**Scope:** PC-connected Blender XR authoring using native Blender data, not a replacement engine.

This document is a **live ordering and acceptance plan** for the capabilities the
creator wants. It complements [the detailed v0.8 implementation plan](V0_8_PLAN.md),
[the original roadmap](ROADMAP.md) and
[the v0.8 tracking/input audit](V0_8_SYSTEM_AUDIT_AND_INPUT_PLAN.md).
It does not silently reopen features deliberately excluded from v0.8.

## 1. What the code actually contains

| Capability | Current status | Code evidence / caveat |
| --- | --- | --- |
| Object and mesh primitives; vertex/edge/face edits; modifiers; native materials and UVs | Implemented | `primitives.py`, `mesh.py`, `v071.py`, `material_uv.py`. No need to recreate standard Blender export. |
| Object layout, X/Y/Z origin alignment and even spacing | Implemented, automated CI passed | `v071.quick_layout` and the native desktop/VR actions from PR #23. Layout uses object origins, not bounding-box snapping. |
| Articulated headset hands and offhand radial menu | v0.8 alpha implemented, automated CI passed; **headset acceptance pending** | `hands_v080.py`, `input_v080.py`, `radial_logic_v080.py`; fallback to classic controls is retained. |
| Fine-grab setting, inspection, read-only measurements and pre-export checks | Partial implementations on `main`, not full production workflows | `interaction_v076.py`, `quality_v080.py`. Inspection is not a complete in-headset measurement or guided repair system. |
| Recoverable local Blender copies | Alpha implemented, full interruption QA pending | `recovery_v080.py`; do not mistake a recovery copy for complete operation-level Undo. |
| Freeform rig, bones, native vertex groups and VR Paint/Erase | Implemented, but still lacks atomic full-stroke history | `armature_v076.py`, `rigging_v076.py`. Brush writes groups directly during held-trigger samples. |
| Read-only Weight Probe | Implemented, automated CI passed | `rigging_v076.sample_vertex_weight` and `WEIGHT_SAMPLE` from PR #24. The probe does **not** yet set the brush target weight. |
| Unified input and exclusive action ownership | **Not finished** | `runtime.py` plus chained `patch_runtime` wrappers in `input_v080.py`, `interaction_v076.py`, `rigging_v076.py` and armature modules. |
| Reversible Isolation/X-Ray and see-through selection | **Not implemented as a complete VR workflow** | Planned in `V0_8_PLAN.md`. Native hide/visibility and overlapping-target selection exist only in part. |
| Controller-driven IK end-effector positioning | **Not implemented** | Bone transforms and Pose Mode already exist; an explicit IK target/chain workflow does not. |
| Advanced geometry selection, numeric transform input, snap to real surfaces | **Not complete** | Some distance-aware picking, fine grab, grid snapping and existing gizmos are present. |
| Controller-drawn editable native Blender curves | **Not implemented** | Planned as conditional v0.8.x work; no separate sculpt engine required. |

**Important status distinction:** a green CI job proves tested Blender/package paths, **not**
physical headset comfort, correct pose tracking, or shipping a stable v0.8 release.
Every remaining item below requires implementation; a checkbox is not a release claim.

## 2. Non-negotiable engineering rules

1. **Always develop from the latest tested `main`.** Make focused, reviewable branches; merge passing increments back into `main` without force-pushes or untested mass merges.
2. **Stability before feature breadth.** P0 regressions, broken input capture, lost weights or unrecoverable operations block new P1/P2 releases.
3. **One contextual Select and one action registry.** Do not duplicate Blender operators, selection controls, editor panels or standard exporters.
4. **Native Blender data.** Preserve UVs, modifiers, shape keys, vertex groups, materials, armature links, rest poses and file paths. No hidden parallel project format.
5. **Preview, cancel, undo, redo, save.** Any mutation has a defined rollback and tracking-loss path. Read-only operations cannot write scene data.
6. **VR first with desktop parity.** In-headset operation must not depend on a keyboard; show useful desktop controls where appropriate without bloating the N-panel.
7. **Performance budgets are measured.** Benchmark with representative scene size and exact Blender/PC/OpenXR/headset configuration; never claim universal frame rates.
8. **Scope guard:** do not implement a redundant exporter, full sculpting, remote asset browser, radial favourites, standalone Quest app or game engine as part of the v0.8 stability release. Later alternatives require separate prioritisation.

## 3. Delivery sequence

### Phase 0 — Stop the leaks: input reliability and undo (P0, finish before new complex tools)

- [ ] **Unify controller input routing:** replace layered `Runtime.tick/select/command` monkey-patching with one tested action dispatcher and mode-specific handlers. Retain operator IDs, the classic menu and SteamVR bridge compatibility.
- [ ] **Exclusive gesture ownership:** a captured menu, bone drag, mesh edit, object grab, two-hand scale or weight stroke must not also fly, turn, trigger another tool or change selection.
- [ ] **Weight Paint stroke transactions:** capture before-values once on Trigger-down; write streamed samples; commit one session-history entry on release. Undo/Redo restores each touched vertex's previous weight **including absent group assignments**. Cancellations restore the pre-stroke weights. A group change or mode change cannot silently commit half a stroke.
- [ ] **Recovery and rearm:** on tracking/focus loss or bridge timeout cancel in-progress mutations, restore original matrices/weights, require trigger/grip neutral before restarting, and verify checkpoint saves are deferred during strokes.
- [ ] **Complete locking:** respect hide-select, linked libraries, group locks, constrained rigs, active modes and multi-user mesh restrictions before starting an operation; explain a refusal in the headset.
- [ ] **Input regressions:** test left/right dominant changes, offhand radial capture, selecting and grabbing rig-overlapping meshes, 30 successive mode/undo cycles, repeated starting/stopping, and constrained two-hand operations.

**Ship gate:** no corrupted mesh/weights, no stuck input, stroke undo/redo/cancel tests pass on all supported Blender CI versions; physical Quest 3 Link/Air Link verification recorded before naming a stable release.

### Phase 1 — See and select what you are making (P1)

These are **all required** follow-ups from the November code audit, not interchangeable options.

- [ ] **Reversible Isolate Selection:** isolate the current mesh, collection or rig + deforming mesh; restore *exactly* the previous selection, hide, local-view and relevant viewport state when leaving isolation, closing XR or reopening Blender.
- [ ] **X-Ray visibility and select-through:** independently toggle display-through and back-side picking for mesh/armature/bones; use obvious status feedback. Never modify actual materials/alpha or export/render visibility to fake X-Ray.
- [ ] **Precision geometry picker:** better depth cycling, loose edge/vertex capture, near/far distance-aware pick radius, deliberate occluded-element selection and anti-misclick feedback.
- [ ] **One Select with gestures:** add box, lasso and brush selection modes to existing contextual Select, preserving add/remove/toggle behavior.
- [ ] **Local precision bubble:** magnify the controller's targeting view/overlay for tiny vertices and bone tips without scaling geometry, UVs or any saved transforms.
- [ ] **Numeric transform input:** lightweight VR keypad and Global/Local/Normal axis plus pivot controls for exact movement/rotation/scale; keep existing incremental controls as fallback.
- [ ] **Scene hierarchy / native collections:** small in-scene list of *loaded objects* with search, selection, rename, hide/show, lock/unlock, parent/collection breadcrumb and jump-to-object. This is not an asset/file browser.
- [ ] **Non-destructive visibility tests:** overlapping bodies/wings, skinned meshes and hidden bones; nested isolation and tool/mode switches; assert no persistent hidden or modified objects.

**Ship gate:** a small occluded vertex can be intentionally picked/edited, and a rig can be isolated and restored with identical scene data and original visibility.

### Phase 2 — Complete the mesh-to-rig creator loop (P1)

- [ ] **VR Weight Eyedropper completion:** extend the already delivered **read-only Weight Probe** with explicit `Use Sample as Brush Weight` and optional `Paint Exact`. Sampling itself remains read-only.
- [ ] **Weight editing tools:** Paint/Erase/Smooth with falloff, X-mirror, normalize, limit influences, selected-vertex weight assignment, zero-weight heatmap and locked-group protection; preserve hand-painted groups during cleanup.
- [ ] **Bone-to-group targeting:** point to a deform bone to activate its matching group on the paired mesh, without writing any weights.
- [ ] **Direct IK-assisted limb posing:** grab a hand/foot or endpoint and position the pose via a bounded configurable IK chain and optional pole, with live skin deformation. Never move rest bones unless Armature Edit Mode is deliberately chosen.
- [ ] **Pose safety:** reset selected/full pose, rest/pose comparison, constraint guardrails, cancel and undo; prevent duplicated IK constraints; include non-humanoid and asymmetric limb tests.
- [ ] **VR rig diagnosis:** map missing bone groups and unmatched L/R groups, unweighted vertices, duplicate armature modifiers and deform problems into non-destructive clickable findings.

**Ship gate:** an asymmetric skinned avatar can be sampled, painted, mirrored where valid, physically posed and restored through undo without changed rest data, missing groups or invalid modifier links.

### Phase 3 — Creator-speed tools that use Blender better in VR (P1/P2)

These are **additional proposals identified from missing headset affordances**, not promises of finished features.

| Priority | New VR-native workflow | Why it is not just a duplicate Blender button | First testable slice |
| --- | --- | --- | --- |
| P1 | **Surface Magnet / Smart Placement** | Existing `OBJ_SNAP` is grid-only; move/stamp to a visible surface with normal alignment, collision/penetration preview and adjustable offsets. | Align a shelf prop to a wall without intersecting it; one undo. |
| P1 | **Live placement ghost and repeated stamping** | Keep one selected reusable native object/collection instance on the controller, place multiple copies and rotate in place without re-entering a desktop duplication command. | Place a series of props in a room; no orphan preview objects. |
| P1 | **Measure → Apply** | Measurement exists as a readout; convert measured distances/angles into explicit constrained move/rotate/scale values without editing until confirmation. | Measure two corners, then align an object using that distance. |
| P1 | **Native Cleanup / Repair preview** | Existing audit counts problems, but it does not guide selections through affected topology or show exact proposed corrections. | Highlight non-manifold edges and preview Merge by Distance with a reversible diff. |
| P2 | **Controller-drawn editable curves** | Create actual native Curve splines directly from tracked hand strokes; smooth jitter, preview, edit control points, set bevel/tube thickness and close paths. | Draw one cable in VR, reopen the `.blend` and edit the spline. |
| P2 | **Reference boards and spatial notes** | Position reference imagery/text near a model inside the headset without baking it into geometry or cluttering exports. | Pin a modelling reference and hide/show it per session. |
| P2 | **UV and material targeting overlay** | Current UV commands and material presets are mostly discrete actions; highlight seams/islands and material slots on the model while selecting in VR. | Preview seam boundaries before unwrapping, without altering UVs. |
| P2 | **Collection-based assemblies** | Reuse native Blender collections to select, move, rotate and stamp repeated modular assemblies in world layout. No custom prefab format. | Reposition one room section as a grouped native collection. |
| P2 | **Guided creator actions** | Contextual 3-step hint for unfamiliar mode operations (select → preview → apply), not a permanent tutorial UI or independent workflow engine. | A new user can construct and edit a simple room scene without desktop input. |
| P2 | **XR performance overlay controls** | Optional controller latency, pick/brush timings and overlay simplification while retaining full model detail. | Compare a known dense rigged scene before/after, with traceable measurements. |

**Phase 3 scope rule:** add these to existing Object, Edit, Material/UV, Model and Project contexts. Avoid six new top-level workspaces for six new commands.

### Phase 4 — Deformation and animation (v0.9 after the stable v0.8 gate)

- [ ] Native shape-key creation/rename/duplicate/edit and explicit compatibility with topology-edit restrictions.
- [ ] Save/mirror/reset pose presets; key object, pose bone and shape-key values with a small VR timeline.
- [ ] View/play keyed animation and scrub between frames inside XR.
- [ ] Corrective shape keys and simple axis-linked drivers; stage separately from general rigging stability.
- [ ] Validate save/reopen and exported Blender-native animation data without adding another export system.

### Phase 5 — Possible post-v1.0 creation experience

**Investigate only after a stable headset-verified core.** These ideas provide some
Horizon-style immediacy without turning Blender into another platform:

- **Modular build kit gestures:** wall/floor alignment, scale-to-span and repeat-along-path, implemented as native meshes/Geometry Nodes rather than proprietary world objects.
- **A simple Geometry Nodes control shelf:** expose already defined modifier sockets/inputs on wrist controls, not a full VR node editor.
- **Creator assembly presets:** opt-in native collection templates for common world scenes; any asset shelf or browser remains out of the v0.8 scope.
- **Scene preview walkthrough:** switch between comfortable editor-scale and viewer-scale navigation to inspect a scene without modifying actual scene scale.
- **Optional collaboration/behaviour prototyping:** research separately; do not claim native Blender is a multiplayer game runtime or silently generate Unity/VRChat behaviour code.
- **Future sculpting study:** only after interaction/performance and undo are strong enough; excluded from v0.8.

## 4. Actual development order and dependencies

| Order | Vertical slice | Depends on | Test and merge condition |
| --- | --- | --- | --- |
| 1 | **Stroke-level Weight Paint Undo/Redo** | Existing `paint_vertices`, `mesh.History` | New tests: 1, 20 and 200 samples; undo/redo, missing assignments, interrupt, lock, mode switch. |
| 2 | Single input/action router and tracking rearm | Existing runtime wrappers; stroke transaction state | Non-radial/radial/bridge regressions, no simultaneous input ownership. |
| 3 | Isolation/X-Ray and depth selection | 2 | Session/mode change restores exact visibility and selection; no saved alpha changes. |
| 4 | Precision geometry picking + selection gestures + numeric transforms | 2–3 | Edit tiny loose vertices/edges and precise transforms; undo and cancel. |
| 5 | Scene hierarchy + Surface Magnet placement | 2–4 | Build aligned objects in XR; native collection/lock semantics. |
| 6 | Weight Eyedropper target, group utilities, repair preview | 1–3 | Weighted mesh stays correct, fully reversible, no group loss. |
| 7 | Direct IK posing and reset | 2, 6 | 1/2-bone and asymmetric rig/pose/undo checks. |
| 8 | Curves, repeated stamping, reference board, guided creation | 2–5 | Editable native data, bounded overlay cost and safe cancel. |
| 9 | v0.9 shape keys, pose library, keyframing | Stable v0.8, 7 | Blender animation/mode/save round trips. |

**Each slice:** focused PR → Blender 4.2/4.5/5.0/5.2 Linux validation → Windows/macOS package checks →
manual headset acceptance where relevant → merge to current `main`.
A PR can merge on green automation as **development code**, but **stable v0.8
release** requires physical Quest 3/SteamVR test evidence and no blocking P0s.

## 5. Definition of done for any new feature

- The feature is **not already available in Mesh XR** as the same practical VR interaction.
- It is reachable from a contextual VR menu and is documented with controls.
- It uses native Blender data and does not require desktop-only handoffs.
- It previews valid targets, handles invalid or locked selections, and offers cancel/rollback.
- It has Blender tests for correct edit, miss, error, Undo, Redo and save/reopen where applicable.
- It does not increase redundant files, modules, duplicated actions or permanent UI controls unnecessarily.
- Existing test matrix and extension packaging are green.
- Real headset performance, controller behavior, tracking interruptions and comfort have been separately reviewed before labelling a production-ready stable version.

## 6. No conflation of delivered vs planned work

- **Shipped to `main` as development code:** v0.8 alpha hands/radial work and safe packaging (PRs #20, #22), Quick Layout (PR #23), read-only Weight Probe (PR #24).
- **Still proposed here:** stable input routing, complete Weight Paint stroke history, X-Ray/isolation, full advanced precision picking, controller IK and the Phase 3–5 extras.
- **No new exporter is needed** to implement this roadmap. Use Blender's own save/export workflows.
