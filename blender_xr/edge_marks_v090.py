# SPDX-License-Identifier: GPL-3.0-or-later
"""Native edit-mesh edge seam/sharp flags with guarded XR-local Undo.

Blender's BMEdge.seam and BMEdge.smooth are the only authored data. Changes
do not split geometry, alter UV loops, create custom attributes or require a
new mesh datablock. Undo/Redo refuses stale topology, selection and flags.
"""
import hashlib
import struct

import bpy
import bmesh

from . import (input_ownership_v080, menus, mesh, mesh_selection_tools_v086,
               runtime, selection, v065)

_PAGE = 'XR_EDGE_MARKS_090'
_ENTRY = 'XR_EDGE_MARK_MENU'
_TAG = 'XR_EDGE_FLAGS_090'
_ACTIONS = {
    'XR_EDGE_MARK_SEAM': ('seam', True),
    'XR_EDGE_CLEAR_SEAM': ('seam', False),
    'XR_EDGE_MARK_SHARP': ('smooth', False),
    'XR_EDGE_CLEAR_SHARP': ('smooth', True),
}
_MAX_EDGES = 150000


def _target(context):
    obj = mesh_selection_tools_v086._editable(context)
    if selection.mode(context) != 'EDGE':
        raise ValueError('Use Edge Select mode to mark native seam or sharp flags')
    bm, edges = mesh_selection_tools_v086._current(obj, 'EDGE')
    if len(edges) > _MAX_EDGES:
        raise ValueError('Native edge marking is limited to 150,000 edges')
    selected = tuple(e for e in edges if e.is_valid and e.select and not e.hide)
    if not selected:
        raise ValueError('Select at least one visible edge first')
    return obj, bm, edges, selected


def _signature(edges, exclude):
    """Guard all unmodified edge flags, including those outside selection."""
    digest = hashlib.blake2b(digest_size=16)
    for edge in edges:
        if edge.index in exclude:
            continue
        digest.update(struct.pack('<IBB', edge.index,
                                  int(edge.seam), int(edge.smooth)))
    return digest.digest()


def _plan(context, action):
    if action not in _ACTIONS:
        raise ValueError('Unsupported native edge flag operation')
    obj, bm, edges, selected = _target(context)
    prop, wanted = _ACTIONS[action]
    changes = tuple((edge.index, bool(getattr(edge, prop)), wanted)
                    for edge in selected
                    if bool(getattr(edge, prop)) != wanted)
    if not changes:
        return None
    touched = frozenset(row[0] for row in changes)
    return (
        _TAG, context.scene.name, context.view_layer.name,
        obj.name, obj.as_pointer(), obj.data.name, obj.data.as_pointer(),
        mesh_selection_tools_v086._topology(bm),
        mesh_selection_tools_v086._selected(edges),
        prop, _signature(edges, touched), changes,
    )


def _preflight(context, entry, backwards):
    (_tag, scene, layer, objname, objptr, meshname, dataptr,
     topo, indices, prop, untouched, changes) = entry
    obj, bm, edges, selected = _target(context)
    if (context.scene.name != scene or context.view_layer.name != layer or
            obj.name != objname or obj.as_pointer() != objptr or
            obj.data.name != meshname or obj.data.as_pointer() != dataptr or
            mesh_selection_tools_v086._topology(bm) != topo or
            mesh_selection_tools_v086._selected(edges) != indices):
        raise ValueError('Edge selection, geometry or scene changed since XR marking')
    touched = frozenset(row[0] for row in changes)
    if _signature(edges, touched) != untouched:
        raise ValueError('Other seam/sharp flags changed outside XR')
    expected = 2 if backwards else 1
    for index, before, after in changes:
        edge = edges[index]
        if not edge.is_valid or edge.hide or bool(getattr(edge, prop)) != (before, after)[expected-1]:
            raise ValueError('A marked edge was edited outside XR history')
    return obj, edges


def _write(context, entry, backwards):
    obj, edges = _preflight(context, entry, backwards)
    prop, changes = entry[9], entry[11]
    writes = []
    try:
        for index, before, after in changes:
            edge = edges[index]
            old, desired = bool(getattr(edge, prop)), (before if backwards else after)
            setattr(edge, prop, desired)
            writes.append((edge, old, desired))
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    except Exception:
        for edge, old, desired in reversed(writes):
            if edge.is_valid and bool(getattr(edge, prop)) == desired:
                setattr(edge, prop, old)
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        raise


def _apply(context, action, history=None):
    entry = _plan(context, action)
    if entry is None:
        return 0, False
    _write(context, entry, backwards=False)
    if history is not None:
        try:
            history.push(entry)
        except Exception:
            _write(context, entry, backwards=True)
            raise
    return len(entry[11]), True


def _history():
    if getattr(mesh.History, '_xr_edge_flags_090_patched', False):
        return
    prior_step, prior_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == _TAG:
            return
        return prior_release(entry)

    def step(self, backwards=True):
        src, dst = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not src or src[-1][0] != _TAG:
            return prior_step(self, backwards)
        entry = src[-1]
        dst.append(entry)
        try:
            _write(bpy.context, entry, backwards)
        except Exception:
            dst.pop()
            raise
        src.pop()
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_edge_flags_090_patched = True


class BXR_OT_edge_flags(bpy.types.Operator):
    bl_idname = 'blender_xr.edge_flags'
    bl_label = 'Edit Native Blender Edge Seams and Sharp Flags'
    bl_description = 'Mark or clear native seam and sharp flags on selected mesh edges'
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(
        items=(
            ('XR_EDGE_MARK_SEAM', 'Mark Seam', 'Set Blender UV seam on selected edges'),
            ('XR_EDGE_CLEAR_SEAM', 'Clear Seam', 'Remove native UV seam from selected edges'),
            ('XR_EDGE_MARK_SHARP', 'Mark Sharp', 'Mark selected edges sharp'),
            ('XR_EDGE_CLEAR_SHARP', 'Clear Sharp', 'Mark selected edges smooth'),
        ), default='XR_EDGE_MARK_SEAM')

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and context.mode == 'EDIT_MESH' and obj.type == 'MESH'
                    and selection.mode(context) == 'EDGE')

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Edge Marks wrist menu in a headset')
            return {'CANCELLED'}
        try:
            count, changed = _apply(context, self.action)
        except (RuntimeError, ValueError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        if not changed:
            self.report({'INFO'}, 'Selected native edge flags are unchanged')
            return {'CANCELLED'}
        self.report({'INFO'}, '{} native Blender edges updated'.format(count))
        return {'FINISHED'}


def install_pages():
    original = tuple(menus.PAGES[mesh_selection_tools_v086._FLOWS_PAGE])
    if not original or original[-1][1] != 'BACK':
        raise ValueError('Native Edge Flows menu is unavailable')
    if not any(action == _ENTRY for label, action in original):
        original = original[:-1] + (('MARK EDGES', _ENTRY), original[-1])
    if len(original) > 12:
        raise ValueError('Edge Flows menu cannot hold native seam marking')
    menus.PAGES[mesh_selection_tools_v086._FLOWS_PAGE] = original
    menus.PAGES[_PAGE] = (
        ('MARK SEAM', 'XR_EDGE_MARK_SEAM'),
        ('CLEAR SEAM', 'XR_EDGE_CLEAR_SEAM'),
        ('MARK SHARP', 'XR_EDGE_MARK_SHARP'),
        ('CLEAR SHARP', 'XR_EDGE_CLEAR_SHARP'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'EDGE SEAMS AND SHARPS'
    v065.TOOLTIPS.update({
        _ENTRY: ('Native Edge Marks',
                 'Edit selected native Blender seam or sharp flags in Edge Mode'),
        'XR_EDGE_MARK_SEAM': ('Mark UV Seam',
                 'Add Blender UV seam to selected native edges'),
        'XR_EDGE_CLEAR_SEAM': ('Clear UV Seam',
                 'Remove Blender UV seam without changing UV loop coordinates'),
        'XR_EDGE_MARK_SHARP': ('Mark Sharp Edge',
                 'Set the selected native edges to sharp shading'),
        'XR_EDGE_CLEAR_SHARP': ('Clear Sharp Edge',
                 'Return the selected native edges to smooth shading'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_edge_flags_090_patched', False):
        return
    _history()
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        page = getattr(menu, 'page', None)
        if action == _ENTRY and page == mesh_selection_tools_v086._FLOWS_PAGE:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release active XR gestures before marking edges')
            _target(context)
            menu.page = _PAGE
            self.status = 'NATIVE EDGE SEAMS / SHARPS'
            return
        if page == _PAGE:
            if action == 'BACK':
                menu.page = mesh_selection_tools_v086._FLOWS_PAGE
                return
            if action in _ACTIONS:
                if input_ownership_v080.is_editing(self):
                    raise ValueError('Release controller gesture before marking edges')
                history = getattr(self, 'history', None)
                if history is None:
                    raise ValueError('XR history required for marking native edges')
                count, changed = _apply(context, action, history)
                self.status = '{} / {} EDGES / {}'.format(
                    action.replace('XR_EDGE_', '').replace('_', ' '),
                    count, 'XR UNDO READY' if changed else 'UNCHANGED')
                return
            raise ValueError('Choose Mark/Clear Seam or Sharp')
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_edge_flags_090_patched = True


CLASSES = (BXR_OT_edge_flags,)
