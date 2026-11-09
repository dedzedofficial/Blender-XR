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


## 4. Expanded creator feature catalogue — keep all ideas, ship in safe slices

**Decision (9 November 2026):** Keep **every feature already listed in Phases 0–5**
(including isolation, X-Ray, advanced selection, stroke Undo/Redo, unified input,
IK posing, numeric transforms, Surface Magnet, repeat stamping, scene hierarchy,
Measure → Apply, weight/rig diagnostics, curve drawing, reference boards, UV/material
overlays, collection assemblies, guided workflows, shape keys and animation).
The additions below expand that full set; they do **not** replace earlier work.

**Status vocabulary:** \`MAIN/ALPHA\` means implemented code, but not headset-proven;
\`REQUIRED\` means accepted for a future milestone; \`CANDIDATE\` means worth
exploring and prototyping before assigning a release. A roadmap entry is never
proof that a tool exists. \`P0\` blocks stable release; \`P1\` improves core
production use; \`P2\` is later feature breadth. No blanket claim that every P2
item will fit into one version.

### A. Precision editing and scene interaction (v0.8.x and v0.9)

| Status / priority | Capability to add or finish | Concrete XR behavior / safety test |
| --- | --- | --- |
| REQUIRED / P1 | **Selection sets / recall** | Save/reselect named *native object or edit-element* sets for repeating edits; invalidate deleted indices safely and do not select hidden/locked objects. |
| REQUIRED / P1 | **Cycle-overlap and focus selection** | Point through overlapping meshes, choose next candidate, highlight before activation, frame selection and restore the earlier selection if cancelled. Extends, not duplicates, current overlapping-object picking. |
| REQUIRED / P1 | **Object-and-element snapping** | Grid, vertex, edge midpoint, face, surface normal and object-origin snapping with a visible source/target indicator and safe offset; never unexpectedly alter mesh topology. |
| REQUIRED / P1 | **Origin/pivot placement** | Set origin to geometry, cursor or another picked origin with transform-safe preview; respect parent/constraint limitations and undo as one operation. |
| REQUIRED / P1 | **Multi-object transform** | Move/rotate/scale deliberately selected objects as one group around chosen pivot; preserve world matrices, parents and linked/locked-object guards. |
| REQUIRED / P1 | **Smart duplicate: linked vs independent** | Make the choice explicit in VR; linked duplicates share mesh data, independent clones copy it; protect edits to shared data and show this in the inspector. |
| REQUIRED / P1 | **Proportional editing and falloff ring** | Radius adjustment from controller, affected-vertex preview, connected topology mode, exact commit/cancel and topology-aware performance cap. |
| REQUIRED / P1 | **Quick-edit favorites by context, not custom radial pinning** | Surface recent/valid operations as contextual suggestions without user-managed pinned rings or duplicate Select; capture/locomotion must stay exclusive. |
| CANDIDATE / P2 | **Axis-aligned placement ruler and guides** | Temporarily draw alignment guides, level and normals around selected geometry; default to non-exported overlays. |
| CANDIDATE / P2 | **Mirrored editing preview** | Preview symmetric mesh/bone edits across a chosen plane and reject non-matching selections rather than silently damage asymmetrical designs. |

**Gate:** tiny/overlapping vertex selection and group transforms work in headset
with correct lock behavior, frame time and one Undo per committed gesture.

### B. More powerful real mesh modelling, without reimplementing Blender (v0.9)

| Status / priority | Capability | XR implementation target / test |
| --- | --- | --- |
| REQUIRED / P1 | **Bridge Edge Loops and Fill** | Select two compatible loops, preview segment count and twist, create native BMesh faces, undo once; fail safely for incompatible loops. |
| REQUIRED / P1 | **Edge Slide / Vertex Slide** | Direct controller slider follows valid mesh edges; constrained preview, cancel and symmetry-safe handling. |
| REQUIRED / P1 | **Inset/Extrude improvements** | Extrude to controller target with normal, axis and numeric constraints, plus face-individual vs region modes; ghost topology only becomes real on commit. |
| REQUIRED / P1 | **Knife / Cut Path in VR** | Draw a bounded cut over mesh polygons with preview and intersections; reject invalid/non-manifold cuts and avoid leaving loose fragments on cancel. |
| REQUIRED / P1 | **Bevel/Chamfer control** | Live width/segments/affect-vertices selection, accurate generated topology counts, one Undo, avoid duplicated desktop modifier controls. |
| REQUIRED / P1 | **Geometry cleanup report → selectable problems** | Detect non-manifold edges, internal faces, loose vertices, degenerate areas, flipped normals, duplicate vertices and long thin triangles; highlight offenders, preview repair and never automatically delete faces. |
| CANDIDATE / P2 | **Retopology-over-surface tools** | Draw a poly strip, new quad patch or edge flow over an existing high-poly reference; preview face count and snapping, keep source mesh unchanged. Avoid promising automatic perfect retopology. |
| CANDIDATE / P2 | **Topology flow and symmetry inspector** | Show quad percentage, triangle density, silhouette deviation and left/right topology differences; perform diagnostics before suggesting explicit fixes. |
| CANDIDATE / P2 | **Selective decimate / LOD preview** | Report triangle reduction vs silhouette/UV/material/weight impact in a preview; non-destructive modifier or explicit duplicate output, never silent loss of shape keys. |
| CANDIDATE / P2 | **Geometry Nodes parameter shelf** | Only expose *existing named modifier inputs* as XR sliders, no new proprietary node graph; modifier socket types checked per Blender version. |

**Preservation rule:** the topology-changing commands must reject or explicitly
stage meshes with shape keys, linked mesh data, unhandled custom attributes or
unsafe weight/UV restoration. A report or preview is acceptable before a safe
implementation; never promise to preserve all arbitrary attributes if the code
cannot prove it.

### C. Character/avatar production and quality control (v0.9+)

| Status / priority | Capability | XR behavior / guardrail |
| --- | --- | --- |
| REQUIRED / P1 | **Weight stroke replay/smoothing and mirror** | Alongside atomic strokes, provide controlled blur/normalize/mirror, group locks and symmetry-axis diagnostics; absent weights remain absent after Undo. |
| REQUIRED / P1 | **Rig and bone symmetry tools** | Preview matching L/R bones and copy or mirror an *explicit selection*, preserving intentional asymmetry and parent hierarchy. |
| REQUIRED / P1 | **Bone roll, chains and naming helpers** | A native-armature editing shelf to inspect/adjust roll, connected parenting, deform toggles and symmetry names; one history entry per operation. |
| REQUIRED / P1 | **Heatmap of influences and unweighted vertices** | Overlay the active bone's weights, gaps, excessive influences and locked groups without changing groups; clickable vertex diagnostic list. |
| REQUIRED / P1 | **Pose shelf and limb endpoints** | Pose snapshot/compare, reset selected/all, IK/FK handling limited to existing/native Blender constraints, and reversible VR controller hand/foot drags. |
| REQUIRED / P2 | **Shape-key sculpt-like vertex editing without Sculpt Mode** | Create Basis and corrective keys; manipulate selected vertices directly in Mesh Edit with keys, without applying invalid topology operations. |
| CANDIDATE / P2 | **Viseme/blink/blendshape audit** | Compare requested names and ranges to actual Blender shape keys, flag missing/misnamed entries; do not auto-create quality-sensitive expressions. |
| CANDIDATE / P2 | **Rig deformation stress preview** | Test extreme but bounded poses and highlight mesh intersections, stretching or unweighted deformation without changing saved rest pose. |
| CANDIDATE / P2 | **Avatar platform checks** | Read-only target presets for VRChat/Unity or general PC/mobile budgets: poly count, material slots, textures, transparency, bones, influences, missing textures and performance warnings. Treat all third-party limits as versioned configuration, not universal truths; **do not build another exporter**. |

**Gate:** test a human and an asymmetric creature rig, make edits, mirror only
intentional data, save/reopen and compare native groups, UVs, rest bones and
modifiers against the pre-edit snapshot.

### D. Horizon-style world/scene building inside Blender (v0.9–v1.x)

| Status / priority | Capability | XR creator scenario / implementation rule |
| --- | --- | --- |
| REQUIRED / P1 | **Surface Magnet and collision-aware placement** | Controller ghost snaps a selected mesh to surfaces, optionally aligns with surface normal, applies an editable offset, warns on intersection and commits one native object transform. |
| REQUIRED / P1 | **Repeat Stamp / linked instance option** | Copy an object or selected assembly with trigger presses and predictable previews; choose linked vs full-copy before stamping; undo each placement or the entire confirmed batch. |
| REQUIRED / P1 | **Modular snap connectors / kit dimensions** | Opt-in floor, wall, corner and doorway anchor gizmos with verified dimensions and grid units. Connectors are ordinary transforms or visible named empties, not proprietary geometry. |
| REQUIRED / P1 | **Collection assembly manipulator** | Pick loaded collection instances and move/rotate/duplicate as coherent modules; do not break existing parent/collection link graphs. |
| REQUIRED / P1 | **World scale and eye-height review** | A non-destructive player-scale mannequin or calibrated overlay and comfortable walk/fly view, with accurate meter/Blender unit readout; must not rescale the user's scene silently. |
| REQUIRED / P1 | **Scene bookmarks / teleport for editing** | Save creator-facing navigation viewpoints, snap view to focus/object, and restore prior location; do not leave camera or viewport objects in export by default. |
| CANDIDATE / P2 | **Repeat along path / radial array builder** | Drive native Array/Curve/Geometry Nodes controls through a compact VR interface and allow reverting to editable sources. |
| CANDIDATE / P2 | **Architectural quick construction** | Draw a measured floor outline, extrude walls to a chosen height and cut door openings with normal mesh/curve operations; preview first. |
| CANDIDATE / P2 | **Room readability / layout check** | Inspect passage width, reachability by walking/teleport mode, prop density and eye-level occlusion as visual warnings, not simulated gameplay or pathfinding guarantees. |
| CANDIDATE / P2 | **Lighting and camera composition handles** | Reposition native light/camera targets from VR, preview what the viewport can display, maintain Blender-native render settings. |
| CANDIDATE / P2 | **Native text/labels and spatial guides** | Place editable Text and Curve objects with compact text entry, choose whether helper labels are temporary overlay or intentional scene content. |
| CANDIDATE / post-v1.0 | **Behaviour/prototype nodes** | Research a constrained, declarative, optional scene-interaction preview later. Blender XR is not a game runtime; do not claim Unity, VRChat or Horizon scripting interoperability. |

**Gate:** build a simple room with aligned surfaces, repeated props and one
editable collection from headset controls only. Save/reopen with native meshes,
collections and modifiers intact; no unexplained helper clutter.

### E. Materials, textures and visual authoring (v0.9+)

| Status / priority | Capability | What is materially missing vs existing color/UV tools |
| --- | --- | --- |
| REQUIRED / P1 | **Material slot selection on the model** | Aim at a face or slot and inspect or assign the native material without mouse selection; show linked/shared material implications. |
| REQUIRED / P1 | **PBR texture channels** | Compact mappings to existing Blender node properties for base colour, roughness, metallic, normal and emission, with missing-asset warnings. Keep actual Blender material/node data and existing files. |
| REQUIRED / P1 | **UV seam/island live preview** | Highlight current seam boundaries, island orientation, distortions and texel-density hints in headset; explicit unwrap/smart UV/pack calls preserve original when cancelled. |
| CANDIDATE / P2 | **Material/texture sampling** | Point at a surface to sample the material/slot and optionally apply it to another mesh/face with a preview; does not copy arbitrary shader graphs blindly. |
| CANDIDATE / P2 | **Decal/sticker placement** | Snap a native plane/decal geometry overlay to a surface with offset and orientation while preserving original UVs; be explicit about transparency/performance cost. |
| CANDIDATE / P2 | **Texture-path audit and relink assist** | Check broken packed/external images and offer Blender-native per-image relink rather than an intrusive new asset browser. |
| CANDIDATE / post-v1.0 | **Full shader/node editor** | Feasibility research only after complete simple materials and input stability; Blender's node graph remains authoritative. |

### F. Comfort, learning and accessibility (cross-cutting)

- [ ] **Seated/standing and left-/right-handed profiles (P1):** accessible controls, calibrated hand offsets, adjustable interaction reach, gesture dead zones and one-hand fallback where possible.
- [ ] **Scale-aware editing mode (P1):** world-scale review vs tiny-object work; changes affect XR navigation/view only, never scene geometry or imported armature scale.
- [ ] **Haptic and readable feedback (P1):** subtle selectable haptic patterns for grab/commit/error, clear text sizes and colour-independent highlighting for selected/locked/invalid targets; no hidden auto-apply.
- [ ] **Undo history visibility (P1):** recent user-readable edit names, grouping and warnings when Blender-global undo cannot safely be mixed with private XR history.
- [ ] **Context help / first-session onboarding (P2):** short tasks for object select, edit mesh, paint weights, pose bone, build room; fully dismissible and never blocks skilled users.
- [ ] **Safe voice commands (CANDIDATE):** optional, local where practical, with preview/confirmation for mutation; not a dependency and not a replacement for accessible controller operation.
- [ ] **Session focus / anti-nausea options (P1):** snap vs smooth turn, comfort vignette where supported, adjustable motion speed and safe stationary editing mode; measured on real headsets.
- [ ] **Control-map diagnostics (P0):** show the currently captured action, raw vs processed hand state, controller availability and neutral-release requirement without recording motion or transmitting telemetry.

### G. Engineering, maintainability and performance (must accompany all phases)

| Status / priority | Improvement | Check / safeguard |
| --- | --- | --- |
| REQUIRED / P0 | **Single command registry and input router** | One action identifier drives permission/valid-mode checks, menu label, icon, tooltip, XR dispatch, desktop adapter and testing. Replace wrappers gradually, never one giant unsafe rewrite. |
| REQUIRED / P0 | **History correctness audit** | Inventory mutating paths (including material slots, parenting, rig constraints and weights) and explicitly mark atomic Undo/Redo, Blender global undo only, or read-only. Never silently drop history. |
| REQUIRED / P0 | **Scene-data integrity tests** | Compare mesh vertices/UV layers/attributes, shape keys, material links, vertex-group assignments, parenting, bone transforms and modifiers before/after cancel/undo/save-reopen. |
| REQUIRED / P0 | **VR input trace and deterministic replay tests** | Synthetic packet playback of offhand menu capture, selection, grabs, cancellation, hand loss and rearm with controlled time; optional local debug log with privacy-by-default. |
| REQUIRED / P0 | **Install/uninstall and migration tests** | Preserve old Blender settings/Operator IDs, recover from partial installation, avoid duplicated handlers/timers and verify repeat enable/disable across Blender versions. |
| REQUIRED / P0 | **Real headset acceptance matrix** | Quest Link/Air Link, SteamVR where available, controller tracking, actual radial input, dominant swap, eye-height, hand model and latency measured on stated hardware. macOS desktop CI is not XR headset certification. |
| REQUIRED / P1 | **Spatial acceleration cache invalidation** | BVH/KD trees tied to topology, deformation and current evaluated geometry so editing/different mesh picks cannot use stale spatial information. |
| REQUIRED / P1 | **Dynamic scene performance warnings** | Live triangle/material/texture and action-latency summaries when user requests them, low-overdraw overlays, no automatic destructive decimation or visual quality changes. |
| REQUIRED / P1 | **Bounded auto-recovery verification** | Simulate write failure, low disk space, XR shutdown, abandoned stroke, disabled checkpoints and recovery-as-new; never overwrite an original project. |
| CANDIDATE / P2 | **Feature flags and rollback switches** | Independently disable alpha IK, curves, optional overlays or new selection modes without downgrading the entire extension. |
| CANDIDATE / P2 | **Scene test fixture library** | Small quad props, dense avatar, distorted UV mesh, multi-material building, asymmetrical bones, corrupted weights and occluded scenes; keep fixture assets license-safe and compact. |
| CANDIDATE / P2 | **File/asset bloat review** | Remove unreachable menus, deprecated patches and duplicated docs only after automated proof and after preserving stable compatibility. Never equate fewer lines with fewer defects. |

### H. Capability priority and edition boundaries

| Release horizon | Required delivery intent | Explicitly deferred |
| --- | --- | --- |
| **v0.8 stabilisation** | Weight Paint atomic undo, exclusive VR input, recoverable edits, exact XR mode/selection handling, basic Isolation/X-Ray and precision interaction where safety gates pass. | Large new modelling suites, full sculpting, standalone Quest and multiplayer runtime. |
| **v0.8.x / v0.9** | Full eyedropper/weight editing, bone selection, IK single-limb drag, surface snapping, object/collection hierarchy and creator scene layout; expand UV/material and native geometry tools in tested vertical slices. | Unverified live collaboration, full node editors, automatic perfect retopo or universal game-engine behaviour system. |
| **v0.9 / v1.0** | Controller-drawn curves, repeat stamping, modular assembly, shape keys, pose presets, exact transforms, cleanup/reports and a complete headset-operable creation loop. | Feature work that would prevent first achieving reliable real-headset use. |
| **After v1.0** | Consider advanced retopology, node-editor interaction, optional scene prototyping, sculpt, physics previews and collaboration **only** with benchmarks, explicit user priority and native Blender data model. | No obligation to ship every candidate: research may reject unsafe/duplicative ideas. |

**Highest-value UX target:** within a headset, a creator should be able to
**(1) build a room, (2) duplicate and snap props, (3) isolate and edit a mesh,
(4) paint and inspect a rig's weights, (5) pose a limb, and (6) undo/recover
every operation**, all without taking off the headset or sacrificing native
Blender editability.

## 5. Actual development order and dependencies

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

## 6. Definition of done for any new feature

- The feature is **not already available in Mesh XR** as the same practical VR interaction.
- It is reachable from a contextual VR menu and is documented with controls.
- It uses native Blender data and does not require desktop-only handoffs.
- It previews valid targets, handles invalid or locked selections, and offers cancel/rollback.
- It has Blender tests for correct edit, miss, error, Undo, Redo and save/reopen where applicable.
- It does not increase redundant files, modules, duplicated actions or permanent UI controls unnecessarily.
- Existing test matrix and extension packaging are green.
- Real headset performance, controller behavior, tracking interruptions and comfort have been separately reviewed before labelling a production-ready stable version.

## 7. No conflation of delivered vs planned work

- **Shipped to `main` as development code:** v0.8 alpha hands/radial work and safe packaging (PRs #20, #22), Quick Layout (PR #23), read-only Weight Probe (PR #24).
- **Still proposed here:** stable input routing, complete Weight Paint stroke history, X-Ray/isolation, full advanced precision picking, controller IK and the Phase 3–5 extras.
- **No new exporter is needed** to implement this roadmap. Use Blender's own save/export workflows.
