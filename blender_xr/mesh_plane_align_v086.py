# SPDX-License-Identifier: GPL-3.0-or-later
"""Exact native edit-mesh plane alignment from the Mesh XR wrist controls.

Flatten all selected mesh vertices (including vertices implied by selected
edges/faces) onto one world or local X/Y/Z plane. Plane positions may use
the selected minimum, arithmetic centre, maximum or Blender's 3D cursor.
All changes are stored in the existing mesh snapshot XR Undo/Redo history.
"""
from mathutils import Vector

from . import input_ownership_v080, menus, mesh, selection, v065

_PAGE = 'XR_FLAT_PLANES_086'
_SPACES = {'XR_FLAT_LOCAL': 'LOCAL', 'XR_FLAT_WORLD': 'WORLD'}
_ANCHORS = {'XR_FLAT_CENTER': 'CENTER', 'XR_FLAT_MIN': 'MIN',
            'XR_FLAT_MAX': 'MAX', 'XR_FLAT_CURSOR': 'CURSOR'}
_AXES = {'XR_FLAT_X': 0, 'XR_FLAT_Y': 1, 'XR_FLAT_Z': 2}


def _editable(context):
    obj = context.view_layer.objects.active
    if (context.mode != 'EDIT_MESH' or obj is None or
            obj.type != 'MESH' or obj.mode != 'EDIT'):
        raise ValueError('Enter Mesh Edit Mode to flatten selected geometry')
    mesh.editable(obj)
    if (obj.override_library or obj.hide_select or
            not obj.visible_get(view_layer=context.view_layer)):
        raise ValueError('Show and unlock the local mesh before aligning')
    if context.view_layer.objects.get(obj.name) != obj:
        raise ValueError('Selected mesh is not in the active view layer')
    return obj


def _settings(session):
    space = getattr(session, '_xr_flat_space', 'LOCAL')
    anchor = getattr(session, '_xr_flat_anchor', 'CENTER')
    if space not in {'LOCAL', 'WORLD'} or anchor not in {'CENTER', 'MIN', 'MAX', 'CURSOR'}:
        raise ValueError('Unsupported plane alignment settings')
    return space, anchor


def _plan(context, obj, axis, space, anchor):
    if axis not in (0, 1, 2):
        raise ValueError('Choose an X/Y/Z plane')
    vertices = tuple(mesh.selected_transform_vertices(
        obj, selection.mode(context)))
    if len(vertices) < 2:
        raise ValueError('Select at least two vertices, edges or faces to flatten')
    for vert in vertices:
        if not vert.is_valid or vert.hide:
            raise ValueError('Hidden/deleted vertices cannot be aligned')

    local_points = tuple((vert.index, vert.co.copy()) for vert in vertices)
    matrix = obj.matrix_world.copy()
    if space == 'WORLD':
        if abs(matrix.determinant()) < 1e-10:
            raise ValueError('Object transform has zero scale')
        inverse = matrix.inverted()
        working = tuple((index, matrix @ point) for index, point in local_points)
    else:
        inverse = None
        working = local_points

    values = tuple(point[axis] for _index, point in working)
    if anchor == 'CENTER':
        plane = sum(values) / len(values)
    elif anchor == 'MIN':
        plane = min(values)
    elif anchor == 'MAX':
        plane = max(values)
    elif anchor == 'CURSOR':
        cursor = Vector(context.scene.cursor.location)
        plane = (cursor if space == 'WORLD' else inverse_cursor(matrix, cursor))[axis]
    else:
        raise ValueError('Unknown plane reference')

    targets = {}
    for index, point in working:
        target = point.copy()
        target[axis] = plane
        local_target = inverse @ target if inverse is not None else target
        targets[index] = local_target
    changed = any((targets[index] - source).length_squared > 1e-16
                  for index, source in local_points)
    return targets if changed else None


def inverse_cursor(matrix, world_cursor):
    """Blender's cursor is world-space even for local mesh alignment."""
    if abs(matrix.determinant()) < 1e-10:
        raise ValueError('Object transform has zero scale')
    return matrix.inverted() @ world_cursor


def _apply(session, context, axis):
    if input_ownership_v080.is_editing(session):
        raise ValueError('Release the active controller gesture before flattening')
    if getattr(session, 'history', None) is None:
        raise ValueError('XR mesh history is unavailable')
    obj = _editable(context)
    space, anchor = _settings(session)
    targets = _plan(context, obj, axis, space, anchor)
    if targets is None:
        session.status = 'FLATTEN / SELECTED GEOMETRY ALREADY ON THAT PLANE'
        return False

    # Use the existing guarded mesh snapshot transaction so Cancel, Undo and
    # Redo all preserve topology, UVs, weights, materials and object transforms.
    def operation():
        bm = mesh.editable(obj)
        bm.verts.ensure_lookup_table()
        for index, target in targets.items():
            if index >= len(bm.verts) or not bm.verts[index].is_valid or bm.verts[index].hide:
                raise ValueError('Selection changed before flattening; try again')
            bm.verts[index].co = target

    entry = mesh._snapshot_operation(obj, operation)
    session.history.push(entry)
    # Selection is unchanged, but a recorded ray point can now be stale.
    session._xr_precision_last_ray = None
    session.status = 'FLATTEN / {} / {} / {}'.format('XYZ'[axis], space, anchor)
    return True


def install_pages():
    options = tuple(menus.PAGES.get('STEP_MENU', ()))
    if not options or options[-1][1] != 'BACK':
        raise ValueError('Mesh Plane Align requires the existing Edit Options page')
    if not any(action == 'XR_FLAT_MENU' for _label, action in options):
        options = options[:-1] + (('FLATTEN', 'XR_FLAT_MENU'), options[-1])
    if len(options) > 12:
        raise ValueError('Mesh Plane Align would overflow the Edit Options menu')
    menus.PAGES['STEP_MENU'] = options
    menus.PAGES[_PAGE] = (
        ('FLATTEN X', 'XR_FLAT_X'), ('FLATTEN Y', 'XR_FLAT_Y'),
        ('FLATTEN Z', 'XR_FLAT_Z'),
        ('LOCAL', 'XR_FLAT_LOCAL'), ('WORLD', 'XR_FLAT_WORLD'),
        ('CENTRE', 'XR_FLAT_CENTER'), ('MINIMUM', 'XR_FLAT_MIN'),
        ('MAXIMUM', 'XR_FLAT_MAX'), ('3D CURSOR', 'XR_FLAT_CURSOR'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'FLATTEN SELECTED'
    v065.TOOLTIPS.update({
        'XR_FLAT_MENU': ('Flatten Selected Geometry',
                         'Project selected vertices onto local or world X/Y/Z plane'),
        'XR_FLAT_X': ('Flatten X', 'Align the selected vertices to one X plane'),
        'XR_FLAT_Y': ('Flatten Y', 'Align the selected vertices to one Y plane'),
        'XR_FLAT_Z': ('Flatten Z', 'Align the selected vertices to one Z plane'),
        'XR_FLAT_LOCAL': ('Local Coordinate Plane', 'Align mesh-space coordinates'),
        'XR_FLAT_WORLD': ('World Coordinate Plane',
                          'Align true world-space coordinates, including scaled/rotated objects'),
        'XR_FLAT_CENTER': ('Align to Average', 'Use the average selected coordinate'),
        'XR_FLAT_MIN': ('Align to Minimum', 'Use the minimum selected coordinate'),
        'XR_FLAT_MAX': ('Align to Maximum', 'Use the maximum selected coordinate'),
        'XR_FLAT_CURSOR': ('Align to 3D Cursor', 'Use the native Blender 3D cursor coordinate'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_flat_mesh_086_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous_command(self, context, action)
        if action == 'XR_FLAT_MENU':
            _editable(context)
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release active input before plane alignment')
            menu.page = _PAGE
            self.status = 'FLATTEN / CHOOSE REFERENCE AND X/Y/Z'
            return
        if menu.page == _PAGE:
            if action == 'BACK':
                menu.page = 'STEP_MENU'
                return
            if action in _SPACES:
                self._xr_flat_space = _SPACES[action]
                self.status = 'FLATTEN SPACE / ' + self._xr_flat_space
                return
            if action in _ANCHORS:
                self._xr_flat_anchor = _ANCHORS[action]
                self.status = 'FLATTEN REFERENCE / ' + self._xr_flat_anchor
                return
            if action in _AXES:
                return _apply(self, context, _AXES[action])
            raise ValueError('Finish or exit Flatten tools first')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_flat_mesh_086_patched = True
