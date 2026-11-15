"""Preview transactions must commit once or roll back without stealing other input."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import blender_xr
from blender_xr import drawing, mesh, runtime, input_ownership_v080 as ownership
from blender_xr import native_modifiers_v080 as mods, native_curves_v080 as curves


def refused(call):
    try:
        call()
    except ValueError:
        return
    raise AssertionError('Unsafe action accepted')


def run():
    blender_xr.register()
    ctx = bpy.context
    session = runtime.Runtime.__new__(runtime.Runtime)
    session.context = ctx
    session.settings = ctx.scene.blender_xr
    session.menu = drawing.Menu()
    session.history = mesh.History()
    session.status = ''
    session.transaction = session.grab = session.air_grab = session.axis_move = None
    session._weight_stroke = session._xr_gesture = session.bone_drag = None
    try:
        bpy.ops.mesh.primitive_cube_add()
        obj = ctx.object
        modifier = obj.modifiers.new('Existing Array', 'ARRAY')
        modifier.count = 3
        session.command(ctx, 'MOD_ARRAY_EDIT_MENU')
        session.command(ctx, 'XR_MODIFIER_PREVIEW')
        assert ownership.owner(session) == 'MODIFIER_PREVIEW'
        session.command(ctx, 'XR_ARRAY_COUNT_UP')
        session.command(ctx, 'XR_ARRAY_COUNT_UP')
        assert modifier.count == 5 and len(session.history.undo) == 0
        refused(lambda: session.command(ctx, 'SAVE'))
        refused(lambda: session.command(ctx, 'MODE_EDIT'))
        refused(lambda: session.command(ctx, 'XR_ARRAY_NEW'))
        session.command(ctx, 'BACK')
        assert session.menu.page == 'XR_MODIFIER_CONFIRM'
        session.command(ctx, 'XR_MODIFIER_CANCEL')
        assert modifier.count == 3 and len(session.history.undo) == 0
        session.command(ctx, 'MOD_ARRAY_EDIT_MENU')
        session.command(ctx, 'XR_MODIFIER_PREVIEW')
        session.command(ctx, 'XR_ARRAY_COUNT_UP')
        session.command(ctx, 'XR_ARRAY_X_UP')
        session.command(ctx, 'BACK')
        session.command(ctx, 'XR_MODIFIER_APPLY')
        assert len(session.history.undo) == 1
        assert modifier.count == 4
        assert session.history.step(True) and modifier.count == 3
        assert session.history.step(False) and modifier.count == 4
        session.history.clear()
        session.command(ctx, 'MOD_ARRAY_EDIT_MENU')
        session.command(ctx, 'XR_MODIFIER_PREVIEW')
        session.command(ctx, 'XR_ARRAY_COUNT_UP')
        ownership.cancel_session_loss(session)
        assert modifier.count == 4 and session._xr_modifier_preview is None
        assert session._xr_rearm_required
        session._xr_rearm_required = False
        session._xr_modifier_release_required = False
        session.command(ctx, 'MOD_ARRAY_EDIT_MENU')
        session.command(ctx, 'XR_MODIFIER_PREVIEW')
        session.command(ctx, 'XR_ARRAY_COUNT_UP')
        original_sample = curves._input_sample
        try:
            def lost(*args):
                raise ValueError('Tracking lost')
            curves._input_sample = lost
            mods._preview_tick(session, ctx)
            assert modifier.count == 4 and session._xr_modifier_preview is None
            assert session._xr_rearm_required
        finally:
            curves._input_sample = original_sample
        # Ordinary immediate editing is still available outside Preview.
        session._xr_rearm_required = False
        session.command(ctx, 'MOD_ARRAY_EDIT_MENU')
        session.command(ctx, 'XR_ARRAY_COUNT_UP')
        assert modifier.count == 5 and len(session.history.undo) == 1
        # External edits must survive cancellation and must not leave input stuck.
        session.command(ctx, 'XR_MODIFIER_PREVIEW')
        modifier.count = 9
        refused(lambda: session.command(ctx, 'XR_MODIFIER_CANCEL'))
        assert modifier.count == 9 and session._xr_modifier_preview is None
        print('PASS native modifier preview apply/cancel, atomic history and tracking rollback')
    finally:
        session.history.clear()
        blender_xr.unregister()


if __name__ == '__main__':
    run()
