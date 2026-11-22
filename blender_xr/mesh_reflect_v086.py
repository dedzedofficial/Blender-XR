# SPDX-License-Identifier: GPL-3.0-or-later
"""Reflect selected native edit-mesh vertices about an axis-aligned plane.

The reflection changes coordinates in place rather than creating mirrored
copies or modifiers. Local/world axis and median/cursor pivot are independent.
All writes are one guarded XR-local mesh snapshot Undo/Redo transaction.
"""
import math

from mathutils import Vector
from . import input_ownership_v080, menus, mesh, selection, v065

_PAGE = 'XR_MESH_MIRROR_086'
_ACTIONS = {
    'XR_REFLECT_X': 0,
    'XR_REFLECT_Y': 1,
    'XR_REFLECT_Z': 2,
}


def _eligible(context):
    obj = context.view_layer.objects.active
    if (obj is None or obj.type != 'MESH' or obj.mode != 'EDIT' or
            context.mode != 'EDIT_MESH'):
        raise ValueError('Reflect Selected requires Mesh Edit Mode')
    mesh.editable(obj)
    if (obj.override_library or obj.hide_select or
            not obj.visible_get(view_layer=context.view_layer)):
        raise ValueError('Reflect Selected requires a visible, unlocked local mesh')
    return obj


def _settings(session):
    space = getattr(session, '_xr_reflect_space', 'LOCAL')
    pivot = getattr(session, '_xr_reflect_pivot', 'MEDIAN')
    if space not in {'LOCAL', 'WORLD'} or pivot not in {'MEDIAN', 'CURSOR'}:
        raise ValueError('Unknown reflection space or pivot')
    return space, pivot


def _plan(context, obj, axis, space, pivot):
    if axis not in (0, 1, 2):
        raise ValueError('Unknown reflection axis')
    bm = mesh.editable(obj)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    verts = mesh.selected_transform_vertices(obj, selection.mode(context))
    if not verts:
        raise ValueError('Select mesh geometry before reflecting')
    original = tuple(sorted(((v.index, v.co.copy()) for v in verts
                             if v.is_valid and not v.hide), key=lambda p: p[0]))
    if len(original) != len(verts):
        raise ValueError('Selection contains hidden or invalid vertices')
    matrix = obj.matrix_world.copy()
    if abs(matrix.determinant()) < 1e-10:
        raise ValueError('Object matrix cannot be inverted')
    inverse = matrix.inverted()
    positions = tuple((idx, matrix @ co if space == 'WORLD' else co)
                      for idx, co in original)
    if pivot == 'MEDIAN':
        centre = sum((co for _idx, co in positions), Vector()) / len(positions)
    elif pivot == 'CURSOR':
        cursor = context.scene.cursor.location.copy()
        centre = cursor if space == 'WORLD' else inverse @ cursor
    else:
        raise ValueError('Unknown reflection pivot')
    if not all(math.isfinite(float(x)) for _idx, co in positions for x in co):
        raise ValueError('Selected vertices have non-finite coordinates')
    if not math.isfinite(float(centre[axis])):
        raise ValueError('Reflection plane is not finite')
    result = {}
    for idx, position in positions:
        mirrored = position.copy()
        mirrored[axis] = 2.0 * centre[axis] - mirrored[axis]
        local = inverse @ mirrored if space == 'WORLD' else mirrored
        if not all(math.isfinite(float(value)) for value in local):
            raise ValueError('Reflection result is not finite')
        result[idx] = local
    if all((result[idx] - co).length_squared < 1e-16 for idx, co in original):
        return None
    return result


def _apply(session, context, action):
    if input_ownership_v080.is_editing(session):
        raise ValueError('Release the active XR gesture before reflecting')
    if getattr(session, 'history', None) is None:
        raise ValueError('XR undo history is unavailable')
    obj = _eligible(context)
    space, pivot = _settings(session)
    axis = _ACTIONS[action]
    plan = _plan(context, obj, axis, space, pivot)
    if not plan:
        session.status = 'REFLECT / ALREADY ON PLANE / NO CHANGE'
        return False

    def mutate():
        bm = mesh.editable(obj)
        bm.verts.ensure_lookup_table()
        for idx in plan:
            if (idx >= len(bm.verts) or not bm.verts[idx].is_valid or
                    bm.verts[idx].hide):
                raise ValueError('Mesh changed before reflection')
        for idx, co in plan.items():
            bm.verts[idx].co = co

    entry = mesh._snapshot_operation(obj, mutate)
    session.history.push(entry)
    session._xr_precision_last_ray = None
    session.status = 'REFLECT / {} / {} / {}'.format('XYZ'[axis], space, pivot)
    return True


def install_pages():
    options = tuple(menus.PAGES.get('STEP_MENU', ()))
    if not options or options[-1][1] != 'BACK':
        raise ValueError('Reflect Selected needs the existing Edit Options page')
    if not any(action == 'XR_REFLECT_MENU' for _label, action in options):
        options = options[:-1] + (('REFLECT', 'XR_REFLECT_MENU'), options[-1])
    if len(options) > 12:
        raise ValueError('Edit Options menu has no room for Reflect Selected')
    menus.PAGES['STEP_MENU'] = options
    menus.PAGES[_PAGE] = (
        ('MIRROR X', 'XR_REFLECT_X'),
        ('MIRROR Y', 'XR_REFLECT_Y'),
        ('MIRROR Z', 'XR_REFLECT_Z'),
        ('LOCAL / WORLD', 'XR_REFLECT_SPACE'),
        ('MEDIAN / CURSOR', 'XR_REFLECT_PIVOT'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'REFLECT SELECTED'
    v065.TOOLTIPS.update({
        'XR_REFLECT_MENU': ('Reflect Selected', 'Reflect native selected mesh coordinates without duplicating geometry'),
        'XR_REFLECT_X': ('Reflect X', 'Mirror selected coordinates across the X-normal plane'),
        'XR_REFLECT_Y': ('Reflect Y', 'Mirror selected coordinates across the Y-normal plane'),
        'XR_REFLECT_Z': ('Reflect Z', 'Mirror selected coordinates across the Z-normal plane'),
        'XR_REFLECT_SPACE': ('Reflection Space', 'Switch between object-local and world-aligned mirror planes'),
        'XR_REFLECT_PIVOT': ('Reflection Pivot', 'Switch between selection median and native 3D cursor'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_mesh_reflect_086_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous_command(self, context, action)
        if action == 'XR_REFLECT_MENU':
            _eligible(context)
            if input_ownership_v080.is_editing(self):
                raise ValueError('Finish the current XR gesture before reflecting')
            menu.page = _PAGE
            space, pivot = _settings(self)
            self.status = 'REFLECT / {} / {}'.format(space, pivot)
            return
        if menu.page == _PAGE:
            if action == 'BACK':
                menu.page = 'STEP_MENU'
                return
            if action == 'XR_REFLECT_SPACE':
                if input_ownership_v080.is_editing(self):
                    raise ValueError('Release XR gesture before changing reflection space')
                space, pivot = _settings(self)
                self._xr_reflect_space = 'WORLD' if space == 'LOCAL' else 'LOCAL'
                self.status = 'REFLECT SPACE / ' + self._xr_reflect_space
                return
            if action == 'XR_REFLECT_PIVOT':
                if input_ownership_v080.is_editing(self):
                    raise ValueError('Release XR gesture before changing reflection pivot')
                space, pivot = _settings(self)
                self._xr_reflect_pivot = 'CURSOR' if pivot == 'MEDIAN' else 'MEDIAN'
                self.status = 'REFLECT PIVOT / ' + self._xr_reflect_pivot
                return
            if action in _ACTIONS:
                return _apply(self, context, action)
            raise ValueError('Finish or exit Reflect Selected first')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_mesh_reflect_086_patched = True
