# Blender XR v0.5.6

Blender XR is a free OpenXR-based VR modeling add-on for Blender by Ded Zed.

## Current workflow

- Vertex / Edge / Face selection directly in VR.
- Grip + trigger adds/removes individual mesh elements from the selection.
- **Move Selected** and **Scale Selected** edit only the current vertex/edge/face selection.
- Extrude vertices, edges and faces.
- Bevel selections and inset selected faces.
- Delete, merge, subdivide and duplicate selected geometry.
- Recalculate / flip normals.
- Edit-mode Undo directly on the main Edit page, with Redo on More Edit.
- Whole-object movement and uniform scaling in Object Mode.
- Distance-aware X/Y/Z and Size gizmos.
- Primitive placement for cube, sphere, cylinder, cone, torus and plane.
- Full-scene flight, snap/smooth turning and grab-air movement.
- Save Blend and session-local Undo / Redo.
- VR **Hue / Saturation / Lightness sliders** with continuous trigger dragging, Pick, Apply and optional presets.
- Different selected faces can keep different colors through Blender material slots.
- Desktop Blender hue-wheel color picker with whole-object or selected-face assignment.
- Shade Smooth / Flat.
- Collapsible scene/object statistics.
- Persistent controller, movement, modeling and UI preferences.

## VR mesh editing

Choose **Edit Mode** from the hand menu. Blender XR starts in Face selection mode, and you can switch between **Vert**, **Edge** and **Face** at any time.

1. Choose **Select**.
2. Point at mesh geometry and press the dominant trigger.
3. Hold grip while triggering to add/remove elements from the current selection.
4. Choose **Move Sel** or **Scale Sel**.
5. Drag the X/Y/Z or Size handle to transform only the selected geometry.
6. Use **Undo** without leaving Edit Mode if you need to revert the last VR edit.

Object-mode **Scale** remains a separate whole-object transform.

## VR colors

Choose **Colors** from either Object Mode or Edit Mode. The color page opens directly to full-width **Hue**, **Saturation** and **Lightness** sliders.

- Point anywhere on a slider to set its value; hold the dominant trigger and drag for continuous adjustment.
- Hue spans the full spectrum.
- Saturation ranges from grey to fully saturated color.
- Lightness ranges from black through the selected color to white.
- The menu shows the current H/S/L values and a live color swatch.
- **Pick** reads the active object's material color, or the selected face material color in Edit Mode.
- **Apply** recolors the active object in Object Mode.
- In **Edit Mode**, switch to **Face** selection first. Apply assigns the chosen color only to the selected faces, so different faces on the same mesh can use different colors.
- **White** and **Black** adjust Lightness to its extremes without discarding the chosen Hue/Saturation.
- **Presets** provides Red, Orange, Yellow, Green, Cyan, Blue, Purple and Pink as optional shortcuts.
- Edit-mode face color assignment participates in Blender XR's lightweight local Undo / Redo history without creating topology snapshots.
- Re-applying the same color to an already matching face does not consume another Undo history entry.

The desktop Blender XR sidebar still provides Blender's normal hue-wheel color picker and Shade Smooth / Flat controls.

## Launch

Blender XR can be launched from either:

- **3D Viewport > Sidebar (`N`) > Blender XR > Start VR**
- **3D Viewport > View > Start Blender XR**

Blender's separate **VR Scene Inspection** add-on supplies Blender's own VR sidebar / Start VR Session control; Blender XR does not replace it.

## Install

1. Download `blender-xr-v0.5.6.zip` from the current GitHub release.
2. In Blender open **Edit > Preferences > Add-ons / Extensions**.
3. Choose **Install from Disk** and select the ZIP.
4. Enable **Blender XR**.
5. Start Blender XR from the sidebar or the 3D Viewport View menu.

Requires Blender **4.2+** with OpenXR support. Automated checks cover Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2. Blender 5.0.1 remains blocked because of its known VR crash.

Blender 5.2's restricted UI draw context is handled by deferring persistent-setting restoration when Scene writes are temporarily forbidden.

## Development

Build the extension with:

```sh
python scripts/build.py
```

The build verifies that the extension manifest, Python version source and packaged README all report the same release version.

Repository documentation:

- https://github.com/dedzedofficial/Blender-XR
- https://github.com/dedzedofficial/Blender-XR/blob/main/ROADMAP.md
- https://github.com/dedzedofficial/Blender-XR/blob/main/TESTING.md

Blender XR is GPL-3.0-or-later and remains free/open source.