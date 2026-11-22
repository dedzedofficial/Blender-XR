# Mesh XR roadmap

One roadmap for building comfortably in VR while keeping real, editable Blender data.
Updated 15 November 2026. **Development work is not a stable release.**

## Where we are

- Published release: **0.8.0**. Current development package: **0.8.5**.
- Current target: **0.8.5 — finish the core scene-authoring tools**.
- Existing tools: mesh editing, freeform bones, weight painting, hand/radial UI,
  hierarchy, colour, curves, lights, atmosphere, parenting, joins, Booleans and image painting.
- Release blockers: supported-version/platform checks, extension preview and physical
  Quest 3/SteamVR acceptance. The full input-router replacement is still unfinished.
- New code in the 0.8.5 completion branch is implemented but must pass release gates
  before being called shipped. [Detailed 0.8.5 checklist](V0_8_5_PLAN.md).

## 0.8.5 — finish and protect the essentials

| Feature | Delivery for this version | State |
| --- | --- | --- |
| Scene hierarchy | Browse collections, search loaded objects, select/multi-select, hide and lock | Implemented; search integrated from PR #53 |
| Colour studio | HSV wheel and sliders, RGB adjustments, headset HEX keypad, swatches, sampling, explicit local/shared edits | Implemented |
| Mirror / Array | Edit native modifiers, references, axes, clipping, counts and offsets; optional Preview/Apply/Cancel with one undo | Implemented |
| Curve modifier | Existing/new modifier, Curve target, positive/negative deformation axes and undo | Implemented |
| Editable curves | Place/edit Bézier points and handles, open/close paths, thickness and resolution | Implemented; freehand strokes later |
| Lighting | Point/Spot/Area/Sun, aim/move, energy, colour, shape and presets | Implemented |
| Light temperature | 2700/4000/6500 K approximations written as native linear light colour | Implemented |
| Explicit flicker | Opt-in native energy keyframes over 24 frames, editable in Blender, undo/redo | Implemented; no background handler |
| Atmosphere | World colour, strength and volume controls with renderer-aware warnings | Implemented |
| Parenting / Empty groups | Keep world transforms, select parents/children, protect invalid relationships | Implemented |
| Join / Unmerge | Retain original objects, join as copy, restore sources; preserve groups through redo | Implemented with compatibility guards |
| Separate / Extract | Loose parts, material, selected geometry and selected-copy extraction | Implemented; select in Edit Mode, operate in Object Mode |
| Boolean tools | Difference/Union/Intersect, retain cutters and guarded Apply | Implemented |
| Texture painting | Native overlay images, ray-to-UV brush, erase/fill, size/opacity, layers, PNG export and stroke undo | Implemented with compatibility guards |
| Input/data protection | Ownership guard, tracking-loss cancel/rearm, atomic strokes and recovery | Existing guards retained; full router migration remains a blocker to claiming full stability |
| Release | Runtime, manifest, ZIP and notes synchronized to 0.8.5; development publication guard | Implemented; stable acceptance pending |

**Modifier Preview:** changes update Blender live, Apply commits one history entry,
and Cancel or tracking loss restores the starting values. Regular button editing remains available. New paint
layers are 256/512/1024 pixels. Join/paint reject unsafe modifier/shape-key cases.
These restrictions must be visible in help, not described as universal support.

## 0.8.6 — interaction and precision

**Precision selection source increment (development, untested):** Optional
controller ray-picker for native edit-mesh vertices and edges. Four world-space
pick radii (12/30/70/120 mm), front-surface filtering or explicit through-mesh
targeting, deterministic depth ordered candidates, and Next/Previous cycling
from the last recorded controller ray. Geometry candidates are recomputed
against live Blender BMesh data before cycling. Object/armature selection,
faces and legacy transforms continue using the established Select workflow.
Accessible under Edit → More → Step → Precision; no global mode or persistent
scene properties. This increment requires creator-side Blender/controller
testing and is not a shipped release.

## 0.8.6 — interaction and precision

**In development on the stacked `feature/v086-hierarchy-navigation-rename` branch:** the existing XR Scene Hierarchy now supports one-click navigation to an object's parent, paginated browsing of its direct children, and a headset rename keyboard with alphabetic case, digits, spaces, underscores, dashes and dots. The rename operation rejects linked/locked or missing objects, prevents exact-name conflicts and is undoable in the active XR session. Because earlier XR undo records refer to old object names, applying a rename with pending history requires an explicit **Rename + Reset Undo** confirmation. This work is source-implemented, not user-tested, merged or released.


- Replace the chained input handlers with one registry/router, in small tested steps.
- One action owner; deterministic replay of tracking loss, mode changes and menu capture.
- Finish calibration profiles, diagnostics, neutral-release recovery and installation/migration checks.
- Box/lasso/brush selection, overlap/depth cycling, named selection sets.
- Exact transform keypad, Global/Local/Normal axes, pivot/origin controls.
- Vertex/edge/face/surface snapping with visible targets; precision grab and magnification.
- Full isolation/X-Ray/selection restoration, including save/reopen and nested scenes.
- Hierarchy rename, object properties, parent breadcrumbs and focus navigation.
- Measured dense-scene picking performance and further precision interaction improvements.

## 0.9 — complete the avatar and modelling workflow

| Area | Features |
| --- | --- |
| Weights | Use sampled weight as brush target, exact painting, smoothing, mirror, normalize, influence limits and locked-group protection |
| Rigging | Bone-to-group picking, roll/chains/naming, explicit symmetry, unweighted/influence heatmaps and clickable diagnosis |
| Posing | Bounded controller IK limb dragging, pole controls, pose reset/compare, existing constraint safety and non-humanoid tests |
| Mesh editing | Bridge/fill improvements, slide, constrained extrusion, bevel controls, proportional falloff and previewed Knife/3D Slice |
| Repair | Select problem geometry, preview merge/cleanup/normals, topology/symmetry diagnostics; preserve UVs, groups and shape keys |
| Shapes | Native Basis/shape-key creation, duplicate/rename/value controls and safe vertex editing |
| Animation | Pose library, mirror/reset poses, timeline scrubbing/playback, object/bone/shape-key keys and simple corrective drivers |
| Materials/UV | Face/slot targeting, PBR channels, seam/island/distortion previews, texel-density hints and texture relinking |

## 0.9.5 — faster world building

- Surface Magnet: normal alignment, editable offset and intersection warnings.
- Repeat Stamp: explicit independent copies vs linked native instances, preview and undo.
- Collection assemblies and multi-object manipulation; modular snap connectors.
- Continuous controller-drawn curves with smoothing; repeat along a path/radial arrangements.
- Measure → Apply, spatial rulers, alignment guides and architectural floor/wall helpers.
- Eye-height/world-scale review, navigation bookmarks and layout/readability checks.
- Native text, reference boards, spatial notes and optional decal placement.
- Camera/light composition handles and existing Geometry Nodes parameter controls.

## 1.0 — a reliable complete creation loop

- Build a room, place props, edit a mesh, paint weights, pose a limb and recover every edit in headset.
- Consistent contextual controls and readable, optional onboarding/help.
- Seated/standing, left/right-handed and one-hand fallbacks; comfort and haptic options.
- Visible undo history; predictable Blender/native XR history boundaries.
- Scene-data round trips, broad device testing and documented real-headset performance.
- Safe BVH/cache invalidation, measured action latency, bounded recovery and useful performance warnings.
- Clean installation, migration, disable/re-enable, packaging and documentation.

## Later research — not committed release promises

Retopology-over-surface; selective LOD/decimation previews; deformation stress tests;
viseme/blendshape audits; versioned avatar-platform checks; advanced Geometry Nodes
and shader editing; voice commands; behaviour previews; physics; collaboration;
sculpting. Every experiment needs an explicit use case, native-data preservation,
performance evidence and a safe cancel path before promotion to a release.

No redundant exporter, proprietary project format, standalone Quest app, remote
asset browser or radial favourites are part of 0.8.5. Blender's own save/export stays authoritative.

## Definition of done

1. Reachable controls with clear valid targets and reasons for refusal.
2. Native Blender data, preserved materials/UVs/weights/links; no hidden destructive shortcuts.
3. Commit, cancel, Undo/Redo, tracking interruption and save/reopen tests where applicable.
4. Supported Blender matrix (4.2/4.5/5.0/5.2), Windows, macOS Intel/Apple Silicon and extension preview.
5. Physical headset acceptance before a stable label; CI alone is insufficient.
6. Update the checklist and release notes from actual evidence, then publish one matching ZIP.

## Detailed backlog and historical decisions

This page is the release-order index. The original detailed ideas remain available;
unchecked historical boxes do not override the current code audit.

- [Full creator feature catalogue](CREATOR_DEVELOPMENT_PLAN.md): every detailed proposal and acceptance scenario.
- [Original v0.8 plan](V0_8_PLAN.md): tracking, interaction, rigging and safety requirements.
- [Input architecture audit](V0_8_SYSTEM_AUDIT_AND_INPUT_PLAN.md).
- [Previous roadmap](docs/archive/ROADMAP_before_085.md): retained without dropping earlier ideas.
- [Testing](TESTING.md) and [platform compatibility](PLATFORM_COMPATIBILITY.md).
