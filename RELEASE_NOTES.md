# Blender XR v0.4.2

Navigation and mesh-selection update by Ded Zed.

- Left stick flies through the scene; right stick turns and changes altitude, independent of dominant hand.
- Faster default flight, optional level walk, left-stick click 4x boost, persistent turbo and Travel speed controls.
- 30-degree snap turning with release-to-rearm, optional smooth turning and configurable angle/speed.
- Turning pivots around the viewer's head without moving scene objects.
- Updated Tools, Shapes and Travel pages with larger labels, selected mesh name, active state and hints.
- Green ray and bounds highlight the mesh under the pointer.
- SELECT can ray-switch meshes while face editing; invalid targets are refused before leaving the old mesh.
- Regression checks for full flight, turning, both-handed controls, real ray switching and all menu pages.

Install **blender-xr-v0.4.2.zip**, or stop VR and use Download & Install, then restart Blender. v0.4.1 remains available.

Automated tests cover Blender 5.0.0 and 5.2.2. Real Quest/Valve hardware, Windows and stereo UI readability remain pending. Existing basic mesh tools, primitive creation, grab-air movement and experimental finger bridge remain included.
