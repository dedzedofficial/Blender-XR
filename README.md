# XR Mesh v0.6.0

**Free and open-source VR mesh modeling inside Blender, by Ded Zed.**

XR Mesh adds a controller-first modeling workflow to Blender through OpenXR. One hand carries a compact tool menu while the other points, selects, edits, transforms, colors and builds directly in VR.

[Latest Release](https://github.com/dedzedofficial/Blender-XR/releases/latest) · [Issues / Support](https://github.com/dedzedofficial/Blender-XR/issues) · [Roadmap](ROADMAP.md) · [Testing](TESTING.md) · [Website](https://fishhwb.github.io/)

## v0.6.0

- Public software/extension name is now **XR Mesh**.
- Keeps the existing **`dedzedofficial/Blender-XR`** repository and **`blender_xr`** extension ID so existing links and update compatibility are preserved.
- Uses the public GitHub Issues tracker for reports and support.
- Keeps the extension free of Python `threading` and `queue`; the build rejects either import if introduced later.
- Uses the existing subprocess/loopback approach for the optional SteamVR hand helper.
- Carries forward the complete v0.5.6 edit and HSL color workflow.

## Core VR editing

- Vertex, edge and face selection in VR.
- Add/remove individual elements from the selection with grip + trigger.
- Move and scale only the selected vertices, edges or faces.
- Extrude, bevel and inset.
- Delete, merge, subdivide and duplicate selected geometry.
- Recalculate and flip face normals.
- Object movement and uniform scaling.
- Distance-aware X/Y/Z and Size gizmos.
- Primitive placement: cube, sphere, cylinder, cone, torus and plane.
- Full-scene flight, snap/smooth turning and grab-air navigation.
- Session Undo / Redo and Save Blend from VR.

## HSL color workflow

Choose **Colors** from Object Mode or Edit Mode.

- Drag full-width **Hue**, **Saturation** and **Lightness** controls in the headset.
- **Pick** loads the active material or selected face color into the HSL controls.
- **Apply** recolors the active object in Object Mode.
- In Edit Mode, Apply colors only the selected faces, so one mesh can keep different colors on different faces.
- White/Black adjust Lightness without losing the chosen Hue/Saturation.
- Optional color presets remain available.

## Launch

XR Mesh can be started from either:

- **3D Viewport > Sidebar (`N`) > XR Mesh > Start VR**
- **3D Viewport > View > Start XR Mesh**

Blender's separate **VR Scene Inspection** extension provides Blender's own Start VR Session control; XR Mesh does not replace it.

## Install

1. Open [Latest Releases](https://github.com/dedzedofficial/Blender-XR/releases/latest).
2. Download the current extension ZIP.
3. In Blender open **Edit > Preferences > Add-ons / Extensions**.
4. Choose **Install from Disk** and select the ZIP.
5. Enable **XR Mesh**.
6. Start XR Mesh from the 3D Viewport sidebar or View menu.

Requires Blender **4.2+** with OpenXR support. Automated checks target Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2. Blender 5.0.1 remains blocked because of its known VR crash.

## Project identity and compatibility

The user-facing name is **XR Mesh**. The GitHub repository intentionally remains **Blender-XR**, the extension ID remains **`blender_xr`**, and current package filenames retain the `blender-xr-...` form. Keeping those technical identifiers avoids breaking existing installs, release links and the Blender Extensions update path while removing “Blender” from the public extension title.

XR Mesh is licensed under **GPL-3.0-or-later** and remains free/open source.

## Support development

Development can optionally be supported on [Patreon](https://www.patreon.com/cw/DedZed). Patreon support does not lock features behind a paid tier.

Independent project by Ded Zed. Not affiliated with the Blender Foundation, Freebird XR or the earlier MARUI BlenderXR project.
