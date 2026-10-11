# Blender XR v0.5.6

**Free VR mesh modeling and scene building inside Blender, by Ded Zed.**

Blender XR adds a controller-first modeling workflow to Blender through OpenXR. One hand carries a compact tool menu while the other points, selects, edits, transforms, places primitives, assigns colors and moves around the scene.

[Latest Release](https://github.com/dedzedofficial/Blender-XR/releases/latest) · [Roadmap](ROADMAP.md) · [Testing](TESTING.md) · [Website](https://fishhwb.github.io/)

## v0.5.6 highlights

- Makes Edit Mode transforms explicit: **Move Sel** and **Scale Sel** affect only the currently selected vertices, edges or faces.
- Adds **Undo** directly to the main Edit page and **Redo** to More Edit.
- Adds controller-friendly **Hue / Saturation / Lightness sliders** inside VR with continuous trigger dragging, Pick and Apply.
- In Edit Mode, color Apply is face-only, supports different colors on different faces, and participates in Blender XR's local Undo / Redo history.
- Keeps optional quick color presets plus the desktop Blender hue-wheel color picker, per-face material assignment and Shade Smooth / Flat controls.
- Fixes version drift so the manifest, Blender sidebar, packaged README and in-headset footer all report **v0.5.6** from the same source.
- Adds build-time checks that fail if those version sources diverge again.
- Preserves the v0.5.5 Blender 5.2 UI-draw fix and native Blender launch route.

## Blender XR vs Blender's VR Scene Inspection button

Blender's own **VR** sidebar and **Start VR Session** control come from the separate **VR Scene Inspection** add-on. Blender XR does not remove or replace that add-on. If Blender's native VR tab is missing, enable **VR Scene Inspection** in Blender's add-on/extensions preferences.

Blender XR itself can be started from either:

- **3D Viewport > Sidebar (`N`) > Blender XR > Start VR**
- **3D Viewport > View > Start Blender XR**

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
- HSL color sliders and per-face material assignment in VR.

## Install

1. Open [Latest Releases](https://github.com/dedzedofficial/Blender-XR/releases/latest).
2. Download `blender-xr-v0.5.6.zip`.
3. In Blender open **Edit > Preferences > Add-ons / Extensions**.
4. Choose **Install from Disk** and select the ZIP.
5. Enable **Blender XR**.
6. In the 3D Viewport press **N** and open the **Blender XR** tab, or open the **View** menu.
7. Pick your dominant hand and press **Start VR**, or choose **View > Start Blender XR**.

The add-on is free, open source and licensed under **GPL-3.0-or-later**.

## Requirements

- Blender **4.2+** with OpenXR support.
- PCVR-capable hardware.
- Two tracked controllers for the standard controller workflow.
- One active OpenXR runtime.

Automated validation covers Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**. Blender 5.0.1 is blocked because of a known VR crash.

## Materials and color

### In VR

Choose **Colors** from Object Mode or Edit Mode. Blender XR opens directly to three full-width **Hue**, **Saturation** and **Lightness** sliders. Point anywhere on a bar and hold the dominant trigger to drag continuously. The Hue bar spans the full spectrum; Saturation ranges from grey to full color; Lightness ranges from black through the chosen color to white. The current H/S/L values and a live swatch are shown in the headset.

**Pick** reads the active material color back into the sliders. **Apply** commits the current color. **White** and **Black** set Lightness to its extremes without discarding the chosen Hue/Saturation. Red, Orange, Yellow, Green, Cyan, Blue, Purple and Pink remain available from the optional **Presets** page.

In **Object Mode**:

1. Select a mesh object.
2. Adjust Hue, Saturation and Lightness, or choose a preset.
3. Press **Apply** to recolor the active object material.
4. Press **Pick** to load the active material color back into the HSL controls.

In **Edit Mode**:

1. Switch to **Face** selection.
2. Select one or more faces.
3. Adjust HSL or choose a preset.
4. Press **Apply** to assign that color only to the selected faces.
5. Select other faces and Apply another color to give different faces different colors on the same mesh.
6. Use **Undo** / **Redo** if needed without leaving Edit Mode.

Face-color history stores only material-slot assignments rather than temporary topology snapshots, and re-applying an unchanged face color does not waste an Undo entry.

### In the Blender sidebar

The **Materials** section uses Blender's normal color picker / hue wheel.

In Object Mode use **Apply to Object**. In Edit Mode select faces and use **Assign to Selected Faces**. Blender XR creates or reuses matching material slots so one mesh can use multiple materials, such as an orange cone with a grey base.

The panel shows the active material and slot. Shared materials are copied before whole-object recoloring so another object is not unexpectedly recolored. **Shade Smooth** and **Shade Flat** remain available in the sidebar.

## Scene statistics

The **Scene Statistics** panel can be expanded or collapsed. When open it shows base-mesh totals for visible objects:

- Objects / Selected
- Meshes / Materials
- Vertices / Edges
- Faces / Triangles
- Active-object V/E/F/T counts

Statistics are cached briefly and recomputed when the scene signature changes instead of being fully recounted on every sidebar redraw. VR material changes invalidate that cache so material counts stay current.

## Persistent preferences

Blender XR remembers the main controller, movement, modeling and statistics-panel settings between Blender files. Scene properties remain the live values used by the running XR session, so existing workflows and saved `.blend` files remain compatible.

Blender 5.2 can forbid Scene writes while a UI panel is drawing. Blender XR detects that specific restriction and safely defers restoring persistent settings until Blender leaves the restricted draw context.

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
| Dominant trigger on HSL slider | Set the value; hold and drag for continuous adjustment. |
| Dominant trigger while selecting | Select the pointed object or mesh element. |
| Grip + trigger while selecting | Add/remove the pointed mesh element from the selection. |
| Trigger on X/Y/Z gizmo | Drag along that axis. |
| Trigger on Size gizmo | Scale selected geometry in Edit Mode or the selected object in Object Mode. |
| Dominant grip in Object Move | Grab and reposition the object. |
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

- Vert / Edge / Face selection mode
- Select
- Move Sel
- Scale Sel
- Extrude
- Bevel
- Colors
- Undo
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
- Redo
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
- VR color controls cover normal material color assignment, not full shader-node authoring.
- UV mapping, rigging and weight painting remain roadmap features.
- Physical headset/runtime behavior can vary even when automated Blender tests pass.

## Development

Build the extension with:

```sh
python scripts/build.py
```

The build refuses to package a release if the manifest, Python version source, Blender sidebar metadata, in-headset version source and packaged README drift apart.

The GitHub test matrix validates Blender XR against Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2 before release, including a clean-profile install of the actual generated extension ZIP.

See [TESTING.md](TESTING.md) for validation details and [ROADMAP.md](ROADMAP.md) for upcoming features.

---

## Support development

Blender XR is developed as a **free and open-source project**. If you find it useful and want to help fund continued development, testing and future VR modeling tools, you can support Ded Zed on Patreon.

**[Support Blender XR development on Patreon](https://www.patreon.com/cw/DedZed)**  
**[FISHHWB Website](https://fishhwb.github.io/)**

Patreon support is optional and does not lock features behind a paid tier.

Independent project by Ded Zed. Not affiliated with the Blender Foundation, Freebird XR or the earlier MARUI BlenderXR project.
