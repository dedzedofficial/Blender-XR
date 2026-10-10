# Blender XR v0.5.3

**Free VR mesh modeling and scene building inside Blender, by Ded Zed.**

Blender XR adds a controller-first modeling workflow to Blender through OpenXR. One hand carries a compact tool menu while the other points, selects, edits, transforms, places primitives and moves around the scene.

[Latest Release](https://github.com/dedzedofficial/Blender-XR/releases/latest) · [Roadmap](ROADMAP.md) · [Testing](TESTING.md) · [Website](https://fishhwb.github.io/)

## v0.5.3 highlights

- Cleaner **Materials** section in the Blender XR sidebar.
- Active material name and material-slot feedback.
- Hue wheel / Blender color picker for quick material color changes.
- **Apply to Object** in Object Mode.
- **Assign to Selected Faces** in Edit Mode for multi-material meshes.
- Scene Statistics can now be collapsed and uses a lightweight cache for larger scenes.
- Main controller, movement, modeling and UI preferences persist between Blender files.
- Safer shared Object/Edit mode switching and mesh-selection handling.
- Centralized material, selection, transform, status, menu and statistics backends for future UV/material/rigging work.
- Standardized distance-aware gizmo sizing without changing the existing interaction model.
- Existing v0.5 mesh tools, primitives, navigation, Save Blend and VR-local Undo/Redo remain available.

## Core modeling features

- Vertex, edge and face selection in VR.
- Add/remove from the selection with grip + trigger.
- Move and scale selected vertices, edges and faces.
- Extrude vertices, edges and faces.
- Bevel vertex/edge selections and face boundaries.
- Inset selected faces.
- Delete, merge, subdivide and duplicate selected geometry.
- Recalculate and flip face normals.
- Object movement and uniform scaling.
- Distance-aware X/Y/Z and Size gizmos.
- Primitive placement: cube, sphere, cylinder, cone, torus and plane.
- Full-scene flight, snap/smooth turning and grab-air navigation.
- Session Undo / Redo and Save Blend from VR.

## Install

1. Open [Latest Releases](https://github.com/dedzedofficial/Blender-XR/releases/latest).
2. Download `blender-xr-v0.5.3.zip`.
3. In Blender open **Edit > Preferences > Add-ons**.
4. Choose **Install from Disk** and select the ZIP.
5. Enable **Blender XR**.
6. In the 3D Viewport press **N** and open the **Blender XR** tab.
7. Pick your dominant hand and press **Start VR**.

The add-on is free, open source and licensed under **GPL-3.0-or-later**.

## Requirements

- Blender **4.2+** with OpenXR support.
- PCVR-capable hardware.
- Two tracked controllers for the standard controller workflow.
- One active OpenXR runtime.

Automated validation covers Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**. Blender 5.0.1 is blocked because of a known VR crash.

## Materials and per-face color

The **Materials** section uses Blender's normal color picker / hue wheel.

In **Object Mode**:

1. Select a mesh.
2. Choose a color.
3. Press **Apply to Object**.

In **Edit Mode**:

1. Switch to **Face** selection.
2. Select one or more faces.
3. Choose a color.
4. Press **Assign to Selected Faces**.

Blender XR creates or reuses a matching material slot and assigns it only to those faces. That means one mesh can have different materials, such as an orange cone with a grey base. The panel shows the active material and current slot so it is easier to see what is being edited.

Shared materials are copied before whole-object recoloring so another object is not unexpectedly recolored.

## Scene statistics

The **Scene Statistics** panel can be expanded or collapsed. When open it shows base-mesh totals for visible objects:

- Objects / Selected
- Meshes / Materials
- Vertices / Edges
- Faces / Triangles
- Active-object V/E/F/T counts

Statistics are cached briefly and recomputed when the scene signature changes instead of being fully recounted on every sidebar redraw.

## Persistent preferences

Blender XR remembers the main controller, movement, modeling and statistics-panel settings between Blender files. Scene properties remain the live values used by the running XR session, so existing workflows and saved `.blend` files remain compatible.

## PCVR setup

| Connection | Setup |
| --- | --- |
| Quest Link / Air Link | Use Meta Quest Link as the active OpenXR runtime. |
| SteamVR | Start SteamVR and set SteamVR as the active OpenXR runtime. |
| Virtual Desktop | Use VDXR where supported, or route through SteamVR. |

Controller bindings target Touch-compatible controllers, Valve Index, Vive and simple OpenXR controller profiles. Actual compatibility depends on the runtime exposing suitable controller actions.

## VR controls

| Control | Action |
| --- | --- |
| Dominant trigger on menu | Choose a tool or command. |
| Dominant trigger while selecting | Select the pointed object or mesh element. |
| Grip + trigger while selecting | Add/remove the pointed mesh element from the selection. |
| Trigger on X/Y/Z gizmo | Drag along that axis. |
| Trigger on Size gizmo | Scale selected geometry or the selected object. |
| Dominant grip in object Move | Grab and reposition the object. |
| Other trigger | Toggle menu or cancel live work. |
| Left thumbstick | Move/fly. |
| Right thumbstick | Turn and move vertically. |
| Left-stick click | Turbo flight. |
| Grip empty space | Pull yourself through the scene. |

## Mesh editing

Enter **Edit Mode** from the VR menu and choose one of the three selection modes:

- **VERT** selects vertices.
- **EDGE** selects edges.
- **FACE** selects faces.

The current selection mode is shown in the menu header and highlighted in the tool grid.

### Main edit page

- Select
- Move
- Scale
- Extrude
- Bevel
- Vertex / Edge / Face mode switch
- More
- Object Mode

### More edit tools

- Inset
- Delete
- Merge
- Subdivide
- Duplicate
- Recalculate Normals
- Flip Normals
- Tool-distance controls

**Inset** is face-only. **Merge** merges the selected vertices to their average position. Vertex/edge picking starts from the visible mesh face under the controller ray so it does not select hidden geometry through the back of the mesh.

## Scene building

Use **Shapes** to add basic meshes directly in VR. A placement preview appears before creation. Newly created objects use the normal Blender mesh system and can immediately be moved or edited.

Use **Travel** for Fly/Walk, Turbo, Faster/Slower, Snap/Smooth turning and Reset View. The left stick controls movement regardless of dominant-hand choice. The right stick handles turning and vertical travel.

## Saving

Use **Save Blend** from the VR menu or desktop sidebar.

- Existing projects save to their current file.
- Unsaved projects default to a timestamped file in `Documents/BlenderXR`.
- A custom first-save path can be chosen before starting VR.
- Private Blender XR history snapshots are not stored in the `.blend` file.

## Experimental finger input

Finger-touch shortcuts and the optional SteamVR skeletal bridge remain experimental. They are not required for standard controller use.

## Current limits

- One local editable mesh at a time for topology work.
- Shared/linked mesh data and shape-key meshes are rejected for topology edits.
- Editing operates on the base mesh cage, not evaluated modifier geometry.
- Scene Statistics reports base-mesh geometry rather than evaluated modifier output.
- VR Undo/Redo is session-local.
- Full material controls, UV mapping, rigging and weight painting remain roadmap features.
- Physical headset/runtime behavior can vary even when automated Blender tests pass.

## Development

Build the extension with:

```sh
python scripts/build.py
```

The GitHub test matrix validates Blender XR against Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2 before release.

See [TESTING.md](TESTING.md) for validation details and [ROADMAP.md](ROADMAP.md) for upcoming features.

---

## Support development

Blender XR is developed as a **free and open-source project**. If you find it useful and want to help fund continued development, testing and future VR modeling tools, you can support Ded Zed on Patreon.

**[Support Blender XR development on Patreon](https://www.patreon.com/cw/DedZed)**  
**[FISHHWB Website](https://fishhwb.github.io/)**

Patreon support is optional and does not lock features behind a paid tier.

Independent project by Ded Zed. Not affiliated with the Blender Foundation, Freebird XR or the earlier MARUI BlenderXR project.
