# SPDX-License-Identifier: GPL-3.0-or-later
"""Exact-step native axis movement from the Mesh XR headset.

One press applies one Blender-native, XR-undoable displacement. Global axes
use Blender world coordinates, while Local axes use the active mesh object's
local coordinates. This is deliberately not a continuous controller gesture:
it remains deterministic when tracking precision is low.
"""
import math

import bmesh
from mathutils import Vector

from . import input_ownership_v080, mesh, menus, v065, v071

_PAGE = 'XR_AXIS_NUDGE_086'
_PRESETS = {
    'XR_NUDGE_1MM': 0.001,
    'XR_NUDGE_1CM': 0.01,
    'XR_NUDGE_10CM': 0.1,
    'XR_NUDGE_1M': 1.0,
}


def _eligible(context):
    obj = context.view_layer.objects.active
    if obj is None or obj.type != 'MESH':
        raise ValueError('Select a mesh object for precise movement')
    if context.view_layer.objects.get(obj.name) != obj:
        raise ValueError('Mesh is outside the active view layer')
    if obj.hide_select or not obj.visible_get(view_layer=context.view_layer):
        raise ValueError('Unlock and show the mesh before precise movement')
    if obj.override_library or obj.library or obj.data.library:
        raise ValueError('Linked or overridden meshes are protected')
    if context.mode == 'EDIT_MESH' and obj.mode == 'EDIT':
        mesh.editable(obj)
        return obj, 'EDIT'
    if context.mode == 'OBJECT' and obj.mode == 'OBJECT':
        v071.editable_object(obj)
        if obj.parent or obj.constraints:
            raise ValueError('Object nudge requires an unparented, unconstrained mesh')
        if obj.animation_data and (obj.animation_data.action or obj.animation_data.drivers):
            raise ValueError('Animated object transforms require the native Blender editor')
        return obj, 'OBJECT'
    raise ValueError('Use Object Mode or Mesh Edit Mode for precise movement')


def _step(session):
    value = float(session.settings.step)
    if not math.isfinite(value) or value < 0.0001 or value > 10.0:
        raise ValueError('Set a valid positive tool distance')
    return value


def _nudge(context, session, axis, direction):
    if axis not in 'XYZ' or direction not in (-1, 1):
        raise ValueError('Invalid axis command')
    if input_ownership_v080.is_editing(session):
        raise ValueError('Finish the current controller gesture first')
    if getattr(session, 'history', None) is None:
        raise ValueError('XR history is required for precise movement')
    obj, mode = _eligible(context)
    distance = _step(session) * direction
    normal = Vector(tuple(1.0 if c == axis else 0.0 for c in 'XYZ'))
    local = getattr(session, '_xr_nudge_space', 'GLOBAL') == 'LOCAL'

    if mode == 'EDIT':
        # For a global world-space displacement, map the requested vector into
        # the local mesh cage without altering the object origin or modifiers.
        if local:
            delta = normal * distance
        else:
            if abs(obj.matrix_world.determinant()) < 1e-10:
                raise ValueError('Cannot move mesh with zero object scale')
            delta = obj.matrix_world.to_3x3().inverted() @ (normal * distance)

        def operation():
            bm = mesh.editable(obj)
            vertices = mesh.selected_transform_vertices(
                obj, mesh.selection_mode(context))
            if not vertices:
                raise ValueError('Select vertices, edges or faces before nudging')
            bmesh.ops.translate(bm, verts=vertices, vec=delta)

        # One native mesh snapshot before/after, integrated into the existing
        # XR-local Undo/Redo and released when history is discarded.
        entry = mesh._snapshot_operation(obj, operation)
    else:
        before = obj.matrix_world.copy()
        if local:
            world_axis = before.to_3x3() @ normal
            if world_axis.length_squared < 1e-12:
                raise ValueError('Local object axis is degenerate')
            offset = world_axis.normalized() * distance
        else:
            offset = normal * distance
        after = before.copy()
        after.translation = before.translation + offset
        obj.matrix_world = after
        entry = ('OBJECT', obj.name, None, before, obj.matrix_world.copy())

    session.history.push(entry)
    session.status = 'NUDGE / {} {} {:.4f} / {}'.format(
        axis, '+' if direction > 0 else '-', abs(distance),
        'LOCAL' if local else 'WORLD')


def install_pages():
    # Existing Object Tools has 12 buttons, whereas Quick Layout and Edit Step
    # have spare capacity. Both routes reach the same nudge page.
    for parent in ('LAYOUT_MENU', 'STEP_MENU'):
        current = tuple(menus.PAGES.get(parent, ()))
        if not current:
            raise ValueError('Missing parent menu: ' + parent)
        if not any(action == 'XR_NUDGE_MENU' for _, action in current):
            current = current[:-1] + (('AXIS NUDGE', 'XR_NUDGE_MENU'), current[-1])
        if len(current) > 12:
            raise ValueError('Axis nudge would overflow ' + parent)
        menus.PAGES[parent] = current
    menus.PAGES[_PAGE] = (
        ('X +', 'XR_NUDGE_X_POS'), ('X -', 'XR_NUDGE_X_NEG'),
        ('Y +', 'XR_NUDGE_Y_POS'), ('Y -', 'XR_NUDGE_Y_NEG'),
        ('Z +', 'XR_NUDGE_Z_POS'), ('Z -', 'XR_NUDGE_Z_NEG'),
        ('WORLD / LOCAL', 'XR_NUDGE_SPACE'),
        ('STEP 1 MM', 'XR_NUDGE_1MM'),
        ('STEP 1 CM', 'XR_NUDGE_1CM'),
        ('STEP 10 CM', 'XR_NUDGE_10CM'),
        ('STEP 1 M', 'XR_NUDGE_1M'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'PRECISE AXIS MOVE'
    v065.TOOLTIPS.update({
        'XR_NUDGE_MENU': ('Exact Step Axis Movement', 'Move active object or selected mesh elements using a fixed X/Y/Z distance'),
        'XR_NUDGE_SPACE': ('World / Local Axes', 'Use Blender world axes or the active mesh local coordinate axes'),
        'XR_NUDGE_1MM': ('1 Millimetre Step', 'Set tool distance to 0.001 Blender units'),
        'XR_NUDGE_1CM': ('1 Centimetre Step', 'Set tool distance to 0.01 Blender units'),
        'XR_NUDGE_10CM': ('10 Centimetre Step', 'Set tool distance to 0.1 Blender units'),
        'XR_NUDGE_1M': ('1 Metre Step', 'Set tool distance to 1 Blender unit'),
    })
    for axis in 'XYZ':
        for suffix, text in (('POS', 'positive'), ('NEG', 'negative')):
            v065.TOOLTIPS['XR_NUDGE_' + axis + '_' + suffix] = (
                'Move {} {}'.format(axis, suffix),
                'Move exactly one tool step along the {} {} axis'.format(text, axis))


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_axis_nudge_086_patched', False):
        return
    install_pages()
    previous = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous(self, context, action)
        if action == 'XR_NUDGE_MENU':
            _eligible(context)
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release active controllers before opening Axis Nudge')
            self._xr_nudge_parent = menu.page
            menu.page = _PAGE
            self.status = 'NUDGE / {:.4f} / {}'.format(
                _step(self), getattr(self, '_xr_nudge_space', 'GLOBAL'))
            return
        if menu.page == _PAGE:
            if action == 'BACK':
                menu.page = getattr(self, '_xr_nudge_parent', 'STEP_MENU')
                return
            if action == 'XR_NUDGE_SPACE':
                self._xr_nudge_space = (
                    'GLOBAL' if getattr(self, '_xr_nudge_space', 'GLOBAL') == 'LOCAL'
                    else 'LOCAL')
                self.status = 'NUDGE AXES / ' + self._xr_nudge_space
                return
            if action in _PRESETS:
                self.settings.step = _PRESETS[action]
                self.status = 'NUDGE STEP / {:.4f} BLENDER UNITS'.format(
                    float(self.settings.step))
                return
            if action.startswith('XR_NUDGE_'):
                parts = action.split('_')
                if len(parts) == 4 and parts[2] in 'XYZ' and parts[3] in ('POS', 'NEG'):
                    _nudge(context, self, parts[2], 1 if parts[3] == 'POS' else -1)
                    return
        return previous(self, context, action)

    Runtime.command = command
    Runtime._xr_axis_nudge_086_patched = True
