# Mesh XR v0.6.4

v0.6.4 is a focused Blender Extensions compatibility and packaging update. It keeps the existing v0.6 modeling, materials, texture and UV feature set while making the optional SteamVR hand bridge self-contained for extension installs.

## Blender Extensions dependency fix

- Bundles **openvr 2.12.1401** as the official `openvr-2.12.1401-py3-none-any.whl` Python wheel required by the SteamVR skeletal hand helper.
- Declares that wheel in `blender_manifest.toml` using Blender's supported extension-wheel mechanism.
- The build downloads the unchanged upstream PyPI wheel when needed and verifies its published SHA-256 before packaging.
- The generated extension ZIP is rejected by the build if the wheel is missing or its checksum does not match.
- The external hand helper reuses the extension's installed `site-packages` through its own process environment, so users no longer need to run `pip install openvr` themselves and Blender's module search path is not modified.

## Naming and packaging

- Current extension/add-on branding is now **Mesh XR**.
- Blender's sidebar, View menu, preferences text and in-headset menu header use Mesh XR branding.
- The stable extension ID and Blender operator namespace remain `blender_xr` for install/update compatibility with the existing extension entry and project code.
- Release archives are now named `mesh-xr-v0.6.4.zip` with a matching SHA-256 file.
- GitHub Actions and release titles now use Mesh XR branding.

## Validation improvements

- CI verifies the OpenVR wheel is physically present in every generated extension package.
- Clean-profile extension smoke tests import the bundled `openvr` module after installing the generated ZIP.
- Automated validation continues across Blender **4.2.0, 4.5.0, 5.0.0 and 5.2.2**.
- The add-on still contains no Python `threading` or `queue` imports.
- The in-extension updater remains removed; updates continue to be managed through Blender Extensions.

## Existing v0.6 features retained

Mesh XR still includes vertex/edge/face selection and editing, Move/Scale Selected, extrude, bevel, inset, delete, merge, subdivide, duplicate, normals tools, object movement/scaling, primitives, flight/navigation, save, session Undo/Redo, HSL and per-face colors, materials, texture images, diagnostic textures, UV unwrap/projection/editing, UV preview, shading and scene statistics.

## Compatibility

Requires Blender **4.2+** with OpenXR support. Blender 5.0.1 remains blocked because of its known VR crash. Standard controller operation does not depend on OpenVR; the bundled OpenVR wheel is used by the optional experimental SteamVR skeletal hand bridge.

See `CHANGELOG.md` for shipped history, `ROADMAP.md` for future work and `TESTING.md` for validation coverage.
