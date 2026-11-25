# Blender XR — scene authoring implementation specification

**Accepted by creator:** 10 November 2026  
**Status:** Approved scope; implementation NOT complete.  
**Integration:** One existing Blender Mesh XR extension ZIP, using Blender-native scene data.  
**Dependencies:** Finish P0 controller ownership, cancel/rearm, history and tracking recovery before shipping new mutating XR interactions. PR #44 remains draft until full CI is verified.

## Scope (do not add separate redundant tools)

1. **Hand-mounted scene hierarchy (P1):** A compact wrist/hand panel showing loaded native Blender collections and their object hierarchy, expandable groups, search, scrolling, single/multi selection, eye visibility and selectable-lock controls. Respect linked-library restrictions, per-view-layer visibility and existing selection/active-object state. Display clear hidden/locked feedback. No separate asset browser.
2. **Upgraded colour controls (P1):** Improve the existing material/colour workflow, not a separate material applicator. HSV wheel, RGB/HEX input, brightness, saved swatches and sampling where safe. Modify the appropriate existing native Blender material colour/node inputs without replacing materials, deleting texture links, or silently altering shared material users. Expose an explicit shared-vs-single-user choice when needed. Alpha only where supported.
3. **Mirror modifier controls (P1):** Add/edit existing native Mirror modifier; X/Y/Z axes, clipping, merge threshold and mirror-object target. Reuse the existing modifier context, never silently stack duplicates; cancel restores prior values.
4. **Array modifier controls (P1):** Add/edit existing native Array modifier; count, relative/constant offset and object-offset controls with live preview and cancel/undo. Preserve original mesh and other modifiers.
5. **Native curve authoring (P1):** Create/edit Blender Curve objects and splines, controller-placed points, Bézier handles, open/closed path, bevel thickness and resolution. Persist fully editable native curves after save/reopen. Preview without orphan objects; undo/cancel as one action.
6. **Interactive VR lighting (P1):** Create Point, Spot, Area and Sun native light objects; grab, rotate and aim; set light energy, colour, colour temperature where compatible, spot cone/softness, area dimensions, and light-specific controls. Support presets (candle, torch, moon, neon, horror flicker) as editable values; animated flicker only as explicit native animation, never silently add handlers or replace lights.
7. **Atmosphere (P2):** Edit native World colour/strength and supported Blender volume/fog settings with renderer-aware availability warnings and reversible previews. Do not promise identical live fog appearance across all viewport engines.

## UX acceptance

- Selecting an object opens only relevant contextual controls: light -> light panel; curve -> spline controls; mesh -> modifier and colour controls.
- The hierarchy is hand-mounted and stays readable; selecting from it must not trigger locomotion, object grabs or radial-menu actions.
- Every mutation respects object editability/visibility, mode and library locks; has clear preview, confirm, cancel and Undo/Redo.
- Existing material textures, UVs, vertex groups, armatures, modifiers, object parenting, saved .blend files and operator IDs remain intact.
- Native Blender objects/modifiers/materials/curves/lights are the only authoritative data. No proprietary project format or parallel scene representation.
- No unnecessary new top-level workspace or separate material application system.

## Safe delivery slices and tests

1. **P0 gate:** complete/verify existing controller recovery PR and unified action ownership before new XR input captures.
2. **Hand hierarchy:** read-only collection/object tree first; then selection; then visibility and locks. Test nested collections, duplicate object names, multi-select, linked objects, hidden objects, cancellation and dominant-hand swaps.
3. **Colour upgrade:** extend current material editor. Test shared node materials, linked textures, non-node materials, HEX/HSV round-trip, cancelled edits, undo and save/reopen.
4. **Mirror/Array:** extend current modifier actions. Test editing existing modifiers, no duplicate stack, negative offsets, locked/linked objects, undo and save/reopen on supported Blender versions.
5. **Curves:** native spline placement and editing, including tracking-loss rollback, point-count bounds, closed loops, save/reopen.
6. **Lights:** native light creation, transform and properties, spotlight aiming, presets and explicit optional animation. Test all four types, cancel, undo, Blender save/reopen.
7. **Atmosphere:** renderer-aware native world/volume editing, reversible controls and warnings.

For every slice: regression tests and all eight supported CI jobs (Blender 4.2/4.5/5.0/5.2, Windows, macOS Intel, macOS Apple Silicon, preview ZIP packaging). Merge only passing PRs; do not claim real headset acceptance without hardware tests.

## Explicit exclusions from this request

Do not add a standalone material applicator, terrain suite, prefab library, performance dashboard, reference boards, general-purpose tutorial system or other rejected features merely because they appeared in earlier candidate roadmaps. Keep existing implemented features intact.

## Current state

This document is a **planning/acceptance increment only**. None of the seven feature groups above is claimed implemented or tested by this change. Follow-up code PRs are required.
