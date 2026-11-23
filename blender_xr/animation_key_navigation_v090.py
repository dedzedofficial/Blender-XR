# SPDX-License-Identifier: GPL-3.0-or-later
"""Navigate native Blender animation keys with guarded XR scene-frame history.

Read existing FCurves only; never insert, delete, offset or duplicate
Action points. The timeline move delegates to timeline_v090.jump_frame so
Undo/Redo uses the exact existing XR_SCENE_FRAME_090 history. Whole-frame
keys in the scene playback range are supported.
"""
import math

from . import (animation_interpolation_v090, input_ownership_v080,
               menus, shape_keyframes_v090, timeline_v090,
               transform_keyframes_v090, v065)

_PREVIOUS = 'XR_ANIM_KEY_PREVIOUS'
_NEXT = 'XR_ANIM_KEY_NEXT'
_SHAPE_PREVIOUS = 'XR_SHAPE_KEY_PREVIOUS'
_SHAPE_NEXT = 'XR_SHAPE_KEY_NEXT'
_MAX_POINTS = 250000
_FRAME_EPS = 1e-4


def _scene_keys(context, curves):
    """Collect the whole-frame keyframes visible in the current playback.

    The bounded scan is read-only, deterministic and does not touch native
    Blender Actions or mesh data. Never round a fractional key to an
    unintended target frame.
    """
    start, end = timeline_v090._frame_limits(context.scene)
    frames = set()
    count = 0
    for curve in curves:
        for point in curve.keyframe_points:
            count += 1
            if count > _MAX_POINTS:
                raise ValueError('Too many native FCurve keys for XR navigation')
            raw = float(point.co.x)
            if not math.isfinite(raw):
                raise ValueError('An animation FCurve contains an invalid frame')
            whole = round(raw)
            if abs(raw - whole) <= _FRAME_EPS and start <= whole <= end:
                frames.add(int(whole))
    return tuple(sorted(frames))


def _transform_curves(context, pose):
    obj, bone = transform_keyframes_v090._owner(context, pose)
    _action, curves = shape_keyframes_v090._curves(obj)
    if not curves:
        raise ValueError('The selected native object has no keyed Action curves')
    if pose:
        # Blender owns the path escaping for bone names containing quotes.
        prefix = bone.path_from_id('location').rsplit('.', 1)[0] + '.'
        accepted = {prefix + prop for prop in (
            'location', 'rotation_euler', 'rotation_quaternion',
            'rotation_axis_angle', 'scale')}
    else:
        accepted = {
            'location', 'rotation_euler', 'rotation_quaternion',
            'rotation_axis_angle', 'scale',
            'delta_location', 'delta_rotation_euler', 'delta_scale',
        }
    return bone.name, tuple(
        curve for curve in curves if curve.data_path in accepted)


def _shape_curves(context):
    _obj, keys, block, _frame = shape_keyframes_v090._target(context)
    path = block.path_from_id('value')
    _action, curve = shape_keyframes_v090._curve(keys, path)
    return block.name, (curve,) if curve is not None else ()


def _move(context, history, source, forwards):
    if history is None:
        raise ValueError('XR Undo history is required for animation navigation')
    if source == 'SHAPE':
        name, curves = _shape_curves(context)
    elif source in {'OBJECT', 'POSE'}:
        name, curves = _transform_curves(context, source == 'POSE')
    else:
        raise ValueError('Choose an object, pose bone or shape key first')
    if not curves:
        raise ValueError('No native animation keys exist for the selected target')

    candidates = _scene_keys(context, curves)
    now = (float(context.scene.frame_current) +
           float(context.scene.frame_subframe))
    if not math.isfinite(now):
        raise ValueError('Current native Blender frame is invalid')
    remaining = tuple(frame for frame in candidates
                      if (frame > now + _FRAME_EPS if forwards
                          else frame < now - _FRAME_EPS))
    if not remaining:
        raise ValueError('No more keys in this direction within playback range')
    destination = remaining[0] if forwards else remaining[-1]
    frame, changed = timeline_v090.jump_frame(
        context, destination, history=history)
    return name, frame[0], len(candidates), changed


def install_pages():
    shape_page = shape_keyframes_v090._PAGE
    interp_page = animation_interpolation_v090._SELECT_PAGE
    shape_buttons = tuple(menus.PAGES[shape_page])
    interp_buttons = tuple(menus.PAGES[interp_page])
    if not shape_buttons or shape_buttons[-1][1] != 'BACK':
        raise ValueError('Shape keyframe menu is unavailable')
    if not interp_buttons or interp_buttons[-1][1] != 'BACK':
        raise ValueError('Native transform curve picker is unavailable')
    for buttons, title in ((shape_buttons, 'Shape Keyframe'),
                           (interp_buttons, 'Transform Keyframe')):
        if len(buttons) > 10:
            raise ValueError(title + ' page lacks two navigation slots')
    if any(a in {_PREVIOUS, _NEXT, _SHAPE_PREVIOUS, _SHAPE_NEXT}
           for _label, a in shape_buttons + interp_buttons):
        raise ValueError('Native keyframe navigation is already installed')
    menus.PAGES[shape_page] = shape_buttons[:-1] + (
        ('PREV KEY', _SHAPE_PREVIOUS),
        ('NEXT KEY', _SHAPE_NEXT),
        shape_buttons[-1],
    )
    menus.PAGES[interp_page] = interp_buttons[:-1] + (
        ('PREV KEY', _PREVIOUS),
        ('NEXT KEY', _NEXT),
        interp_buttons[-1],
    )
    v065.TOOLTIPS.update({
        _PREVIOUS: ('Previous Object/Bone Key',
            'Jump to the previous existing whole-frame key on the active target'),
        _NEXT: ('Next Object/Bone Key',
            'Jump to the next existing whole-frame key on the active target'),
        _SHAPE_PREVIOUS: ('Previous Shape Keyframe',
            'Evaluate at the previous native keyframe on the selected shape'),
        _SHAPE_NEXT: ('Next Shape Keyframe',
            'Evaluate at the next native keyframe on the selected shape'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_animation_key_navigation_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        page = getattr(menu, 'page', None)
        shape = page == shape_keyframes_v090._PAGE
        selected = page == animation_interpolation_v090._SELECT_PAGE
        if ((shape and action in {_SHAPE_PREVIOUS, _SHAPE_NEXT}) or
                (selected and action in {_PREVIOUS, _NEXT})):
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gestures before navigating frames')
            source = ('SHAPE' if shape else
                      getattr(self, '_xr_interp_source', None))
            if selected and source not in {'OBJECT', 'POSE'}:
                raise ValueError('Open an Object or Pose Animation page first')
            forwards = action in {_NEXT, _SHAPE_NEXT}
            name, frame, total, changed = _move(
                context, getattr(self, 'history', None), source, forwards)
            # Picking a different native frame invalidates a stale FCurve
            # interpolation/delete approval. Re-select a current-frame key.
            self._xr_interp_target = None
            self._xr_key_delete_pending = None
            self.status = 'ANIM {} / FRAME {} / {} KEYS / {}'.format(
                name.upper()[:18], frame, total,
                'XR UNDO READY' if changed else 'UNCHANGED')
            return
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_animation_key_navigation_090_patched = True
