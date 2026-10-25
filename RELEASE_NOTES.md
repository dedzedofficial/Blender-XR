# Mesh XR v0.7.6 — merged into main

**Compared with v0.7.5, the most recent published release.** Version 0.7.6 was merged into `main` in [PR #18](https://github.com/dedzedofficial/Blender-XR/pull/18) on 25 October 2026; this does **not** mean a tagged GitHub / Blender Extensions release has been published.

## Highlights

- **One Select tool for VR:** pick meshes, vertices, edges, faces, armatures, edit bones and pose bones with native Blender mode awareness; duplicate Select Mesh/Select Rig buttons removed.
- **Controller manipulation:** Grip to grab and move geometry and objects; Move, Scale and Rotate with Trigger; better picking for loose/small vertices and edges; session-local Undo/Redo for geometry and bone transforms.
- **Freeform armatures:** create and edit bones without the old humanoid-shape restriction; bone selection and transforms in VR, with native Blender editing operations still available.
- **Native Weight Paint Mode:** select Weight Paint from the same VR Mode menu as Object/Edit. Paint and Erase actual vertex-group weights with the controller, select groups, adjust brush strength and size, and receive feedback when the ray misses the surface.
- **Blender parenting methods:** Rigging → Parent supports Automatic Weights, Empty Groups, Envelope Weights, Armature Deform, Object Parent and Clear Parent (Keep Transform), while protecting existing painted weights.
- **Compact icon-led interface:** seven sidebar workspaces with native Blender icons, hover tooltips, collapsed advanced panels and fallback icon rendering. Existing UV, materials and modelling tools remain.
- **Compatibility:** successful automated extension packaging and full regression runs on Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**. See [CI run #40147094901](https://github.com/dedzedofficial/Blender-XR/actions/runs/40147094901).

For a detailed breakdown, read the [v0.7.6 changelog](CHANGELOG.md). Physical OpenXR headset control feel and painting accuracy require device verification beyond Blender's background tests.

---

## v0.7.5 foundations carried forward

Mesh XR v0.7.5 expands the controller-first OpenXR workflow with a desktop headset mirror toggle, controller precision and scaling improvements, a starter rigging workflow, and non-destructive asset diagnostics.

## PC View Mode
- Toggle the current desktop 3D View between the normal Blender viewport and Blender's native live OpenXR session mirror, where supported.
- Switching the PC display does not start or stop the headset session.
- Unsupported Blender builds show a clear message instead of a nonfunctional control.
- Session cleanup attempts to restore the normal PC viewport if Mesh XR stops or the headset session ends unexpectedly.

## Controller modelling
- Optional Precision Snap quantizes supported controller-driven geometry distances and axis translations to the configured tool step.
- Two-controller object scaling lets you grab an object with one controller and use the second controller to scale it around the midpoint between your hands.
- Scaling is committed as one Mesh XR Undo/Redo entry when either grip is released.
- Optional haptic feedback gives short controller pulses after completed geometry edits and object transforms, when supported by the active OpenXR runtime.

## Rigging and weight painting
- Create a proportion-based starter humanoid armature with clearer root, pelvis, spine, chest, head, arm and leg bone names.
- Bind selected meshes to the active armature with Blender automatic weights.
- Normalize and clean vertex-group weights and enter Blender Weight Paint mode from the Mesh XR Workflow panel.
- Failure handling now attempts to clean up incomplete rig creation, restore the original selection, and report failed binding or mode changes accurately.

The starter armature is only a guide. Inspect and adjust bone placement, test deformations and correct weights before using the rig for production or export. Complex anatomy and non-human meshes require manual work.

## Asset readiness audit
- Read-only checks for open boundary edges, genuine non-manifold edges, loose vertices/edges, degenerate faces, UV availability, material slots and modifier count.
- Reports source-mesh triangle count separately from modifier-evaluated triangle count.
- Checks the configured triangle budget against evaluated triangles when Blender can provide them, and clearly falls back to the base mesh if evaluation is unavailable.
- Open boundaries are reported separately from edges shared by three or more faces.

## Reliability and compatibility
- Precision Snap, Haptic Feedback and Triangle Budget settings persist between Blender files.
- Expanded regression tests cover topology classification, modifier-evaluated triangle counts, starter-rig bone names, scaling pivot calculations and failed rig creation recovery.
- The extension package and regression suite pass the Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2 automated matrix.

## Compatibility
- Blender 4.2 or newer with OpenXR support.
- Windows and Linux extension package targets.
- Headset mirroring, controller feel and haptic behaviour still need manual confirmation on physical OpenXR hardware.
- The rigging helpers are not a production auto-rigger, and weight binding should be checked on each asset.
