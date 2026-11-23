# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicitly confirmed deletion of one native Blender FCurve keyframe.

The selected current-frame object/pose/shape key must be selected through
the interpolation editor first. A separate confirmation then removes exactly
that FCurve point; guarded XR history can reconstruct its native metadata.
Other Actions, FCurves, keyframes and scene data are left untouched.
"""
import math

import bpy

from . import (animation_interpolation_v090 as interp, input_ownership_v080,
               menus, mesh, shape_keyframes_v090, transform_keyframes_v090,
               v065)

_PAGE = 'XR_KEY_DELETE_CONFIRM_090'
_OPEN = 'XR_KEY_DELETE_MENU'
_CONFIRM = 'XR_KEY_DELETE_CONFIRM'
_CANCEL = 'XR_KEY_DELETE_CANCEL'
_TAG = 'XR_NATIVE_KEY_DELETE_090'


def _lookup(context, captured):
    """Read a native FCurve even when the selected frame has no keyframe."""
    src = captured['source']
    channel = captured['channel']
    if src == 'SHAPE':
        obj, keys, block, frame = shape_keyframes_v090._target(context)
        owner = keys
        path, axis = block.path_from_id('value'), 0
        identity = (obj.as_pointer(), obj.data.as_pointer(),
                    keys.as_pointer(), block.as_pointer(), block.name)
        action, curve = shape_keyframes_v090._curve(owner, path)
    else:
        if channel not in transform_keyframes_v090._CHANNELS:
            raise ValueError('Unknown selected transform FCurve')
        prop, axis = transform_keyframes_v090._CHANNELS[channel]
        pose = src == 'POSE'
        obj, block, path, frame, _value = transform_keyframes_v090._target(
            context, pose, prop, axis)
        identity = (obj.as_pointer(),
                    obj.data.as_pointer() if obj.data else None,
                    block.as_pointer() if pose else None,
                    block.name if pose else None, obj.name)
        action, curve = transform_keyframes_v090._curve(obj, path, axis)
    if (context.scene.name != captured['scene'] or
            context.scene.as_pointer() != captured['scene_ptr'] or
            context.view_layer.name != captured['layer'] or
            identity != captured['identity'] or
            path != captured['path'] or axis != captured['axis'] or
            frame != captured['frame'] or action is None or curve is None or
            action.as_pointer() != captured['action'] or
            curve.as_pointer() != captured['curve'] or
            interp._fingerprint(curve, frame) != captured['other']):
        raise ValueError('Native curve/frame changed since keyframe selection')
    point = shape_keyframes_v090._point(curve, frame)
    return curve, point


def _properties(point):
    return {
        'value': float(point.co.y),
        'interp': str(point.interpolation),
        'easing': str(point.easing),
        'type': str(point.type),
        'left_type': str(point.handle_left_type),
        'right_type': str(point.handle_right_type),
        'left': tuple(float(v) for v in point.handle_left),
        'right': tuple(float(v) for v in point.handle_right),
    }


def _matches(point, saved):
    if point is None:
        return False
    now = _properties(point)
    if any(now[key] != saved[key] for key in (
            'interp', 'easing', 'type', 'left_type', 'right_type')):
        return False
    return math.isclose(now['value'], saved['value'], abs_tol=1e-5)


def _recreate(curve, frame, saved):
    point = curve.keyframe_points.insert(frame, saved['value'], options=set())
    point.interpolation = saved['interp']
    point.easing = saved['easing']
    point.type = saved['type']
    point.handle_left_type = saved['left_type']
    point.handle_right_type = saved['right_type']
    curve.update()
    # Explicitly preserve creator-positioned manual handles; Blender owns
    # AUTO/VECTOR handles, which are recalculated from neighbouring points.
    if saved['left_type'] in {'FREE', 'ALIGNED'}:
        point.handle_left = saved['left']
    if saved['right_type'] in {'FREE', 'ALIGNED'}:
        point.handle_right = saved['right']
    curve.update()
    return point


def _perform(context, state, restore):
    captured = state['captured']
    curve, point = _lookup(context, captured)
    saved = state['point']
    if restore:
        if point is not None or state['present']:
            raise ValueError('Keyframe deletion Undo is no longer applicable')
        created = None
        try:
            created = _recreate(curve, captured['frame'], saved)
            context.scene.frame_set(captured['frame'], subframe=0.0)
            context.view_layer.update()
        except Exception:
            if created is not None:
                try:
                    if shape_keyframes_v090._point(curve, captured['frame']) == created:
                        curve.keyframe_points.remove(created)
                        curve.update()
                except Exception:
                    pass
            raise
        state['present'] = True
    else:
        if not state['present'] or not _matches(point, saved):
            raise ValueError('Keyframe changed since the requested XR deletion')
        curve.keyframe_points.remove(point)
        try:
            curve.update()
            context.scene.frame_set(captured['frame'], subframe=0.0)
            context.view_layer.update()
        except Exception:
            try:
                if shape_keyframes_v090._point(curve, captured['frame']) is None:
                    _recreate(curve, captured['frame'], saved)
            except Exception:
                pass
            raise
        state['present'] = False


def _capture(context, chosen):
    # Reject any edits made after the interpolator first selected the key,
    # including changes to that point or any of its neighbour values.
    current = interp._capture(context, chosen['source'], chosen['channel'])
    if any(current[key] != chosen[key] for key in (
            'source', 'channel', 'scene', 'scene_ptr', 'layer', 'identity',
            'action', 'curve', 'path', 'axis', 'frame',
            'before', 'point_guard', 'other')):
        raise ValueError('Choose the current-frame keyframe again before deletion')
    _curve, point = _lookup(context, current)
    return {'captured': current, 'point': _properties(point), 'present': True}


def _delete(context, state, history):
    if history is None:
        raise ValueError('XR history is required before removing native keyframes')
    _perform(context, state, restore=False)
    try:
        history.push((_TAG, state))
    except Exception:
        _perform(context, state, restore=True)
        raise


def _history():
    if getattr(mesh.History, '_xr_confirmed_key_delete_090', False):
        return
    old_step, old_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == _TAG:
            return
        return old_release(entry)

    def step(self, backwards=True):
        src, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not src or src[-1][0] != _TAG:
            return old_step(self, backwards)
        entry = src[-1]
        dest.append(entry)
        try:
            _perform(bpy.context, entry[1], restore=backwards)
        except Exception:
            dest.pop()
            raise
        src.pop()
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_confirmed_key_delete_090 = True


def install_pages():
    buttons = tuple(menus.PAGES[interp._STYLE_PAGE])
    if not buttons or buttons[-1][1] != 'BACK' or len(buttons) >= 12:
        raise ValueError('Native interpolation menu has no deletion slot')
    menus.PAGES[interp._STYLE_PAGE] = buttons[:-1] + (
        ('REMOVE KEY', _OPEN), buttons[-1])
    menus.PAGES[_PAGE] = (
        ('DELETE NOW', _CONFIRM),
        ('KEEP KEY', _CANCEL),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'DELETE NATIVE KEY?'
    v065.TOOLTIPS.update({
        _OPEN: ('Review Native Keyframe Deletion',
            'Inspect an exact FCurve key at this frame before any removal'),
        _CONFIRM: ('Delete the Selected Native Keyframe',
            'Remove only the selected object/bone/shape key; XR Undo restores it'),
        _CANCEL: ('Keep Existing Keyframe',
            'Cancel without editing Blender animation data'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_confirmed_key_delete_090_patched', False):
        return
    _history()
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == interp._STYLE_PAGE and action == _OPEN:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR controllers before changing keyframes')
            choice = getattr(self, '_xr_interp_target', None)
            if choice is None:
                raise ValueError('Choose an existing native FCurve key first')
            self._xr_key_delete_pending = _capture(context, choice)
            self.menu.page = _PAGE
            self.status = 'DELETE KEY? / CONFIRM OR KEEP / NO CHANGE YET'
            return
        if page == _PAGE:
            if action in {_CANCEL, 'BACK'}:
                self._xr_key_delete_pending = None
                self.menu.page = interp._STYLE_PAGE
                self.status = 'KEYFRAME KEPT / NO BLENDER DATA CHANGED'
                return
            if action != _CONFIRM:
                raise ValueError('Confirm or cancel native keyframe removal')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controller gesture before deleting a key')
            pending = getattr(self, '_xr_key_delete_pending', None)
            if pending is None:
                raise ValueError('No confirmed native keyframe target')
            _delete(context, pending, getattr(self, 'history', None))
            self._xr_key_delete_pending = None
            self._xr_interp_target = None
            self.menu.page = (shape_keyframes_v090._PAGE
                              if pending['captured']['source'] == 'SHAPE' else
                              interp._SELECT_PAGE)
            self.status = ('NATIVE KEY DELETED / FRAME {} / XR UNDO READY'.format(
                pending['captured']['frame']))
            return
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_confirmed_key_delete_090_patched = True
