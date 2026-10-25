# Mesh XR v0.8 — VR-First Workflow and Rigging Completion Plan

**Status:** Proposed specification; no v0.8 implementation or release is implied.
**Baseline:** Mesh XR v0.7.6 merged and published on GitHub, 25 October 2026.
**Mission:** Make Mesh XR feel like Blender operated naturally inside a PC-connected VR headset, with predictable controller interactions and a complete mesh → rig → weight → pose workflow. Add four targeted VR-native features: reversible Isolation/X-Ray, Weight Eyedropper, direct IK-assisted posing and controller-drawn Blender curves.

**New design-first requirement:** Before implementing v0.8 controller or hand-related functionality, review [the full system audit and tracking/radial design](V0_8_SYSTEM_AUDIT_AND_INPUT_PLAN.md). The hand-display, finger tracking and thumbstick-radial-menu work has a **mandatory capability and input-map research gate**. This document is a plan, not an assertion that those integrations work on Quest 3 PC-VR.


> v0.7.6 implemented many *individual* actions. v0.8 focuses on making them cooperate reliably under real tracked-controller input. Do not rebuild or duplicate features just to fill a roadmap checkbox.

## Product rules (non-negotiable)

1. **One action, one control.** One contextual Select button; never add separate Select Mesh, Select Rig or Select Bone buttons. Tools vary by Blender's actual active mode, selection and object type.
2. **Blender owns the data.** Work in native Object, Mesh Edit, Armature Edit, Pose and Weight Paint modes; write real mesh, armature, modifier, constraint and vertex-group data. Do not create a parallel hidden scene state.
3. **Predictable hands.** Trigger selects or operates the active tool; Grip grabs. A deliberate modifier extends selection. A captured gesture cannot also navigate or click the menu.
4. **Visible and reversible.** Preview the affected target and pivot; clear results/miss messages; consistent undo/redo, cancel, and Save. Never overwrite existing painted weights silently.
5. **No junk UI.** Context-specific wrist menu, shared global Mode/Undo/Redo/Save, one source-of-truth action registry. No dead buttons, duplicate aliases in menus or obsolete panels.
6. **Version discipline.** Develop on a v0.8 branch. Preserve the shipped 0.7.6 installation and operator IDs where practical; use pull requests to merge completed, reviewed and CI-validated milestones into `main`.
7. **No browser or sculpt workspace.** Do not build a VR Asset/File Browser, sculpt mode, or extra selection controls in 0.8. An optional simple in-scene Outliner is not an asset browser.

## What exists in v0.7.6 (build on, do not rebuild)

- Object/Mesh Edit/Armature Edit/Pose/Weight Paint access; contextual selection; controller Move/Scale/Rotate.
- Freeform armature creation, bone editing, basic pose manipulation and mesh/armature pairing.
- Blender Ctrl+P parenting types, bone-named vertex groups and controller-driven weight brush.
- Seven compact desktop workspaces, existing materials/UV/modifier tools, session-local Undo/Redo and Blender 4.2/4.5/5.0/5.2 automated tests.

**Evidence gap:** A successful headless Blender test does not prove OpenXR controller events, on-headset accuracy, display overlays, haptic feel or frame rate.

## Milestone 0 — New hands, finger tracking and radial menu feasibility (design gate)

The user requested **real 3D hands instead of ball-shaped controller indicators**, better hand/finger tracking and a **thumbstick-operated radial menu**. Investigate and decide the technical approach *before implementing* anything.

- [ ] Validate Blender/OpenXR controller state and visual overlay capabilities across supported Blender versions and the actual Quest 3 PC-VR runtime/connection.
- [ ] Design a lightweight left/right skinned hand model, optional estimated finger animations from ordinary Touch inputs, and safe controller/dot display fallback.
- [ ] Measure the SteamVR bridge limitations: its current transport sends only one pinch and aggregate curl per hand, **not** per-joint poses. Prototype a versioned provider plan for per-finger/hand joints with honest estimated/partial/full reporting.
- [ ] Assess native `XR_EXT_hand_tracking` feasibility: runtime support and safe access to hand joints via an actual supported bridge. Do not claim controller-animation equals optical tracking.
- [ ] Prototype **NON-DOMINANT Trigger hold → NON-DOMINANT thumbstick selects one radial wedge → release the same Trigger to activate**. The dominant hand stays free for editing. Recenter to cancel; submenus require recentering. Temporarily suspend locomotion/turning on both sticks while the menu is open, support automatic left/right-handed mapping, and consider pinch-operated fallback where physical thumbsticks are absent.
- [ ] Identify device mapping, gesture overlap, dropped tracking, handedness, joint coordinate and redraw/framerate hazards, with tests and accessibility fallback for the existing ray-driven grid.
- [ ] Choose hand-mesh visual style, wrist/radial anchoring and input thresholds based on headset experiments before feature implementation.

**Gate:** A documented capability matrix, tracked issue/risk list, approved input map, visual hands prototype feasibility result and an implementation sequence. No v0.8 hand/menu work should proceed on unsupported optical-joint assumptions.

**Detailed audit and proposed solutions:** [V0_8_SYSTEM_AUDIT_AND_INPUT_PLAN.md](V0_8_SYSTEM_AUDIT_AND_INPUT_PLAN.md).

## macOS desktop scope (v0.8 integration workstream)

Add support for **macOS Apple Silicon (Blender 5.x)** and **macOS Intel (Blender 4.5 LTS and earlier)** as desktop Blender extension targets. Preserve existing Windows x64 and Linux x64 functionality.

- Do not add Windows ARM64 or mobile/standalone application development as part of this scope.
- Validate packaging **and** Blender registration/UI/mesh/rigging operators on a Mac Intel Blender 4.5 build and an Apple Silicon Blender 5.2 build.
- Distinguish Blender desktop functionality from **real OpenXR headset availability**. macOS preliminary OpenXR starts with Blender 5.1; headset availability, controller alignment, radial selection and finger tracking are unverified until real Mac hardware/runtime tests.
- Track implementation and verification in [PR #20](https://github.com/dedzedofficial/Blender-XR/pull/20) and [macOS platform guide on the development branch](https://github.com/dedzedofficial/Blender-XR/blob/dev/v0.8.0/PLATFORM_COMPATIBILITY.md).

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
- [ ] **Direct editing.** Reliable selected vertex/edge/face grabbing, multi-selection, *box/lasso/brush select* (one shared Select tool with gesture types), proportional editing with adjustable falloff (start with connected vertex neighborhoods), and hand-directed Extrude with ghost preview and one-step cancel/undo.
- [ ] **Precision bubble.** Optional temporary controller-local magnification/target zoom for tiny vertices and bone tips without scaling the actual mesh or saving a distorted model.
- [ ] **Reversible isolation + X-Ray.** See the focused 0.8 feature section. Put both under a single View/Visibility menu; no extra Select buttons.
- [ ] **Scene hierarchy.** A small, searchable, filterable Object/Outliner panel in the same menu system: select, hide/show, lock/unlock, rename, set active, collections and parent relations. No second independent object-selection tool.
- [ ] **Visibility and guidance.** Show current Blender mode, active object/bone/group, selected count, active tool, axis/pivot, brush size/strength and concise reasons an action cannot run. Use a brief first-run in-VR tutorial that can be disabled.

**B is complete when:** From the headset, users can accurately edit a cube's individual vertices, extrude a face, rotate by an exact angle, snap an object to geometry, select a different object in the hierarchy and save—all with no mouse/keyboard.

## Milestone C — Production rigging + vertex groups + Weight Paint (P0/P1)

- [ ] **Armature editor:** Consistent selection of head/body/tail; grab and rotate/scale bones; parent/connect/unparent; duplicate, extrude, mirror, symmetry, deform toggle, roll, visibility and naming. Keep exact Blender bone structure.
- [ ] **Parent/deform workflow:** Mesh + armature selection flows into Blender's standard parent types; show what will be parented and whether it uses Auto/Empty/Envelope weights. Preserve transforms and existing painted weights.
- [ ] **Vertex-group manager:** Create, rename, remove, duplicate, lock, select, and choose groups; assign/remove weights from selected vertices; inspect exact weights and number of bone influences. No automatic deletion of unmatched groups.
- [ ] **VR weight brush:** Reliable strokes on visible evaluated/skinned geometry with current active group, explicit Paint/Erase, native weight heatmap, adjustable radius and strength, smooth/blur, falloff and stroke preview.
- [ ] **Weight Eyedropper.** Sample an individual vertex's active-group weight using the controller, show the exact 0–1 value, set the brush's target weight and optionally apply that sampled value with normal smoothing/lock rules. See the feature section below.
- [ ] **Bone-to-weight selection.** When working on a rigged mesh, point at a deform bone to activate its corresponding vertex group without navigating a long list. Never create or overwrite weights just by selecting a bone.
- [ ] **Weight utilities:** X-mirror, Normalize All, Clean, Smooth, Limit Total/Influences, locked-group respect, clear/reset and optional auto-normalize; show warnings before destructive operations.
- [ ] **Deformation loop:** Pose a bone while viewing its skinned mesh; switch Rest/Pose position; reset selected/all bones and observe weight changes without losing the rig/mesh pairing.
- [ ] **Direct physical posing.** Grip a visible bone endpoint/hand/foot and move the controller to reposition the posed limb via optional IK (rather than editing rest bones); keep ordinary single-bone rotation available. See focused 0.8 feature section.
- [ ] **Basic constraints:** Add and remove IK, choose target and chain length, Copy Location and Copy Rotation; enable/disable constraints and show their effect in Pose Mode.

**C is complete when:** A user can create a rig from a non-humanoid mesh, edit bones, parent with empty groups, sample/paint/smooth symmetrical weights, test poses including basic direct IK drag, correct deformations and save the .blend without taking off the headset.

## Milestone C2 — Four requested VR-native additions (P1; after interaction stability)

### 1. Isolation + X-Ray (P1, early)

- [ ] **Isolate Selection / Restore Scene:** Show only the selected mesh, armature, or explicitly chosen group; support isolating a mesh *with its deforming rig*. One toggle restores exactly the visibility state captured at entry.
- [ ] **X-Ray:** Show armatures/bones or back-side vertices through meshes, with an adjustable overlay opacity and a clear badge/status that X-Ray selection is active. Hidden/occluded picking must be opt-in to avoid accidental rear-side selection.
- [ ] Distinguish **display-through** from **select-through** (two independent states). Avoid modifying render visibility, exporters, object parenting, stored material alpha or saved scene data. Prefer viewport/session-level state; preserve and restore any unavoidable Blender per-object flags.
- [ ] Preserve hide/lock settings that existed *before* isolation. Nested isolates, mode switches, undo, XR session exits and reloads must not leave permanent hidden objects.
- [ ] Test meshes inside overlapping armatures, parented meshes, collections and isolated edit bones. Restore selection and scene without changing .blend geometry.

**Acceptance:** Isolate a rig and its mesh from a cluttered scene, paint weights and pick hidden bones through the skinned mesh, exit X-Ray and isolation and recover the exact original visibility and selection. No scene objects were deleted or made permanently transparent.

### 2. Weight Eyedropper (P1, early)

- [ ] Add **Sample Weight** to the *existing* Weight Paint menu. It acts on the active group; do not create another selection mode or require a duplicated rig select control.
- [ ] Controller ray samples the nearest eligible vertex (or explicit interpolated surface weight, clearly labeled) on the visible, potentially armature-deformed mesh. Display group, sampled weight **0.000–1.000** and exact source.
- [ ] Sampling **must be read-only**. A missing weight is explicitly 0.0, not an exception and not a silent assignment.
- [ ] Set the brush target weight from the sampled value; **Paint Exact** applies it with controlled falloff. Existing additive Paint/Erase continue to work; lock flags, optional auto-normalize and undo must be respected.
- [ ] Avoid sampling from another mesh or vertex group when an armature is rendered in front; test both small low-poly meshes and dense skinned meshes.

**Acceptance:** Sample a vertex with weight 0.35, see 0.350, paint the same value on another vertex, undo/redo, switch groups and prove the original sampled vertex was never modified.

### 3. Direct physical posing (P1, mid-to-late)

- [ ] In **Pose Mode**, grip a visible bone or endpoint, translate/rotate the controller and preview the connected mesh's deformation continuously. Transform *pose bones*, never edit rest positions.
- [ ] Basic IK-assisted drag for end effectors (hand/foot), with a visible target and chain length; configurable pole direction when needed. If no IK chain is configured, use ordinary pose-bone rotation with clear feedback.
- [ ] Provide **Reset Selected**, **Reset Full Pose**, **Rest/Pose Display**, and a non-destructive pose comparison. Respect existing constraints and avoid duplicate constraints after repeated operations.
- [ ] Keep parent-child bone dependencies stable; support undo/cancel and restore pose transforms on tracking loss or mode switch. No keyframes are added unless the user deliberately enables animation in a future version.
- [ ] Include 1-bone, 2-bone and asymmetric non-humanoid rigs in tests; controller direct poses and constraints must update the skinned model.

**Acceptance:** Grab a character's hand, bend the elbow with a controlled IK chain, reposition and release; reset pose; undo/redo the operation and inspect unchanged rest-bone and vertex-group data.

**v0.8 boundary:** Single-limb IK/direct pose, **not** automatic full-body posing, retargeting, physics or an animation editor; those are future work.

### 4. Draw Curves in 3D (P2, late alpha / conditional beta)

- [ ] **Curve Draw tool**: hold Trigger while moving a controller to preview a freehand 3D line, releasing to create an editable native Blender **Curve** object and spline (not a baked mesh).
- [ ] Provide a straight/segmented path and a smoothed freehand spline option; distance-threshold sampling, point-count limit and jitter reduction so noisy controller tracking does not produce thousands of points.
- [ ] Expose curve **thickness/bevel**, resolution, simple cyclic/closed toggle and start/end snap. Allow selection and grab manipulation of control points using the existing Select/Grab pattern.
- [ ] Optional explicit **Convert to Mesh** and a back-out/cancel path; preserve the original Curve unless the user confirms replacement.
- [ ] Support cable/tube/rope-style paths and simple guides; do not implement full sculpting, freehand topology retopology or procedural Geometry Nodes editor.
- [ ] One stroke = one undo entry; live preview stays lightweight and does not create temporary scene objects that survive cancel/session failure.

**Acceptance:** Trace a smooth curved cable around a prop by moving one controller, adjust thickness, move an endpoint, snap to an object, save/reopen and optionally convert to mesh without silently deleting the editable original.

**Schedule guard:** Curve Draw ships in stable 0.8 **only if** interaction stability, rigging, weight sampling and Quest performance gates have passed. If not, keep it on the v0.8 experimental branch for 0.8.x rather than delaying P0 bug fixes.

## Milestone C3 — Tidy-up and modelling cleanup (P1, incremental)

This is a safer, smaller improvement than building a sculpt engine. Put tasks under an existing **Cleanup / Repair** submenu, not another permanent main-toolbar row.

- [ ] **Mesh cleanup with preview:** Merge by Distance with adjustable threshold and counts; Delete Loose vertices/edges; Recalculate Normals; inspect/fix flipped normals; Dissolve Degenerate edges/faces. Each operation clearly states what it will change and offers Undo.
- [ ] **Non-manifold inspection:** Existing asset-audit counts become selectable/highlighted offending elements; warn before destructive geometry fixes. Never auto-fill arbitrary holes or delete faces without confirmation.
- [ ] **Rig cleanup:** Validate missing deform groups, bone naming collisions, unreachable parent links, unmatched left/right groups and duplicated armature modifiers. Suggest fixes but never replace hand-painted weights automatically.
- [ ] **Weight cleanup:** Normalize / Clean / Limit Total, preserve locked groups, display orphan/unweighted vertices and zero-influence spots without inventing weights.
- [ ] **Organisation:** Consistent contextual Rename, Hide, Unhide, Lock, parent breadcrumb, material-slot cleanup, selection count and compact scene hierarchy. The hierarchy is for **objects already in the .blend**, not an asset or file browser.
- [ ] **UI cleanup:** Remove duplicated/dormant labels, stale 0.7.6 draft language, unreachable actions and deprecated help text. Single action registry drives menus, icons, tooltips, input guards and docs.
- [ ] **Performance cleanup:** Cache BVH/KD selection acceleration data by mesh/topology/evaluated state; refresh only when needed; simplify modifier inspections and avoid unnecessary UI redraws during strokes.

**Acceptance:** Run cleanup on a deliberately messy rigged mesh; the preview explains counts and proposed modifications, edits are reversible, no painted weights disappear and the hierarchy/material state remains intact.

## Milestone D — Quest 3 PC-VR responsiveness and release quality (P0)

- [ ] Performance-profile a representative Quest 3 over Link/Air Link or SteamVR connection on a *documented reference PC*, not standalone Quest Blender.
- [ ] Cache ray/BVH/KD selection structures and update them only when the relevant evaluated geometry changes; avoid rebuilding a vertex tree on every painting sample or Curve Draw sampling.
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
| 0.8-0 / research gate | Input audit, 3D hand design, tracked-joint source probes, thumbstick radial prototype | Feasibility decisions, fallback mapping and physical headset input checklist |
| 0.8-A / alpha 1 | Single input router, shared Select/Grab and interaction tests | Real Quest 3 selection, transformation, cancellation and mode change work repeatedly |
| 0.8-B / alpha 2 | Precision transforms and compact menu/outliner | Edit, snap, type exact values, undo and save entirely inside headset |
| 0.8-C / beta 1 | Full armature/weight/pose workflow; isolation/X-Ray; eyedropper and direct IK drag | Mesh-to-rig end-to-end scenario plus isolated and read-only weight sampling |
| 0.8-C2 / beta 2 | Safe Cleanup/Repair; optional controller Curve Draw | Undoable mesh/rig cleanup; editable native Curve strokes if performance gates pass |
| 0.8-D / RC | Performance, documentation, accessibility, Windows/headset QA | Four-version CI, packaged installer, VR acceptance and no outstanding P0 bugs |
| 0.8 stable | Final release approval and publish | Completed milestones in `main`, approved release checklist and verified installer |

## Rendering and control preferences under consideration

- **Hand visuals:** Animated hands by default on compatible controllers; user can choose Hands / Controllers / Pointers / Hidden. Custom hands are rendered into the XR overlay, not as user-scene objects.
- **Finger input:** Estimated controller gestures available first; SteamVR partial fingers if actually reported; optical individual joints only after capability and transform-space proof.
- **Menu:** New radial UI is operated **entirely from the non-dominant hand**: hold its Trigger and tilt its own thumbstick; release to select or recenter to cancel. Automatic hand reversal for left-handed editing. The dominant controller must not be required for menu navigation. Retain the classic ray-button grid for unsupported controllers/accessibility and capture navigation input while the radial is open.
- **Tracking loss:** No guessed transforms or automatic commit. Cancel/restores editing, show state and require neutral rearm before next action.
- **Performance:** No full Blender scene objects to represent hands; batched GPU overlay, safe draw-state restoration, low update overhead, measured frame time on Quest 3 PC-VR.

## Explicitly out of scope for 0.8 (avoid feature creep)

- Full animation/timeline/shape-key/driver editing: planned for **v0.9**.
- A fully VR-native replacement for *every* desktop Blender editor (e.g. full node editors/Graph Editor): a longer-term aspiration, not a 0.8 promise.
- Full custom IK/FK auto-rigging, mocap, AI-generated rigs, complex physics/retopology tools, and a separate desktop replacement application.
- Sculpt Mode / brush-based freeform sculpting or high-density dynamic topology; explicitly excluded from 0.8.
- A VR asset browser / file browser; explicitly excluded. A small in-scene Outliner for currently loaded objects remains in scope.
- Full-body auto-posing / retargeting / automatic character animation; only manual single-limb IK-assisted dragging is in scope.
- Extensive new model types or visual themes before core input/painting reliability.
- Hand-tracking-only manipulation until it has a separate, reliable acceptance test; controllers remain the stable default.

## 0.8 headset acceptance checklist

Run from a new Blender scene, with the headset connected to PC Blender:

1. Start/stop/restart the XR session and use menu, travel and both controllers; no frozen input, cursor, stuck tool or leaked overlay.
2. In Object Mode select meshes and armatures with the **same** Select. In Mesh Edit Mode pick a small/loose vertex or edge, add a second selection, grip/move/scale/rotate and Undo/Redo.
3. Use global/local axis and snapping, enter an exact transform, extrude to hand and cancel without topology corruption.
4. Switch Object → Mesh Edit → Object → Armature Edit → Pose → Weight Paint → Object repeatedly. Correct active selection and tool/menu each time.
5. Create a freeform rig, extend bones, choose Blender parenting, enter Weight Paint, pick a bone/group, **sample a weight without changing it**, paint/erase/smooth/mirror, physically IK-pose one limb and inspect deformation. Repeat parenting without losing weights.
5a. Isolate a mesh and rig, enable see-through and select-through X-Ray independently, edit a hidden bone, then restore exactly the previous scene visibility.
5b. Perform non-destructive cleanup on a deliberately messy mesh/rig and verify preview counts, Undo/Redo and no lost weights. If Curve Draw is enabled, draw, smooth, bevel and edit a native 3D curve then cancel another stroke cleanly.
6. Recover from out-of-range controllers, lost tracking and stopping XR mid-transform/paint. The .blend must remain valid.
7. Verify hover/pointer/palette readability, controller comfort, dominant-hand swap, undo feedback, mirrored viewport and expected performance.
8. Install the packaged extension on a clean supported Blender profile, save/reopen the .blend, disable/reenable Mesh XR and compare the edited scene.

## Engineering guardrails

- No new feature-specific Select buttons or hidden/unreachable aliases.
- UI handlers do not directly mutate arbitrary Blender state; they route through checked, testable native operations.
- Maintain backwards-compatible operators and settings where feasible, document migrations otherwise.
- Keep a feature matrix: implemented + headset-tested / implemented but headset-unverified / planned.
- A GitHub Actions green check means **Blender automation passes**, not that a feature has been proven usable on actual XR hardware.
- Each milestone is independently reviewable, tested and reversible; merge completed milestones to `main` through validated pull requests.

The priority order is intentional: **input correctness and performance first; reliable Blender workflows second; targeted VR extras last.** User-selected extras are Isolation/X-Ray, Weight Eyedropper, Direct Posing and Draw Curves, plus non-destructive mesh/rig cleanup. **No asset browser or sculpt mode.**
