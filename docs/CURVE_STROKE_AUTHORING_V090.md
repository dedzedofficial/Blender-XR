# Mesh XR controller-drawn Curve authoring (v0.9.0 development)

## Purpose

Draw a real editable Blender Curve directly in the headset with the dominant controller. This extends the existing Shapes → Curve editor; it does not create a separate drawing scene or export format.

## Headset workflow

1. Open **Shapes → Curve** and choose **Draw Path**.
2. Release the dominant Trigger once to arm the stroke. The wrist menu hides while drawing.
3. Hold the dominant Trigger and move the controller grip through the scene. The grip pose is sampled from the shared validated controller frame; the aim ray is not used as the stroke position.
4. Release Trigger to inspect the orange GPU line preview. No Blender object or Curve datablock exists yet.
5. Choose **Confirm** to create one native 3D Bézier spline, **Close Path** to toggle a cyclic spline, or **Cancel** to discard the preview.
6. Continue editing the new Curve with the existing point, handle, cyclic and appearance controls. The creation is one Mesh XR Undo/Redo entry and the Curve is saved normally in the .blend file.

The offhand Trigger cancels an active stroke. Tracking/session loss also cancels it and requires the existing neutral-controller rearm before another edit can start.

## Sampling and limits

- Samples are accepted only from the validated dominant-hand grip pose.
- Consecutive samples closer than approximately 15 mm at viewer scale 1 are filtered to reduce jitter.
- A bounded one-pass smoothing step keeps the first and last samples fixed.
- The stroke is capped at 128 Bézier points.
- Open paths require at least two distinct points; closed paths require at least three.
- The Curve uses Blender's native 3D Bézier spline, automatic handles, 16 curve resolution and a 0.012 bevel depth for cable-like visibility.
- Scene, view layer, mode, active object and selected-object identity are fingerprinted before drawing and rechecked at confirmation. A changed selection requires a fresh stroke.

## Data and safety boundary

- The preview is a GPU overlay only; it does not add helper objects, temporary meshes, materials or custom scene properties.
- Confirmation creates a normal Blender Curve object and Curve datablock in the active scene collection.
- Existing meshes, UVs, materials, vertex groups, armatures, modifiers and transforms are not edited.
- Failed creation attempts remove the partial object/datablock and restore the prior selection. If cleanup itself fails, XR rollback is blocked and the artist is told to review the scene and restart XR.
- The Curve uses the existing native Curve creation history entry, so Undo removes the new object and Redo recreates it with the same Curve datablock.

## Validation status

The Blender integration regression is committed in `tests/test_curve_stroke_v090.py`. It covers release-to-arm, distance filtering, preview-only sampling, stale-selection refusal, open/closed preview state, native Bézier creation, XR Undo/Redo, .blend save/reopen, offhand cancellation and insufficient-point refusal.

This source increment has not yet been executed in Blender in the current development session. The regression must be run on Blender 4.2, 4.5, 5.0 and 5.2 before review. Real Quest 3 PC-VR, SteamVR, controller comfort and frame-time acceptance are also outstanding; no headset certification is claimed.
