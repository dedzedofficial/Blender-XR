# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared selection helpers for Blender XR mesh tools."""
import bpy
import bmesh

SELECT_MODES = ('VERT', 'EDGE', 'FACE')
_SELECTION_FLAGS = {mode: tuple(mode == candidate for candidate in SELECT_MODES)
                    for mode in SELECT_MODES}
_BM_COLLECTIONS = {'VERT': 'verts', 'EDGE': 'edges', 'FACE': 'faces'}


def mode(context=None):
    context = context or bpy.context
    flags = tuple(bool(value) for value in context.tool_settings.mesh_select_mode)
    if flags[0]:
        return 'VERT'
    if flags[1]:
        return 'EDGE'
    return 'FACE'


def set_mode(context, selection_mode):
    if selection_mode not in SELECT_MODES:
        raise ValueError('Unknown mesh selection mode')
    context.tool_settings.mesh_select_mode = _SELECTION_FLAGS[selection_mode]
    obj = context.view_layer.objects.active
    if obj and obj.type == 'MESH' and obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(obj.data)
        bm.select_mode = {selection_mode}
        bm.select_flush_mode()
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)


def selected_indices(obj, selection_mode):
    if not obj or obj.type != 'MESH' or obj.mode != 'EDIT':
        return []
    bm = bmesh.from_edit_mesh(obj.data)
    collection = getattr(bm, _BM_COLLECTIONS[selection_mode])
    collection.ensure_lookup_table()
    collection.index_update()
    return [item.index for item in collection if item.is_valid and item.select and not item.hide]


def restore_indices(obj, selection_mode, indices):
    if not obj or obj.type != 'MESH' or obj.mode != 'EDIT':
        return
    bm = bmesh.from_edit_mesh(obj.data)
    for collection in (bm.verts, bm.edges, bm.faces):
        for item in collection:
            item.select_set(False)
    collection = getattr(bm, _BM_COLLECTIONS[selection_mode])
    collection.ensure_lookup_table()
    for index in indices:
        if 0 <= index < len(collection):
            item = collection[index]
            if item.is_valid and not item.hide:
                item.select_set(True)
    bm.select_mode = {selection_mode}
    bm.select_flush_mode()
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)


def counts(obj):
    if not obj or obj.type != 'MESH' or obj.mode != 'EDIT':
        return {'VERT': 0, 'EDGE': 0, 'FACE': 0}
    bm = bmesh.from_edit_mesh(obj.data)
    return {
        'VERT': sum(1 for item in bm.verts if item.is_valid and item.select and not item.hide),
        'EDGE': sum(1 for item in bm.edges if item.is_valid and item.select and not item.hide),
        'FACE': sum(1 for item in bm.faces if item.is_valid and item.select and not item.hide),
    }
