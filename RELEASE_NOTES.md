# Blender XR v0.5.5

v0.5.5 restores a clear native Blender desktop launch path for Blender XR without changing the existing VR modeling workflow.

## New in v0.5.5

- Kept the existing **3D Viewport > Sidebar > Blender XR > Start VR** button.
- Added **3D Viewport > View > Start Blender XR** as a second native Blender launch entry.
- The View menu entry automatically changes to **Stop Blender XR** while a Blender XR session is active.
- Fixed a Blender 5.2 sidebar draw failure where restoring persistent settings attempted to write Scene properties from `Panel.draw()`, causing `Writing to ID classes in this context is not allowed` and preventing the Blender XR panel from drawing.
- Persistent settings now restore immediately where Blender permits writes and automatically defer to a safe timer callback when invoked from a restricted UI draw context.
- Added Blender-side regression coverage so the launch operator, panel version, native View-menu entry and draw-context restore fallback are checked across supported Blender versions.
- Added a clean-profile package smoke test that installs and enables the built ZIP through Blender's Extensions CLI before validating registration.
- Updated package metadata and documentation to v0.5.5.

## About Blender's own VR button

Blender's separate **VR Scene Inspection** add-on exposes Blender's native **VR** sidebar and **Start VR Session** control. Blender XR does not remove or replace that add-on. If that native Blender VR tab is missing, enable **VR Scene Inspection** in Blender's add-on/extensions preferences. Blender XR itself can now be launched from either its own sidebar or the 3D Viewport **View** menu.

## Compatibility

Automated validation targets Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**. Blender 5.0.1 remains blocked because of its known VR crash.

All v0.5.3 materials, scene statistics, persistence, mesh editing, primitives, navigation, Save Blend and VR-local Undo/Redo behavior remains available.
