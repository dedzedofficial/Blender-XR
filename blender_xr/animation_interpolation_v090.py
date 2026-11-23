# SPDX-License-Identifier: GPL-3.0-or-later
"""Edit native Blender FCurve point interpolation using XR menus.

One exact current-frame keyframe at a time. No new keys, Action datablocks
or curves are created; this changes only Keyframe.interpolation. The same
guarded session-local Undo/Redo works for object channels, pose bones and
relative shape-key value curves on both legacy and slotted Blender Actions.
"""
import bpy

from . import (input_ownership_v080, menus, mesh,
               shape_keyframes_v090, transform_keyframes_v090, v065)

_SELECT_PAGE = 'XR_INTERP_PICK_090'
_STYLE_PAGE = 'XR_INTERP_STYLE_090'
_TAG = 'XR_FCURVE_INTERP_090'
_STYLES = {
    'XR_INTERP_CONSTANT': 'CONSTANT',
    'XR_INTERP_LINEAR': 'LINEAR',
    'XR_INTERP_BEZIER': 'BEZIER',
}
_SHAPE_MENU = 'XR_INTERP_SHAPE_MENU'
_PICK_MENU = 'XR_INTERP_SELECT_MENU'
_PICK_CHANNEL = {
    key.replace('XR_ANIM_KEY_', 'XR_INTERP_PICK_'): key
    for key in transform_keyframes_v090._CHANNELS
}


def _resolve(context, source, channel):
    """Resolve the current native FCurve; refuse missing/multiple targets."""
    if source == 'SHAPE':
        obj, keys, block, frame = shape_keyframes_v090._target(context)
        owner = keys
        data_path, axis = block.path_from_id('value'), 0
        identity = (obj.as_pointer(), obj.data.as_pointer(),
                    keys.as_pointer(), block.as_pointer(), block.name)
    else:
        if channel not in transform_keyframes_v090._CHANNELS:
            raise ValueError('Select a native transform FCurve channel')
        prop, axis = transform_keyframes_v090._CHANNELS[channel]
        pose = source == 'POSE'
        obj, block, data_path, frame, _value = transform_keyframes_v090._target(
            context, pose, prop, axis)
        owner = obj
        identity = (obj.as_pointer(),
                    obj.data.as_pointer() if obj.data else None,
                    block.as_pointer() if pose else None,
                    block.name if pose else None, obj.name)
    action, fc = shape_keyframes_v090._curve(owner, data_path) if (
        source == 'SHAPE') else transform_keyframes_v090._curve(owner, data_path, axis)
    point = shape_keyframes_v090._point(fc, frame) if fc is not None else None
    if action is None or fc is None or point is None:
        raise ValueError('No native keyframe exists at the current frame')
    if action.library or action.override_library or action.users > 1:
        raise ValueError('Native FCurve requires a local single-user Action')
    return (obj, owner, block, identity, action, fc, point,
            data_path, axis, frame)


def _fingerprint(fc, frame):
    return transform_keyframes_v090._other_points(fc, frame)


def _point_guard(point):
    return (str(point.easing), str(point.type),
            str(point.handle_left_type), str(point.handle_right_type))


def _capture(context, source, channel):
    (obj, _owner, _block, identity, action, fc, point,
     path, axis, frame) = _resolve(context, source, channel)
    return {
        'source': source, 'channel': channel,
        'scene': context.scene.name, 'scene_ptr': context.scene.as_pointer(),
        'layer': context.view_layer.name, 'identity': identity,
        'action': action.as_pointer(), 'curve': fc.as_pointer(),
        'path': path, 'axis': axis, 'frame': frame,
        'point_guard': _point_guard(point),
        'other': _fingerprint(fc, frame),
        'before': str(point.interpolation),
        'after': None,
    }


def _guard(context, state, expected):
    (obj, owner, block, identity, action, curve, point,
     path, axis, frame) = _resolve(context, state['source'], state['channel'])
    if (context.scene.name != state['scene'] or
            context.scene.as_pointer() != state['scene_ptr'] or
            context.view_layer.name != state['layer'] or
            identity != state['identity'] or
            action.as_pointer() != state['action'] or
            curve.as_pointer() != state['curve'] or
            path != state['path'] or axis != state['axis'] or
            frame != state['frame'] or
            _point_guard(point) != state['point_guard'] or
            _fingerprint(curve, frame) != state['other'] or
            str(point.interpolation) != expected):
        raise ValueError('Target keyframe or its Action changed outside XR')
    return point, curve


def _set(context, state, expected, desired):
    point, curve = _guard(context, state, expected)
    point.interpolation = desired
    try:
        curve.update()
        context.scene.frame_set(state['frame'], subframe=0)
        context.view_layer.update()
    except Exception:
        # Roll back only our own property when it still contains the target
        # style, preserving later external edits to the native Action.
        if str(point.interpolation) == desired:
            point.interpolation = expected
            curve.update()
        raise


def _apply(context, state, style, history):
    if style not in _STYLES.values():
        raise ValueError('Select a supported Blender keyframe interpolation')
    if history is None:
        raise ValueError('XR history is required for native interpolation edits')
    current = _capture(context, state['source'], state['channel'])
    if any(current[key] != state[key] for key in (
            'source', 'channel', 'scene', 'scene_ptr', 'layer',
            'identity', 'action', 'curve', 'path', 'axis', 'frame')):
        raise ValueError('Selected keyframe changed; choose a channel again')
    before = current['before']
    if before == style:
        return False
    current['after'] = style
    _set(context, current, before, style)
    try:
        history.push((_TAG, current))
    except Exception:
        _set(context, current, style, before)
        raise
    return True


def _history():
    if getattr(mesh.History, '_xr_fcurve_interp_090', False):
        return
    old_step, old_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == _TAG:
            return
        return old_release(entry)

    def step(self, backwards=True):
        src, dst = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not src or src[-1][0] != _TAG:
            return old_step(self, backwards)
        entry = src[-1]
        state = entry[1]
        before, after = (state['after'], state['before']) if backwards else (
            state['before'], state['after'])
        # Reserve the destination entry before a native FCurve edit; if the
        # edit refuses an external conflict the history stacks stay intact.
        dst.append(entry)
        try:
            _set(bpy.context, state, before, after)
        except Exception:
            dst.pop()
            raise
        src.pop()
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_fcurve_interp_090 = True


def install_pages():
    for parent in (transform_keyframes_v090._OBJECT_PAGE,
                   transform_keyframes_v090._POSE_PAGE):
        buttons = tuple(menus.PAGES[parent])
        if not buttons or buttons[-1][1] != 'BACK' or len(buttons) > 11:
            raise ValueError('Object/Pose animation page lacks an interpolation slot')
        menus.PAGES[parent] = buttons[:-1] + (
            ('EDIT CURVE', _PICK_MENU), buttons[-1])
    shape = tuple(menus.PAGES[shape_keyframes_v090._PAGE])
    if not shape or shape[-1][1] != 'BACK' or len(shape) >= 12:
        raise ValueError('Shape Keyframes page has no interpolation slot')
    menus.PAGES[shape_keyframes_v090._PAGE] = shape[:-1] + (
        ('INTERPOLATE', _SHAPE_MENU), shape[-1])
    menus.PAGES[_SELECT_PAGE] = tuple((
        label.replace('XR_ANIM_KEY_', '').replace('_', ' '),
        'XR_INTERP_PICK_' + label.removeprefix('XR_ANIM_KEY_'))
        for label in transform_keyframes_v090._CHANNELS
    ) + (('BACK', 'BACK'),)
    menus.TITLES[_SELECT_PAGE] = 'PICK ANIMATED CHANNEL'
    menus.PAGES[_STYLE_PAGE] = (
        ('CONSTANT', 'XR_INTERP_CONSTANT'),
        ('LINEAR', 'XR_INTERP_LINEAR'),
        ('BEZIER', 'XR_INTERP_BEZIER'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_STYLE_PAGE] = 'KEYFRAME INTERPOLATION'
    v065.TOOLTIPS.update({
        _PICK_MENU: ('Edit Object/Bone Keyframe Interpolation',
            'Choose one already-keyed transform component before changing its curve'),
        _SHAPE_MENU: ('Edit Shape Keyframe Interpolation',
            'Choose a native interpolation style for the active shape key at this frame'),
        'XR_INTERP_CONSTANT': ('Constant Keyframe',
            'Use stepped interpolation after the selected native key'),
        'XR_INTERP_LINEAR': ('Linear Keyframe',
            'Use linear interpolation after the selected native key'),
        'XR_INTERP_BEZIER': ('Bezier Keyframe',
            'Use native smooth Bezier interpolation after the selected key'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_fcurve_interp_090_patched', False):
        return
    _history()
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if (action == _PICK_MENU and page in {
                transform_keyframes_v090._OBJECT_PAGE,
                transform_keyframes_v090._POSE_PAGE}):
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gestures before editing keyframes')
            self._xr_interp_source = ('POSE' if page ==
                                      transform_keyframes_v090._POSE_PAGE else 'OBJECT')
            self._xr_interp_target = None
            self.menu.page = _SELECT_PAGE
            self.status = 'INTERPOLATE / CHOOSE AN ANIMATED XYZ CHANNEL'
            return
        if action == _SHAPE_MENU and page == shape_keyframes_v090._PAGE:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gestures before editing shape curves')
            self._xr_interp_source = 'SHAPE'
            self._xr_interp_target = _capture(context, 'SHAPE', None)
            self.menu.page = _STYLE_PAGE
            self.status = 'SHAPE CURVE / CHOOSE INTERPOLATION'
            return
        if page == _SELECT_PAGE:
            if action == 'BACK':
                self.menu.page = (transform_keyframes_v090._POSE_PAGE
                                  if getattr(self, '_xr_interp_source', '') == 'POSE'
                                  else transform_keyframes_v090._OBJECT_PAGE)
                return
            if action not in _PICK_CHANNEL:
                raise ValueError('Choose a transform FCurve channel')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before choosing a curve')
            source = getattr(self, '_xr_interp_source', 'OBJECT')
            self._xr_interp_target = _capture(
                context, source, _PICK_CHANNEL[action])
            self.menu.page = _STYLE_PAGE
            self.status = 'NATIVE CURVE / CHOOSE CONSTANT, LINEAR, BEZIER'
            return
        if page == _STYLE_PAGE:
            if action == 'BACK':
                self.menu.page = (shape_keyframes_v090._PAGE
                                  if getattr(self, '_xr_interp_source', '') == 'SHAPE'
                                  else _SELECT_PAGE)
                self._xr_interp_target = None
                return
            if action not in _STYLES:
                raise ValueError('Choose Constant, Linear or Bezier')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR controllers before editing interpolation')
            target = getattr(self, '_xr_interp_target', None)
            if target is None:
                raise ValueError('Choose a current-frame keyframe first')
            changed = _apply(context, target, _STYLES[action],
                             getattr(self, 'history', None))
            self.status = ('FCURVE / {} / {}'.format(
                _STYLES[action], 'XR UNDO READY' if changed else 'UNCHANGED'))
            # Refresh the chosen keyframe snapshot only after a deliberate
            # edit; subsequent style changes can use the same wrist page.
            self._xr_interp_target = _capture(context, target['source'],
                                              target['channel'])
            return
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_fcurve_interp_090_patched = True
