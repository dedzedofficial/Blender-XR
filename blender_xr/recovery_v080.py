# SPDX-License-Identifier: GPL-3.0-or-later
"""Blender-native safe recovery checkpoints for Mesh XR 0.8.

No background threads or remote storage.  The Blender main-thread timer skips
all active modal/VR edits; save_as_mainfile(copy=True) leaves the current file
path unchanged.  Recovery explicitly opens a *copy*, never the checkpoint or
the original project in place.
"""
from pathlib import Path
from datetime import datetime, timezone
import shutil
import time
import bpy
from bpy.props import BoolProperty

_LAST = 0.0
_LAST_FILE = ''
_TICK_SECONDS = 15.0


def folder():
    return Path(bpy.utils.user_resource('CONFIG', path='mesh_xr/recovery', create=True))


def checkpoints():
    return sorted(folder().glob('meshxr-*.blend'), key=lambda p: p.stat().st_mtime, reverse=True)


def safe_to_save(context):
    if getattr(bpy.app, 'background', False):
        return False
    if context is None or context.scene is None or not hasattr(context.scene, 'blender_xr'):
        return False
    if context.mode != 'OBJECT':
        return False
    from . import runtime
    session = runtime.CURRENT
    if session is not None and (
            session.transaction or session.grab or session.axis_move or
            session.air_grab or session.two_hand_scale or
            getattr(session, '_xr_gesture', None) or
            getattr(session, 'axis_drag', None) or
            getattr(session, 'request_stop', False) or
            getattr(getattr(session, 'radial', None), 'active', False)):
        return False
    return True


def make_checkpoint(context, *, clock=None):
    global _LAST, _LAST_FILE
    if not safe_to_save(context):
        raise ValueError('Finish the current edit/gesture and return to Object Mode before checkpointing')
    if clock is None:
        clock = time.time()
    settings = context.scene.blender_xr
    destination = folder()
    destination.mkdir(parents=True, exist_ok=True)
    source = Path(bpy.data.filepath).stem if bpy.data.filepath else 'Untitled'
    source = ''.join(c if c.isalnum() or c in '._-' else '_' for c in source)[:56]
    stamp = datetime.fromtimestamp(clock, timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    target = destination / ('meshxr-' + source + '-' + stamp + '.blend')
    from . import project, runtime
    history = runtime.CURRENT.history if runtime.CURRENT else None
    before_path = bpy.data.filepath
    try:
        with project.without_snapshots(history):
            result = bpy.ops.wm.save_as_mainfile(filepath=str(target), copy=True, check_existing=False)
        if 'FINISHED' not in result or not target.is_file():
            raise ValueError('Blender did not write a valid recovery copy')
        if bpy.data.filepath != before_path:
            raise ValueError('Recovery must not change the active project path')
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise ValueError('Checkpoint failed: ' + str(exc)) from exc
    _LAST = time.monotonic()
    _LAST_FILE = target.name
    retain = max(1, int(settings.recovery_keep))
    for stale in checkpoints()[retain:]:
        try:
            stale.unlink()
        except OSError:
            pass
    return target


def tick():
    global _LAST
    if not bpy.app.timers.is_registered(tick):
        return None
    try:
        context = bpy.context
        scene = context.scene
        if scene and hasattr(scene, 'blender_xr'):
            settings = scene.blender_xr
            interval = max(60, int(settings.recovery_minutes) * 60)
            if (settings.recovery_enabled and getattr(bpy.data, 'is_dirty', False)
                    and time.monotonic() - _LAST >= interval
                    and safe_to_save(context)):
                try:
                    make_checkpoint(context)
                except (ValueError, RuntimeError, OSError):
                    _LAST = time.monotonic()  # rate-limit repeated filesystem errors
    except (ReferenceError, RuntimeError, AttributeError):
        pass  # Blender can be loading/closing a scene when timers run.
    return _TICK_SECONDS


def register_timer():
    global _LAST
    _LAST = time.monotonic()
    if not bpy.app.timers.is_registered(tick):
        bpy.app.timers.register(tick, first_interval=_TICK_SECONDS, persistent=True)


def unregister_timer():
    if bpy.app.timers.is_registered(tick):
        bpy.app.timers.unregister(tick)


class BXR_OT_checkpoint(bpy.types.Operator):
    bl_idname = 'blender_xr.recovery_checkpoint'
    bl_label = 'Create Recovery Checkpoint'
    bl_description = 'Write a separate timestamped .blend copy without changing the current project'

    def execute(self, context):
        try:
            path = make_checkpoint(context)
        except ValueError as exc:
            self.report({'WARNING'}, str(exc))
            return {'CANCELLED'}
        context.scene.blender_xr.status = 'Recovery saved: ' + path.name
        self.report({'INFO'}, 'Created recovery copy: ' + path.name)
        return {'FINISHED'}


class BXR_OT_restore_checkpoint(bpy.types.Operator):
    bl_idname = 'blender_xr.recovery_restore'
    bl_label = 'Open Latest Recovery as New File'
    bl_description = 'Confirm then open a NEW copy of the latest checkpoint; does not overwrite the current project'

    @classmethod
    def poll(cls, context):
        from . import runtime
        return runtime.CURRENT is None and bool(checkpoints())

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        from . import runtime
        if runtime.CURRENT is not None:
            return {'CANCELLED'}
        candidates = checkpoints()
        if not candidates:
            self.report({'ERROR'}, 'No recovery checkpoints exist')
            return {'CANCELLED'}
        source = candidates[0]
        out = source.with_name(source.stem + '-restored-' +
                               datetime.now(timezone.utc).strftime('%H%M%S%f') + '.blend')
        try:
            shutil.copy2(source, out)
            bpy.ops.wm.open_mainfile(filepath=str(out), load_ui=False)
        except (OSError, RuntimeError) as exc:
            self.report({'ERROR'}, 'Could not open recovery: ' + str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}


def draw(layout, settings):
    row = layout.row(align=True)
    row.prop(settings, 'recovery_enabled', text='Safe recovery', toggle=True, icon='FILE_BACKUP')
    if settings.recovery_enabled:
        col = layout.column(align=True)
        col.prop(settings, 'recovery_minutes', text='Minutes')
        col.prop(settings, 'recovery_keep', text='Keep copies')
    row = layout.row(align=True)
    row.enabled = safe_to_save(bpy.context)
    row.operator('blender_xr.recovery_checkpoint', text='Checkpoint now', icon='FILE_TICK')
    candidates = checkpoints()
    if candidates:
        layout.label(text='Latest: ' + candidates[0].name[:40], icon='FILE_BLEND')
        row = layout.row(align=True)
        row.enabled = bpy.context.scene is not None and __import__(
            __package__ + '.runtime', fromlist=['CURRENT']).CURRENT is None
        row.operator('blender_xr.recovery_restore', text='Open recovery copy', icon='RECOVER_LAST')
    layout.label(text='Copies are private and never overwrite your project', icon='INFO')


CLASSES = (BXR_OT_checkpoint, BXR_OT_restore_checkpoint)
