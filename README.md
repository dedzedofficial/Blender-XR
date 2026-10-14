# Mesh XR v0.6.4

**Free VR mesh modeling and scene building inside Blender, by Ded Zed.**

Mesh XR adds a controller-first OpenXR modeling workflow to Blender. One hand carries a compact tool menu while the other points, selects, edits, transforms, places primitives, manages materials and textures, edits UVs, and moves around the scene.

[Latest Release](https://github.com/dedzedofficial/Blender-XR/releases/latest) · [Report Issues](https://github.com/dedzedofficial/Blender-XR/issues) · [Roadmap](ROADMAP.md) · [Changelog](CHANGELOG.md) · [Testing](TESTING.md)

## v0.6.4 highlights

v0.6.4 is a focused Blender Extensions packaging and compatibility update.

- Current extension/add-on branding is **Mesh XR**.
- Bundles the official `openvr==2.12.1401` `py3-none-any` wheel for the optional SteamVR skeletal hand bridge.
- Declares the dependency through Blender's extension `wheels` manifest field.
- Build tooling downloads the unchanged PyPI wheel when needed and verifies its published SHA-256 before packaging.
- The hand bridge loads the extension's installed `site-packages`, removing the previous manual `pip install openvr` requirement.
- CI confirms the wheel is present in the generated ZIP and imports it after a clean Blender extension install.
- Release packages now use `mesh-xr-v<version>.zip` naming.
- The stable `blender_xr` extension ID and operator namespace are retained for compatibility.

The complete v0.6 materials, textures and UV workflow remains unchanged.

## Launch

Mesh XR can be started from either:

- **3D Viewport > Sidebar (`N`) > Mesh XR > Start VR**
- **3D Viewport > View > Start Mesh XR**

Blender's separate **VR Scene Inspection** extension provides Blender's own Start VR Session control; Mesh XR does not remove or replace it.

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

## Materials, colors and textures

Open **Materials** from Object Mode or Edit Mode. The headset hub provides Base Color/HSL, material properties, material slots, textures, UV tools and Material Preview.

The color page keeps full-width **Hue**, **Saturation** and **Lightness** sliders, Pick/Apply controls, White/Black lightness shortcuts and optional color presets. In Edit Mode, Face selection allows different faces on one mesh to retain different materials/colors.

Material tools include:

- Create, duplicate and delete materials in VR.
- Auto-name materials in VR or enter a custom name from the desktop panel.
- Add/remove/cycle material slots.
- Assign the active slot to selected faces or select faces that use the active slot.
- Base Color, Metallic, Roughness, Alpha and Emission controls.
- Load an image from disk on desktop, then cycle/apply available Blender images in VR.
- Clear the Mesh XR image texture without deleting the Blender image datablock.
- Built-in numbered checker, directional and color-grid diagnostics.

Generated diagnostic images are packed into the `.blend` so they are self-contained.

## UV mapping

UV tools operate on selected mesh faces in Edit Mode:

- Unwrap, Smart Project, Cube Project and Planar Project.
- Mark and Clear seams.
- Move U/V, rotate and scale UVs.
- Reset UVs and Pack Islands.
- Open a compact VR UV wireframe preview.

Mesh XR uses Blender's native UV operators where their context is available and falls back to deterministic projection/packing behavior where needed, including restricted/background contexts.

## Experimental finger input

Finger-touch shortcuts and the optional SteamVR skeletal bridge remain experimental and are not required for standard controller use. The bridge still runs as an external helper process, but v0.6.4 ships its required OpenVR Python library inside the Blender Extension package. The helper locates that bundled `site-packages` directory automatically.

## Install

1. Open [Latest Releases](https://github.com/dedzedofficial/Blender-XR/releases/latest).
2. Download the current `mesh-xr-v0.6.4.zip` extension package.
3. In Blender open **Edit > Preferences > Add-ons / Extensions**.
4. Choose **Install from Disk** and select the ZIP.
5. Enable **Mesh XR**.
6. In the 3D Viewport press **N** and open the **Mesh XR** tab, or open the **View** menu.
7. Pick your dominant hand and press **Start VR**.

The extension is free, open source and licensed under **GPL-3.0-or-later**.

## Requirements

- Blender **4.2+** with OpenXR support.
- PCVR-capable hardware.
- Two tracked controllers for the standard controller workflow.
- One active OpenXR runtime.

Automated validation covers Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**. Blender 5.0.1 is blocked because of a known VR crash.

## Current limits

- One local editable mesh at a time for topology work.
- Shared/linked mesh data and shape-key meshes are rejected for topology edits.
- Editing operates on the base mesh cage, not evaluated modifier geometry.
- Scene Statistics reports base-mesh geometry rather than evaluated modifier output.
- VR Undo/Redo is session-local; not every material/UV operation is currently part of that lightweight history.
- Texture management currently targets a practical single Base Color image workflow rather than arbitrary shader-node authoring.
- Custom text naming and browsing arbitrary files use Blender's desktop dialogs; VR provides auto-name and image cycling instead.
- Rigging, weight painting, animation and advanced modifier workflows remain future roadmap features.
- Physical headset/runtime behavior can vary even when automated Blender tests pass.

## Development

Build the extension with:

```sh
python scripts/build.py
```

The build verifies manifest/version/package metadata, Mesh XR branding, the v0.5.6 and v0.6 runtime layers, material/UV modules, menu routing, the pinned OpenVR wheel checksum, and rejects packaged imports of `threading` or `queue`.

The GitHub test matrix validates Mesh XR against Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2, including a clean-profile install of the generated extension ZIP and bundled OpenVR import.

See [TESTING.md](TESTING.md), [ROADMAP.md](ROADMAP.md) and [CHANGELOG.md](CHANGELOG.md).

Independent project by Ded Zed. Not affiliated with the Blender Foundation, Freebird XR or the earlier MARUI BlenderXR project.
