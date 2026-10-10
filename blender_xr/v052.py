# SPDX-License-Identifier: GPL-3.0-or-later
"""v0.5.2 compatibility wrappers kept for older tests/imports.

The implementation now lives in purpose-based modules used by v0.5.3+.
"""
from . import materials, statistics


def apply_object_color(obj, color):
    if obj and obj.mode == 'EDIT':
        material, _count, _slot = materials.assign_color_to_selected_faces(obj, color)
        return material
    return materials.apply_object_color(obj, color)


def assign_color_to_selected_faces(obj, color):
    material, count, _slot = materials.assign_color_to_selected_faces(obj, color)
    return material, count


def set_shading(obj, smooth):
    obj = materials.editable_mesh_object(obj)
    for polygon in obj.data.polygons:
        polygon.use_smooth = bool(smooth)
    obj.data.update()
    statistics.invalidate()
    return len(obj.data.polygons)


def scene_stats(context):
    return statistics.scene_stats(context)
