# Blender XR v0.5.2

v0.5.2 is a focused quality-of-life update built on the v0.5 mesh-editing release.

## New in v0.5.2

- Added a native Blender **color picker / hue wheel** for the active mesh object.
- In **Object Mode**, **Apply Color** updates the object's viewport color and active Principled BSDF Base Color.
- In **Face Edit Mode**, select one or more faces, choose a color and press **Apply Color** to automatically create or reuse a matching material and assign it only to those selected faces.
- This allows multi-material objects such as a cone with an orange body and a grey base without leaving the Blender XR workflow.
- Reapplying an existing color reuses its matching material slot instead of creating unnecessary duplicate materials.
- Shared materials are copied before whole-object recoloring so changing one object does not unexpectedly recolor others.
- Added a **Scene Statistics** section showing visible Objects, Selected Objects, Meshes, Materials, Vertices, Edges, Faces and Triangles.
- Added an active-object V/E/F/T statistics readout.
- Added **Shade Smooth** and **Shade Flat** controls.
- Preserved the full v0.5 vertex/edge/face workflow, axis gizmos, primitives, scene travel, Save Blend and VR-local Undo/Redo.
- Updated the roadmap with the v1 direct-hand transform target and dominant-thumbstick-click **Extrude-to-Hand** while retaining the current axis-based tools.

## Compatibility

Automated validation targets Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**. Blender 5.0.1 remains blocked because of its known VR crash.

Scene Statistics currently reports base-mesh geometry rather than evaluated modifier output. Physical headset/runtime behavior can still vary even when automated Blender tests pass.
