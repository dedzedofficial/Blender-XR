# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Blender shape-key value and mute editing from existing XR menus.

This editor never edits shape-key topology or invents a custom avatar format.
Value/mute changes create guarded per-key XR history entries. Existing
animation/driver curves are not overridden, and Basis is read-only.
"""
import math

import bpy

from . import input_ownership_v080, menus, mesh, runtime, v065

_PAGE = 'XR_SHAPE_KEYS_090'
_ACTIONS = {
    'XR_SHAPE_VALUE_ZERO': ('VALUE', 0.0),
    'XR_SHAPE_VALUE_HALF': ('VALUE', 0.5),
    'XR_SHAPE_VALUE_ONE': ('VALUE', 1.0),
    'XR_SHAPE_VALUE_DOWN': ('DELTA', -0.1),
    'XR_SHAPE_VALUE_UP': ('DELTA', 0.1),
    'XR_SHAPE_VALUE_FINE_DOWN': ('DELTA', -0.01),
    'XR_SHAPE_VALUE_FINE_UP': ('DELTA', 0.01),
    'XR_SHAPE_MUTE': ('MUTE', None),
}


def _object(context):
    obj = context.view_layer.objects.active
    if (obj is None or obj.type != 'MESH' or context.mode != 'OBJECT' or
            obj.mode != 'OBJECT'):
        raise ValueError('Select a mesh in Blender Object Mode for Shape Keys')
    if (obj.library or obj.override_library or obj.data.library or
            obj.data.override_library or obj.data.users != 1 or
            obj.hide_select or obj.hide_get() or not obj.visible_get()):
        raise ValueError('Use a visible, local, single-user shape-key mesh')
    data = obj.data.shape_keys
    if data is None or not data.use_relative or len(data.key_blocks) < 2:
        raise ValueError('Create a native Basis and shape key in Blender first')
    return obj, data


def _target(context):
    obj, data = _object(context)
    idx = int(obj.active_shape_key_index)
    if idx <= 0 or idx >= len(data.key_blocks):
        raise ValueError('Select a non-Basis shape key before editing its value')
    key = data.key_blocks[idx]
    if len(key.data) != len(obj.data.vertices):
        raise ValueError('Shape key no longer matches the mesh vertex count')
    # Keyframes and drivers have their own authoring/Undo lifecycle. Do not
    # fight the animation system by writing an animated evaluation result.
    animation = data.animation_data
    if animation is not None and (animation.action or len(animation.drivers)):
        raise ValueError('Animated shape keys must be edited in Blender animation tools')
    return obj, data, idx, key


def _state(key):
    return (float(key.value), bool(key.mute))


def _same(a, b):
    return abs(float(a[0]) - float(b[0])) <= 1e-6 and bool(a[1]) == bool(b[1])


def _guard(context, entry):
    (_kind, name, obj_ptr, data_name, mesh_ptr, key_ptr,
     index, key_name, block_ptr, _before, _after, shape,
     layout) = entry
    obj = bpy.data.objects.get(name)
    if (obj is None or context.mode != 'OBJECT' or obj.mode != 'OBJECT' or
            context.view_layer.objects.get(name) != obj or
            obj.as_pointer() != obj_ptr or obj.type != 'MESH' or
            obj.data.as_pointer() != mesh_ptr or obj.data.name != data_name):
        raise ValueError('Shape key owner changed outside XR')
    current, keys = _object(context)
    if current != obj or keys.as_pointer() != key_ptr:
        raise ValueError('Native Blender Key datablock was replaced')
    if len(obj.data.vertices) != shape:
        raise ValueError('Shape key mesh topology changed outside XR')
    current_layout = tuple((i, block.name, block.as_pointer())
                           for i, block in enumerate(keys.key_blocks))
    if current_layout != layout:
        raise ValueError('Shape key names or layout changed outside XR history')
    if index <= 0 or index >= len(keys.key_blocks):
        raise ValueError('A shape key was removed since the XR edit')
    block = keys.key_blocks[index]
    if block.name != key_name or block.as_pointer() != block_ptr:
        raise ValueError('Shape key was renamed or replaced since XR edit')
    if len(block.data) != shape:
        raise ValueError('Shape key geometry no longer matches the base mesh')
    return obj, block


def _write(context, entry, backwards):
    obj, block = _guard(context, entry)
    expected, desired = (entry[10], entry[9]) if backwards else (entry[9], entry[10])
    if not _same(_state(block), expected):
        raise ValueError('Shape key was edited outside XR history')
    block.value = desired[0]
    block.mute = desired[1]
    context.view_layer.update()


def _apply(context, action, history=None):
    if action not in _ACTIONS:
        raise ValueError('Unknown shape key action')
    obj, data, index, block = _target(context)
    prior = _state(block)
    kind, amount = _ACTIONS[action]
    if kind == 'MUTE':
        desired = (prior[0], not prior[1])
    else:
        value = (amount if kind == 'VALUE' else prior[0] + amount)
        value = max(float(block.slider_min), min(float(block.slider_max), float(value)))
        if not math.isfinite(value):
            raise ValueError('Shape key value must be finite')
        desired = (round(value, 4), prior[1])
    if _same(prior, desired):
        return block.name, desired, False

    layout = tuple((i, other.name, other.as_pointer())
                   for i, other in enumerate(data.key_blocks))
    entry = ('XR_SHAPE_VALUE_090', obj.name, obj.as_pointer(),
             obj.data.name, obj.data.as_pointer(), data.as_pointer(),
             index, block.name, block.as_pointer(), prior, desired,
             len(obj.data.vertices), layout)
    _guard(context, entry)
    block.value, block.mute = desired
    try:
        context.view_layer.update()
        if history is not None:
            history.push(entry)
    except Exception:
        # Refuse a stale rollback if another editor overwrote this key.
        if _same(_state(block), desired):
            block.value, block.mute = prior
            context.view_layer.update()
        raise
    return block.name, desired, True


def _step_key(context, increment):
    obj, data = _object(context)
    idx = int(obj.active_shape_key_index)
    obj.active_shape_key_index = (1 + ((max(idx, 1) - 1 + increment)
                                  % (len(data.key_blocks) - 1)))
    key = data.key_blocks[obj.active_shape_key_index]
    return key.name, _state(key)


class BXR_OT_shape_key_value(bpy.types.Operator):
    bl_idname = 'blender_xr.shape_key_value'
    bl_label = 'Blender XR Shape Key Value'
    bl_description = 'Change the native active shape key value or mute without overwriting animation'
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(items=[
        (action, action.replace('XR_SHAPE_', '').replace('_', ' ').title(),
         'Native shape key change')
        for action in _ACTIONS], default='XR_SHAPE_VALUE_UP')

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and obj.mode == 'OBJECT'
                    and obj.data.shape_keys and
                    len(obj.data.shape_keys.key_blocks) > 1)

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the wrist Shape Keys menu during XR')
            return {'CANCELLED'}
        try:
            name, state, changed = _apply(context, self.action)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, '{} / {:.3f} / {}'.format(
            name, state[0], 'MUTED' if state[1] else 'ENABLED'))
        return {'FINISHED'} if changed else {'CANCELLED'}


def _history():
    if getattr(mesh.History, '_xr_shape_value_090_patched', False):
        return
    old_step, old_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == 'XR_SHAPE_VALUE_090':
            return
        return old_release(entry)

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] != 'XR_SHAPE_VALUE_090':
            return old_step(self, backwards)
        _write(bpy.context, source[-1], backwards)
        dest.append(source.pop())
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_shape_value_090_patched = True


def install_pages():
    parent = tuple(menus.PAGES.get('LAYOUT_MENU', ()))
    if not parent or parent[-1][1] != 'BACK':
        raise ValueError('Shape Keys requires the existing Object Layout menu')
    if not any(action == 'XR_SHAPE_MENU' for _label, action in parent):
        parent = parent[:-1] + (('SHAPE KEYS', 'XR_SHAPE_MENU'), parent[-1])
    if len(parent) > 12:
        raise ValueError('No room in existing Object Layout menu for Shape Keys')
    menus.PAGES['LAYOUT_MENU'] = parent
    menus.PAGES[_PAGE] = (
        ('PREVIOUS', 'XR_SHAPE_PREVIOUS'),
        ('NEXT', 'XR_SHAPE_NEXT'),
        ('ZERO', 'XR_SHAPE_VALUE_ZERO'),
        ('HALF', 'XR_SHAPE_VALUE_HALF'),
        ('ONE', 'XR_SHAPE_VALUE_ONE'),
        ('VALUE -', 'XR_SHAPE_VALUE_DOWN'),
        ('VALUE +', 'XR_SHAPE_VALUE_UP'),
        ('FINE -', 'XR_SHAPE_VALUE_FINE_DOWN'),
        ('FINE +', 'XR_SHAPE_VALUE_FINE_UP'),
        ('MUTE', 'XR_SHAPE_MUTE'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'SHAPE KEY VALUES'
    v065.TOOLTIPS.update({
        'XR_SHAPE_MENU': ('Native Shape Key Values', 'Adjust existing native Blender shape-key values in Object Mode'),
        'XR_SHAPE_PREVIOUS': ('Previous Shape Key', 'Select preceding shape key, skipping the Basis'),
        'XR_SHAPE_NEXT': ('Next Shape Key', 'Select next shape key, skipping the Basis'),
        'XR_SHAPE_MUTE': ('Mute Shape Key', 'Toggle the current native shape key mute flag with XR Undo'),
        'XR_SHAPE_VALUE_ZERO': ('Shape Value 0', 'Set active non-Basis key value to zero'),
        'XR_SHAPE_VALUE_HALF': ('Shape Value Half', 'Set active non-Basis key value to half'),
        'XR_SHAPE_VALUE_ONE': ('Shape Value 1', 'Set active non-Basis key value to one'),
        'XR_SHAPE_VALUE_DOWN': ('Shape Value Down 0.1', 'Decrease current shape key by 0.1'),
        'XR_SHAPE_VALUE_UP': ('Shape Value Up 0.1', 'Increase current shape key by 0.1'),
        'XR_SHAPE_VALUE_FINE_DOWN': ('Shape Fine Down', 'Decrease current shape key by 0.01'),
        'XR_SHAPE_VALUE_FINE_UP': ('Shape Fine Up', 'Increase current shape key by 0.01'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_shape_keys_090_patched', False):
        return
    _history()
    install_pages()
    original_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if action == 'XR_SHAPE_MENU':
            _object(context)
            if input_ownership_v080.is_editing(self):
                raise ValueError('Finish the active controller edit before Shape Keys')
            self.menu.page = _PAGE
            self.status = 'SHAPE KEYS / SELECT NON-BASIS KEY'
            return
        if page == _PAGE:
            if action == 'BACK':
                self.menu.page = 'LAYOUT_MENU'
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release the active XR gesture to edit Shape Keys')
            if action in {'XR_SHAPE_PREVIOUS', 'XR_SHAPE_NEXT'}:
                name, state = _step_key(context, -1 if action.endswith('PREVIOUS') else 1)
                self.status = 'SHAPE KEY / {} / {:.3f}'.format(name.upper(), state[0])
                return
            if action in _ACTIONS:
                history = getattr(self, 'history', None)
                if history is None:
                    raise ValueError('XR Undo history required for Shape Keys')
                name, state, changed = _apply(context, action, history=history)
                self.status = 'SHAPE {} / {:.3f} / {}'.format(
                    name.upper(), state[0], 'MUTED' if state[1] else
                    'UNDO READY' if changed else 'UNCHANGED')
                return
            raise ValueError('Unknown Shape Keys menu action')
        return original_command(self, context, action)

    Runtime.command = command
    Runtime._xr_shape_keys_090_patched = True


CLASSES = (BXR_OT_shape_key_value,)
