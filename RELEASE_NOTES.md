# Blender XR v0.3.0

Initial free development release by Ded Zed.

- Dominant-hand selection before entering VR.
- Non-dominant hand menu and dominant hand selection/control.
- Face extrusion, bevel, inset, and object movement/rotation.
- Continuous previews, cancel, and 20-step VR-local undo/redo.
- GitHub update buttons with private repository authentication, checksum verification, rollback, and restart prompt.

Install **blender-xr-v0.3.0.zip**, not GitHub's source-code ZIP.

Automated checks run in Blender 5.0.0 and 5.2.2. Physical Quest 3, Air Link, SteamVR, Virtual Desktop, and Windows updater testing remain pending. The OpenXR connection paths are intended targets, not verified compatibility claims.

Requires a Blender build with OpenXR. Blender 5.0.1 is blocked because of its known VR crash. v0.3 edits one local, single-user mesh without shape keys. Use the VR menu for undo/redo during a session.
