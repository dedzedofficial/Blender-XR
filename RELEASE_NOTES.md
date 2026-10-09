# Blender XR v0.5.0

v0.5 turns the earlier face-focused editor into a broader VR mesh-modeling workflow.

## New in v0.5

- Added **Vertex / Edge / Face** selection modes directly in the VR edit menu.
- Grip + trigger keeps additive/toggle selection across all three mesh selection modes.
- Move and Scale now work on selected vertices, edges or faces through the existing VR gizmos.
- Extrude now supports selected vertices, edges and faces.
- Bevel supports vertex and edge workflows; Inset remains face-only.
- Delete now removes the currently selected geometry type instead of only faces.
- Added **Merge**, **Subdivide**, **Duplicate**, **Recalculate Normals** and **Flip Normals** actions.
- Added a compact secondary edit-tools page so the hand menu stays readable instead of becoming one large panel.
- Added dedicated VR selection feedback for vertices, edges and faces.
- Preserved object movement/scaling, primitives, scene flight, ray mesh switching, Save Blend, Undo/Redo and experimental finger features.
- Patreon and Website buttons remain available at the bottom of the Blender sidebar.

## Compatibility

Automated regression coverage now includes the v0.5 mesh workflow on Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**. Blender 5.0.1 remains blocked because of its known VR crash.

Physical headset/runtime testing is still ongoing, so the automated matrix should not be treated as a complete hardware compatibility matrix.
