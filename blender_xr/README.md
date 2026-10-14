# Mesh XR v0.6.4

Mesh XR is a free OpenXR-based VR mesh-modeling extension for Blender by Ded Zed.

## v0.6.4

v0.6.4 is a focused Blender Extensions packaging update. It keeps the full v0.6 Materials + UV feature set while making the optional SteamVR skeletal hand bridge self-contained.

### Blender Extensions compatibility

- Bundles `openvr==2.12.1401` as the official platform-independent Python wheel declared in `blender_manifest.toml`.
- Build tooling verifies the upstream PyPI SHA-256 before packaging the wheel.
- The hand bridge uses the extension's installed `site-packages`; users do not need to install `openvr` manually.
- The stable extension ID and operator namespace remain `blender_xr` for compatibility.
- The add-on still contains no Python `threading` or `queue` imports and has no in-extension updater.

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

Choose **Edit Mode** from the hand menu. Mesh XR supports Vertex / Edge / Face selection, additive grip + trigger selection, Move Sel, Scale Sel, Extrude, Bevel, Inset, Delete, Merge, Subdivide, Duplicate, Recalculate/Flip Normals and session Undo/Redo.

Whole-object movement/scaling, distance-aware gizmos, primitive placement, flight, snap/smooth turning, grab-air movement and Save Blend remain available.

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
