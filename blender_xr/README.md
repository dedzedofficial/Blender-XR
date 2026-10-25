# Mesh XR v0.8.0

**Cross-platform desktop:** Windows x64/ARM64, Linux x64, macOS Intel/Apple Silicon are declared extension targets. Some platform/Blender combinations cannot start VR; the Session workspace shows status instead of promising incompatible runtime support. See [Platform Compatibility](https://github.com/dedzedofficial/Blender-XR/blob/dev/v0.8.0/PLATFORM_COMPATIBILITY.md). iOS/Quest standalone require separate apps.

## v0.8 alpha 1 — offhand radial menu and articulated controller hands

- **Radial menu:** hold the **non-dominant Trigger** and point that **same hand's thumbstick** at a tool. Release Trigger to activate, or recenter the stick and release to cancel. Returning to thumbstick centre after highlighting a category opens that submenu while still holding Trigger. The dominant hand stays free for editing.
- **Navigation safety:** while the radial menu captures input, movement, turning and old trigger selection are suspended. Right-handed users control the menu with their left controller; left-handed users with their right controller.
- **Hands instead of controller spheres:** light, articulated left/right 3D hands render only in the XR overlay and never create Blender mesh objects. Grip and Trigger drive **estimated** finger curls. Tracking individual physical finger joints is not yet implemented by this hand visual feature.
- **Fallbacks:** choose **Classic ray menu** and **Native controllers** or **Pointers only** from the Session workspace. The experimental SteamVR finger bridge continues to use classic controls when no thumbstick is available.
- **Availability:** early alpha, automated Blender tests are required, and physical Quest 3 PC-VR testing is outstanding. Real optical hand tracking and upgraded SteamVR per-joint streaming are future milestones of 0.8.

## Previous v0.7.6 capabilities

## 0.7.6 native Weight Paint Mode and Blender parenting

Open the standard headset **Mode** menu and choose **Weight Paint** just as you would choose Object or Edit Mode. The active Blender mesh switches to `WEIGHT_PAINT`, and the VR controller paints real vertex-group weights. Use Paint or Erase, switch groups, change brush size/strength and exit with Done (Object Mode). The status tells you whether the controller ray hit a mesh; Weight Paint does not automatically parent the object.

To parent like Blender Ctrl+P, select your mesh and rig (armature active) or use the remembered pairing from Create Armature. Open **Rigging → Parent** and choose Automatic Weights, Empty Groups, Envelope Weights, Armature Deform or Object Parent. Clear Parent retains the mesh transform. Repeat parenting is guarded so existing painted weights are preserved. The Model sidebar offers equivalent commands. These features are covered by Blender tests but still need headset acceptance testing.

## 0.7.6 Blender-style controller selection and transforms

The former Select Mesh and Select Rig actions have been consolidated into **Select**. Aim at a visible armature bone or mesh in Object Mode; repeated selection over an overlapped rig/mesh switches the target. In Mesh Edit Mode, Select points/edges/faces directly, including nearby loose elements. Hold the controller's **Grip** to grab and move selected geometry or an object; choose **Move**, **Scale**, or **Rotate** then hold **Trigger** to transform with controller motion. Bone editing and Pose Mode use the same context-based select and transform gestures. All controller transforms have VR-local Undo/Redo support. The old modelling tools remain accessible, and an automated menu audit checks for duplicate actions. Hardware testing remains required for v0.7.6 acceptance.

## 0.7.6 paired rigging and controller weight painting

The Rigging page includes **Select Rig** and **Select Mesh**. Mesh XR remembers which mesh belongs to the rig even before parenting; Bind Empty Groups and Auto Weights therefore work without manually reselecting both. Select Mesh opens the actual mesh, Select Rig returns to the armature, and Grip+Trigger adds another Object Mode selection. Enter Weight Paint to select the first available vertex group (automatically creating empty groups if the mesh is not yet bound); the headset displays Paint, Erase, Previous/Next Group, Strength +/- and Brush Size +/-. Aim at the model and hold the dominant Trigger to apply or erase native Blender vertex-group weights. Done returns to Object Mode, while Pose tests the deforming skeleton. These interactions coexist with existing standard mesh Object/Edit controls. **Test on headset** before release.

## 0.7.6 controller armature editing

In the VR Rigging page choose **Select Rig** or point directly at an armature bone in Object Mode. Choose **Edit Bones** to open the dedicated in-headset bone editor. Trigger selects bones; choose Move, Head or Tail to move them with the controller. Selection, topology/parenting, roll and settings submenus expose native Blender bone editing tools. Choose Finish to return to Object Mode. The desktop Model workspace also includes **Edit Bone Tools** and Blender's own complete Edit Armature menu for advanced options. These VR interactions need hardware validation before v0.7.6 acceptance.

## 0.7.6 freeform rigging

The old `Create Basic Human Rig` action is now **Create Armature**. Any mesh shape is accepted (or select no mesh to create at the 3D cursor). The new armature has one editable bone. Select it, choose **Edit Bones** and add or extrude bones in Blender; **Finish Bones** exits editing. Select the mesh plus the armature, make the armature active, and click **Empty Groups** to bind for manual Weight Paint. **Auto Weights** remains optional. Select the bound mesh and click **Paint**. You can add bones from the headset menu, but precise Edit Bone positioning is in Blender's native desktop armature tools. The old operator ID is retained for compatibility. This stays version 0.7.6 while testing.

## 0.7.6 UI preview

All workspaces, nested desktop panels and actionable headset menus are now intended to show icons. Core-menu icon occlusion is fixed and controller menus use line-symbol fallbacks if a packaged icon cannot render. The current build is a tester candidate; keep version 0.7.6 until manual headset checks pass.


In the 3D View, open the **Blender XR** sidebar. The compact native-icon selector switches between Session, Model, Material, UV, Travel, Project and Help. Start/Stop VR and a short status remain visible above it. Advanced material, UV and workflow sections are collapsed subpanels shown only with their matching workspace. Every button keeps its underlying Blender operator and descriptive hover tooltip.

The test ZIP is built from the draft pull request as `mesh-xr-v0.7.6.zip`. This is not a headset-hardware-verified release.


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
- **Asset readiness:** read-only topology/UV/material audit, separate base and evaluated triangle counts, and a configurable budget checked against the evaluated mesh when available.
- **Rigging:** proportion-based starter humanoid armature, Blender automatic-weight binding, weight cleanup/normalization and native Weight Paint mode entry, with selection restoration and cleanup when setup fails.
- **Workflow panel:** a collapsed-by-default desktop panel groups asset checks, rigging and controller modeling guidance.

XR shutdown also returns the active Mesh XR viewport from headset mirroring to the regular PC view. Unexpected XR-session termination is cleaned up promptly.

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
