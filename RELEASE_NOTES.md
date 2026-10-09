# Blender XR v0.4.3

Fixing update by Ded Zed.

- Fixed the unsupported BOOLEAN XR action enum that prevented session startup. Optional touch and boost inputs now use Blender-supported FLOAT actions.
- Added real Blender RNA action-type regression validation to catch this error without a headset.
- Save Blend in Tools/Travel and the desktop sidebar. Existing projects save to the current filepath; unsaved projects get a timestamped file in Documents/BlenderXR, with an optional first-save path.
- Committed edit-mode geometry is saved; private VR history stays out of the .blend file while current-session undo remains available.
- Blender minimum lowered to 4.2.0, with automated checks on 4.2.0, 4.5.0, 5.0.0 and 5.2.2.

Install **blender-xr-v0.4.3.zip**, or stop VR and use Download & Install, then restart Blender. This is an installable extension for Blender 4.2+ with OpenXR.

Physical headset, Windows saving paths and stereo rendering remain pending user testing. Existing navigation, primitive creation, ray selection and mesh tools remain included.
