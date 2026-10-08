# Blender XR roadmap

Free Blender VR tools by Ded Zed. Versions describe scoped goals, not promises of complete Blender parity. There is no paid feature tier planned.

## v0.3.0: initial basic editing

Implemented:

- Installable Blender 5+ extension with GPL-3.0-or-later source.
- Left/right dominant-hand choice before starting VR.
- Tool menu attached to the non-dominant controller.
- Dominant-controller pointing, object selection, and face selection.
- Extrude, bevel, and inset with controller-driven distance previews.
- Move and rotate an unparented object using the dominant grip.
- Add/remove selected faces by gripping while selecting in face mode.
- Cancel a live operation with the other trigger.
- VR-local undo/redo for the latest 20 tool/move operations.
- Viewer movement with the non-dominant thumbstick and reset view.
- GitHub release check, checksum-verified download, installation rollback, and restart prompt.
- Automated geometry, cancellation, history, packaging, and updater tests.

Release gate still requiring real hardware:

- Quest 3 with Air Link and Meta OpenXR.
- Quest 3 with SteamVR as the OpenXR runtime.
- Quest 3 with Virtual Desktop and VDXR, plus its SteamVR route.
- Stereo menu readability, controller ordering, ray direction, and button feedback.
- Windows installation/update/restart tests.

v0.3 is an initial development release. Headless mesh tests do not establish headset compatibility.

## v0.4: dependable everyday control

- Fix reported v0.3 headset/runtime issues first.
- Snap turning, recentering improvements, and adjustable menu position/size.
- Joystick amount adjustment, visible selected tool amounts, and axis snapping.
- Better tracking-loss handling and actionable runtime diagnostics.
- Test native Blender undo integration and outside-VR edits before replacing local history.

## v0.5: expand mesh editing

- Vertex and edge selection alongside faces.
- Delete, merge, loop cuts, and proportional movement.
- Object scaling and axis-constrained transforms.
- Multi-face extrusion improvements for disconnected/complex selections.

## v0.6: scene creation

- Add basic mesh primitives from the hand menu.
- Duplicate objects, basic snapping, and world scale controls.
- Controller profiles and validation beyond Quest Touch controllers.

## v0.7: workflow polish

- Better interaction with existing modifiers and material previews.
- Minimal UI refinements, accessibility, and language support.
- Improve update diagnostics and authenticated private-release setup.

## v1.0: reliable basic VR modeling

- Published compatibility matrix with physical headset test results.
- Stable basic modeling workflow across tested Blender versions and OpenXR runtimes.
- Documentation, reproducible installers, and complete regression coverage for supported tools.

Sculpt brushes, UV editing, texture/weight painting, node editors, shape-key-safe topology changes, and multiplayer need separate design and are not promised by v0.3.
