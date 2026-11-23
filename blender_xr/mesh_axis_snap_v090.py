# SPDX-License-Identifier: GPL-3.0-or-later
"""Rigid, single-axis native edit-mesh snapping in XR.

Moves the selection centre on exactly one world or local axis. Target can
be the Blender 3D cursor, active mesh object origin or world origin.
Other axes, relative distances, topology and vertex attributes are preserved.
"""
import math

from mathutils import Vector

from . import input_ownership_v080, menus, mesh, mesh_snap_v086, selection, v065

_PAGE = 'XR_SNAP_AXIS_090'
_AXES = {'XR_SNAP_AXIS_X': 0, 'XR_SNAP_AXIS_Y': 1, 'XR_SNAP_AXIS_Z': 2}
_TARGETS = {
    'XR_SNAP_AXIS_CURSOR': 'CURSOR',
    'XR_SNAP_AXIS_OBJECT': 'OBJECT',
    'XR_SNAP_AXIS_WORLD': 'WORLD',
}
_SPACES = {'XR_SNAP_AXIS_LOCAL': 'LOCAL', 'XR_SNAP_AXIS_GLOBAL': 'WORLD'}


def _finite(vector):
    return all(math.isfinite(float(value)) for value in vector)


def _plan(context, obj, axis, target, space):
    if axis not in (0, 1, 2) or target not in _TARGETS.values():
        raise ValueError('Unknown axis snap target or axis')
    if space not in _SPACES.values():
        raise ValueError('Choose local or world axis space')
    vertices = tuple(sorted(mesh.selected_transform_vertices(
        obj, selection.mode(context)), key=lambda v: v.index))
    if not vertices:
        raise ValueError('Select visible vertices, edges or faces first')
    if any(not vert.is_valid or vert.hide for vert in vertices):
        raise ValueError('Selection contains hidden or deleted vertices')
    original = tuple((vert.index, vert.co.copy()) for vert in vertices)
    original_indices = tuple(idx for idx, _point in original)
    matrix = obj.matrix_world.copy()
    if (not all(_finite(row) for row in matrix) or
            not math.isfinite(float(matrix.determinant())) or
            abs(matrix.determinant()) <= 1e-10):
        raise ValueError('Object transform is singular or invalid')
    inverse = matrix.inverted()
    if target == 'CURSOR':
        world_target = Vector(context.scene.cursor.location)
    elif target == 'OBJECT':
        world_target = matrix.translation.copy()
    else:
        world_target = Vector((0.0, 0.0, 0.0))
    if not _finite(world_target):
        raise ValueError('Axis snap reference has invalid coordinates')
    if space == 'LOCAL':
        # Cursor and world origin are Blender world-space coordinates;
        # convert only the target to the object's local coordinates.
        local_target = inverse @ world_target
        centre = sum((point for _, point in original), Vector()) / len(original)
        offset = Vector((0.0, 0.0, 0.0))
        offset[axis] = local_target[axis] - centre[axis]
        planned = {idx: point + offset for idx, point in original}
    else:
        world_points = tuple((idx, matrix @ point) for idx, point in original)
        centre = sum((point for _, point in world_points), Vector()) / len(world_points)
        offset = Vector((0.0, 0.0, 0.0))
        offset[axis] = world_target[axis] - centre[axis]
        planned = {idx: inverse @ (point + offset)
                   for idx, point in world_points}
    if not all(_finite(point) for point in planned.values()):
        raise ValueError('Axis snap would create invalid mesh coordinates')
    if not any((planned[idx] - point).length_squared > 1e-16
               for idx, point in original):
        return None
    # Retain original coordinates to reject a stale plan if another
    # operation modified the mesh before the XR history transaction.
    return original, original_indices, planned


def _apply(session, context, axis):
    if input_ownership_v080.is_editing(session):
        raise ValueError('Release active controller gesture before axis snap')
    if getattr(session, 'history', None) is None:
        raise ValueError('XR mesh Undo history is unavailable')
    obj = mesh_snap_v086._eligible(context)
    target = getattr(session, '_xr_axis_snap_target', 'CURSOR')
    space = getattr(session, '_xr_axis_snap_space', 'WORLD')
    plan = _plan(context, obj, axis, target, space)
    if plan is None:
        session.status = 'AXIS SNAP / ALREADY ALIGNED / NO CHANGE'
        return False
    original, original_indices, planned = plan

    def mutate():
        bm = mesh.editable(obj)
        bm.verts.ensure_lookup_table()
        selected_now = tuple(sorted(v.index for v in mesh.selected_transform_vertices(
            obj, selection.mode(context)) if v.is_valid and not v.hide))
        if selected_now != original_indices:
            raise ValueError('Mesh selection changed before axis snap')
        # Validate every target before writing the first vertex.
        for idx, position in original:
            if (idx < 0 or idx >= len(bm.verts) or
                    not bm.verts[idx].is_valid or bm.verts[idx].hide or
                    (bm.verts[idx].co - position).length_squared > 1e-16):
                raise ValueError('Mesh changed since axis snap was planned')
        for idx, _position in original:
            bm.verts[idx].co = planned[idx]

    mesh.snapshot_and_push(obj, mutate, session.history)
    session._xr_precision_last_ray = None
    session.status = 'AXIS SNAP / {} / {} / {}'.format(
        'XYZ'[axis], space, target)
    return True


def install_pages():
    snap = tuple(menus.PAGES[mesh_snap_v086._PAGE])
    if not snap or snap[-1][1] != 'BACK':
        raise ValueError('Snap Selected wrist page is unavailable')
    if any(action == 'XR_SNAP_AXIS_MENU' for _label, action in snap):
        raise ValueError('Axis snap is already in the menu')
    if len(snap) >= 12:
        raise ValueError('Snap Selected menu has no capacity for axis snap')
    menus.PAGES[mesh_snap_v086._PAGE] = (
        *snap[:-1], ('AXIS SNAP', 'XR_SNAP_AXIS_MENU'), snap[-1])
    menus.PAGES[_PAGE] = (
        ('SNAP X', 'XR_SNAP_AXIS_X'),
        ('SNAP Y', 'XR_SNAP_AXIS_Y'),
        ('SNAP Z', 'XR_SNAP_AXIS_Z'),
        ('3D CURSOR', 'XR_SNAP_AXIS_CURSOR'),
        ('OBJECT ORIGIN', 'XR_SNAP_AXIS_OBJECT'),
        ('WORLD ORIGIN', 'XR_SNAP_AXIS_WORLD'),
        ('LOCAL AXES', 'XR_SNAP_AXIS_LOCAL'),
        ('WORLD AXES', 'XR_SNAP_AXIS_GLOBAL'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'AXIS SNAP SELECTED'
    v065.TOOLTIPS.update({
        'XR_SNAP_AXIS_MENU': ('Constrained Axis Snap',
            'Move the selected mesh rigidly along one local or world axis'),
        'XR_SNAP_AXIS_X': ('Snap X', 'Align selection centre on only the X axis'),
        'XR_SNAP_AXIS_Y': ('Snap Y', 'Align selection centre on only the Y axis'),
        'XR_SNAP_AXIS_Z': ('Snap Z', 'Align selection centre on only the Z axis'),
        'XR_SNAP_AXIS_CURSOR': ('Target 3D Cursor',
            'Use the Blender scene cursor as axis snap reference'),
        'XR_SNAP_AXIS_OBJECT': ('Target Object Origin',
            'Use the active mesh origin as axis snap reference'),
        'XR_SNAP_AXIS_WORLD': ('Target World Origin',
            'Use global zero as axis snap reference'),
        'XR_SNAP_AXIS_LOCAL': ('Local Axis Snap',
            'Constrain movement to the mesh object local axis'),
        'XR_SNAP_AXIS_GLOBAL': ('World Axis Snap',
            'Constrain movement to the true world-space axis'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_axis_snap_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous_command(self, context, action)
        if menu.page == mesh_snap_v086._PAGE and action == 'XR_SNAP_AXIS_MENU':
            mesh_snap_v086._eligible(context)
            if input_ownership_v080.is_editing(self):
                raise ValueError('Finish controller edit before axis snap')
            menu.page = _PAGE
            self.status = 'AXIS SNAP / CHOOSE TARGET, SPACE AND AXIS'
            return
        if menu.page == _PAGE:
            if action == 'BACK':
                menu.page = mesh_snap_v086._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Finish controller gesture before axis snap')
            if action in _TARGETS:
                self._xr_axis_snap_target = _TARGETS[action]
                self.status = 'AXIS SNAP TARGET / ' + self._xr_axis_snap_target
                return
            if action in _SPACES:
                self._xr_axis_snap_space = _SPACES[action]
                self.status = 'AXIS SNAP SPACE / ' + self._xr_axis_snap_space
                return
            if action in _AXES:
                return _apply(self, context, _AXES[action])
            raise ValueError('Use Axis Snap settings or Back')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_axis_snap_090_patched = True
