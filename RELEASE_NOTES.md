# Mesh XR v0.7.1

## Advanced modeling
- Rotate objects on world X/Y/Z axes using 15° steps, reset rotation, and snap object origins to the configured modeling-step grid.
- Duplicate local mesh objects with modifiers and other object settings preserved through XR-local Undo/Redo.
- Rotate vertex, edge and face selections about their center on local X/Y/Z axes.
- Dissolve vertices or edges, fill selected boundary holes, bridge selected edge loops and recalculate normals.

## Modifiers
- Create Mesh XR-managed Mirror X/Y/Z, Array and Solidify modifiers.
- Change the last managed Array's count, Solidify's thickness, toggle visibility and remove the last managed modifier.
- Undo/Redo restores the Mesh XR-managed modifier state without editing third-party modifiers.

## Reliability and editing consistency
- Protect material deletion from reading the name of an already-removed Blender datablock.
- Require exactly one selected edge and reject non-quad paths for Loop Cut.
- Clear stale controller hover and tooltips on tracking loss.
- Track UV mapping/transform/seam commands and selected-face material assignment in XR-local history.

## Packaging and publishing
- Keep the Blender Extensions ID `blender_xr` and stable operator names.
- Continue bundling the verified OpenVR wheel and keeping the add-on free from prohibited in-extension updater code.
- Validate Python source and test the full installed extension against Blender 4.2.0, 4.5.0, 5.0.0 and 5.2.2 before publishing.
- Publish a new, immutable GitHub version when checks pass, then submit its ZIP through the Blender Extensions API using the configured token. Official availability depends on the platform's approval process.

## Known limits
- Rotation is stepped rather than a continuous hand-driven rotation gizmo.
- Modifier management deliberately affects Mesh XR-managed modifiers; applying/reordering other modifiers is deferred.
- General-purpose numeric transforms, direct selected-geometry hand manipulation, rigging and animation remain roadmap work.
- Real headset compatibility needs physical validation, not only automated Blender tests.
