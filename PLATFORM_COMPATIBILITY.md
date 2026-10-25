# Mesh XR — Platform Compatibility (v0.8 development)

**Desktop extension target:** Windows, Linux and macOS, on supported Blender versions and architectures.
**Important:** Platform-compatible packaging does **not** guarantee an XR runtime or headset connection. Mesh XR remains a Blender desktop add-on that requires Blender to be running on the host.

## Desktop platform matrix

| Host | Blender extension | Immersive VR | Known conditions |
| --- | --- | --- | --- |
| Windows x64 | Packaged and CI-tested | Targeted | Compatible OpenXR runtime/headset, e.g. Windows Quest Link/SteamVR. Real-device testing required. |
| Windows ARM64 | Packaged, architecture not device-tested | Runtime-dependent | Blender version and native ARM64 OpenXR/driver support may differ from x64. Do not promise all VR headsets. |
| Linux x64 | Packaged; Blender 4.2/4.5/5.0/5.2 integration CI | Runtime-dependent | OpenXR runtime (e.g. SteamVR/Monado) and compatible Linux headset stack required. |
| macOS Apple Silicon (ARM64) | Packaged; native macOS packaging CI | **Experimental** from Blender 5.1 | Blender added preliminary Metal/OpenXR graphics support, but a real compatible headset runtime is not established. Simulator-only testing is not evidence of physical HMD support. |
| macOS Intel x64 | Packaged; native macOS packaging CI | Not supported for production | Blender 4.5 LTS is the last Intel Mac version; Blender 5.1+ preliminary macOS XR requires newer Blender/Apple Silicon. |
| Linux ARM64 | Outside currently published Blender Extensions platform tags | Not claimed | No official `linux-arm64` extension host identifier. |
| iPhone / iPad (iOS / iPadOS) | **No native Blender extension** | Not applicable to this ZIP | Requires a separate application, not this Blender add-on. |
| Quest standalone (Android) | **No native desktop Blender extension** | Not applicable to this ZIP | Requires separate native app or streaming from PC Blender. |

This single packaged extension is pure Python with a pure-Python `py3-none-any` OpenVR wheel and platform-neutral icon assets. Installation on a desktop host is independent of whether the optional SteamVR skeletal bridge has an active runtime.

## VR host startup behavior

The **Session** workspace reports the detected desktop target and VR readiness. **Start VR** is blocked with a clear explanation when Blender lacks OpenXR support, or when a macOS build predates Blender 5.1. Blender's OpenXR startup ultimately checks the presence of a running compatible headset runtime.

- Standard controller-based functionality should not depend on SteamVR. The skeletal bridge is opt-in and may not work on all hosts.
- Mac users can still use the regular desktop panels, materials, UV tools and rigging functions even when no physical XR runtime is available.
- Windows ARM64, macOS and Linux device/runtime compatibility require native testing; successful ZIP installation alone is not proof of correct controller bindings or GPU rendering.
- Hand visuals, GPU overlays, haptics and XR controller action maps must each be tested on real hardware/runtime combinations.

## iOS / iPadOS: separate companion application (future feasibility project)

To support Apple mobile devices usefully, propose a **remote controller/companion** rather than falsely claiming Blender can run on iOS.

1. A native or cross-platform app renders a lightweight live preview of the Blender scene streamed from an authenticated desktop host.
2. It exposes scene navigation, selection, hand/radial controls and opt-in gesture input as a remote control for Mesh XR.
3. Full mesh geometry, modifiers, projects, rigs and data edits remain on the desktop Blender host; iOS is an input/display client.
4. Use local pairing with explicit one-time authorization, secure transport and disconnection safety. Do **not** expose unauthenticated Blender Python execution or an open network port.
5. iOS camera-based hand tracking and AR/visionOS immersive usage are separate investigations: actual hand joint APIs, performance and Apple distribution restrictions must be verified.
6. Standalone Android Quest would likewise require a separate native renderer and bridge; not a modification to the existing desktop extension ZIP.

**No iOS, iPadOS, visionOS or standalone Android app has been built by this milestone.**

## Verification plan

- Blender 4.2.0, 4.5.0, 5.0.0, 5.2.2 headless regression matrix on Linux.
- Python compatibility/unit and ZIP build/checksum smoke tests running on native Windows/macOS hosts.
- Gradually extend to full Blender headless registration and Blender operators on Windows, macOS ARM64 and eligible older Intel Macs.
- Real OpenXR tests on Windows and Linux (and future macOS when compatible runtime/headset exists).
- Maintain a compatibility table with **packaged / installed / Blender-tested / real-HMD-tested** as separate statuses.

## References

- [Blender system requirements](https://www.blender.org/download/requirements/)
- [Blender 5.1 OpenXR on macOS](https://developer.blender.org/docs/release_notes/5.1/virtual_reality/)
- [Blender Extensions manifest platform identifiers](https://developer.blender.org/docs/features/extensions/schema/1.0.0/)
- [Blender XR runtime architecture](https://developer.blender.org/docs/features/gpu/viewports/xr/)
