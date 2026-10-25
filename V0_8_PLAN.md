# Mesh XR v0.8 — VR-First Workflow and Rigging Completion Plan

**Status:** Proposed specification; no v0.8 implementation or release is implied.
**Baseline:** Mesh XR v0.7.6 merged and published on GitHub, 25 October 2026.
**Mission:** Make Mesh XR feel like Blender operated naturally inside a PC-connected VR headset, with predictable controller interactions and a complete mesh → rig → weight → pose workflow.

> v0.7.6 implemented many *individual* actions. v0.8 focuses on making them cooperate reliably under real tracked-controller input. Do not rebuild or duplicate features just to fill a roadmap checkbox.

## Product rules (non-negotiable)

1. **One action, one control.** One contextual Select button; never add separate Select Mesh, Select Rig or Select Bone buttons. Tools vary by Blender's actual active mode, selection and object type.
2. **Blender owns the data.** Work in native Object, Mesh Edit, Armature Edit, Pose and Weight Paint modes; write real mesh, armature, modifier, constraint and vertex-group data. Do not create a parallel hidden scene state.
3. **Predictable hands.** Trigger selects or operates the active tool; Grip grabs. A deliberate modifier extends selection. A captured gesture cannot also navigate or click the menu.
4. **Visible and reversible.** Preview the affected target and pivot; clear results/miss messages; consistent undo/redo, cancel, and Save. Never overwrite existing painted weights silently.
5. **No junk UI.** Context-specific wrist menu, shared global Mode/Undo/Redo/Save, one source-of-truth action registry. No dead buttons, duplicate aliases in menus or obsolete panels.
6. **Version discipline.** Develop on a v0.8 branch. Preserve the shipped 0.7.6 installation and operator IDs where practical; keep unreleased work out of main until QA.

## What exists in v0.7.6 (build on, do not rebuild)

- Object/Mesh Edit/Armature Edit/Pose/Weight Paint access; contextual selection; controller Move/Scale/Rotate.
- Freeform armature creation, bone editing, basic pose manipulation and mesh/armature pairing.
- Blender Ctrl+P parenting types, bone-named vertex groups and controller-driven weight brush.
- Seven compact desktop workspaces, existing materials/UV/modifier tools, session-local Undo/Redo and Blender 4.2/4.5/5.0/5.2 automated tests.

**Evidence gap:** A successful headless Blender test does not prove OpenXR controller events, on-headset accuracy, display overlays, haptic feel or frame rate.

## Milestone A — Interaction-engine stabilisation (P0, release blocker)

- [ ] Replace the chained runtime `tick`, `select` and `command` monkey patches with a single input/action router and stable, mode-specific tool handlers. Preserve supported extension/operator compatibility.
- [ ] Build one gesture state machine: `idle → hover → select → begin → drag → commit/cancel`. Guarantee exclusive input ownership between menu, navigation, grab, transform and Weight Paint strokes.
- [ ] Centralise action registration, mode guards, icon/tooltip mappings, and wrist-menu availability. Include automated checks for duplicate and unreachable actions.
- [ ] Use Blender's real active selection/mode for decisions. Pair metadata is a fallback, not a substitute for an explicit user selection; changing mesh/rig/mode must not lose editable selection.
- [ ] Accurate picking across overlapping objects, visible armatures, bones, vertices, edges and faces: nearest/depth targeting, selection cycling, optional X-ray for hidden bones and tolerance scaled to controller distance.
- [ ] Controller grabs and Trigger transforms must preserve the starting pivot, orientation, selection and object transform; implement reliable begin/update/end/cancel and tool feedback.
- [ ] Unified undo/redo coverage for transforms, parenting, group editing, weight strokes and supported rig operations. Cancel must roll back fully; interrupted tracking must not leave an active drag.
- [ ] Build an optional *local* bug-report export with tool, mode, headset input profile, add-on/Blender versions and error logs. Do not upload or collect telemetry automatically.

**A is complete when:** 30 consecutive mode-switch and grab/select/undo cycles work on a physical Quest 3 PC-VR setup without unresponsive controls, unintended operations, lost selection or corrupted weight data.

## Milestone B — Blender-quality controller editing and interface (P0/P1)

- [ ] **Single contextual wrist menu.** Always-present Mode, Undo, Redo and Save; contextual tool row for Object, Mesh Edit, Armature Edit, Pose and Weight Paint. Consistent Back behaviour. No duplicated Select or mode buttons.
- [ ] **Precise transforms.** Switch Global/Local/Normal axes; constrain X/Y/Z; choose Median/Individual/3D Cursor/Active pivot; grid and vertex/edge/face snapping with visual indicators.
- [ ] **Numeric entry.** In-headset keypad for exact translation, rotation, scale, extrusion distance, brush strength and weight values. Physical controllers remain usable without numeric input.
- [ ] **Direct editing.** Reliable selected vertex/edge/face grabbing, multi-selection, proportional editing with adjustable falloff (start with connected vertex neighborhoods), and hand-directed Extrude with ghost preview and one-step cancel/undo.
- [ ] **Scene hierarchy.** A small, searchable, filterable Object/Outliner panel in the same menu system: select, hide/show, lock/unlock, rename, set active, collections and parent relations. No second independent object-selection tool.
- [ ] **Visibility and guidance.** Show current Blender mode, active object/bone/group, selected count, active tool, axis/pivot, brush size/strength and concise reasons an action cannot run. Use a brief first-run in-VR tutorial that can be disabled.

**B is complete when:** From the headset, users can accurately edit a cube's individual vertices, extrude a face, rotate by an exact angle, snap an object to geometry, select a different object in the hierarchy and save—all with no mouse/keyboard.

## Milestone C — Production rigging + vertex groups + Weight Paint (P0/P1)

- [ ] **Armature editor:** Consistent selection of head/body/tail; grab and rotate/scale bones; parent/connect/unparent; duplicate, extrude, mirror, symmetry, deform toggle, roll, visibility and naming. Keep exact Blender bone structure.
- [ ] **Parent/deform workflow:** Mesh + armature selection flows into Blender's standard parent types; show what will be parented and whether it uses Auto/Empty/Envelope weights. Preserve transforms and existing painted weights.
- [ ] **Vertex-group manager:** Create, rename, remove, duplicate, lock, select, and choose groups; assign/remove weights from selected vertices; inspect exact weights and number of bone influences. No automatic deletion of unmatched groups.
- [ ] **VR weight brush:** Reliable strokes on visible evaluated/skinned geometry with current active group, explicit Paint/Erase, native weight heatmap, adjustable radius and strength, smooth/blur, falloff and stroke preview.
- [ ] **Weight utilities:** X-mirror, Normalize All, Clean, Smooth, Limit Total/Influences, locked-group respect, clear/reset and optional auto-normalize; show warnings before destructive operations.
- [ ] **Deformation loop:** Pose a bone while viewing its skinned mesh; switch Rest/Pose position; reset selected/all bones and observe weight changes without losing the rig/mesh pairing.
- [ ] **Basic constraints:** Add and remove IK, choose target and chain length, Copy Location and Copy Rotation; enable/disable constraints and show their effect in Pose Mode.

**C is complete when:** A user can create a rig from a non-humanoid mesh, edit bones, parent with empty groups, paint and smooth symmetrical weights, test poses, correct deformations and save the .blend without taking off the headset.

## Milestone D — Quest 3 PC-VR responsiveness and release quality (P0)

- [ ] Performance-profile a representative Quest 3 over Link/Air Link or SteamVR connection on a *documented reference PC*, not standalone Quest Blender.
- [ ] Cache ray/BVH/KD selection structures and update them only when the relevant evaluated geometry changes; avoid rebuilding a vertex tree on every painting sample.
- [ ] Batch/aggregate brush writes and depsgraph/UI refreshes; benchmark complex skinned scenes and normal modelling scenes without compromising correct native data.
- [ ] Minimise VR overlay redraws, unnecessary Python allocations, material/icon reloads and selection rescans per frame.
- [ ] Do not allow dropped tracking, headset removal, interrupted VR session or mode-switch during a stroke to corrupt the scene. Recover controls and preserve the .blend.
- [ ] Add a practical optional comfort/performance panel: frame-time display, brush sample rate, scene complexity warnings and reduced-overlay mode.
- [ ] Retain Blender automated matrix **4.2.0 / 4.5.0 / 5.0.0 / 5.2.2**, plus package install/uninstall/reenable tests and real Windows + Quest 3 input and rendering smoke tests.
- [ ] Validate Touch controller bindings, dominant-hand swap, hand/menu alignment, two-hand scaling, headset mirror and optional SteamVR controller profiles where equipment is available.
- [ ] Require a real-headset QA sign-off before saying controls/painting are fixed or publishing the stable v0.8 release.

**D is complete when:** All CI checks pass; the core end-to-end headset workflows pass with no blocking control failures; benchmark logs show no major frame-time or memory regressions against v0.7.6. Frame-rate targets must be measured on specified hardware rather than claimed universally.

## Sequence and release gates

| Stage | Deliverable | Must pass to move forward |
| --- | --- | --- |
| 0.8-A / alpha 1 | Single input router, shared Select/Grab and interaction tests | Real Quest 3 selection, transformation, cancellation and mode change work repeatedly |
| 0.8-B / alpha 2 | Precision transforms and compact menu/outliner | Edit, snap, type exact values, undo and save entirely inside headset |
| 0.8-C / beta | Full armature/vertex-group/paint/pose workflow plus basic constraints | Mesh-to-rig end-to-end scenario with visible, correct weights and preserved data |
| 0.8-D / RC | Performance, documentation, accessibility, Windows/headset QA | Four-version CI, packaged installer, VR acceptance and no outstanding P0 bugs |
| 0.8 stable | Merge from the test branch and publish | Approved release checklist and verified installer |

## Explicitly out of scope for 0.8 (avoid feature creep)

- Full animation/timeline/shape-key/driver editing: planned for **v0.9**.
- A fully VR-native replacement for *every* desktop Blender editor (e.g. full node editors/Graph Editor): a longer-term aspiration, not a 0.8 promise.
- Full custom IK/FK auto-rigging, mocap, AI-generated rigs, complex physics/retopology tools, and a separate desktop replacement application.
- Extensive new model types or visual themes before core input/painting reliability.
- Hand-tracking-only manipulation until it has a separate, reliable acceptance test; controllers remain the stable default.

## 0.8 headset acceptance checklist

Run from a new Blender scene, with the headset connected to PC Blender:

1. Start/stop/restart the XR session and use menu, travel and both controllers; no frozen input, cursor, stuck tool or leaked overlay.
2. In Object Mode select meshes and armatures with the **same** Select. In Mesh Edit Mode pick a small/loose vertex or edge, add a second selection, grip/move/scale/rotate and Undo/Redo.
3. Use global/local axis and snapping, enter an exact transform, extrude to hand and cancel without topology corruption.
4. Switch Object → Mesh Edit → Object → Armature Edit → Pose → Weight Paint → Object repeatedly. Correct active selection and tool/menu each time.
5. Create a freeform rig, extend bones, choose Blender parenting, enter Weight Paint, pick a bone/group, paint/erase/smooth/mirror, pose the rig and inspect deformation. Repeat parenting without losing weights.
6. Recover from out-of-range controllers, lost tracking and stopping XR mid-transform/paint. The .blend must remain valid.
7. Verify hover/pointer/palette readability, controller comfort, dominant-hand swap, undo feedback, mirrored viewport and expected performance.
8. Install the packaged extension on a clean supported Blender profile, save/reopen the .blend, disable/reenable Mesh XR and compare the edited scene.

## Engineering guardrails

- No new feature-specific Select buttons or hidden/unreachable aliases.
- UI handlers do not directly mutate arbitrary Blender state; they route through checked, testable native operations.
- Maintain backwards-compatible operators and settings where feasible, document migrations otherwise.
- Keep a feature matrix: implemented + headset-tested / implemented but headset-unverified / planned.
- A GitHub Actions green check means **Blender automation passes**, not that a feature has been proven usable on actual XR hardware.
- Each milestone is separately reviewable, tested and reversible; do not merge an entire unstable 0.8 branch directly into main.

The priority order is intentional: **input correctness and performance first; reliable Blender workflows second; extra tool breadth last.**
