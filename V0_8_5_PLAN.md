# Mesh XR v0.8.5 — Assembly, Boolean and Native Paint Release

**Approved by creator:** 10 November 2026

**Status:** In development; not released. Keep add-on manifest/version at 0.8.0 until all accepted v0.8.5 capabilities have merged and the release gate passes.

## Completion scope — 15 November 2026

The creator requested a practical 0.8.5 completion plus one simple giant roadmap.
[ROADMAP.md](ROADMAP.md) is now the release-order index. Earlier detailed plans remain
historical requirements; their old status tables must not be treated as a current audit.

Implementation in the completion branch:

- [x] Integrate wrist hierarchy search from PR #53 without dropping assembly controls.
- [x] Add selected-geometry Separate and Extract Copy, preserving retained originals.
- [x] Preserve object vertex-group definitions/locks when redoing joined/separated output.
- [x] Add native Curve modifier target and six deformation-axis controls.
- [x] Add headset HEX entry, RGB adjustments and an HSV wheel to the existing colour studio.
- [x] Add light-temperature presets as approximate native linear RGB colours.
- [x] Add explicit editable native flicker keyframes with Undo/Redo and existing-animation guards.
- [x] Add real Blender regression coverage for the new controls and preservation paths.
- [ ] Complete the supported Blender/platform matrix and extension preview for this branch.
- [ ] Record physical Quest 3/SteamVR acceptance, including wheel aiming and interrupted edits.
- [ ] Resolve remaining input-router stability acceptance before a stable release claim.
- [ ] Update release version/manifest/README/ZIP naming together only after gates pass.

0.8.5 uses immediate undoable modifier button edits. Continuous preview/confirm/cancel,
freehand curve strokes, hierarchy rename, precision selection and IK are scheduled in
the roadmap rather than being misrepresented as finished. Native curve objects and
the Curve deformation modifier are separate delivered features.

## Accepted v0.8.5 scope

1. **General object parenting** — select multiple children and an active parent; change or clear parent while retaining each child's world transform; refuse cycles, linked/hidden/locked objects and unsafe parenting relationships.
2. **Native Empty assemblies** — create Empty control objects, group selected objects underneath, choose parents/children, inspect/edit in existing hand-mounted hierarchy.
3. **Join native mesh objects** — join selected meshes into one Blender mesh with compatible materials, UVs and vertex groups. Provide Join as Copy (originals visible) and Join with Sources Retained (originals hidden and locked in native Blender file until unmerged).
4. **Unmerge / Separate / Extract** — exact restoration of retained original components where available; otherwise explicitly separate by selection, loose islands or material. No false claim to reconstruct original objects from arbitrary topology.
5. **Boolean Shape Builder** — Difference, Union and Intersect using native Boolean modifiers and real cutter objects; preserve existing modifier stacks and protect textures, rigs and shape keys. Destructive Apply only with compatibility checks.
6. **VR Texture Paint Studio** — paint on native Blender image textures via headset ray/UV hit, existing XR colour picker, brush radius/strength, eraser and fill where safe, explicit layers and saved images. Undo per stroke; restore pixels on cancellation/tracking loss. Never silently overwrite existing texture image or Base Color link.

## Explicit exclusions

- Deform/Lattice Studio, Origin/Pivot Studio, 3D Slice/Cut and live stamping: not accepted for this version.
- New project format, redundant exporter, shader graph replacement or standalone Quest application.
- Deleting originals in a way that makes Unmerge impossible.

## Delivery gates

- Slice A: Parenting / Empty, linked from existing Scene Hierarchy, guarded XR session undo/redo and saved .blend persistence.
- Slice B: Reversible Join / Join as Copy / Unmerge, then safe Separate / Extract.
- Slice C: Non-destructive Boolean operations and compatible Apply.
- Slice D: Native image texture painting, protected image/textures/UVs, per-stroke undo/cancel, image saving.
- Slice E: Integrated acceptance tests; only then set manifest/runtime/package version to 0.8.5, update documentation and release archive naming.

Each increment requires all eight CI jobs: Blender 4.2, 4.5, 5.0, 5.2; Windows; macOS Apple Silicon and Intel; extension ZIP preview. Automated Blender checks do not substitute for physical Quest 3 validation.

If incomplete or any check fails, keep draft PR open and clearly state v0.8.5 has NOT shipped.
