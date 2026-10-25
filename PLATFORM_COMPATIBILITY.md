# Mesh XR — macOS Desktop Compatibility (v0.8 development)

**Scope:** Add Mesh XR support for **Mac computers running desktop Blender**, including **Apple Silicon (M-series)** and **Intel Macs on compatible Blender versions**. Retain the existing **Windows x64 and Linux x64** support without expanding their platform work in this milestone.

**Not in scope:** iOS, iPadOS, Apple Vision Pro, a phone/tablet companion, or a native standalone Quest/Android app. Those are not macOS desktop systems.

## Platform and Blender support

| Host | Blender edition | Mesh XR desktop tools | OpenXR / immersive VR |
| --- | --- | --- | --- |
| macOS Apple Silicon (M1/M2/M3/M4 and successors) | Blender 4.2–5.2 supported in the extension's Blender version range; prefer current supported Blender builds | Packaged and native macOS packaging CI tested | Blender 5.1+ includes **preliminary** macOS OpenXR; **actual headset runtime and tracking are not verified** |
| macOS Intel (x86-64) | **Blender 4.5 LTS and earlier**, including 4.2 | Packaged and native Intel macOS packaging CI tested | Not a supported production target; Blender 4.5 predates macOS OpenXR and Blender 5.0+ has no official Intel Mac build |
| Windows x64 | Supported Blender versions | Existing support preserved | Existing compatible PC OpenXR runtime required |
| Linux x64 | Supported Blender versions | Existing support preserved; Blender 4.2/4.5/5.0/5.2 regression CI | Existing compatible Linux OpenXR runtime required |

Blender officially ended Intel Mac builds with **Blender 4.5 LTS**. Blender 5.0+ on macOS requires Apple Silicon (macOS 13 or later). Blender 5.1 introduced preliminary OpenXR graphics binding for macOS, with testing possible through simulator software; **a physical macOS OpenXR headset runtime was not established in the 5.1 release notes**. Supporting macOS desktop modelling does *not* mean Quest controllers, hand tracking or the VR radial menu are hardware-verified on Mac.

## macOS installation

1. Install the **Mac-compatible desktop Blender build** from [blender.org](https://www.blender.org/download/). For Intel Macs use Blender 4.5 LTS, not Blender 5.x.
2. Open Blender → **Edit → Preferences → Get Extensions** (or **Install from Disk** in the extensions menu, depending on Blender version) and select the **Mesh XR v0.8 installer ZIP**.
3. Open the 3D Viewport → **Mesh XR / Blender XR** sidebar. Standard Blender-side modelling, rigging, UV and material tools are available without VR hardware.
4. Check the **Session → Platform** section before selecting Start VR. On Mac, OpenXR VR is disabled for Blender versions below 5.1 and labelled experimental where compiled OpenXR is available.
5. Do not expect a headset to connect without a real compatible OpenXR runtime; if unavailable, continue with standard Blender desktop tools.

The ZIP is a platform-neutral Python Blender extension containing a platform-independent OpenVR wheel, not a standalone macOS app or .dmg. No iPhone/iPad app is needed or planned for this scope.

## Compatibility checks and remaining work

- [x] Package declares `macos-arm64` and `macos-x64` in its Blender extension manifest, while preserving the existing `windows-x64` / `linux-x64` hosts.
- [x] Detect macOS host architecture and Blender version; provide helpful Intel Mac and experimental OpenXR messages.
- [x] Run ZIP packaging, integrity, controller-protocol, radial input and platform tests on native **Apple Silicon and Intel macOS** GitHub runners.
- [ ] Execute and record native Blender registration and user-tool smoke tests on physical/CI macOS installs for Intel 4.5 and Apple Silicon 5.2 (tracked separately from packaging tests).
- [ ] Verify XR graphics, controller mapping, non-dominant thumbstick radial selection, and tracked fingers on **actual compatible Mac headset runtime** if such a runtime is available.
- [ ] Confirm packaging, menu readability, and performance in real Blender GUI sessions on both architectures.

Only claim the support level actually tested: **packaging**, **Blender extension registration/operators**, and **XR headset behaviour** are separate gates.

## Official references

- [Blender minimum system requirements](https://www.blender.org/download/requirements/)
- [Blender 4.5 LTS is last Intel Mac build](https://devtalk.blender.org/t/deprecation-and-removal-of-macos-intel-builds-in-blender-5-0/38835)
- [Blender 5.1 preliminary OpenXR on macOS](https://developer.blender.org/docs/release_notes/5.1/virtual_reality/)
- [Blender official extension platforms](https://developer.blender.org/docs/features/extensions/schema/1.0.0/)
