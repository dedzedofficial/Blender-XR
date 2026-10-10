# SPDX-License-Identifier: GPL-3.0-or-later
"""Safe object/edit mode transitions for Blender XR."""
import bpy
from . import selection


def enter_edit(context, obj, selection_mode='FACE'):
    if not obj or obj.type != 'MESH':
        raise ValueError('Select a mesh object')
    if obj.library or obj.data.library or obj.data.users > 1 or obj.data.shape_keys:
        raise ValueError('Use a local single-user mesh without shape keys')
    if any(other.mode == 'EDIT' for other in context.view_layer.objects if other != obj):
        raise ValueError('Leave other edit modes first')
    for other in context.selected_objects:
        if other != obj:
            other.select_set(False)
    context.view_layer.objects.active = obj
    obj.select_set(True)
    if obj.mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')
    selection.set_mode(context, selection_mode)
    return obj


def exit_edit(context, obj):
    if not obj or obj.type != 'MESH':
        raise ValueError('Select a mesh object')
    if obj.mode == 'EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')
    return obj


def switch_active_mesh(context, current, target, keep_edit=False, selection_mode='FACE'):
    if not target or target.type != 'MESH':
        raise ValueError('Point at a mesh')
    was_editing = bool(current and current.mode == 'EDIT')
    if was_editing:
        exit_edit(context, current)
    for selected in context.selected_objects:
        selected.select_set(False)
    target.select_set(True)
    context.view_layer.objects.active = target
    if keep_edit:
        enter_edit(context, target, selection_mode)
    return target
