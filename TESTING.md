# Validation

## Automated checks

Executed locally with official Linux Blender 5.0.0 and 5.2.2 binaries:

- Registration, unregistration, and re-registration.
- Cube-face extrusion, bevel, and inset produce changed, manifold geometry.
- Repeated previews rebuild from the baseline without accumulating topology.
- Cancellation restores geometry; history undo and redo restore before/after geometry.
- Face ray picking and additive selection.
- Multi-face extrusion and UV preservation when cancelling a preview.
- Guards for empty selection, shared mesh data, and shape keys.
- Input hysteresis and every menu button's ray target.
- Controller profile coverage and optional sensor bindings.
- Held gesture debounce, skeletal tip/curl extraction and helper manifest generation.
- Real loopback UDP reception, session keys, replay rejection, malformed/nonfinite data, timeout and release-before-arming.
- Release ZIP path validation, identity/version checks, and simulated update installation rollback.
- Update redirect handling strips authorization on GitHub asset redirects and refuses unrelated hosts.

Background Blender has no XR session state. Controller action-map activation and headset rendering cannot be validated by these checks. Hardware/network update tests below remain pending.

## Quest 3 manual checklist

Repeat with Meta OpenXR + Air Link, SteamVR OpenXR, and Virtual Desktop VDXR:

1. Confirm Blender version, add-on version, active runtime, and controller tracking.
2. Start from a simple cube and switch dominant hand in the sidebar before VR.
3. Confirm menu follows the non-dominant hand and appears in both eyes.
4. Confirm dominant ray points in the correct direction and clicks all menu buttons.
5. Select a mesh, enter face mode, select one face, and test each tool by a short click and by dragging.
6. Confirm release commits and the other trigger cancels; inspect the resulting mesh after stopping VR.
7. Test additive face selection, undo/redo, and history clearing on stop.
8. Switch to object mode; grab, move, rotate, cancel, and undo.
9. Test menu visibility, thumbstick movement, reset, ESC, and reopening VR.
10. Disconnect/reconnect controllers, stop the runtime, and verify error/cleanup behavior.
11. Save/reopen the project and disable/re-enable the add-on.
12. On Windows, test a real newer GitHub release with and without private-repository authorization; check checksum failure, writable-folder failure, restart, and new version display.

Record runtime/headset/version/results in an issue. Do not mark compatibility as verified until the corresponding physical test is complete.

## v0.4 finger and headset checks

Repeat controller checks with both dominant-hand choices on Quest/Rift and Valve hardware. Record the active controller profile, PCVR transport and OpenXR runtime. Steam Frame requires a compatible profile or runtime remapping; do not mark its native profile supported.

1. Verify controllers still work with both finger options disabled.
2. Enable finger-touch shortcuts: hold trigger-touch plus thumbstick-touch for 0.7 seconds on each hand. Confirm one event per hold and that unrelated touches do not trigger it.
3. With SteamVR OpenXR, choose Finger bridge, start VR, install the system-Python helper dependency and launch the copied command.
4. Release both hands to arm; test dominant pinch selection/menu clicks, pinch tool previews, other-hand pinch cancel, and finger-curl MOVE grab/release.
5. Stop the helper mid-preview and mid-grab. Confirm cancellation restores the baseline, rather than committing. Restart the helper while fingers are held; confirm editing waits for both hands to release.
6. Check partial/full skeletal inputs are available on the actual device. Estimated poses must leave the mode waiting.
7. For Virtual Desktop controller-free input, verify both SteamVR skeletons and OpenXR hand/controller poses are present. Native Air Link/VDXR hand tracking alone is not implemented.
8. Use real SteamVR Input bindings to confirm the helper background process receives skeletal actions while Blender has input focus.

These physical tests have not been run by the automated suite. v0.4 remains a development release.
