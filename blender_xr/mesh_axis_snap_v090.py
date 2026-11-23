# SPDX-License-Identifier: GPL-3.0-or-later
"""Rigid world-axis snapping of native Blender edit-mesh selections.

Move the current selected vertices as ONE rigid group along just world X,
Y or Z. Align the group's world-space centre with the native 3D cursor,
world origin or active selected BMesh element on that axis. Unlike per-vertex
grid snapping or planar flattening, this preserves all relative vertex
positions, face shapes, UVs and topology. XR Undo/Redo uses the existing
native mesh snapshot history.
"""
import math

import bpy
import bmesh
from bpy.props import EnumProperty
from mathutils import Vector

from . import (input_ownership_v080, menus, mesh, mesh_selection_tools_v086,
               mesh_snap_v086, runtime, selection, v065)

_PAGE = 'XR_SNAP_AXIS_CENTER_090'
_ENTRY = 'XR_SNAP_AXIS_MENU'
_ACTIONS = {
    'XR_SNAP_CURSOR_X': ('CURSOR', 0),
    'XR_SNAP_CURSOR_Y': ('CURSOR', 1),
    'XR_SNAP_CURSOR_Z': ('CURSOR', 2),
    'XR_SNAP_ORIGIN_X': ('ORIGIN', 0),
    'XR_SNAP_ORIGIN_Y': ('ORIGIN', 1),
    'XR_SNAP_ORIGIN_Z': ('ORIGIN', 2),
    'XR_SNAP_ACTIVE_X': ('ACTIVE', 0),
    'XR_SNAP_ACTIVE_Y': ('ACTIVE', 1),
    'XR_SNAP_ACTIVE_Z': ('ACTIVE', 2),
}
_MAX_VERTICES = 120000


def _finite(point):
    return all(math.isfinite(float(value)) for value in point)


def _matrix_stamp(matrix):
    return tuple(tuple(float(value) for value in row) for row in matrix)


def _active_reference(bm):
    """Return a selected, visible native active element with its local centre."""
    item = bm.select_history.active
    if (item is None or not item.is_valid or item.hide or not item.select):
        raise ValueError('Choose a visible active vertex, edge or face in Edit Mode')
    if isinstance(item, bmesh.types.BMVert):
        kind, centre = 'VERT', item.co.copy()
    elif isinstance(item, bmesh.types.BMEdge):
        kind = 'EDGE'
        centre = (item.verts[0].co + item.verts[1].co) * 0.5
    elif isinstance(item, bmesh.types.BMFace):
        kind, centre = 'FACE', item.calc_center_median()
    else:
        raise ValueError('Active edit element is not native mesh geometry')
    if not _finite(centre):
        raise ValueError('Active reference contains non-finite coordinates')
    return kind, int(item.index), tuple(float(v) for v in centre)


def _reference(context, obj, bm, target):
    world = obj.matrix_world
    if target == 'CURSOR':
        point = context.scene.cursor.location.copy()
        ref = ('CURSOR', tuple(float(v) for v in point))
    elif target == 'ORIGIN':
        point = Vector((0.0, 0.0, 0.0))
        ref = ('ORIGIN',)
    else:
        kind, index, local = _active_reference(bm)
        point = world @ Vector(local)
        ref = ('ACTIVE', kind, index, local)
    if not _finite(point):
        raise ValueError('Snap reference has invalid world coordinates')
    return point, ref


def _selected_vertices(context, obj):
    mode = selection.mode(context)
    vertices = tuple(sorted(mesh.selected_transform_vertices(obj, mode),
                            key=lambda item: item.index))
    if not vertices or len(vertices) > _MAX_VERTICES:
        raise ValueError('Choose 1–120,000 visible vertices, edges or faces')
    if any(not item.is_valid or item.hide or not _finite(item.co)
           for item in vertices):
        raise ValueError('Selected mesh contains hidden or invalid vertices')
    return mode, tuple((item.index, tuple(float(v) for v in item.co))
                       for item in vertices)


def _plan(context, action):
    if action not in _ACTIONS:
        raise ValueError('Unknown axis snapping operation')
    obj = mesh_snap_v086._eligible(context)
    matrix = obj.matrix_world.copy()
    if not _finite(matrix.translation) or abs(matrix.determinant()) <= 1e-10:
        raise ValueError('Object transform must be finite and invertible')
    mode, original = _selected_vertices(context, obj)
    bm, _items = mesh_selection_tools_v086._current(obj, mode)
    topology = mesh_selection_tools_v086._topology(bm)
    target, axis = _ACTIONS[action]
    reference_point, reference = _reference(context, obj, bm, target)
    world_positions = tuple(matrix @ Vector(co) for _idx, co in original)
    if any(not _finite(point) for point in world_positions):
        raise ValueError('Selected world coordinates are invalid')
    centre = sum(world_positions, Vector()) / len(world_positions)
    delta = float(reference_point[axis]) - float(centre[axis])
    if not math.isfinite(delta):
        raise ValueError('World axis offset is not finite')
    if abs(delta) <= 1e-9:
        return None
    offset = Vector((0.0, 0.0, 0.0))
    offset[axis] = delta
    inverse = matrix.inverted()
    target_local = tuple((
        idx, tuple(float(v) for v in (inverse @ (world @ Vector(co) + offset))))
        for idx, co in original)
    if any(not _finite(co) for _idx, co in target_local):
        raise ValueError('The transformed vertices have invalid coordinates')
    return {
        'obj_name': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh_name': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'scene': context.scene.name, 'layer': context.view_layer.name,
        'mode': mode, 'topology': topology, 'matrix': _matrix_stamp(matrix),
        'before': original, 'after': target_local, 'reference': reference,
        'axis': axis, 'target': target,
    }


def _check_reference(context, obj, bm, reference):
    if reference[0] == 'CURSOR':
        if tuple(float(v) for v in context.scene.cursor.location) != reference[1]:
            raise ValueError('3D cursor moved before the XR snap completed')
    elif reference[0] == 'ACTIVE':
        kind, index, centre = _active_reference(bm)
        if (kind, index, centre) != reference[1:]:
            raise ValueError('Active edit element moved or changed before snapping')


def _write(context, plan):
    """Validate the whole native edit selection before changing any vertex."""
    obj = mesh_snap_v086._eligible(context)
    if (obj.name != plan['obj_name'] or obj.as_pointer() != plan['obj_ptr'] or
            obj.data.name != plan['mesh_name'] or
            obj.data.as_pointer() != plan['mesh_ptr'] or
            context.scene.name != plan['scene'] or
            context.view_layer.name != plan['layer'] or
            selection.mode(context) != plan['mode'] or
            _matrix_stamp(obj.matrix_world) != plan['matrix']):
        raise ValueError('Snap target, view layer or object transform changed')
    bm, _items = mesh_selection_tools_v086._current(obj, plan['mode'])
    if mesh_selection_tools_v086._topology(bm) != plan['topology']:
        raise ValueError('Mesh topology or visibility changed before snapping')
    _check_reference(context, obj, bm, plan['reference'])
    current_mode, current = _selected_vertices(context, obj)
    if current_mode != plan['mode'] or current != plan['before']:
        raise ValueError('Selected vertices moved or changed before snapping')
    bm.verts.ensure_lookup_table()
    written = []
    try:
        for index, coords in plan['after']:
            vertex = bm.verts[index]
            if not vertex.is_valid or vertex.hide:
                raise ValueError('A snap target became unavailable')
            previous = vertex.co.copy()
            vertex.co = Vector(coords)
            written.append((vertex, previous, coords))
    except Exception:
        for vertex, previous, coords in reversed(written):
            if vertex.is_valid and tuple(float(v) for v in vertex.co) == coords:
                vertex.co = previous
        raise
    return obj


def _apply(session, context, action):
    if input_ownership_v080.is_editing(session):
        raise ValueError('Release controller gesture before axis snapping')
    history = getattr(session, 'history', None)
    if history is None:
        raise ValueError('XR Undo history required for native axis snapping')
    plan = _plan(context, action)
    if plan is None:
        session.status = 'AXIS SNAP / GROUP CENTRE ALREADY ALIGNED'
        return False
    obj = mesh_snap_v086._eligible(context)
    mesh.snapshot_and_push(obj, lambda: _write(context, plan), history)
    session._xr_precision_last_ray = None
    session.status = 'AXIS SNAP / {} / WORLD {} / XR UNDO READY'.format(
        plan['target'], 'XYZ'[plan['axis']])
    return True


class BXR_OT_snap_axis_center(bpy.types.Operator):
    bl_idname = 'blender_xr.snap_axis_center'
    bl_label = 'Rigid Axis Snap to Cursor, Origin or Active Element'
    bl_description = 'Move the native edit selection centre along just one world axis'
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        items=[(key, '{} / World {}'.format(kind.title(), 'XYZ'[axis]),
                'Rigidly translate the selected mesh on one world-space axis')
               for key, (kind, axis) in _ACTIONS.items()],
        default='XR_SNAP_CURSOR_X')

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and obj.mode == 'EDIT'
                    and context.mode == 'EDIT_MESH')

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the Axis Snap wrist menu while XR is running')
            return {'CANCELLED'}
        try:
            plan = _plan(context, self.action)
            if plan is None:
                self.report({'INFO'}, 'Selection centre is already aligned')
                return {'CANCELLED'}
            obj = _write(context, plan)
            try:
                mesh.update(obj)
            except Exception:
                # Restore the original native coordinates only if all targets
                # still match what this explicit operator just wrote.
                bm = mesh.editable(obj)
                bm.verts.ensure_lookup_table()
                if all(tuple(float(v) for v in bm.verts[index].co) == after
                       for index, after in plan['after']):
                    for index, before in plan['before']:
                        bm.verts[index].co = Vector(before)
                    mesh.update(obj)
                raise
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Rigid centre snap to {} / world {}'.format(
            plan['target'], 'XYZ'[plan['axis']]))
        return {'FINISHED'}


def install_pages():
    parent = tuple(menus.PAGES[mesh_snap_v086._PAGE])
    if not parent or parent[-1][1] != 'BACK':
        raise ValueError('Existing native Snap Selected menu is missing')
    if not any(action == _ENTRY for _label, action in parent):
        parent = parent[:-1] + (
            ('AXIS CENTRE', _ENTRY), parent[-1])
    if len(parent) > 12:
        raise ValueError('Axis Snap would overflow the native wrist menu')
    menus.PAGES[mesh_snap_v086._PAGE] = parent
    menus.PAGES[_PAGE] = (
        ('CURSOR X', 'XR_SNAP_CURSOR_X'),
        ('CURSOR Y', 'XR_SNAP_CURSOR_Y'),
        ('CURSOR Z', 'XR_SNAP_CURSOR_Z'),
        ('WORLD X', 'XR_SNAP_ORIGIN_X'),
        ('WORLD Y', 'XR_SNAP_ORIGIN_Y'),
        ('WORLD Z', 'XR_SNAP_ORIGIN_Z'),
        ('ACTIVE X', 'XR_SNAP_ACTIVE_X'),
        ('ACTIVE Y', 'XR_SNAP_ACTIVE_Y'),
        ('ACTIVE Z', 'XR_SNAP_ACTIVE_Z'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'RIGID AXIS SNAP'
    v065.TOOLTIPS.update({
        _ENTRY: ('Rigid Axis Centre Snap',
            'Align the selected group to cursor, origin or active element on just X/Y/Z'),
    })
    for action, (target, axis) in _ACTIONS.items():
        v065.TOOLTIPS[action] = (
            'Centre to ' + target.title() + ' World ' + 'XYZ'[axis],
            'Move the complete selected mesh rigidly; preserve shape and other axes')


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_axis_snap_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous_command(self, context, action)
        if action == _ENTRY and menu.page == mesh_snap_v086._PAGE:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR edit before axis snapping')
            mesh_snap_v086._eligible(context)
            menu.page = _PAGE
            self.status = 'AXIS SNAP / CURSOR, WORLD OR ACTIVE / XYZ'
            return
        if menu.page == _PAGE:
            if action == 'BACK':
                menu.page = mesh_snap_v086._PAGE
                return
            if action in _ACTIONS:
                return _apply(self, context, action)
            raise ValueError('Select an axis snap or Back')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_axis_snap_090_patched = True


CLASSES = (BXR_OT_snap_axis_center,)
