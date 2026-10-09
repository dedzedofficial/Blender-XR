# Blender XR v0.4.1

Fixing update by Ded Zed. All changes remain under v0.4.1.

- Fixed AttributeError: Event has no attribute timer, which interrupted the VR control loop.
- Left thumbstick now moves the viewer independently of dominant-hand choice.
- Either-hand grip into empty space lets you pull yourself around in 3D. Point at a mesh in MOVE to grip the object instead.
- Added a hand-menu primitive picker: cube, sphere, cylinder, cone, torus and plane.
- Placement bounds preview, surface placement, configurable shape size and empty-space placement distance.
- New primitive creation supports VR-local undo/redo and creates ordinary Blender meshes for further editing.
- Regression tests reproduce the timer failure and check locomotion, grip priority, placement and creation history.

Install **blender-xr-v0.4.1.zip** through Install from Disk, or use the existing GitHub Download & Install button with VR stopped. Restart Blender after installation, especially if the previous VR loop raised an error.

Existing Meta/Valve presets, mesh tools and experimental finger bridge remain included. Controller mode is the default. Real Quest/Valve hardware testing remains pending; automated checks use Blender 5.0.0 and 5.2.2.
