# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Blender scene timeline controls from the XR wrist menu.

Only changes Scene.frame_current/frame_subframe through Scene.frame_set().
No duplicate animation tracks, keyframe authoring, external timeline, or
persistent mesh/rig data is created. Frame history is guarded per scene.
"""
import bpy

from . import input_ownership_v080, menus, mesh, runtime, v065

_PAGE = 'XR_TIMELINE_090'
_ACTIONS = {
    'XR_TIME_PREV_10': -10,
    'XR_TIME_PREV': -1,
    'XR_TIME_NEXT': 1,
    'XR_TIME_NEXT_10': 10,
}


def _scene(context):
    scene = context.scene
    if scene is None or scene.library or scene.override_library:
        raise ValueError('Use a local Blender scene for XR timeline control')
    return scene


def _time_state(scene):
    return (int(scene.frame_current), float(scene.frame_subframe))


def _frame_limits(scene):
    start, end = int(scene.frame_start), int(scene.frame_end)
    if end < start:
        raise ValueError('Scene playback start is greater than end')
    return start, end


def _apply(context, action, history=None):
    scene = _scene(context)
    start, end = _frame_limits(scene)
    before = _time_state(scene)
    current = before[0]
    if action in _ACTIONS:
        target = max(start, min(end, current + _ACTIONS[action]))
    elif action == 'XR_TIME_START':
        target = start
    elif action == 'XR_TIME_END':
        target = end
    elif action == 'XR_TIME_FRAME_ZERO':
        target = max(start, min(end, 0))
    elif action == 'XR_TIME_FRAME_24':
        target = max(start, min(end, 24))
    else:
        raise ValueError('Unsupported XR timeline control')
    after = (target, 0.0)
    if before == after:
        return before, False
    # The ranges and the exact previous evaluation state are included in the
    # history record. A redraw or controller frame cannot create an implicit
    # playback/keyframe state; only this explicit command calls frame_set.
    entry = ('XR_SCENE_FRAME_090', scene.name, scene.as_pointer(),
             before, after, start, end)
    scene.frame_set(target, subframe=0.0)
    try:
        if history is not None:
            history.push(entry)
    except Exception:
        if _time_state(scene) == after:
            scene.frame_set(before[0], subframe=before[1])
        raise
    return after, True


def _history():
    if getattr(mesh.History, '_xr_timeline_090_patched', False):
        return
    old_step, old_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == 'XR_SCENE_FRAME_090':
            return
        return old_release(entry)

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] != 'XR_SCENE_FRAME_090':
            return old_step(self, backwards)
        _kind, name, ptr, before, after, start, end = source[-1]
        scene = _scene(bpy.context)
        if (scene.name != name or scene.as_pointer() != ptr or
                _frame_limits(scene) != (start, end)):
            raise ValueError('Native Blender scene or frame range changed')
        expected = after if backwards else before
        if _time_state(scene) != expected:
            raise ValueError('Timeline frame was changed outside XR history')
        value = before if backwards else after
        scene.frame_set(value[0], subframe=value[1])
        dest.append(source.pop())
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_timeline_090_patched = True


class BXR_OT_timeline_step(bpy.types.Operator):
    bl_idname = 'blender_xr.timeline_step'
    bl_label = 'Blender XR Native Timeline Step'
    bl_description = 'Step the active Blender scene timeline without editing animation data'
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(items=[
        ('XR_TIME_PREV_10', '-10', 'Back 10 frames'),
        ('XR_TIME_PREV', '-1', 'Back one frame'),
        ('XR_TIME_NEXT', '+1', 'Forward one frame'),
        ('XR_TIME_NEXT_10', '+10', 'Forward 10 frames'),
        ('XR_TIME_START', 'Start', 'Jump to playback start'),
        ('XR_TIME_END', 'End', 'Jump to playback end'),
    ], default='XR_TIME_NEXT')

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the native timeline wrist menu during XR')
            return {'CANCELLED'}
        try:
            state, changed = _apply(context, self.action)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Blender scene frame {}{}'.format(
            state[0], ' / SUBFRAME {:.3f}'.format(state[1]) if state[1] else ''))
        return {'FINISHED'} if changed else {'CANCELLED'}


def install_pages():
    parent = tuple(menus.PAGES.get('LAYOUT_MENU', ()))
    if not parent or parent[-1][1] != 'BACK':
        raise ValueError('Native Timeline requires the existing Object Layout menu')
    if not any(action == 'XR_TIME_MENU' for _label, action in parent):
        parent = parent[:-1] + (('TIMELINE', 'XR_TIME_MENU'), parent[-1])
    if len(parent) > 12:
        raise ValueError('Native Timeline would overflow Object Layout wrist menu')
    menus.PAGES['LAYOUT_MENU'] = parent
    menus.PAGES[_PAGE] = (
        ('-10 FRAMES', 'XR_TIME_PREV_10'),
        ('-1 FRAME', 'XR_TIME_PREV'),
        ('+1 FRAME', 'XR_TIME_NEXT'),
        ('+10 FRAMES', 'XR_TIME_NEXT_10'),
        ('START', 'XR_TIME_START'),
        ('END', 'XR_TIME_END'),
        ('FRAME 0', 'XR_TIME_FRAME_ZERO'),
        ('FRAME 24', 'XR_TIME_FRAME_24'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'BLENDER TIMELINE'
    v065.TOOLTIPS.update({
        'XR_TIME_MENU': ('Scene Timeline', 'View native Blender animation at specific frames, no keyframe edits'),
        'XR_TIME_PREV_10': ('Back Ten Frames', 'Step the scene frame back 10, clamped to playback start'),
        'XR_TIME_PREV': ('Previous Frame', 'Step the scene one frame back'),
        'XR_TIME_NEXT': ('Next Frame', 'Step the scene one frame forward'),
        'XR_TIME_NEXT_10': ('Forward Ten Frames', 'Step the scene frame forward 10'),
        'XR_TIME_START': ('Playback Start', 'Evaluate at the scene frame-start bound'),
        'XR_TIME_END': ('Playback End', 'Evaluate at the scene frame-end bound'),
        'XR_TIME_FRAME_ZERO': ('Frame Zero', 'Evaluate at frame 0 when in scene range'),
        'XR_TIME_FRAME_24': ('Frame 24', 'Evaluate at frame 24 when in scene range'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_timeline_090_patched', False):
        return
    _history()
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if action == 'XR_TIME_MENU':
            _scene(context)
            if input_ownership_v080.is_editing(self):
                raise ValueError('Finish the active XR controller gesture first')
            self.menu.page = _PAGE
            self.status = 'BLENDER TIMELINE / FRAME {}'.format(context.scene.frame_current)
            return
        if page == _PAGE:
            if action == 'BACK':
                self.menu.page = 'LAYOUT_MENU'
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release live XR controls before changing the timeline')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('XR Undo history unavailable for timeline')
            state, changed = _apply(context, action, history=history)
            self.status = ('FRAME {} / {}'.format(
                state[0], 'UNDO READY' if changed else 'UNCHANGED'))
            return
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_timeline_090_patched = True


CLASSES = (BXR_OT_timeline_step,)
