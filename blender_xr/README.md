# XR Mesh v0.6.1

XR Mesh is a free OpenXR-based VR mesh-modeling extension for Blender by Ded Zed.

## v0.6.1

v0.6.1 completes the v0.6 Materials + UV milestone while retaining the Blender Extensions compliance work from v0.6.0.

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
- Native Blender UV operators are preferred where available, with deterministic fallbacks for restricted contexts.

### Desktop panels

The XR Mesh sidebar includes collapsed **Advanced Materials + Textures** and **UV Mapping** panels for image-file browsing, custom material naming and the same practical UV operations.

## VR mesh editing

Choose **Edit Mode** from the hand menu. XR Mesh supports Vertex / Edge / Face selection, additive grip + trigger selection, Move Sel, Scale Sel, Extrude, Bevel, Inset, Delete, Merge, Subdivide, Duplicate, Recalculate/Flip Normals and session Undo/Redo.

Whole-object movement/scaling, distance-aware gizmos, primitive placement, flight, snap/smooth turning, grab-air movement and Save Blend remain available.

## Launch

- **3D Viewport > Sidebar (`N`) > XR Mesh > Start VR**
- **3D Viewport > View > Start XR Mesh**

Blender's separate **VR Scene Inspection** extension supplies Blender's own Start VR Session control; XR Mesh does not replace it.

## Install

1. Download the current release ZIP.
2. In Blender open **Edit > Preferences > Add-ons / Extensions**.
3. Choose **Install from Disk** and select the ZIP.
4. Enable **XR Mesh**.
5. Start XR Mesh from the 3D Viewport sidebar or View menu.

Requires Blender **4.2+** with OpenXR support. Automated checks target Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2. Blender 5.0.1 remains blocked because of its known VR crash.

The add-on contains no Python `threading` or `queue` imports. Updates are managed by Blender Extensions; there is no in-extension updater or funding UI.

## Support and source

Public issue tracker: https://github.com/dedzedofficial/Blender-XR/issues

Source repository: https://github.com/dedzedofficial/Blender-XR

XR Mesh is licensed under GPL-3.0-or-later.
