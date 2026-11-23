# SPDX-License-Identifier: GPL-3.0-or-later
"""Native ShapeKey.value keyframe creation with XR-owned Undo/Redo.

Keys are inserted into Blender's real Key datablock Action/FCurves, supporting
legacy (4.2/4.3) and slotted (4.4+) Actions. Existing keys at the requested
frame are never overwritten. Session-local history removes/reinserts only
the point created by XR; the native Action and FCurve remain editable.
"""
import math

import bpy

from . import (input_ownership_v080, menus, mesh, runtime, shape_key_v090,
               shape_key_structure_v090, v065)

_PAGE = 'XR_SHAPE_KEYFRAMES_090'
_PARENT = shape_key_structure_v090._PAGE
_TAG = 'XR_SHAPE_KEYFRAME_090'
_VALUES = {
    'XR_SHAPE_KEY_0': 0.0,
    'XR_SHAPE_KEY_HALF': 0.5,
    'XR_SHAPE_KEY_1': 1.0,
}
_CURRENT = 'XR_SHAPE_KEY_CURRENT'
_INFO = 'XR_SHAPE_KEY_INFO'
_EPS = 1e-4


def _target(context):
    obj, keys = shape_key_v090._object(context)
    index = int(obj.active_shape_key_index)
    if not 0 < index < len(keys.key_blocks):
        raise ValueError('Choose a non-Basis shape key to animate')
    block = keys.key_blocks[index]
    if len(block.data) != len(obj.data.vertices):
        raise ValueError('Shape-key vertices no longer match the mesh')
    if not math.isfinite(float(block.value)):
        raise ValueError('Shape-key evaluated value is invalid')
    frame = float(context.scene.frame_current) + float(context.scene.frame_subframe)
    if abs(frame - round(frame)) > _EPS:
        raise ValueError('Select a whole Blender frame before adding a key')
    action_data = keys.animation_data
    if action_data:
        if any(driver.data_path == block.path_from_id('value')
               for driver in action_data.drivers):
            raise ValueError('This shape key is driven; edit its driver in Blender')
        action = action_data.action
        if action and (action.library or action.override_library or action.users > 1):
            raise ValueError('Use a local single-user native animation Action')
    return obj, keys, block, int(round(frame))


def _curves(keys):
    """Resolve only the assigned native Action slot's visible FCurves."""
    ad = keys.animation_data
    action = ad.action if ad else None
    if action is None:
        return None, ()
    if getattr(action, 'is_action_layered', False):
        slot = getattr(ad, 'action_slot', None)
        if slot is None:
            raise ValueError('Shape-key Action has no assigned Blender slot')
        curves = []
        for layer in action.layers:
            for strip in layer.strips:
                if strip.type != 'KEYFRAME':
                    continue
                bag = strip.channelbag(slot)
                if bag:
                    curves.extend(bag.fcurves)
        return action, tuple(curves)
    return action, tuple(action.fcurves)


def _curve(keys, path):
    action, curves = _curves(keys)
    matches = [fc for fc in curves
               if fc.data_path == path and fc.array_index == 0]
    if len(matches) > 1:
        raise ValueError('Shape-key Action has ambiguous duplicate value curves')
    return action, matches[0] if matches else None


def _point(fc, frame):
    matches = [point for point in fc.keyframe_points
               if abs(float(point.co.x) - frame) < _EPS]
    if len(matches) > 1:
        raise ValueError('Several native keys occupy the requested frame')
    return matches[0] if matches else None


def _rest_signature(fc, frame):
    """Detect outside edits to other points on this one native FCurve."""
    return tuple((
        round(float(p.co.x), 6), round(float(p.co.y), 6),
        str(p.interpolation), str(p.handle_left_type),
        str(p.handle_right_type),
        round(float(p.handle_left.x), 6),
        round(float(p.handle_left.y), 6),
        round(float(p.handle_right.x), 6),
        round(float(p.handle_right.y), 6))
        for p in fc.keyframe_points
        if abs(float(p.co.x) - frame) >= _EPS)


def _metadata(point):
    return (str(point.interpolation), str(point.easing),
            str(point.type), str(point.handle_left_type),
            str(point.handle_right_type))


def _same(value, expected):
    return abs(float(value) - float(expected)) < 1e-5


def _state(context, obj, keys, block, frame, value, prior, action, curve):
    return {
        'scene': context.scene.name,
        'scene_ptr': context.scene.as_pointer(),
        'layer': context.view_layer.name,
        'obj_name': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh_name': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'keys_ptr': keys.as_pointer(),
        'layout': tuple((b.name, b.as_pointer()) for b in keys.key_blocks),
        'key_name': block.name, 'key_ptr': block.as_pointer(),
        'path': block.path_from_id('value'),
        'frame': frame, 'value': float(value), 'prior': float(prior),
        'action_ptr': action.as_pointer(), 'curve_ptr': curve.as_pointer(),
        'point_meta': _metadata(_point(curve, frame)),
        'present': True,
        'rest_present': _rest_signature(curve, frame),
        'rest_missing': None,
    }


def _guard(context, state):
    obj, keys, block, frame = _target(context)
    if (state['scene'] != context.scene.name or
            state['scene_ptr'] != context.scene.as_pointer() or
            state['layer'] != context.view_layer.name or
            state['obj_name'] != obj.name or
            state['obj_ptr'] != obj.as_pointer() or
            state['mesh_name'] != obj.data.name or
            state['mesh_ptr'] != obj.data.as_pointer() or
            state['keys_ptr'] != keys.as_pointer() or
            state['layout'] != tuple((key.name, key.as_pointer())
                                     for key in keys.key_blocks) or
            state['key_name'] != block.name or
            state['key_ptr'] != block.as_pointer() or
            state['path'] != block.path_from_id('value') or
            state['frame'] != frame):
        raise ValueError('Shape key, frame or scene changed outside XR history')
    action, fc = _curve(keys, state['path'])
    if (action is None or fc is None or
            action.as_pointer() != state['action_ptr'] or
            fc.as_pointer() != state['curve_ptr']):
        raise ValueError('Native Blender Action or FCurve was replaced')
    expected = (state['rest_present'] if state['present']
                else state['rest_missing'])
    if expected is not None and _rest_signature(fc, frame) != expected:
        raise ValueError('Other native keyframes changed outside XR history')
    point = _point(fc, frame)
    if state['present']:
        if (point is None or not _same(point.co.y, state['value']) or
                _metadata(point) != state['point_meta']):
            raise ValueError('Inserted XR keyframe was edited outside XR')
    elif point is not None:
        raise ValueError('Another keyframe now occupies the saved XR frame')
    return obj, keys, block, fc, point


def _set_point_meta(point, metadata):
    (point.interpolation, point.easing, point.type,
     point.handle_left_type, point.handle_right_type) = metadata


def _toggle(context, state, backwards):
    if bool(state['present']) != bool(backwards):
        raise ValueError('XR keyframe history is out of sequence')
    _obj, _keys, block, fc, point = _guard(context, state)
    frame = state['frame']
    if backwards:
        old_meta = _metadata(point)
        fc.keyframe_points.remove(point)
        try:
            fc.update()
            # The native Action owns the evaluated value at this frame.
            context.scene.frame_set(frame)
            if len(fc.keyframe_points) == 0:
                block.value = state['prior']
            context.view_layer.update()
        except Exception:
            # Do not strand an un-undoable key deletion if Blender's
            # evaluation/depsgraph fails after editing the FCurve.
            try:
                if _point(fc, frame) is None:
                    restored = fc.keyframe_points.insert(
                        frame, state['value'], options=set())
                    _set_point_meta(restored, old_meta)
                    fc.update()
                context.scene.frame_set(frame)
            except Exception:
                pass
            raise
        state['rest_missing'] = _rest_signature(fc, frame)
        state['present'] = False
        state['point_meta'] = old_meta
    else:
        created = fc.keyframe_points.insert(
            frame, state['value'], options=set())
        try:
            _set_point_meta(created, state['point_meta'])
            fc.update()
            context.scene.frame_set(frame)
            context.view_layer.update()
        except Exception:
            try:
                if _point(fc, frame) == created:
                    fc.keyframe_points.remove(created)
                    fc.update()
                    context.scene.frame_set(frame)
            except Exception:
                pass
            raise
        state['rest_present'] = _rest_signature(fc, frame)
        state['present'] = True


def _insert(context, action_name, history=None):
    if action_name not in _VALUES and action_name != _CURRENT:
        raise ValueError('Choose a current-value or preset shape-key frame')
    obj, keys, block, frame = _target(context)
    path = block.path_from_id('value')
    action, fc = _curve(keys, path)
    if fc is not None and _point(fc, frame) is not None:
        raise ValueError('Native keyframe already exists at this frame; no overwrite')
    old_value = float(block.value)
    desired = old_value if action_name == _CURRENT else _VALUES[action_name]
    desired = max(float(block.slider_min), min(float(block.slider_max), desired))
    if not math.isfinite(desired):
        raise ValueError('Keyframe value must be finite')
    block.value = desired
    inserted = False
    try:
        inserted = bool(block.keyframe_insert(data_path='value', frame=frame))
        if not inserted:
            raise ValueError('Blender did not insert the native shape keyframe')
        action, fc = _curve(keys, path)
        if action is None or fc is None:
            raise ValueError('Blender created no accessible native FCurve')
        point = _point(fc, frame)
        if point is None or not _same(point.co.y, desired):
            raise ValueError('Blender keyframe value differs from the requested value')
        state = _state(context, obj, keys, block, frame,
                       desired, old_value, action, fc)
        if history is not None:
            history.push((_TAG, state))
        context.view_layer.update()
        return block.name, frame, desired
    except Exception:
        # Remove only an insertion that still matches our intended value.
        # Never overwrite another editor's newly created native keyframe.
        if inserted:
            try:
                action, fc = _curve(keys, path)
                point = _point(fc, frame) if fc else None
                if point and _same(point.co.y, desired):
                    fc.keyframe_points.remove(point)
                    fc.update()
            except (ValueError, RuntimeError, ReferenceError):
                pass
        if _same(block.value, desired):
            block.value = old_value
        raise


def _inspect(context):
    _obj, keys, block, frame = _target(context)
    _action, fc = _curve(keys, block.path_from_id('value'))
    point = _point(fc, frame) if fc is not None else None
    if point is None:
        return block.name, frame, 'UNKEYED'
    return block.name, frame, 'KEYED {:.3f}'.format(point.co.y)


class BXR_OT_shape_keyframe(bpy.types.Operator):
    bl_idname = 'blender_xr.shape_keyframe'
    bl_label = 'Insert Native Shape Keyframe'
    bl_description = 'Insert a new native Blender shape-key value keyframe at the current frame'
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(items=(
        (_CURRENT, 'Key Current', 'Key the currently evaluated shape-key value'),
        ('XR_SHAPE_KEY_0', 'Key Zero', 'Insert a value of zero at the current frame'),
        ('XR_SHAPE_KEY_HALF', 'Key Half', 'Insert a value of 0.5 at the current frame'),
        ('XR_SHAPE_KEY_1', 'Key One', 'Insert a value of one at the current frame'),
    ), default=_CURRENT)

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and obj.mode == 'OBJECT'
                    and obj.data.shape_keys and
                    len(obj.data.shape_keys.key_blocks) > 1)

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Shape Keyframes wrist menu during VR')
            return {'CANCELLED'}
        try:
            name, frame, value = _insert(context, self.action)
        except (RuntimeError, ValueError, ReferenceError, TypeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, '{} / FRAME {} / {:.3f}'.format(name, frame, value))
        return {'FINISHED'}


def _history():
    if getattr(mesh.History, '_xr_shape_value_keyframe_090', False):
        return
    old_step, old_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == _TAG:
            return
        return old_release(entry)

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] != _TAG:
            return old_step(self, backwards)
        entry = source[-1]
        dest.append(entry)
        try:
            _toggle(bpy.context, entry[1], backwards)
        except Exception:
            dest.pop()
            raise
        source.pop()
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_shape_value_keyframe_090 = True


def install_pages():
    page = tuple(menus.PAGES[_PARENT])
    if not page or page[-1][1] != 'BACK':
        raise ValueError('Native Shape Manage page was modified')
    if not any(action == 'XR_SHAPE_KEYFRAMES_MENU' for _l, action in page):
        page = page[:-1] + (('KEYFRAMES', 'XR_SHAPE_KEYFRAMES_MENU'),
                           page[-1])
    if len(page) > 12:
        raise ValueError('Shape Manage has no room for native keyframe tools')
    menus.PAGES[_PARENT] = page
    menus.PAGES[_PAGE] = (
        ('KEY CURRENT', _CURRENT),
        ('KEY 0', 'XR_SHAPE_KEY_0'),
        ('KEY 0.5', 'XR_SHAPE_KEY_HALF'),
        ('KEY 1', 'XR_SHAPE_KEY_1'),
        ('CHECK', _INFO),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'SHAPE KEY FRAMES'
    v065.TOOLTIPS.update({
        'XR_SHAPE_KEYFRAMES_MENU': ('Native Shape Keyframes',
            'Insert shape value animation directly into Blender native FCurves'),
        _CURRENT: ('Key Current Shape Value',
            'Insert a new native keyframe with the current evaluated value'),
        'XR_SHAPE_KEY_0': ('Key Value 0', 'Insert a zero-value shape keyframe'),
        'XR_SHAPE_KEY_HALF': ('Key Value 0.5', 'Insert a half-value shape keyframe'),
        'XR_SHAPE_KEY_1': ('Key Value 1', 'Insert a full-value shape keyframe'),
        _INFO: ('Check Keyframe', 'Read whether this shape value already has a key at the current frame'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_native_shape_keyframe_090', False):
        return
    _history()
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if (action == 'XR_SHAPE_KEYFRAMES_MENU' and
                page == _PARENT):
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release gestures before shape keyframing')
            _target(context)
            self.menu.page = _PAGE
            self.status = 'NATIVE SHAPE KEYFRAMES / CURRENT OR PRESET'
            return
        if page == _PAGE:
            if action == 'BACK':
                self.menu.page = _PARENT
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before changing animation')
            if action == _INFO:
                name, frame, result = _inspect(context)
                self.status = '{} / FRAME {} / {}'.format(
                    name.upper()[:25], frame, result)
                return
            if action == _CURRENT or action in _VALUES:
                history = getattr(self, 'history', None)
                if history is None:
                    raise ValueError('XR history required before adding keyframes')
                name, frame, value = _insert(context, action, history=history)
                self.status = '{} / FRAME {} / KEYED {:.3f} / UNDO READY'.format(
                    name.upper()[:24], frame, value)
                return
            raise ValueError('Unsupported Shape Keyframes action')
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_native_shape_keyframe_090 = True


CLASSES = (BXR_OT_shape_keyframe,)
