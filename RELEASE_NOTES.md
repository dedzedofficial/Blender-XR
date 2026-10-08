# Blender XR v0.4.0

Free development release by Ded Zed.

- Automatic, Meta and Valve/SteamVR controller presets, with Touch, Index, Vive and simple bindings.
- Expanded compatibility target matrix for Quest/Rift and Valve Index/Steam Frame. Newer native controller profiles depend on runtime compatibility; all physical combinations remain unverified.
- Optional Touch/Index finger-touch hold shortcuts for menu access and cancellation.
- Experimental free SteamVR skeletal helper: thumb/index pinch for selection/tool previews, finger curl for MOVE grab, other-hand pinch for menu/cancel.
- Input-loss cancellation, release-before-arming, session-key loopback input and hardware-free regression tests.
- Existing extrude, bevel, inset, move/rotate, VR history and GitHub updater remain included.

Install **blender-xr-v0.4.0.zip**, not GitHub's source-code ZIP. Restart Blender after updating.

Controller mode is the default. Finger bridge mode requires system Python, the optional openvr package, SteamVR skeletal input, and tracked controller/hand poses. It does not implement native Air Link controller-free hand tracking. Consult the README before enabling it.

Automated checks cover Blender 5.0.0 and 5.2.2. Real headsets, Windows and the experimental bridge's simultaneous SteamVR input need user testing. Requires OpenXR; Blender 5.0.1 is blocked due to its known VR crash.
