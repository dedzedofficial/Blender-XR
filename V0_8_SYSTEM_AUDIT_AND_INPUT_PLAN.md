# Mesh XR v0.8 — Deep System Audit, 3D Hands, Finger Tracking and Radial UI

**Status:** Research and design proposal — **no feature implementation authorised by this document**.  
**Audit date:** 25 October 2026.  
**Code inspected:** `dev/v0.8.0` at the start of this audit; based on the released 0.7.6 code.  
**Related requirements:** [V0_8_PLAN.md](V0_8_PLAN.md) · [ROADMAP.md](ROADMAP.md) · [Implementation issue #19](https://github.com/dedzedofficial/Blender-XR/issues/19).

## Product objective

Replace the feeling of a flat button grid plus controller spheres with a coherent VR editor: **comfortable animated hands, trackable fingers where realistically supported, one gesture dispatcher and a fast thumbstick radial menu**. Keep direct mesh and bone editing, native Blender data, performance, input discoverability and reliable controller fallback. **No sculpting and no VR asset browser.**

**Decision boundary:** This is *planning, feasibility and issue discovery*, before starting runtime or UI code. Approve a concrete control map and complete a headset-level feature probe before changing the controller engine.

## Current architecture (code-backed)

| Subsystem | Implementation today | Key observation |
| --- | --- | --- |
| Input profiles | `blender_xr/actions.py` | Own OpenXR action set with grip/aim poses, trigger, squeeze/grab, per-hand 2D thumbstick, thumbstick click and optional touch. Profiles Touch, Index, Vive, simple. |
| Interaction controller | `blender_xr/runtime.py` | Samples actions; derives rays from aim poses; assigns offhand trigger to menu toggle; left physical stick to move and right physical stick to turn/lift; grip may navigate or grab object. |
| Versioned patches | `blender_xr/__init__.py`, `v05.py`, `v056.py`, `v060.py`, `v065.py`, `v071.py`, `armature_v076.py`, `rigging_v076.py`, `interaction_v076.py` | Multiple wrappers change `Runtime.tick/command/select` and menu definitions. Hard to reason about event ownership, controller state and cross-mode regressions. |
| Hand visuals | `runtime.py`, `drawing.py` | `XrSessionSettings.show_controllers=True` and overlay pointer/gizmo; no Mesh XR custom GPU skinned hand or joint-pose animation is implemented. User describes visible controller indicators as balls. |
| Existing menu | `drawing.Menu`, `menus.py`, `v065.py` | Flat two-column, up-to-12+ rows, billboard panel positioned by offhand grip, selected by dominant ray+trigger; icon and tooltip patches layered on it. |
| Finger shortcuts | `gestures.HoldGesture` and `actions.touch` | Holds two touch sensors for 0.7s to trigger hide/cancel shortcuts; **not joint tracking**. |
| SteamVR bridge | `steamvr_hand_bridge.py` + `gestures.HandBridge` | Reads skeletal bone data, then sends only **pinch distance and one average curl** for each hand as authenticated loopback UDP. No full skeleton gets to Blender. Bridge inputs replace trigger/grab and disable stick navigation. |
| Geometry tools | `mesh.py`, `interaction_v076.py`, `armature_v076.py` | Direct grip/trigger transforms and native mode selection exist; the new dispatcher must preserve their behaviour and safety. |
| Weight brush | `rigging_v076.py` | Rebuilds a KD-tree for each paint call; per-stroke mesh/depsgraph refresh and raycasts may be expensive for dense models. |
| Render overhead | `drawing.draw` | Builds selected-geometry line vertices during XR drawing; monitor cost for dense selections and high scene complexity. |
| Testing | `tests/test_gestures.py`, `test_interaction_v076.py`, 4-version CI | Protocol/math/unit tests and Blender headless tests; there is no captured real-controller replay or headset framerate/latency acceptance harness. |

### Important risks and likely defect candidates to verify

1. **Multiple sample paths per frame.** The top-level controller tick and later interaction wrappers may read the SteamVR bridge in separate places. `interaction_v076.tick` directly indexes `self.bridge.read()[self.dom]` in a grip check; stale data can return `None`. Add a single per-frame validated input snapshot and test stale packets.
2. **Menu/navigation conflict.** Physical left thumbstick translates the user; physical right thumbstick turns/controls lift, with right stick click for boost. A thumbstick radial menu must *capture* the stick and suppress locomotion for the entire menu interaction, not just while highlighting a wedge.
3. **Inconsistent hand capabilities.** Current SteamVR code refuses `estimated` tracking entirely; that intentionally avoids false claims, but makes the finger bridge unusable on some Touch-only configurations even for cosmetically estimated poses. Tracking quality and permission/capability reporting should be distinct from whether hands can be drawn.
4. **Bridge contains insufficient data.** Current protocol (`v=1`) carries `pinch/curl` but no per-finger curls, splay, wrist pose, 26-ish joints, per-joint validity or timestamps. Changing the hand model alone cannot add full articulation.
5. **Hardcoded physical-stick routing.** Dominant-hand preference swaps primary editing hands, but locomotion remains assigned to left stick and turning to right. Radial interactions need explicit physical-device and logical-hand mappings.
6. **Loss/reconnection safety.** Controller state, bridge data and menu states need neutral-release rearming on tracking loss, session focus changes and headset/controller handoff; never trigger a stale click or commit a transform when data disappears.
7. **Native tracking feasibility.** Blender Python XR APIs clearly expose controller aim/grip and action states, but full OpenXR joint access is *not established* through supported Blender Python bindings. Do not assume direct `XR_EXT_hand_tracking` calls can attach to Blender's owned OpenXR session. Test capabilities and an external bridge first.
8. **Visual feedback may conflict with built-in controller overlays.** Custom hands plus `show_controllers=True` can display both hand meshes and dots/controllers; hiding native indicators must retain ray alignment, pointer affordances and headset comfort.

## Design A — Hand appearance (highest confidence, high user value)

### Recommended first implementation: lightweight, selectable hand avatars

- A left and right **rigged low-poly hand mesh** with recognizable palm, thumb and four fingers, in a neutral VR-friendly style. Support optional simple glove style and neutral tones.
- Use **GPU/XR overlay rendering** rather than adding Blender objects to the user's scene. The hands must not appear in exports, object selection, asset audits, modifier stacks or scene collections.
- Use controller **grip pose** for hand root and **aim pose** only for the ray/pointing direction. Calibrate orientation and distance separately for each controller family and handedness. Do not assume a Quest 3 controller center is the wrist joint.
- Animations when only controllers are connected: Idle/Open → Point (trigger released) → Pinch (trigger squeeze) → Grasp (grip squeeze) → Menu (relaxed/point) → Manipulate (held object).
- Smooth joint animation over a short time window with bounded easing to avoid snapping and visible lag; do **not** smooth the actual pick ray or rigid transform enough to compromise precision.
- Optional tool hints on the hand (one unobtrusive trigger/grip cursor) and a small visible pointer highlight at the fingertip/ray target.
- Hand-display options: **Hands / Controllers / Minimal Pointers / Hidden**, user-adjustable scale/offset and left-right calibration. For controllers, hand animations are **estimated**, not true tracked joints.
- Disable or replace Blender's default controller/ball indicator while custom hands render, where supported, to avoid duplicate ghost hands; preserve fallback if GPU shaders or XR draw handlers fail.
- Requirements: paired render model from both eye views, no scene contamination, proper mirrored handedness and palm orientation, overlay restoration after restart, low mesh draw cost.

### Joint data quality tiers and capability matrix

| Input mode | Data available | Visual hand behavior | Manipulation controls |
| --- | --- | --- | --- |
| Standard Quest Touch controllers | grip/aim, trigger, squeeze, touch where available | **Animated approximation**, finger curl from buttons/touch | Trigger / Grip; fully supported without bridge |
| Valve Index/Knuckles via SteamVR | SteamVR skeletal joints / finger curl, quality marked as partial when applicable | Articulated fingers mapped to native hand skeleton | Existing Grip/Trigger; optional pinch gestures after tuning |
| Supported optical hands from runtime or bridge | Per-joint positions/orientations with tracking validity | Fully articulated fingers when real joint stream is available | Pinch select, palm-menu gestures with confidence and hysteresis |
| Unsupported/untracked/disconnected | No reliable joint data | Fall back to controller hand or minimal pointers | No unexpected auto-click; show tracking-lost and neutral-rearm state |

**Do not equate controller-estimated finger animations to optical finger tracking.** Quest 3 standalone camera hand tracking does not automatically mean PC Blender over Link/Air Link provides the same joints.

## Design B — Upgrade the tracking pipeline (feasibility spike before coding)

1. Inventory runtime capabilities in **Blender 4.2, 4.5, 5.0, 5.2** and actual PC runtime choices (Meta Quest Link, SteamVR, Steam Link, Virtual Desktop if available).
2. Prefer Blender-supported grip/aim actions for controller transforms. For joint streams, attempt a **read-only, out-of-process, documented interface** to an active XR/SteamVR runtime. If no compatible source is available, show an honest unavailable state; do not quietly simulate 'full tracking'.
3. Upgrade SteamVR bridge sampling to return a structured **skeletal hand frame**, not just pinch/curl: wrist pose, per-finger curl/splay, joint positions/rotations when valid, tracking grade (estimated/partial/full), timestamp, handedness, confidence or joint-validity flags and explicit pose reference frame.
4. Keep existing legacy `v1` pinch/curl bridge protocol as fallback; create a separately versioned `v2` message. Avoid unsafe arbitrary JSON if it exceeds UDP datagram caps; use bounded typed/binary packets or properly framed local IPC, finite-value validation and strict length/sequence limits.
5. Normalize coordinate conventions and handedness: SteamVR skeleton's local pose basis ≠ Blender world coordinates. Establish a calibration transform against Blender's current XR navigation/reference space.
6. Sample **one immutable input frame per hand per renderer tick**, even when several tools need gesture state. No multiple socket drains/read calls during a gesture. Keep a short staleness threshold and release/rearm rules.
7. Security: local-only transport, unguessable session key, strict schema+range validation, monotonic sequence/time, no persistent networking, no sending hand data to an external service, clean bridge shutdown. Never create Blender-threading/socket workers inside the extension without extension policy assessment.
8. Investigate native OpenXR `XR_EXT_hand_tracking` / `XR_EXT_hand_interaction` **as optional future backends only** after proving runtime supports extensions and that a safe documented bridge can access joints. Don't inject native code into Blender's internal XR session through unsupported handles.
9. Opt-in gesture vocabulary at first: **pinch select / pinch hold drag / open-hand release**, with thresholds, independent left/right validity, confidence gates, 150–300ms debounce candidates and a dedicated calibration/test screen. Never let a pinch gesture unexpectedly click a menu and move geometry simultaneously.

**Hard gate:** Get actual per-joint data from a working Quest/SteamVR reference session and reliably transform to Blender XR coordinates *before* marking full optical hand tracking implemented. If runtime support is absent, ship controller hands + partial SteamVR fingers and record optical hands as a capability-limited future task.

## Design C — Thumbstick radial menu (preferred UI)

### Proposed mechanics

- **Menu-open input:** **hold offhand Trigger** to show a menu at the offhand wrist/hand (replaces current trigger-toggle option when radial mode is enabled). This works on Touch without extra reserved buttons.
- **Navigation input:** while that hold is active, the **dominant-hand thumbstick** selects a wedge using its angle. This temporarily disables *dominant-stick turning/lift/boost*; disable both movement and turning during the menu hold to remove unintended navigation or floating while browsing.
- **Activation:** rotate stick past outer deadzone → highlight wedge; release **offhand Trigger** while a wedge is valid → activate exactly once. Keep the stick neutral on release → close without action. If controller tracking is lost or any operation already owns input → **cancel**, not activate.
- **Submenus:** categories expand into another radial ring/page while the menu is held. The user can flick to the category, return stick to neutral to arm the next selection, then flick to an option. Include **Back** as a consistent wedge. Avoid more than 8 items per ring.
- **Suggested sectors:** 8 directions; at most 6 common actions plus Back/More in mode-specific rings. Persistent status in the center indicates the current mode/tool/selection and input hint; avoid long labels covering a neighboring wedge.
- **Hysteresis:** first-choice entry deadzone ~0.55 normalized radial distance, a lower hold/exit threshold ~0.40, angular boundary hysteresis ~8–12 degrees; tune on real controllers, not fixed magic values. Sampling between neighboring sectors should never trigger a double click.
- **Physical thumbstick clicks:** do not depend on clicking the stick to activate a wedge; physical click remains optional backup or precision confirm with clear user preference. Use release-to-select by default after usability testing.
- **Optional Quick Favourites ring:** user can pin a handful of actions from current mode without duplicating the action or creating another Select tool.
- **Modes:** Object, Mesh Edit, Armature Edit, Pose, Weight Paint. Common Undo/Redo/Save/Mode always reachable from utility ring or a single common area; categories only show actions valid in current Blender mode.
- **Alternative interactions:** no-thumbstick optical hand tracking uses palm-facing menu with index aim/pinch selection and the same state/router; a fallback **ray-operated classic grid** remains for Vive trackpad/simple controllers and accessibility.
- **Accessibility:** left-handed edit grip maps logical dominant/offhand explicitly; ability to invert thumbstick menu assignment or move to accessible side, increase size, switch to high-contrast color/icon/label, toggle menu open strategy and use classic menu.
- **Visual anchor:** default follows offhand while initial hold opens, then stabilizes with mild filtering; do not let hand jitter rotate the active sectors. Design for comfortable reading distance without requiring an awkward wrist pose.

### Radial selection input state machine

```text
NORMAL_EDITING
  └─ offhand trigger press (no active edit) → RADIAL_OPEN
RADIAL_OPEN
  ├─ dominant stick in deadzone → no selection (cancel on release)
  ├─ valid wedge direction → RADIAL_PREVIEW
  └─ tracking lost / cancellation → NORMAL_EDITING, no action
RADIAL_PREVIEW
  ├─ move between wedges → update highlight with hysteresis
  ├─ category wedge → RADIAL_SUBMENU (require neutral recenter)
  ├─ release opener on actionable wedge → DISPATCH_ONCE → NORMAL_EDITING
  └─ release opener at center / tracking loss → CANCEL
RADIAL_SUBMENU
  ├─ stick returns neutral then chooses final wedge
  ├─ Back wedge → parent ring
  └─ release opener on command → DISPATCH_ONCE
```

**Design conflict:** offhand trigger currently toggles the panel, while offhand grip may navigate/scale and dominant stick participates in turning/lift. Build an explicit **input arbitration/capture system** and decide gestures in one place. A popup drawn but not capturing navigation is not acceptable.

### Suggested ring information architecture

| Ring / Blender mode | Main slots (examples, not all commands) | Secondary ring |
| --- | --- | --- |
| Always reachable | Select, Mode, Undo, Redo, Save, More | Common utilities, Visibility, Help |
| Object | Select, Grab/Move, Rotate, Scale, Parent, Add, More, Back | Transform precision, collections, visibility |
| Mesh Edit | Select, Move, Rotate, Scale, Extrude, Geometry, More, Back | Vertex/Edge/Face mode, Bevel, Inset, Duplicate, Cleanup |
| Armature Edit | Select, Move Bone, Rotate, Extrude Bone, Parent, Bone Operations, More, Back | Symmetry, Roll, Naming, Visibility |
| Pose | Select, Move/Rotate, Direct IK, Reset Pose, Constraints, More, Back | Chain/Target, Pose/Rest view |
| Weight Paint | Paint, Erase, Smooth, Eyedropper, Group, Radius/Strength, More, Back | Mirror/Normalize/Clean/Limit influences |

**UI alternative worth prototyping:** place the radial menu around the *dominant* controller thumbstick rather than floating above the wrist. Both designs share the same selection logic; evaluate legibility and hand occlusion in the headset before locking the visual anchor.

## System architecture target

```text
OpenXR Touch/Index/Vive inputs ─┐
SteamVR skeletal hand frames ──┼─> HandTrackingProvider
Optical hand provider (optional)─┘   normalized two-hand frame
                                   ↓
                              InputFrameSampler
                              one sample / XR tick
                                   ↓
                GestureRouter / priority + capture ownership
               ┌─────────────┬──────────────┬──────────────────┐
          Radial/Menu      Locomotion      Blender editing
          state machine    and comfort     tool state machine
               └─────────────┴──────────────┴──────────────────┘
                                   ↓
                         Native Blender operations
                         transform, edit, paint, pose
                                   ↓
                           Scene-local history / undo

One shared HandRenderer + PointerRenderer + MenuRenderer reads the
same normalized frame; visual smoothing never alters raw edit precision.
```

Interaction ownership order: **tracking invalid → cancel/rearm; active edit gesture → edit owns input; menu-open → menu owns relevant button/stick; navigation → locomotion owns stick/grab-air; idle → selection/tool pickup**. One action cannot be dispatched by more than one handler. Use per-controller snapshots and explicit capture tokens, rather than chaining `Runtime.tick` wrappers.

## Additional cleanup this audit recommends

1. Convert patch-stack menu definitions into **one declarative action registry** used for mode guards, tooltips, icons, menu placement and tests.
2. Remove contradictory 0.7.6 preview/draft descriptions, dead duplicate aliases and stale documentation but preserve supported Blender operator identifiers as backwards-compatible wrappers.
3. Decouple `drawing.draw` into batched hand, pointer, menu, selected-element and gizmo render passes; cache static geometry/text/icon meshes and avoid scanning every selected vertex/edge on each draw.
4. Cache evaluated raycast/BVH and vertex KD structures; invalidate when the underlying geometry changes. A controller visual should never require a full scene rebuild.
5. Make menu and hand view **session-local overlays** rather than modifications to the user's .blend objects or materials.
6. Separate **Tracking / Controls / Hands / Menus** preferences, with compatibility validation and a Reset to Safe Defaults button. Persist only explicit preferences; do not persist temporary hand poses or menu state in .blend.
7. Add a controller diagnostics window: left/right grip, aim, trigger, stick, pinch confidence, tracking source, joint validity, bridge freshness, action profile, menu capture state and frame-time; avoid personal hand motion recording by default.
8. Audit the old `finger_touch` shortcuts for conflicts with radial opening and physical touch sensors. One gesture must not both cancel a transform and commit a radial action.
9. Switch from ambiguous round-button statuses to explicit `AVAILABLE / ESTIMATED / PARTIAL / FULL / UNAVAILABLE` tracking labels and accessible help.
10. Ensure SteamVR helper runtime process is clearly installed, started, stopped and permissioned; no silent unbounded restart loops or user requirement to paste opaque terminal commands in the normal controller workflow.
11. Replay known failure conditions in tests: hand switching, stick drift, grip+trigger held, tracking lost during drag, bridge dropout, lost menu opener, rapid mode switching, controller reconnect and two hands interacting simultaneously.
12. Retain traditional controller/ray-menu mode for unsupported runtimes and users who prefer it.

## Feasibility, problems and mitigation

| Risk | Likelihood | Severity | Resolution / gate |
| --- | --- | --- | --- |
| Quest 3 PC link does not expose optical hand joints to Blender | High/unknown by runtime | High | Capability probe, provider interface, controller fallback; no promise of optical tracking until verified |
| OpenXR instance/session ownership prevents a standalone Python joint API | Significant | High | Use documented Blender APIs / external helper; prototype before choosing native implementation |
| Hand joint data is in different tracking/reference coordinates | High | High | Common calibration origin and handedness tests, confidence mask, measured joint-to-pointer error |
| Cursor/menu jitter makes wedge selection uncomfortable | Medium | High | Fixed orientation during open, radial deadzone/hysteresis, optional wrist filtering and release-to-select |
| Radial takes over thumbsticks used for movement/turn | Certain if unhandled | High | Input capture arbiter, locomotion suppression while menu open, device mapping tests |
| Finger tracking drops or gets occluded while editing | High with optical | High | Hold last visual pose briefly, cancel/restore active gesture, require release-and-rearm before reactivation |
| Hand mesh causes VR render latency or blocks mesh visibility | Medium | Medium | Small rig, batching, LOD/transparent outline, hide-hands option and performance telemetry |
| Double hands / spheres remain displayed | Medium | Medium | Disable native controller visual when overlay active; restore if renderer fails |
| Skeletal bridge UDP `v1` too small for full per-joint payload | Certain | Medium | New bounded `v2` payload, strict parsing, local-only transport and packet-size tests |
| Different controller profiles / Vive trackpad lack desired stick | Certain | Medium | Classic grid fallback and profile-specific radial mappings |
| New menu breaks Blender undo/tool modes | Medium | High | Central action registry, one command dispatch, automated integration matrix and manual acceptance |
| Replacing the runtime patch stack destabilises stable modelling | Medium | High | Stage-by-stage refactor, exhaustive regression suite, feature flags, preserve old operators and default legacy controls during alpha |
| UI comfort/accessibility insufficient | Medium | Medium | User tests on actual headset, short-list ring, handedness, contrast and toggle/hold options |

## Pre-implementation experiments (must answer before feature coding)

**Spike 0 — Reproduce the current setup**
- Inventory actual Blender version, Quest 3 connection path, active OpenXR runtime, controller family, SteamVR helper status and current balls/controller visual style.
- Record video/screenshots of head-menu alignment and a typical Select → Grab → Paint → Undo sequence. No diagnostic logging of hand joint data without opt-in.

**Spike 1 — Hands, no finger-tracking dependencies**
- In an isolated test harness (not runtime replacement), render a static/manually animated rigged hand from the existing grip pose. Measure eye-to-eye rendering, rotation offsets, GPU/frame-time cost and default controller dot suppression.
- Gate: hands stay fixed to tracked grip with understandable pose, no ghost duplicates, no scene objects, toggle fallback works.

**Spike 2 — Tracking capability matrix**
- Using supported runtime interfaces, test hand tracking availability by connection route, both hands at once, joint confidence and actual returned reference-frame joints.
- Gate: prove data quality before promising full tracked fingers. Partial SteamVR and controller-estimated animation work even if optical hands are not available.

**Spike 3 — Radial input-only prototype**
- Pure action-state prototype with synthetic stick traces, radial sectors, deadzone/hysteresis and offhand trigger hold; verify no duplicate actions, no locomotion while captured, neutral cancellation, submenu recentering and consistent dominant-hand swaps.
- In-headset gate: comfortable selection of 8 wedge choices from standing and seated positions; no accidental tool activation.

**Spike 4 — Integrated alpha (after approval)**
- Consolidate one input frame and capture router, then add hand visuals and radial UI behind configuration toggles.
- Gate: legacy ray menu and non-visual hands remain fully usable; no regressions to Object/Edit/Armature/Pose/Weight Paint, Undo, Grip and Trigger.

## Proposed staged work after design approval

| Phase | Scope | Primary test |
| --- | --- | --- |
| **0.8 Research Gate** | Audit, feature/source capability tests, radial input map and hand design signoff | Evidence of usable native inputs and chosen fallback |
| **0.8 Alpha A** | Central input sampler/router, tracking safety and classic controls unchanged | Synthetic controller replay + headset select/grab/mode test |
| **0.8 Alpha B** | Low-poly left/right animated hands, option to replace default spheres/controllers | Visual alignment, latency and frame-time test |
| **0.8 Alpha C** | Thumbstick radial menu with fallback classic grid | 8-way selection, mode changes, no movement conflicts |
| **0.8 Beta Tracking** | SteamVR per-finger/joint v2 bridge; optical provider only if proven feasible | Joint calibration, pose validity, confidence/loss tests |
| **0.8 Beta Workflow** | Isolation/X-Ray, eyedropper, direct posing, curves, cleaning as scoped in v0.8 main plan | Full native Blender editing + pose/weight pipeline |
| **0.8 RC** | Preferences, tutorials, diagnostics, Windows/Quest3 integration QA and performance | 4-version CI + real-device signoff + clean extension ZIP |

## Release acceptance, explicitly measured

1. **Hands:** both hands rendered instead of balls, correct handedness and alignment, finger animations reflect available physical input, no extra scene objects, no duplicate overlays; disable/fallback works.
2. **Input:** controller-select and -grab precision is no worse than v0.7.6, thumbstick navigation and turn resume immediately and cleanly after menu closure.
3. **Radial:** all categories reachable using dominant stick; release-to-select causes one action only; no accidental edits on menu opening, device reconnection or lost tracking.
4. **Tracking:** UI truthfully indicates estimated/partial/full and validates both hands; only call it optical hand tracking when actual joint data is confirmed.
5. **Safety:** tracking loss cancels an active edit without corrupting meshes/rig/weights; legacy input and menu can be restored.
6. **Performance:** headset frame times and input-to-visual latency measured against 0.7.6 on the same documented PC, headset runtime and scene; no unexplained regressions.
7. **Cross-version:** Blender 4.2, 4.5, 5.0, 5.2 extension install and integration tests; Quest 3 PC-VR (and other available controllers) real device checks.
8. **Delivery:** staged commits, meaningful tests, repeatable packaged alpha ZIPs, changelog and reviewable PRs.

## External technical references

- Khronos OpenXR 1.1 specification: https://registry.khronos.org/OpenXR/specs/1.1/html/xrspec.html
- Blender XR Python API reference: https://docs.blender.org/api/5.0/bpy.types.XrSessionState.html
- Blender XR overlay/Python capability notes: https://developer.blender.org/docs/release_notes/3.0/python_api/
- Valve skeletal tracking and quality levels: https://github.com/ValveSoftware/openvr/wiki/SteamVR-Skeletal-Input
- Valve skeletal input guidance: https://valvesoftware.github.io/steamvr_unity_plugin/articles/Skeleton-Input.html

**Planning conclusion:** Build controller-driven, accurately skinned **visual hands first**, with a trustworthy full-joint provider abstraction rather than assuming Quest optical hand input is available in Blender. Design a **thumbstick-release radial menu** backed by an explicit action-capture router. Treat physical headset experiments, coordinate validation and safe controller fallback as non-negotiable gates before implementing the final 0.8 hand/radial runtime.
