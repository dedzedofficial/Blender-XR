# SPDX-License-Identifier: GPL-3.0-or-later
"""Native VR Measure -> Apply for exact object placement.

Capture a distance between two selected Blender object origins, then move the
active object by that distance on a world or local X/Y/Z axis. Measurements
are session-only and read-only until an explicit apply command.
"""
import math

import bpy
from mathutils import Vector

from . import input_ownership_v080, menus, mesh, v065

_PAGE = 'XR_MEASURE_APPLY_086'
_AXES = {
    'XR_MEASURE_X_POS': ('X', 1), 'XR_MEASURE_X_NEG': ('X', -1),
    'XR_MEASURE_Y_POS': ('Y', 1), 'XR_MEASURE_Y_NEG': ('Y', -1),
    'XR_MEASURE_Z_POS': ('Z', 1), 'XR_MEASURE_Z_NEG': ('Z', -1),
}


def _same(a, b):
    return all(abs(float(a[i][j]) - float(b[i][j])) < 1e-5
               for i in range(4) for j in range(4))


def _pair(context):
    if context.mode != 'OBJECT':
        raise ValueError('Measure Apply requires native Object Mode')
    selected = tuple(context.selected_objects)
    active = context.view_layer.objects.active
    if (len(selected) != 2 or active not in selected or
            any(obj.mode != 'OBJECT' for obj in selected)):
        raise ValueError('Select exactly two objects, with the mover active')
    other = selected[0] if selected[1] == active else selected[1]
    return active, other


def _editable(obj):
    if (obj.library or obj.override_library or obj.hide_select or
            obj.hide_get() or not obj.visible_get() or obj.parent is not None
            or obj.constraints or
            (obj.data is not None and
             (obj.data.library or obj.data.override_library))):
        raise ValueError('Use an unlocked local, unparented object with no constraints')
    if (obj.animation_data and
            (obj.animation_data.action or obj.animation_data.drivers)):
        raise ValueError('Animated object transforms must use Blender animation tools')
    if abs(obj.matrix_world.determinant()) < 1e-10:
        raise ValueError('Object has zero scale')
    return obj


def _capture(session, context):
    a, b = _pair(context)
    before = a.matrix_world.copy()
    other = b.matrix_world.copy()
    value = (before.translation - other.translation).length
    if not math.isfinite(value) or value <= 1e-8:
        raise ValueError('Object origins coincide; choose different endpoints')
    session._xr_measure_capture = {
        'scene': context.scene.name, 'layer': context.view_layer.name,
        'mover': a.name, 'mover_ptr': a.as_pointer(),
        'other': b.name, 'other_ptr': b.as_pointer(),
        'mover_matrix': before, 'other_matrix': other, 'distance': value,
    }
    scale = float(context.scene.unit_settings.scale_length) or 1.0
    session.status = 'MEASURE CAPTURED / {:.4f} SCENE METRES'.format(value * scale)


def _valid_capture(session, context):
    saved = getattr(session, '_xr_measure_capture', None)
    if saved is None:
        raise ValueError('Capture two object origins before applying distance')
    a, b = _pair(context)
    if (saved['scene'] != context.scene.name or
            saved['layer'] != context.view_layer.name or
            saved['mover'] != a.name or a.as_pointer() != saved['mover_ptr'] or
            saved['other'] != b.name or b.as_pointer() != saved['other_ptr'] or
            not _same(a.matrix_world, saved['mover_matrix']) or
            not _same(b.matrix_world, saved['other_matrix'])):
        session._xr_measure_capture = None
        raise ValueError('Measured objects changed; capture distance again')
    return a, b, saved


def _move(session, context, axis, sign):
    if input_ownership_v080.is_editing(session):
        raise ValueError('Release controller gesture before applying measurement')
    obj, other, saved = _valid_capture(session, context)
    _editable(obj)
    history = getattr(session, 'history', None)
    if history is None:
        raise ValueError('XR Undo history is required for Measure Apply')
    base = obj.matrix_world.copy()
    normal = Vector(tuple(1.0 if axis == a else 0.0 for a in 'XYZ'))
    local = getattr(session, '_xr_measure_space', 'WORLD') == 'LOCAL'
    if local:
        normal = base.to_3x3() @ normal
    if normal.length_squared < 1e-10:
        raise ValueError('Measured transform axis is invalid')
    displacement = normal.normalized() * float(saved['distance']) * sign
    after = base.copy()
    after.translation = base.translation + displacement
    if not all(math.isfinite(float(v)) for row in after for v in row):
        raise ValueError('Measured position is not finite')
    obj.matrix_world = after
    try:
        context.view_layer.update()
        history.push(('XR_MEASURE_APPLY_086', obj.name, obj.as_pointer(),
                      obj, obj.data.name if obj.data else None,
                      base, after.copy(), context.scene.name,
                      context.view_layer.name))
    except Exception:
        if _same(obj.matrix_world, after):
            obj.matrix_world = base
            context.view_layer.update()
        raise
    saved['mover_matrix'] = after.copy()
    session.status = 'MEASURE APPLY / {} {} / {:.4f} / {}'.format(
        axis, '+' if sign > 0 else '-', saved['distance'],
        'LOCAL' if local else 'WORLD')


def _history():
    if getattr(mesh.History, '_xr_measure_apply_history', False):
        return
    old_step, old_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == 'XR_MEASURE_APPLY_086':
            return
        return old_release(entry)

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] != 'XR_MEASURE_APPLY_086':
            return old_step(self, backwards)
        _tag, name, ptr, identity, data_name, before, after, scene_name, layer_name = source[-1]
        obj = bpy.data.objects.get(name)
        if (bpy.context.mode != 'OBJECT' or
                bpy.context.scene.name != scene_name or
                bpy.context.view_layer.name != layer_name or
                obj is None or obj != identity or obj.as_pointer() != ptr or
                obj.mode != 'OBJECT' or
                (obj.data.name if obj.data else None) != data_name):
            raise ValueError('Measure Apply object identity or scene changed')
        _editable(obj)
        expected = after if backwards else before
        if not _same(obj.matrix_world, expected):
            raise ValueError('Measure Apply object moved outside XR history')
        obj.matrix_world = (before if backwards else after).copy()
        bpy.context.view_layer.update()
        dest.append(source.pop())
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_measure_apply_history = True


def install_pages():
    parent = tuple(menus.PAGES['LAYOUT_MENU'])
    if not any(action == 'XR_MEASURE_MENU' for _label, action in parent):
        if not parent or parent[-1][1] != 'BACK' or len(parent) >= 12:
            raise ValueError('Object Layout menu has no room for Measure Apply')
        menus.PAGES['LAYOUT_MENU'] = parent[:-1] + (
            ('MEASURE', 'XR_MEASURE_MENU'), parent[-1])
    menus.PAGES[_PAGE] = (
        ('CAPTURE', 'XR_MEASURE_CAPTURE'),
        ('X +', 'XR_MEASURE_X_POS'), ('X -', 'XR_MEASURE_X_NEG'),
        ('Y +', 'XR_MEASURE_Y_POS'), ('Y -', 'XR_MEASURE_Y_NEG'),
        ('Z +', 'XR_MEASURE_Z_POS'), ('Z -', 'XR_MEASURE_Z_NEG'),
        ('WORLD / LOCAL', 'XR_MEASURE_SPACE'),
        ('CLEAR', 'XR_MEASURE_CLEAR'), ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'MEASURE TO APPLY'
    v065.TOOLTIPS.update({
        'XR_MEASURE_MENU': ('Measure to Apply', 'Use two existing Blender object origins to capture an exact world distance'),
        'XR_MEASURE_CAPTURE': ('Capture Distance', 'Read-only distance between two selected objects; active object will be moved'),
        'XR_MEASURE_SPACE': ('World / Local Axis', 'Choose world or active-object local axes for measured translation'),
        'XR_MEASURE_CLEAR': ('Clear Captured Distance', 'Discard the session-only measurement without changing Blender objects'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_measure_apply_086_patched', False):
        return
    _history()
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        if getattr(self, 'menu', None) is None:
            return previous_command(self, context, action)
        if action == 'XR_MEASURE_MENU':
            if input_ownership_v080.is_editing(self):
                raise ValueError('Finish the active controller edit first')
            _pair(context)
            self.menu.page = _PAGE
            self.status = 'MEASURE APPLY / CAPTURE TWO OBJECT ORIGINS'
            return
        if self.menu.page == _PAGE:
            if action == 'BACK':
                self.menu.page = 'LAYOUT_MENU'
                return
            if action == 'XR_MEASURE_CAPTURE':
                _capture(self, context)
                return
            if action == 'XR_MEASURE_CLEAR':
                self._xr_measure_capture = None
                self.status = 'MEASURE CLEARED / NO SCENE EDIT'
                return
            if action == 'XR_MEASURE_SPACE':
                self._xr_measure_space = ('LOCAL' if getattr(
                    self, '_xr_measure_space', 'WORLD') == 'WORLD' else 'WORLD')
                self.status = 'MEASURE APPLY / ' + self._xr_measure_space
                return
            if action in _AXES:
                axis, sign = _AXES[action]
                return _move(self, context, axis, sign)
            raise ValueError('Unknown Measure Apply command')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_measure_apply_086_patched = True
