# SPDX-License-Identifier: GPL-3.0-or-later
"""Exact signed numeric mesh translations with a controller-native keypad.

The keypad only collects a decimal in the current XR session. APPLY runs
one Blender-native BMesh mesh snapshot transaction on the selected vertices,
edges or faces. No extra objects, modifiers, origins, or custom mesh data.
"""
import math

import bpy
from bpy.props import EnumProperty, FloatProperty
from mathutils import Vector

from . import (input_ownership_v080, menus, mesh, mesh_axis_snap_v090,
               mesh_selection_tools_v086, mesh_snap_v086, runtime,
               selection, v065)

_PAGE = 'XR_NUMERIC_MOVE_090'
_DIGITS_PAGE = 'XR_NUMERIC_MOVE_DIGITS_090'
_ENTRY = 'XR_NUMERIC_MOVE_MENU'
_APPLY = 'XR_NUMERIC_MOVE_APPLY'
_DIGITS = {f'XR_NUMERIC_MOVE_{value}': value for value in '0123456789'}
_MAX_SELECTED = 120000
_MAX_DIGITS = 9
_MAX_DECIMALS = 5
_MAX_DISTANCE = 1000.0
_EPSILON = 1e-12


def _distance(text_value, sign):
    if not isinstance(text_value, str) or not text_value:
        raise ValueError('Enter a signed distance on the XR numeric keypad')
    if text_value.count('.') > 1 or any(ch not in '0123456789.' for ch in text_value):
        raise ValueError('Numeric distance contains an unsupported character')
    if text_value == '.':
        raise ValueError('Enter a complete decimal distance')
    value = float(text_value) * int(sign)
    if not math.isfinite(value) or abs(value) > _MAX_DISTANCE:
        raise ValueError('Use a signed distance within 1000 Blender units')
    if abs(value) < _EPSILON:
        raise ValueError('Numeric mesh movement requires a nonzero distance')
    return value


def _eligible(context):
    obj = mesh_snap_v086._eligible(context)
    matrix = obj.matrix_world
    if not all(math.isfinite(float(value)) for row in matrix for value in row):
        raise ValueError('Object world matrix contains non-finite components')
    if abs(float(matrix.determinant())) < 1e-10:
        raise ValueError('Object matrix is not invertible')
    return obj


def _plan(context, axis, space, distance):
    if axis not in 'XYZ' or space not in {'LOCAL', 'WORLD'}:
        raise ValueError('Choose a local/world X, Y or Z axis first')
    if not math.isfinite(distance) or not 0.0 < abs(distance) <= _MAX_DISTANCE:
        raise ValueError('Distance is outside supported numeric movement bounds')
    obj = _eligible(context)
    mode = selection.mode(context)
    bm, _items = mesh_selection_tools_v086._current(obj, mode)
    topology = mesh_selection_tools_v086._topology(bm)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    selected = tuple(sorted(mesh.selected_transform_vertices(obj, mode),
                            key=lambda vertex: vertex.index))
    if not selected or len(selected) > _MAX_SELECTED:
        raise ValueError('Select between 1 and 120,000 visible mesh vertices')
    if any(not vert.is_valid or vert.hide or
           not all(math.isfinite(float(x)) for x in vert.co)
           for vert in selected):
        raise ValueError('Selected vertex is hidden or contains invalid coordinates')
    before = tuple((vert.index, tuple(float(x) for x in vert.co))
                   for vert in selected)
    axis_vec = Vector(tuple(float(letter == axis) for letter in 'XYZ'))
    if space == 'LOCAL':
        delta = axis_vec * distance
    else:
        delta = obj.matrix_world.to_3x3().inverted() @ (axis_vec * distance)
    if not all(math.isfinite(float(x)) for x in delta):
        raise ValueError('Numeric move would create invalid coordinates')
    after = tuple((index, tuple(a + float(b) for a, b in zip(co, delta)))
                  for index, co in before)
    if any(not all(math.isfinite(x) for x in coords) for _index, coords in after):
        raise ValueError('Numeric move would create invalid mesh vertices')
    return {
        'scene': context.scene.name, 'layer': context.view_layer.name,
        'obj': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'matrix': mesh_axis_snap_v090._matrix_stamp(obj.matrix_world),
        'mode': mode, 'topology': topology,
        'before': before, 'after': after,
        'axis': axis, 'space': space, 'distance': distance,
    }


def _write(context, plan):
    obj = _eligible(context)
    if (context.scene.name != plan['scene'] or
            context.view_layer.name != plan['layer'] or
            obj.name != plan['obj'] or obj.as_pointer() != plan['obj_ptr'] or
            obj.data.name != plan['mesh'] or
            obj.data.as_pointer() != plan['mesh_ptr'] or
            mesh_axis_snap_v090._matrix_stamp(obj.matrix_world) != plan['matrix'] or
            selection.mode(context) != plan['mode']):
        raise ValueError('Mesh identity, axis space or scene changed before movement')
    bm, _items = mesh_selection_tools_v086._current(obj, plan['mode'])
    if mesh_selection_tools_v086._topology(bm) != plan['topology']:
        raise ValueError('Mesh topology or visibility changed before movement')
    selected = tuple(sorted(mesh.selected_transform_vertices(obj, plan['mode']),
                            key=lambda vertex: vertex.index))
    if tuple(v.index for v in selected) != tuple(i for i, _point in plan['before']):
        raise ValueError('Mesh selection changed before numeric move')
    bm.verts.ensure_lookup_table()
    for index, coords in plan['before']:
        vertex = bm.verts[index]
        if (not vertex.is_valid or vertex.hide or
                any(abs(float(a) - b) > 1e-10 for a, b in zip(vertex.co, coords))):
            raise ValueError('A mesh vertex changed since numeric move was planned')
    for index, coords in plan['after']:
        bm.verts[index].co = Vector(coords)
    return obj


def apply(context, axis, space, distance, history=None):
    plan = _plan(context, axis, space, distance)
    obj = _eligible(context)
    if history is not None:
        mesh.snapshot_and_push(obj, lambda: _write(context, plan), history)
    else:
        # Blender's own operator Undo owns desktop history; keep a temporary
        # native edit-mesh snapshot to recover if evaluation fails.
        saved = mesh.snapshot(obj)
        try:
            _write(context, plan)
            mesh.update(obj)
        except Exception:
            mesh.restore(obj, saved)
            raise
        finally:
            if saved.name in bpy.data.meshes:
                bpy.data.meshes.remove(saved)
    return len(plan['before'])


class BXR_OT_numeric_move(bpy.types.Operator):
    bl_idname = 'blender_xr.numeric_mesh_move'
    bl_label = 'Exact Signed Mesh Axis Move'
    bl_description = 'Rigid native mesh translation by an exact signed Blender distance'
    bl_options = {'REGISTER', 'UNDO'}

    axis: EnumProperty(items=[(c, c, 'Move along axis ' + c) for c in 'XYZ'],
                       default='X')
    space: EnumProperty(items=(
        ('WORLD', 'World', 'Move along global Blender coordinates'),
        ('LOCAL', 'Local', 'Move along active mesh local coordinates'),
    ), default='WORLD')
    distance: FloatProperty(name='Signed Distance', default=0.01,
                            min=-_MAX_DISTANCE, max=_MAX_DISTANCE, precision=5)

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH')

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the headset Numeric Move keypad in XR')
            return {'CANCELLED'}
        try:
            count = apply(context, self.axis, self.space, self.distance)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, '{} vertices moved precisely'.format(count))
        return {'FINISHED'}


def _state(session):
    state = getattr(session, '_xr_numeric_move_state', None)
    if not isinstance(state, dict):
        raise ValueError('Open the Numeric Move keypad before entering distance')
    return state


def _status(session, label):
    state = _state(session)
    sign = '-' if state['sign'] < 0 else '+'
    session.status = 'NUMERIC {} / {}{} {} {} / {}'.format(
        label, sign, state['text'] or '(EMPTY)', state['space'],
        state['axis'], 'XR UNDO ON APPLY')


def _start(session, context):
    _eligible(context)
    session._xr_numeric_move_state = {
        'text': '', 'sign': 1, 'axis': 'X',
        'space': 'WORLD',
    }
    session.menu.page = _PAGE
    _status(session, 'MOVE')


def _reset(session, parent):
    session._xr_numeric_move_state = None
    session.menu.page = parent


def _digit(session, action):
    state = _state(session)
    value = _DIGITS.get(action)
    if value is not None:
        if len(state['text'].replace('.', '')) >= _MAX_DIGITS:
            raise ValueError('Numeric input is limited to nine digits')
        decimals = (len(state['text'].split('.', 1)[1])
                    if '.' in state['text'] else 0)
        if decimals >= _MAX_DECIMALS:
            raise ValueError('Numeric move supports up to five decimal places')
        state['text'] += value
    elif action == 'XR_NUMERIC_MOVE_DECIMAL':
        if '.' not in state['text']:
            state['text'] += '.'
    elif action == 'XR_NUMERIC_MOVE_DELETE':
        state['text'] = state['text'][:-1]
    else:
        raise ValueError('Unknown signed numeric keypad key')
    _status(session, 'INPUT')


def install_pages():
    existing = tuple(menus.PAGES[mesh_axis_snap_v090._PAGE])
    if not existing or existing[-1][1] != 'BACK':
        raise ValueError('Axis Snap menu is unavailable for Numeric Move')
    if not any(action == _ENTRY for _label, action in existing):
        existing = existing[:-1] + (('NUMERIC MOVE', _ENTRY), existing[-1])
    if len(existing) > 12:
        raise ValueError('Axis Snap has no room for Numeric Move')
    menus.PAGES[mesh_axis_snap_v090._PAGE] = existing
    menus.PAGES[_PAGE] = (
        ('ENTER DIGITS', 'XR_NUMERIC_MOVE_DIGITS'),
        ('AXIS X', 'XR_NUMERIC_MOVE_AXIS_X'),
        ('AXIS Y', 'XR_NUMERIC_MOVE_AXIS_Y'),
        ('AXIS Z', 'XR_NUMERIC_MOVE_AXIS_Z'),
        ('WORLD/LOCAL', 'XR_NUMERIC_MOVE_SPACE'),
        ('POS/NEG', 'XR_NUMERIC_MOVE_SIGN'),
        ('DELETE', 'XR_NUMERIC_MOVE_DELETE'),
        ('CLEAR', 'XR_NUMERIC_MOVE_CLEAR'),
        ('APPLY', _APPLY),
        ('BACK', 'BACK'),
    )
    # Twelve buttons including Done. Only the dedicated APPLY action
    # mutates Blender data, never a keypad tap or thumbstick direction.
    menus.PAGES[_DIGITS_PAGE] = tuple(
        (digit, 'XR_NUMERIC_MOVE_' + digit) for digit in '1234567890'
    ) + (('.', 'XR_NUMERIC_MOVE_DECIMAL'), ('DONE', 'XR_NUMERIC_MOVE_DONE'))
    menus.TITLES[_PAGE] = 'EXACT NUMERIC AXIS MOVE'
    menus.TITLES[_DIGITS_PAGE] = 'TYPE DISTANCE'
    v065.TOOLTIPS.update({
        _ENTRY: ('Exact Numeric Mesh Move',
                 'Enter a signed decimal distance for a rigid world/local axis move'),
        _APPLY: ('Apply Exact Native Move',
                 'Commit one Blender mesh transaction after explicit confirmation'),
        'XR_NUMERIC_MOVE_DIGITS': ('Enter Numeric Distance',
                 'Open the headset decimal keypad; no mesh data is changed while typing'),
        'XR_NUMERIC_MOVE_SIGN': ('Invert Signed Direction',
                 'Switch positive or negative distance before Apply'),
        'XR_NUMERIC_MOVE_SPACE': ('World or Local Axis',
                 'Use the global or mesh-local X/Y/Z axis'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_numeric_mesh_move_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == mesh_axis_snap_v090._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controller gesture before Numeric Move')
            _start(self, context)
            return
        if page not in {_PAGE, _DIGITS_PAGE}:
            return previous_command(self, context, action)
        if action == 'BACK':
            if page == _DIGITS_PAGE:
                self.menu.page = _PAGE
                return
            _reset(self, mesh_axis_snap_v090._PAGE)
            self.status = 'NUMERIC MOVE / CANCELLED / NO MESH CHANGE'
            return
        if input_ownership_v080.is_editing(self):
            raise ValueError('Finish XR editing gesture before typing or applying')
        state = _state(self)
        if page == _DIGITS_PAGE:
            if action == 'XR_NUMERIC_MOVE_DONE':
                self.menu.page = _PAGE
                _status(self, 'READY')
                return
            if action in _DIGITS or action == 'XR_NUMERIC_MOVE_DECIMAL':
                _digit(self, action)
                return
            raise ValueError('Use a numeric keypad button or Done')
        if action == 'XR_NUMERIC_MOVE_DIGITS':
            self.menu.page = _DIGITS_PAGE
            _status(self, 'TYPE')
            return
        if action.startswith('XR_NUMERIC_MOVE_AXIS_'):
            axis = action[-1:]
            if axis not in 'XYZ':
                raise ValueError('Choose X, Y or Z')
            state['axis'] = axis
        elif action == 'XR_NUMERIC_MOVE_SPACE':
            state['space'] = 'LOCAL' if state['space'] == 'WORLD' else 'WORLD'
        elif action == 'XR_NUMERIC_MOVE_SIGN':
            state['sign'] *= -1
        elif action == 'XR_NUMERIC_MOVE_DELETE':
            _digit(self, action)
            return
        elif action == 'XR_NUMERIC_MOVE_CLEAR':
            state['text'] = ''
        elif action == _APPLY:
            if getattr(self, 'history', None) is None:
                raise ValueError('XR history is required for exact mesh movement')
            distance = _distance(state['text'], state['sign'])
            count = apply(context, state['axis'], state['space'],
                          distance, self.history)
            _reset(self, mesh_axis_snap_v090._PAGE)
            self._xr_precision_last_ray = None
            self.status = 'EXACT MOVE / {} VERTICES / {} {} {:.5f} / XR UNDO READY'.format(
                count, state['space'], state['axis'], distance)
            return
        else:
            raise ValueError('Choose axis/space, type a distance or Apply')
        _status(self, 'READY')

    Runtime.command = command
    Runtime._xr_numeric_mesh_move_090_patched = True


CLASSES = (BXR_OT_numeric_move,)
