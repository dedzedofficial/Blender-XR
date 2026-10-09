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

## v0.4.0: Meta/Valve targets and optional fingers

Implemented:

- Automatic, Meta and Valve/SteamVR controller binding presets.
- Documented Quest, Rift, Index and conditional Steam Frame compatibility targets.
- Opt-in controller finger-touch hold for menu/cancel.
- Experimental external SteamVR skeletal bridge: pinch selection/tool use and finger-curl object grab.
- Loopback-only session-key protocol, bounded packet processing, input freshness and release-before-arming checks.
- Tracking loss cancels unfinished work; estimated skeletal data cannot drive finger tools.
- Automated profile, skeletal sample, gesture, malformed packet, replay and reconnection tests.

Pending physical release validation: every headset/runtime combination above, controller touch behavior, skeletal measurements and background SteamVR input. Native OpenXR hand joints are not exposed through Blender's current Python API. Native Air Link hand tracking and native Steam Frame controller extensions need upstream integration or a different backend.

## v0.4.1: fixing update

- Fixed the missing Event.timer access that interrupted the VR modal loop.
- Left thumbstick locomotion independent of dominant-hand choice, with deadzone and speed limiting.
- Either-hand grab-air translation, with object-grip priority and no navigation feedback drift.
- Hand-menu primitive picker and placement preview: cube, sphere, cylinder, cone, torus and plane.
- Primitive creation in object mode, with VR-local undo/redo and snapshot cleanup.
- Regression tests reproduce timer events without the missing attribute and simulate both handedness settings.

## v0.4.2: flight and mesh switching

- Unbounded scene flight: left stick moves, right stick turns and changes altitude.
- Default 3 m/s flight, 4x turbo, held left-stick click boost, Travel speed controls and configurable snap/smooth turning.
- Head-pivot rotation with a nonzero starting 3D cursor.
- Tools, Shapes and Travel menu pages with larger labels, selected mesh name and ray-target bounds.
- Ray switching between meshes while face editing, with validation before leaving the current mesh.
- Regression tests for flight, turning, pivot preservation, both dominant-hand settings and real scene ray switching.

## v0.4.3: startup fix, saving and Blender 4.2+

- Fixed unsupported BOOLEAN XR action types; trigger touch, thumb touch and boost use FLOAT state values.
- Test every action type against Blender's real RNA enum, even without an XR session.
- Save Blend in the hand menu and desktop sidebar, current-file saves, timestamped first saves and an optional first-save path.
- Saved projects exclude private VR mesh history; saving retains live-session undo data in memory.
- Minimum Blender 4.2.0 with automated 4.2.0, 4.5.0, 5.0.0 and 5.2.2 coverage.

## v0.4.x: follow-up after headset testing

- Fix reported runtime/profile issues first; publish actual hardware results.
- Improve gesture thresholds from measured headset behavior.
- Adjustable menu position/size, axis snapping and improved diagnostics.
- Test native Blender undo integration before replacing local history.

## v0.5: expand mesh editing

- Vertex and edge selection alongside faces.
- Delete, merge, loop cuts, and proportional movement.
- Object scaling and axis-constrained transforms.
- Multi-face extrusion improvements for disconnected/complex selections.

## v0.6: scene creation

- Expand the existing hand-menu primitives with more creation options.
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

## v0.4.4: easier building and public updates

- [x] Ray-picked XYZ movement and extrusion handles.
- [x] Bevel/inset thickness drag handles.
- [x] Delete selected faces with undo/redo.
- [x] Separate Edit Tools menu.
- [x] One public updater button without authentication.
- [x] Verified current release replaces older downloads.
- [ ] Quest and Valve headset usability testing for ray dragging and menu placement.
- [ ] Mesh vertex/edge selection and object scale/rotation handles.
