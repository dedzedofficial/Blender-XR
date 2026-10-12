# XR Mesh validation

XR Mesh uses automated Blender regression tests plus manual headset/runtime checks. Background Blender can validate geometry, data, UI registration and package behavior, but it cannot prove stereo readability, physical controller feel or runtime-specific tracking behavior.

## Automated matrix

GitHub Actions validates the generated extension ZIP with official Linux Blender binaries:

- Blender 4.2.0
- Blender 4.5.0
- Blender 5.0.0
- Blender 5.2.2

Blender 5.0.1 remains intentionally blocked because of its known VR crash.

Every matrix job builds the actual installer, installs it into a clean extension profile, verifies registration, then runs the modeling/navigation/material/UV regression suites.

## Core regression coverage

Automated checks cover:

- Registration, unregistration and re-registration.
- Extension ZIP identity/version metadata and clean-profile installation.
- Forbidden packaged `threading` / `queue` import checks.
- Face/vertex/edge selection and additive selection.
- Extrude, Bevel, Inset, Delete, Merge, Subdivide, Duplicate and normals operations.
- Selected geometry Move/Scale and adaptive X/Y/Z/Size handles.
- Preview cancellation and session-local Undo/Redo.
- Six primitive types, placement previews and creation history.
- Flight/walk, turbo, snap/smooth turning, vertical movement and grab-air navigation.
- Mesh switching and edit-mode guards.
- Real `.blend` saving, first-save paths, collision guards and private-history omission.
- HSL color conversion, slider targeting/dragging, Pick/Apply and per-face color history.
- Scene/object statistics and shading helpers.
- Blender 5.2-safe deferred preference restoration.

## v0.6.1 materials + UV regression suite

`tests/test_v060.py` specifically validates the completed v0.6 milestone:

- v0.6 runtime patch and Materials/UV menu routing.
- Material creation, duplication, deletion and rename behavior.
- Material slot creation/removal/cycling.
- Selected-face slot assignment and select-faces-by-active-slot.
- Principled Metallic, Roughness, Alpha and Emission values.
- Generated numbered checker, directional and color-grid images.
- Apply and clear Base Color image textures.
- UV layer creation.
- Planar Project, Smart Project, Cube Project and Unwrap.
- Seam marking and clearing.
- UV U/V movement, rotation and scaling.
- Reset UVs and Pack Islands.
- UV preview-segment generation.
- VR page navigation among Materials, properties, UV transform and UV preview.

The v0.6 suite runs on all four supported CI Blender versions. Release publishing separately runs it on Blender 5.2.2 before GitHub/Blender Extensions upload.

## Manual headset checklist — core workflow

Repeat on each runtime/controller combination you want to claim as physically verified.

1. Confirm Blender version, XR Mesh version, active OpenXR runtime and controller tracking.
2. Start from a simple cube and test both dominant-hand settings.
3. Confirm the menu follows the non-dominant hand, appears in both eyes and all buttons are readable/clickable.
4. Test Vertex, Edge and Face selection, including grip + trigger additive selection.
5. Test Move Sel, Scale Sel, Extrude, Bevel, Inset, Delete, Merge, Subdivide, Duplicate and normals tools.
6. Confirm preview commit/cancel behavior and Undo/Redo.
7. Test Shapes, object grab, flight/walk, turbo, snap/smooth turning, vertical movement and grab-air navigation.
8. Save, reopen, stop/restart VR and disable/re-enable the extension.
9. Disconnect/reconnect controllers and stop the runtime mid-session to confirm safe cleanup.

## Manual headset checklist — v0.6.1 Materials + UV

1. Open **Materials** in Object Mode and create/duplicate/delete materials.
2. Open **Properties** and adjust Metallic, Roughness, Alpha and Emission; confirm the material updates visually.
3. Toggle **Material Preview** and confirm the viewport/headset result is useful on the active runtime.
4. Enter Edit Mode/Face selection, create at least two material slots and assign different slots to different faces.
5. Use **Select Faces** for the active slot and confirm the expected faces become selected.
6. Load a texture image using the desktop file picker, then cycle/apply/clear images from the VR Texture page.
7. Apply Checker, Direction and Color Grid diagnostics and confirm they are visible on the material.
8. Mark seams, run Unwrap, Smart, Cube and Planar projections and inspect the result in Blender's UV Editor after stopping VR.
9. Test U/V move, ±15° rotate, scale, Reset and Pack.
10. Open **UV Preview** and confirm its wireframe is readable in both eyes and follows the selected faces closely enough for practical inspection.
11. Save and reopen the `.blend`; confirm packed diagnostic images and material/UV data persist.

## Experimental finger-input checks

Finger-touch shortcuts and the SteamVR skeletal bridge remain experimental.

- Verify normal controllers first with finger options disabled.
- Test both dominant-hand choices.
- Confirm one event per held finger-touch gesture and no false activations.
- For the SteamVR bridge, confirm the external helper receives skeletal input while Blender has focus.
- Release both hands before arming; test pinch selection/tool use and finger-curl object grabbing.
- Stop the helper during previews/grabs and confirm unfinished operations cancel rather than commit.
- Tracking loss or stale/estimated data must not drive destructive edits.

## Reporting physical compatibility

Automated tests are not a substitute for headset validation. When reporting a compatibility result, include:

- XR Mesh version.
- Blender version.
- Headset/controllers.
- PCVR transport.
- Active OpenXR runtime.
- Whether standard controllers or the experimental finger bridge were used.
- Exact steps and result, preferably with logs/video for failures.

Use the public issue tracker for reproducible problems: https://github.com/dedzedofficial/Blender-XR/issues
