# SPDX-License-Identifier: GPL-3.0-or-later
"""Load packaged icon PNGs as cached GPU textures for the world-space XR menu."""
from pathlib import Path

import bpy
import gpu

_ICON_DIR = Path(__file__).resolve().parent / "icons"
_CACHE = {}
_MISSING = set()


def texture_for(name):
    """Return a cached GPUTexture, or None when an optional icon is unavailable."""
    if not name or name in _MISSING:
        return None
    cached = _CACHE.get(name)
    if cached:
        return cached[1]
    path = _ICON_DIR / (name + ".png")
    if not path.is_file():
        _MISSING.add(name)
        return None
    try:
        image = bpy.data.images.load(str(path), check_existing=True)
        image.alpha_mode = 'STRAIGHT'
        texture = gpu.texture.from_image(image)
    except (RuntimeError, ValueError, TypeError):
        _MISSING.add(name)
        return None
    _CACHE[name] = (image, texture)
    return texture


def clear_cache():
    """Release Python references; Blender owns the underlying image datablocks."""
    _CACHE.clear()
    _MISSING.clear()
