# SPDX-License-Identifier: GPL-3.0-or-later
"""Editable native Blender scene playback range from the XR wrist.

Frame range changes are direct Scene.frame_start/frame_end edits. No new
Action, FCurve, keyframe, track or XR timeline format is created. The usual
XR Undo/Redo history validates the exact scene, bounds and evaluation
frame before restoring a previous playback range.
"""
import bpy

from . import (input_ownership_v080, menus, mesh, runtime,
               timeline_v090, v065)

_PAGE = 'XR_TIME_RANGE_090'
_QUICK_PAGE = 'XR_TIME_JUMPS_090'
_TAG = 'XR_TIMELINE_RANGE_090'
_RANGE_MENU = 'XR_TIME_RANGE_MENU'
_QUICK_MENU = 'XR_TIME_QUICK_MENU'
_SET_START = 'XR_TIME_SET_START'
_SET_END = 'XR_TIME_SET_END'
_STEPS = {
    'XR_TIME_START_MINUS_10': (0, -10),
    'XR_TIME_START_PLUS_10': (0, 10),
    'XR_TIME_START_MINUS_1': (0, -1),
    'XR_TIME_START_PLUS_1': (0, 1),
    'XR_TIME_END_MINUS_10': (1, -10),
    'XR_TIME_END_PLUS_10': (1, 10),
    'XR_TIME_END_MINUS_1': (1, -1),
    'XR_TIME_END_PLUS_1': (1, 1),
}
_ACTIONS = frozenset(_STEPS) | {_SET_START, _SET_END}
_JUMPS = {'XR_TIME_FRAME_ZERO', 'XR_TIME_FRAME_24'}


def _scene(context):
    scene = timeline_v090._scene(context)
    window = getattr(context, 'window', None)
    if window is not None and window.screen.is_animation_playing:
        raise ValueError('Pause Blender playback before modifying its frame range')
    if getattr(scene, 'use_preview_range', False):
        raise ValueError('Disable Blender Preview Range before changing playback bounds')
    return scene


def _bounds(scene):
    return timeline_v090._frame_limits(scene)


def _clock(scene):
    return timeline_v090._time_state(scene)


def _request(context, action):
    scene = _scene(context)
    current = _bounds(scene)
    before = _clock(scene)
    desired = list(current)
    if action == _SET_START:
        if before[1] != 0.0:
            raise ValueError('Set a whole frame before marking playback start')
        desired[0] = before[0]
    elif action == _SET_END:
        if before[1] != 0.0:
            raise ValueError('Set a whole frame before marking playback end')
        desired[1] = before[0]
    elif action in _STEPS:
        index, step = _STEPS[action]
        desired[index] += step
    else:
        raise ValueError('Unknown Blender timeline range action')
    # The bounds are native Blender Scene properties. Refuse an invalid
    # interval before touching either RNA property, rather than relying
    # on Blender silently clamping an unrepresentable value.
    if desired[0] > desired[1]:
        raise ValueError('Playback start must be at or before playback end')
    name = 'frame_start' if current[0] != desired[0] else 'frame_end'
    prop = scene.bl_rna.properties.get(name)
    if prop is not None:
        proposed = desired[0] if name == 'frame_start' else desired[1]
        if proposed < prop.hard_min or proposed > prop.hard_max:
            raise ValueError('Playback bound is outside the Blender RNA range')
    return scene, current, tuple(desired), before


def _entry(context, scene, current, desired, clock):
    return (_TAG, scene.name, scene.as_pointer(), context.view_layer.name,
            current, desired, clock)


def _write(context, entry, backwards):
    _kind, name, ptr, layer, before, after, clock = entry
    scene = _scene(context)
    if (scene.name != name or scene.as_pointer() != ptr or
            context.view_layer.name != layer or
            _clock(scene) != clock):
        raise ValueError('Timeline scene or evaluated frame changed outside XR history')
    expected, desired = (after, before) if backwards else (before, after)
    if _bounds(scene) != expected:
        raise ValueError('Playback range changed outside XR timeline history')
    changing = tuple(index for index in (0, 1)
                     if expected[index] != desired[index])
    if len(changing) != 1:
        raise ValueError('Native range history must change one bound per entry')
    name = 'frame_start' if changing[0] == 0 else 'frame_end'
    setattr(scene, name, desired[changing[0]])
    try:
        if _bounds(scene) != desired:
            raise ValueError('Blender refused the requested exact playback range')
        context.view_layer.update()
    except Exception:
        # If Blender or a dependency-graph update fails, restore only the
        # bound this operation wrote, and never overwrite an external edit.
        if _bounds(scene) == desired:
            setattr(scene, name, expected[changing[0]])
        raise


def _apply(context, action, history=None):
    scene, before, after, clock = _request(context, action)
    if before == after:
        return before, False
    entry = _entry(context, scene, before, after, clock)
    _write(context, entry, backwards=False)
    try:
        if history is not None:
            history.push(entry)
    except Exception:
        _write(context, entry, backwards=True)
        raise
    return after, True


class BXR_OT_timeline_range(bpy.types.Operator):
    bl_idname = 'blender_xr.timeline_range'
    bl_label = 'Set Native Blender Scene Playback Range'
    bl_description = 'Mark the active Blender frame as playback start or end'
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(items=(
        (_SET_START, 'Start Here', 'Use current frame as Blender playback start'),
        (_SET_END, 'End Here', 'Use current frame as Blender playback end'),
    ), default=_SET_START)

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Timeline Range wrist submenu')
            return {'CANCELLED'}
        try:
            bounds, changed = _apply(context, self.action)
        except (ValueError, RuntimeError, ReferenceError, TypeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Blender playback {}..{}'.format(*bounds))
        return {'FINISHED'} if changed else {'CANCELLED'}


def _history():
    if getattr(mesh.History, '_xr_timeline_range_090_patched', False):
        return
    prior_step, prior_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == _TAG:
            return
        return prior_release(entry)

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] != _TAG:
            return prior_step(self, backwards)
        entry = source[-1]
        dest.append(entry)
        try:
            _write(bpy.context, entry, backwards=backwards)
        except Exception:
            dest.pop()
            raise
        source.pop()
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_timeline_range_090_patched = True


def install_pages():
    current = tuple(menus.PAGES[timeline_v090._PAGE])
    existing = {action for _label, action in current}
    if not current or current[-1][1] != 'BACK' or not _JUMPS.issubset(existing):
        raise ValueError('Native Timeline quick-frame buttons were changed')
    if _RANGE_MENU in existing or _QUICK_MENU in existing:
        raise ValueError('Native Timeline Range is already installed')
    retained = tuple((label, action) for label, action in current[:-1]
                     if action not in _JUMPS)
    menus.PAGES[timeline_v090._PAGE] = retained + (
        ('RANGE', _RANGE_MENU),
        ('FRAME JUMPS', _QUICK_MENU),
        current[-1],
    )
    if len(menus.PAGES[timeline_v090._PAGE]) > 12:
        raise ValueError('Native Timeline would overflow XR wrist capacity')
    menus.PAGES[_PAGE] = (
        ('SET START', _SET_START), ('SET END', _SET_END),
        ('START -10', 'XR_TIME_START_MINUS_10'),
        ('START +10', 'XR_TIME_START_PLUS_10'),
        ('END -10', 'XR_TIME_END_MINUS_10'),
        ('END +10', 'XR_TIME_END_PLUS_10'),
        ('START -1', 'XR_TIME_START_MINUS_1'),
        ('START +1', 'XR_TIME_START_PLUS_1'),
        ('END -1', 'XR_TIME_END_MINUS_1'),
        ('END +1', 'XR_TIME_END_PLUS_1'),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_QUICK_PAGE] = (
        ('FRAME 0', 'XR_TIME_FRAME_ZERO'),
        ('FRAME 24', 'XR_TIME_FRAME_24'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'PLAYBACK RANGE'
    menus.TITLES[_QUICK_PAGE] = 'TIMELINE FRAME JUMPS'
    v065.TOOLTIPS.update({
        _RANGE_MENU: ('Native Playback Range', 'Edit actual Blender scene start/end frames with XR Undo'),
        _QUICK_MENU: ('Frame Shortcuts', 'The previous Blender Frame 0 and Frame 24 commands'),
        _SET_START: ('Start At Current Frame', 'Set Blender playback start to the current whole frame'),
        _SET_END: ('End At Current Frame', 'Set Blender playback end to the current whole frame'),
    })
    for action, (index, step) in _STEPS.items():
        v065.TOOLTIPS[action] = (
            ('Start' if index == 0 else 'End') + ' ' + ('+' if step > 0 else '') + str(step),
            'Move the native Blender playback bound without changing any animation curves')


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_timeline_range_090_patched', False):
        return
    _history()
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        page = getattr(menu, 'page', None)
        if page == timeline_v090._PAGE and action in {_RANGE_MENU, _QUICK_MENU}:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controller gesture before changing playback bounds')
            _scene(context)
            menu.page = _PAGE if action == _RANGE_MENU else _QUICK_PAGE
            self.status = 'BLENDER TIMELINE / ' + ('PLAYBACK RANGE' if
                menu.page == _PAGE else 'QUICK FRAMES')
            return
        if page in {_PAGE, _QUICK_PAGE}:
            if action == 'BACK':
                menu.page = timeline_v090._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gestures before changing the timeline')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('XR history is required for timeline commands')
            if page == _PAGE and action in _ACTIONS:
                bounds, changed = _apply(context, action, history)
                self.status = 'RANGE {}..{} / {}'.format(
                    *bounds, 'XR UNDO READY' if changed else 'UNCHANGED')
                return
            if page == _QUICK_PAGE and action in _JUMPS:
                state, changed = timeline_v090._apply(context, action, history)
                self.status = 'FRAME {} / {}'.format(
                    state[0], 'XR UNDO READY' if changed else 'UNCHANGED')
                return
            raise ValueError('Unknown native timeline range control')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_timeline_range_090_patched = True


CLASSES = (BXR_OT_timeline_range,)
