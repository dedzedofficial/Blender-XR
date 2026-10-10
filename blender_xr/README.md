# Blender XR v0.5.3

Blender XR is a free OpenXR-based VR modeling add-on for Blender by Ded Zed.

## Current workflow

- Vertex / Edge / Face selection in VR.
- Move, scale, extrude, bevel and inset selected geometry.
- Delete, merge, subdivide and duplicate selected geometry.
- Recalculate / flip normals.
- Object movement and uniform scaling.
- Distance-aware X/Y/Z and Size gizmos.
- Primitive placement for cube, sphere, cylinder, cone, torus and plane.
- Full-scene flight, snap/smooth turning and grab-air movement.
- Save Blend and session-local Undo / Redo.
- Materials color picker with whole-object or selected-face assignment.
- Shade Smooth / Flat.
- Collapsible scene/object statistics.
- Persistent controller, movement, modeling and UI preferences.

## Materials

In Object Mode, choose a color and use **Apply to Object**.

In Edit Mode, select one or more faces, choose a color and use **Assign to Selected Faces**. Blender XR creates or reuses a matching material slot, so a single mesh can use multiple materials.

## Install

1. Download the current `blender-xr-v0.5.3.zip` from GitHub Releases.
2. In Blender open **Edit > Preferences > Add-ons**.
3. Choose **Install from Disk** and select the ZIP.
4. Enable **Blender XR**.
5. Open the 3D Viewport sidebar with **N**, choose the **Blender XR** tab and press **Start VR**.

Requires Blender **4.2+** with OpenXR support. Automated checks cover Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2. Blender 5.0.1 is blocked because of its known VR crash.

## v0.5.3 cleanup

v0.5.3 keeps the existing VR input/locomotion workflow intact while moving growing systems into purpose-based modules:

- `materials.py`
- `selection.py`
- `transforms.py`
- `modes.py`
- `status.py`
- `menus.py`
- `statistics.py`
- `preferences.py`

Legacy version helpers remain as compatibility layers where needed so existing tests and call sites do not have to be rewritten all at once.

## Development

Build the extension with:

```sh
python scripts/build.py
```

The repository README, testing notes and roadmap contain the full current documentation:

- https://github.com/dedzedofficial/Blender-XR
- https://github.com/dedzedofficial/Blender-XR/blob/main/ROADMAP.md
- https://github.com/dedzedofficial/Blender-XR/blob/main/TESTING.md

Blender XR is GPL-3.0-or-later and remains free/open source.
