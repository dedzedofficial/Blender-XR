# SPDX-License-Identifier: GPL-3.0-or-later
"""Drive Blender's native screen animation playback from XR wrist menus.

The playback state belongs to the existing Blender Screen and its native
operator, not a competing XR timer, animation evaluation loop or keyframe
format. No Blender data is changed and playback controls do not enter
mesh.History; explicit frame steps continue to use timeline_v090 history.
"""
import bpy

from . import input_ownership_v080, menus, runtime, timeline_v090, v065

_TOGGLE = 'XR_TIME_PLAY_PAUSE'
_REVERSE = 'XR_TIME_REVERSE'


def _window_screen_area(context):
    """Resolve an existing window/screen suitable for native screen ops.

    XR runtime timers may have no 3D View area in bpy.context. Search only
    the invoking window's existing areas and never switch screens or create
    an editor to make an operator appear to succeed.
    """
    window = context.window
    if window is None or window.screen is None:
        raise ValueError('A Blender window is needed for timeline playback')
    screen = window.screen
    area = context.area
    if area is None or not any(item == area for item in screen.areas):
        area = next((item for item in screen.areas
                     if item.type in {'DOPESHEET_EDITOR', 'VIEW_3D', 'GRAPH_EDITOR'}),
                    None)
    if area is None:
        area = next(iter(screen.areas), None)
    if area is None:
        raise ValueError('No suitable Blender editor area for playback')
    return window, screen, area


def _playing(context):
    _window, screen, _area = _window_screen_area(context)
    return bool(screen.is_animation_playing)


def _execute(context, action):
    """Execute Blender's screen animation operators in their own UI context."""
    if action not in {_TOGGLE, _REVERSE}:
        raise ValueError('Unrecognized native timeline playback action')
    timeline_v090._scene(context)
    if getattr(context.scene, 'is_nla_tweakmode', False):
        # Native playback itself supports tweak mode, but this editor does
        # not modify NLA strip timing. Do not assume another animation owner.
        pass
    window, screen, area = _window_screen_area(context)
    with context.temp_override(window=window, screen=screen, area=area):
        if screen.is_animation_playing:
            if action == _REVERSE:
                raise ValueError('Pause playback before starting reverse')
            if not bpy.ops.screen.animation_cancel.poll():
                raise ValueError('Blender cannot pause playback in this window')
            outcome = bpy.ops.screen.animation_cancel(restore_frame=False)
            if 'FINISHED' not in outcome:
                raise ValueError('Native Blender playback did not pause')
            return 'PAUSED'
        if not bpy.ops.screen.animation_play.poll():
            raise ValueError('Native Blender timeline cannot play in this window')
        outcome = bpy.ops.screen.animation_play(reverse=(action == _REVERSE))
        if 'FINISHED' not in outcome:
            raise ValueError('Native Blender timeline playback did not start')
        return 'PLAY REVERSE' if action == _REVERSE else 'PLAY FORWARD'


class BXR_OT_timeline_playback(bpy.types.Operator):
    bl_idname = 'blender_xr.timeline_playback'
    bl_label = 'Native Blender Timeline Playback'
    bl_description = 'Play or pause the active Blender screen timeline using its built-in playback'
    bl_options = {'INTERNAL'}

    action: bpy.props.EnumProperty(
        items=(
            (_TOGGLE, 'Play / Pause', 'Toggle native Blender scene playback'),
            (_REVERSE, 'Play Reverse', 'Start native reverse playback after pausing'),
        ),
        default=_TOGGLE)

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Timeline wrist menu during VR')
            return {'CANCELLED'}
        try:
            status = _execute(context, self.action)
        except (ValueError, RuntimeError, TypeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Blender timeline / ' + status)
        return {'FINISHED'}


def install_pages():
    current = tuple(menus.PAGES[timeline_v090._PAGE])
    if not current or current[-1][1] != 'BACK':
        raise ValueError('Native Timeline wrist layout is missing')
    if not any(action == _TOGGLE for _label, action in current):
        current = current[:-1] + (
            ('PLAY / PAUSE', _TOGGLE), ('REVERSE', _REVERSE), current[-1])
    if len(current) > 12:
        raise ValueError('Playback controls would exceed native XR menu capacity')
    menus.PAGES[timeline_v090._PAGE] = current
    v065.TOOLTIPS.update({
        _TOGGLE: ('Play / Pause Blender Timeline',
                  'Start forward playback or pause Blender-native playback in the existing window'),
        _REVERSE: ('Play Timeline Reverse',
                   'Start reverse native Blender playback; pause first if already playing'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_native_timeline_playback_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == timeline_v090._PAGE and action in {_TOGGLE, _REVERSE}:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR controller gestures before playback')
            result = _execute(context, action)
            self.status = 'BLENDER TIMELINE / ' + result + ' / FRAME ' + str(
                context.scene.frame_current)
            return
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_native_timeline_playback_patched = True


CLASSES = (BXR_OT_timeline_playback,)
