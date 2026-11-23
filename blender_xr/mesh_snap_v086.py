# SPDX-License-Identifier: GPL-3.0-or-later
"""Native XR edit-mesh snapping with independent or rigid selection movement.

Vertex Grid rounds selected coordinates independently (changing the shape).
Centre Grid, Centre Cursor, Centre Object Origin and Centre World Origin
translate the entire selected group rigidly, preserving its shape.
All operations use native editable BMesh coordinates and existing XR-local
mesh snapshot Undo/Redo, without Blender operator context overrides.
"""
import math

from mathutils import Vector

from . import (input_ownership_v080, menus, mesh, mesh_selection_tools_v086,
               selection, v065)

_PAGE = 'XR_MESH_SNAP_086'
_ACTIONS = {
    'XR_SNAP_LOCAL_VERTS': 'LOCAL_VERTS',
    'XR_SNAP_WORLD_VERTS': 'WORLD_VERTS',
    'XR_SNAP_LOCAL_CENTER': 'LOCAL_CENTER',
    'XR_SNAP_WORLD_CENTER': 'WORLD_CENTER',
    'XR_SNAP_CENTER_CURSOR': 'CENTER_CURSOR',
    'XR_SNAP_CENTER_OBJECT': 'CENTER_OBJECT',
    'XR_SNAP_CENTER_WORLD': 'CENTER_WORLD',
}


def _eligible(context):
    obj = context.view_layer.objects.active
    if (context.mode != 'EDIT_MESH' or obj is None or
            obj.type != 'MESH' or obj.mode != 'EDIT'):
        raise ValueError('Snap Selected needs Blender Mesh Edit Mode')
    if obj.override_library or obj.hide_select:
        raise ValueError('Unlock the local mesh before using Snap Selected')
    mesh.editable(obj)
    if not obj.visible_get(view_layer=context.view_layer):
        raise ValueError('Show the selected mesh before snapping')
    if context.view_layer.objects.get(obj.name) != obj:
        raise ValueError('Mesh is outside the current view layer')
    return obj


def _snap_number(value, size):
    """Nearest multiple with symmetric half-away-from-zero ties."""
    if not math.isfinite(value):
        raise ValueError('Selected mesh has non-finite coordinates')
    amount = abs(value) / size
    return math.copysign(math.floor(amount + 0.5) * size, value)


def _snap_point(point, size):
    return Vector(tuple(_snap_number(float(coord), size) for coord in point))


def _plan(context, obj, operation, size):
    if operation not in _ACTIONS.values():
        raise ValueError('Unknown mesh snap operation')
    verts = tuple(sorted(mesh.selected_transform_vertices(
        obj, selection.mode(context)), key=lambda v: v.index))
    if not verts:
        raise ValueError('Select vertices, edges or faces before snapping')
    original = tuple((v.index, v.co.copy()) for v in verts
                     if v.is_valid and not v.hide)
    if len(original) != len(verts):
        raise ValueError('Selected geometry became hidden or invalid')
    matrix = obj.matrix_world.copy()
    if abs(matrix.determinant()) <= 1e-10:
        raise ValueError('Mesh object transform is not invertible')
    inverse = matrix.inverted()
    world = tuple((idx, matrix @ position) for idx, position in original)
    local_center = sum((position for _idx, position in original), Vector()) / len(original)
    world_center = sum((position for _idx, position in world), Vector()) / len(world)

    if operation == 'LOCAL_VERTS':
        after = {idx: _snap_point(position, size) for idx, position in original}
    elif operation == 'WORLD_VERTS':
        after = {idx: inverse @ _snap_point(position, size)
                 for idx, position in world}
    elif operation == 'LOCAL_CENTER':
        offset = _snap_point(local_center, size) - local_center
        after = {idx: position + offset for idx, position in original}
    elif operation == 'WORLD_CENTER':
        offset = _snap_point(world_center, size) - world_center
        after = {idx: inverse @ (position + offset)
                 for idx, position in world}
    else:
        if operation == 'CENTER_CURSOR':
            target = Vector(context.scene.cursor.location)
        elif operation == 'CENTER_OBJECT':
            target = matrix.translation.copy()
        else:
            target = Vector((0.0, 0.0, 0.0))
        offset = target - world_center
        after = {idx: inverse @ (position + offset)
                 for idx, position in world}
    if not all(all(math.isfinite(float(value)) for value in point)
               for point in after.values()):
        raise ValueError('Snap result has invalid coordinates')
    moved = any((after[idx] - position).length_squared > 1e-16
                for idx, position in original)
    return after if moved else None


def _native_selection_stamp(context, obj, operation):
    """Fingerprint the native edit targets before a guarded snap transaction.

    Capture topology/visibility, selected element IDs, implied target vertex
    coordinates and world transform. A target cursor is a live reference, so
    cursor movement also expires the planned snap. No Blender data is changed.
    """
    mode = selection.mode(context)
    bm, elements = mesh_selection_tools_v086._current(obj, mode)
    selected = tuple(mesh_selection_tools_v086._selected(elements))
    targets = tuple(sorted(mesh.selected_transform_vertices(obj, mode),
                           key=lambda vertex: vertex.index))
    if not targets:
        raise ValueError('Select native geometry before snapping')
    if any(not v.is_valid or v.hide for v in targets):
        raise ValueError('Snap targets are hidden or invalid')
    points = tuple((int(v.index), tuple(float(component) for component in v.co))
                   for v in targets)
    matrix = tuple(tuple(float(value) for value in row)
                   for row in obj.matrix_world)
    cursor = (tuple(float(value) for value in context.scene.cursor.location)
              if operation == 'CENTER_CURSOR' else None)
    if (not all(math.isfinite(c) for _idx, point in points for c in point) or
            not all(math.isfinite(c) for row in matrix for c in row) or
            (cursor is not None and not all(math.isfinite(c) for c in cursor))):
        raise ValueError('Snap targets or reference contain non-finite values')
    return (
        context.scene.as_pointer(), context.view_layer.name,
        obj.as_pointer(), obj.data.as_pointer(), mode,
        mesh_selection_tools_v086._topology(bm),
        selected, points, matrix, cursor,
    )


def _apply(session, context, action):
    if input_ownership_v080.is_editing(session):
        raise ValueError('Release the active XR gesture before snapping')
    history = getattr(session, 'history', None)
    if history is None:
        raise ValueError('XR undo history is unavailable')
    obj = _eligible(context)
    step = float(session.settings.step)
    if not math.isfinite(step) or not 0.0001 <= step <= 10.0:
        raise ValueError('Set a valid tool step to use grid snapping')
    operation = _ACTIONS[action]
    before = _native_selection_stamp(context, obj, operation)
    plan = _plan(context, obj, operation, step)
    if not plan:
        session.status = 'SNAP / ALREADY ALIGNED / NO CHANGE'
        return False

    def mutate():
        # Preflight the entire current native edit cage before the first
        # coordinate write. Index-only checks are insufficient when Blender
        # edits or Undo reuse an index with different geometry/selection.
        if _eligible(context) != obj or _native_selection_stamp(
                context, obj, operation) != before:
            raise ValueError('Native mesh, selection or snap reference changed')
        bm = mesh.editable(obj)
        bm.verts.ensure_lookup_table()
        expected = tuple(idx for idx, _point in before[7])
        if tuple(sorted(plan)) != expected:
            raise ValueError('Snap targets changed before commit')
        for idx in expected:
            target = plan[idx]
            if (idx < 0 or idx >= len(bm.verts) or
                    not bm.verts[idx].is_valid or bm.verts[idx].hide or
                    not all(math.isfinite(float(v)) for v in target)):
                raise ValueError('Snap target is no longer valid')
        for idx in expected:
            bm.verts[idx].co = plan[idx]

    mesh.snapshot_and_push(obj, mutate, session.history)
    session._xr_precision_last_ray = None
    session.status = 'SNAP / {} / STEP {:.4f}'.format(operation.replace('_', ' '), step)
    return True


def install_pages():
    parent = tuple(menus.PAGES.get('STEP_MENU', ()))
    if not parent or parent[-1][1] != 'BACK':
        raise ValueError('Snap Selected requires existing Edit Options page')
    if not any(action == 'XR_SNAP_MENU' for _label, action in parent):
        parent = parent[:-1] + (('SNAP', 'XR_SNAP_MENU'), parent[-1])
    if len(parent) > 12:
        raise ValueError('Edit Options page has no room for native Snap Selected')
    menus.PAGES['STEP_MENU'] = parent
    menus.PAGES[_PAGE] = (
        ('LOCAL GRID', 'XR_SNAP_LOCAL_VERTS'),
        ('WORLD GRID', 'XR_SNAP_WORLD_VERTS'),
        ('LOCAL CENTRE', 'XR_SNAP_LOCAL_CENTER'),
        ('WORLD CENTRE', 'XR_SNAP_WORLD_CENTER'),
        ('TO 3D CURSOR', 'XR_SNAP_CENTER_CURSOR'),
        ('TO OBJECT ORIGIN', 'XR_SNAP_CENTER_OBJECT'),
        ('TO WORLD ORIGIN', 'XR_SNAP_CENTER_WORLD'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'SNAP SELECTED'
    v065.TOOLTIPS.update({
        'XR_SNAP_MENU': ('Snap Selected', 'Snap native selected mesh geometry to a grid or a precise centre'),
        'XR_SNAP_LOCAL_VERTS': ('Local Vertex Grid', 'Snap each selected vertex to the local Blender tool-step grid'),
        'XR_SNAP_WORLD_VERTS': ('World Vertex Grid', 'Snap each selected vertex to the true world-axis tool-step grid'),
        'XR_SNAP_LOCAL_CENTER': ('Local Selection Centre Grid', 'Move the selected group as one to the nearest local grid intersection'),
        'XR_SNAP_WORLD_CENTER': ('World Selection Centre Grid', 'Move the selected group as one to the nearest world grid intersection'),
        'XR_SNAP_CENTER_CURSOR': ('Move Selection Centre to Cursor', 'Move selected vertices rigidly so their centre meets the native 3D cursor'),
        'XR_SNAP_CENTER_OBJECT': ('Move Selection Centre to Object Origin', 'Move selected vertices rigidly to the active object origin'),
        'XR_SNAP_CENTER_WORLD': ('Move Selection Centre to World Origin', 'Move selected vertices rigidly to coordinates 0,0,0'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_native_mesh_snap_086_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous_command(self, context, action)
        if action == 'XR_SNAP_MENU':
            _eligible(context)
            if input_ownership_v080.is_editing(self):
                raise ValueError('Finish the current controller gesture first')
            menu.page = _PAGE
            self.status = 'SNAP SELECTED / CHOOSE GRID OR CENTRE'
            return
        if menu.page == _PAGE:
            if action == 'BACK':
                menu.page = 'STEP_MENU'
                return
            if action in _ACTIONS:
                return _apply(self, context, action)
            raise ValueError('Finish or exit Snap Selected first')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_native_mesh_snap_086_patched = True
