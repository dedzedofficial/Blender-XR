# XR Mesh v0.6.0

XR Mesh is a free OpenXR-based VR mesh-modeling extension for Blender by Ded Zed.

## v0.6.0

- Renames the public extension from **Blender XR** to **XR Mesh** for Blender Extensions compliance.
- Sends the manifest Support/Report Issues link directly to the public GitHub Issues tracker.
- Removes the in-extension updater/funding UI. Updates are handled by Blender Extensions.
- Keeps the extension free of Python `threading` and `queue`; the build now rejects either import if it is introduced later.
- Keeps the optional external SteamVR hand helper on the existing `subprocess`/loopback-socket path.
- Activates the v0.5.6 runtime patch during normal extension startup so the documented HSL controls and selected-geometry workflow are actually live.

## VR mesh editing

Choose **Edit Mode** from the hand menu. XR Mesh supports:

- Vertex / Edge / Face selection directly in VR.
- Grip + trigger to add/remove individual mesh elements from the selection.
- **Move Sel** and **Scale Sel** for the current vertex/edge/face selection.
- Extrude, bevel and inset.
- Delete, merge, subdivide and duplicate selected geometry.
- Recalculate and flip normals.
- Undo / Redo during the XR session.
- Whole-object movement and uniform scaling in Object Mode.
- Distance-aware X/Y/Z and Size gizmos.
- Cube, sphere, cylinder, cone, torus and plane placement.
- Flight, snap/smooth turning and grab-air movement.

## Color workflow

Choose **Colors** from Object Mode or Edit Mode.

- Hue / Saturation / Lightness sliders can be pointed at and dragged continuously.
- **Pick** reads the active material color back into the controls.
- **Apply** recolors the active object in Object Mode.
- In Edit Mode, switch to **Face** selection and Apply to color only the selected faces.
- Different faces can keep different colors through material slots.
- White and Black adjust Lightness without discarding the chosen Hue/Saturation.
- Optional color presets remain available.
- Face-color changes participate in the extension's session-local Undo / Redo history.

The desktop sidebar also provides Blender's normal color picker and Shade Smooth / Flat controls.

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

## Support and source

Public issue tracker: https://github.com/dedzedofficial/Blender-XR/issues

Source repository: https://github.com/dedzedofficial/Blender-XR

XR Mesh is licensed under GPL-3.0-or-later.
