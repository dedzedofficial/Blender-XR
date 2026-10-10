# Blender XR v0.5.3

v0.5.3 is a cleanup and foundation release. It keeps the v0.5.2 workflow intact while making the project easier to extend safely toward Materials/UV, modifiers, rigging and the v1 direct-hand tools.

## New in v0.5.3

- Renamed the sidebar appearance workflow to a clearer **Materials** section.
- Added active material name and material-slot feedback.
- The color button now clearly reads **Apply to Object** in Object Mode and **Assign to Selected Faces** in Edit Mode.
- Scene Statistics can be collapsed and uses a short-lived cache instead of fully recounting geometry on every panel redraw.
- Blender XR now remembers the main controller, movement, modeling and statistics-panel settings between Blender files.
- Centralized material creation/reuse/face assignment in a dedicated material module.
- Centralized vertex/edge/face selection handling while keeping the existing mesh API compatible.
- Centralized transform helper behavior for the existing axis tools and future direct-hand transforms.
- Added safe shared Object/Edit mode transition helpers.
- Centralized short status messages used by the desktop and XR workflows.
- Moved VR menu page definitions out of the GPU drawing code so future Materials/UV pages can be added without growing the renderer.
- Reduced the old v0.5.2 helper file to a compatibility wrapper instead of continuing to grow version-specific files.
- Standardized gizmo sizing/picking constants while preserving the existing distance-aware behavior.
- Preserved v0.5.2 object/face color assignment, scene statistics, shading controls, mesh tools, primitives, navigation, Save Blend and VR-local Undo/Redo.

## Compatibility

Automated validation targets Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**. Blender 5.0.1 remains blocked because of its known VR crash.

The refactor intentionally leaves the proven controller input and locomotion loop structurally unchanged. Scene Statistics still reports base-mesh geometry rather than evaluated modifier output.
