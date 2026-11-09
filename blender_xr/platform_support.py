# SPDX-License-Identifier: GPL-3.0-or-later
"""Cross-platform desktop and OpenXR capability reporting for Mesh XR.

The extension is installed *in desktop Blender*. Running the add-on itself
does not imply a functioning OpenXR runtime or headset connection.
This module intentionally has no bpy dependency for OS-independent tests.
"""
import platform

DESKTOP_EXTENSION_TARGETS = (
    'windows-x64', 'linux-x64', 'macos-x64', 'macos-arm64',
)


def desktop_platform(system=None, machine=None):
    """Return Blender's declared extension platform tag, or None."""
    if system is None:
        system = platform.system()
    if machine is None:
        machine = platform.machine()
    system = str(system).lower()
    machine = str(machine).lower()
    if system == 'windows':
        return 'windows-x64' if machine in ('amd64', 'x86_64', 'x64') else None
    if system in ('darwin', 'macos'):
        return 'macos-arm64' if machine in ('arm64', 'aarch64') else (
            'macos-x64' if machine in ('x86_64', 'amd64') else None)
    if system == 'linux':
        return 'linux-x64' if machine in ('x86_64', 'amd64') else None
    return None


def support_info(blender_version=(5, 2, 2), has_openxr=False,
                 system=None, machine=None):
    """Return install and XR-start readiness, without assuming a headset.

    Desktop Blender compatibility can be determined locally. Presence of a
    compatible and active OpenXR runtime still requires a live XR start test.
    """
    tag = desktop_platform(system, machine)
    if tag is None:
        return {'tag': None, 'desktop': False, 'vr': False,
                'message': 'Mesh XR requires a supported desktop Blender installation on Windows x64, Linux x64, or macOS Intel/Apple Silicon'}
    version = tuple(int(part) for part in blender_version[:3])
    if tag == 'macos-x64' and version >= (5, 0, 0):
        return {'tag': tag, 'desktop': False, 'vr': False,
                'message': 'Blender 5.0+ requires Apple Silicon on macOS; use Blender 4.5 LTS on Intel Mac'}
    if not has_openxr:
        return {'tag': tag, 'desktop': True, 'vr': False,
                'message': 'Desktop Mesh XR tools available; this Blender build has no OpenXR VR support'}
    if tag.startswith('macos-'):
        if version < (5, 1, 0):
            return {'tag': tag, 'desktop': True, 'vr': False,
                    'message': 'Desktop tools work, but macOS OpenXR requires Blender 5.1+ and a compatible runtime'}
        return {'tag': tag, 'desktop': True, 'vr': True,
                'message': 'macOS OpenXR is experimental; a compatible active headset/runtime is still required'}
    return {'tag': tag, 'desktop': True, 'vr': True,
            'message': 'Desktop supported; VR requires a compatible active OpenXR runtime and headset'}


def current_info(bpy):
    return support_info(bpy.app.version,
                        bool(getattr(bpy.app.build_options, 'xr_openxr', False)))


def runtime_help(bpy):
    return current_info(bpy)['message']
