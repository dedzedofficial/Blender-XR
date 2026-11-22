# Mesh XR v0.8.5 — Assembly, Boolean and Native Paint Release

**Approved by creator:** 10 November 2026

**Status:** Version 0.8.5 development package; not a published or headset-certified stable release. The runtime, manifest, installer and release notes now agree on 0.8.5. `RELEASE_CHANNEL` remains `development`, and publication is blocked until release acceptance is recorded.

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
- [x] Pass the 39-script Linux suite on Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2; build and verify the 0.8.5 ZIP.
- [ ] Complete native Windows/macOS validation and local supported-version test matrix (GitHub Actions intentionally removed from main on 18 November 2026).
- [ ] Record physical Quest 3/SteamVR acceptance, including wheel aiming and interrupted edits.
- [ ] Resolve remaining input-router stability acceptance before a stable release claim.
- [x] Synchronize development version/manifest/README/ZIP naming to 0.8.5.
- [x] Add native Mirror/Array/Curve preview, Apply/Cancel, atomic undo and tracking-loss rollback.
- [x] Run extension preview for manual validation too, with version-independent artifact paths.
- [x] Align the draft branch with main's local-first test policy and remove legacy workflow conflicts.
- [x] Add Windows local whole-suite runner and paint-history corruption protections.
- [ ] Rerun the local Blender matrix on these newest commits; previous 39-script Linux results precede the latest changes.
- [ ] Change release channel to stable only after all release gates pass.

0.8.5 supports immediate undoable modifier edits and an explicit Preview session.
In Preview, aim at the wrist buttons; Back opens Apply/Cancel/Resume. Offhand Trigger
cancels after release. No navigation or other tools run during the preview.
Freehand curve strokes, hierarchy rename, precision selection and IK remain later roadmap work. Native curve objects and
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
- Slice E: Integrated acceptance tests, matching 0.8.5 development metadata and package. Stable publication still requires the documented platform and physical-headset gates.

Each increment requires equivalent **local** evidence: Blender 4.2, 4.5, 5.0, 5.2 regression runs; Windows and macOS Apple Silicon/Intel package checks; extension ZIP integrity and clean-profile install. The retired GitHub Actions workflows must not be restored merely to satisfy older CI wording. Run `dev-local.ps1 -Build -BlenderPath 'path/to/blender.exe'` on Windows for a complete local Blender regression pass. Automated checks do not substitute for physical Quest 3 validation.

If incomplete or any check fails, keep draft PR open and clearly state v0.8.5 has NOT shipped.
