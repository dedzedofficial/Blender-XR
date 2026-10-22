# Mesh XR v0.7.5

v0.7.5 development adds a PC View Mode toggle to switch the current Blender viewport between the normal desktop view and Blender's live OpenXR session mirror, where supported. The toggle is display-only and does not start or stop VR. It also carries forward the v0.7.1 Object Tools, Geometry Tools, managed modifiers and UV history.

Mesh XR is a free OpenXR-based VR mesh-modeling extension for Blender by Ded Zed.

## v0.7.5 development — PC View Mode

- In the Mesh XR sidebar, use **PC View Mode > Show VR View on PC** to switch the current 3D View between the regular desktop viewport and Blender's native live XR session mirror.
- The toggle is enabled only while Mesh XR's OpenXR session is active.
- Turning mirroring off restores the normal desktop view; it does not stop the headset session.
- If the current Blender build does not expose `SpaceView3D.mirror_xr_session`, the panel reports that mirroring is unavailable rather than pretending it worked.
- The mirror is Blender's XR compositor output, not a recording and not a separate reconstructed camera view.

## v0.7.5 development — workflow tools

- **Precision Snap:** optional quantization of controller-driven geometry tool distances and axis translation using the configured tool step.
- **Two-handed scaling:** grab an object with one controller, grab with the other, and scale around the midpoint between hands. Releasing either grip commits one XR history entry.
- **Optional haptics:** short OpenXR pulses after completed geometry edits and object transforms, when enabled and supported.
- **Asset readiness:** read-only topology/UV/material audit with triangle and modifier counts, plus a configurable triangle-budget warning.
- **Rigging:** proportion-based starter humanoid armature, Blender automatic-weight binding, weight cleanup/normalization and native Weight Paint mode entry.
- **Workflow panel:** a collapsed-by-default desktop panel groups asset checks, rigging and controller modeling guidance.

The starter armature is a guide, not a finished production rig. Review bone placement before binding and test the resulting weights before using or exporting the asset.

## v0.6.5

v0.6.5 is a modeling and usability update built on the v0.6 Materials + UV workflow and the v0.6.4 Blender Extensions packaging fixes.

### Icon-first VR modeling UI

- The main Object and Edit toolbars now use simple pictogram icons instead of long text labels.
- Raycast over an icon to highlight it immediately; hold the ray there for about 0.5 seconds to show the tool name and a short explanation.
- The first toolbar control is a Blender-style Mode selector with explicit Object Mode and Edit Mode choices.
- Edit Mode keeps dedicated Vertex, Edge and Face selection icons.
- Inset Faces is directly available on the main Edit toolbar again.
- Secondary modeling commands remain grouped under More Edit to keep the main toolbar compact.

The repository includes `ICON_GUIDE.md` with an icon-by-icon explanation and short usage instructions.

### Loop Cut

- Select an edge in Edit Mode and open Loop Cut to detect its continuous quad edge ring.
- The detected ring is previewed in orange before applying the cut.
- Choose between 1 and 16 cuts.
- A single cut can be positioned from 5% to 95% in 5% steps.
- Multiple cuts are spaced evenly.
- Invalid/non-quad rings are rejected with a clear message rather than producing an unpredictable cut.
- Loop Cut participates in Mesh XR local Undo/Redo.

### Delete Object

- Object Mode now has a dedicated Delete Object command.
- Edit Mode keeps Delete Geometry as a separate operation, so deleting selected vertices/edges/faces cannot accidentally remove the whole object.
- Deleted mesh objects can be restored with Mesh XR Undo and removed again with Redo.

### Blender Extensions compatibility

- Bundles `openvr==2.12.1401` as the official platform-independent Python wheel declared in `blender_manifest.toml`.
- Build tooling verifies the upstream PyPI SHA-256 before packaging the wheel.
- The hand bridge uses the extension's installed `site-packages`; users do not need to install `openvr` manually.
- The stable extension ID and operator namespace remain `blender_xr` for compatibility.
- The add-on contains no Python `threading` or `queue` imports and has no in-extension updater.

### Materials + textures

- Create, duplicate, delete and auto-name materials in VR; custom-name them from the desktop panel.
- Add, remove and cycle material slots.
- Assign the active slot to selected faces and select faces using the active slot.
- Control Base Color, Metallic, Roughness, Alpha and Emission.
- Keep the existing HSL sliders, color presets and Pick/Apply workflow.
- Load texture images from disk on desktop; cycle/apply/clear available images in VR.
- Use built-in numbered checker, directional UV and color-grid diagnostic textures.
- Toggle Material Preview.

### UV mapping

- Standard Unwrap, Smart Project, Cube Project and Planar Project.
- Mark and Clear seams.
- Move U/V, rotate and scale selected UVs.
- Reset UVs and Pack Islands.
- Compact in-headset UV wireframe preview.

## VR mesh editing

Choose **Edit Mode** from the mode icon. Mesh XR supports Vertex / Edge / Face selection, additive grip + trigger selection, Move Selection, Scale Selection, Extrude, Bevel, Inset Faces, Loop Cut, Delete Geometry, Merge, Subdivide, Duplicate, Recalculate/Flip Normals and session Undo/Redo.

Whole-object movement/scaling, Delete Object, distance-aware gizmos, primitive placement, flight, snap/smooth turning, grab-air movement and Save Blend remain available.

## Launch

- **3D Viewport > Sidebar (`N`) > Mesh XR > Start VR**
- **3D Viewport > View > Start Mesh XR**

Blender's separate **VR Scene Inspection** extension supplies Blender's own Start VR Session control; Mesh XR does not replace it.

## Install

1. Download the current release ZIP.
2. In Blender open **Edit > Preferences > Add-ons / Extensions**.
3. Choose **Install from Disk** and select the ZIP.
4. Enable **Mesh XR**.
5. Start Mesh XR from the 3D Viewport sidebar or View menu.

Requires Blender **4.2+** with OpenXR support. Automated checks target Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2. Blender 5.0.1 remains blocked because of its known VR crash.

## Optional SteamVR hand bridge

Standard controller use does not require OpenVR. For the experimental SteamVR skeletal hand-input path, Mesh XR ships the required OpenVR Python wheel inside the Blender Extension package. Use **Copy Hand Bridge Command** while a Mesh XR session is active and run the copied command in a system terminal.

## Support and source

Public issue tracker: https://github.com/dedzedofficial/Blender-XR/issues

Source repository: https://github.com/dedzedofficial/Blender-XR

Mesh XR is licensed under GPL-3.0-or-later.
