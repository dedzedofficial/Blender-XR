"""Native Blender regression checks for hand-operated Mirror/Array modifier editing."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import blender_xr
from blender_xr import drawing, menus, mesh, native_modifiers_v080 as native, runtime


def refusal(callback, message):
    try:
        callback()
    except ValueError as exc:
        assert message.lower() in str(exc).lower(), str(exc)
    else:
        raise AssertionError('Unsafe modifier operation was accepted: ' + message)


def run():
    blender_xr.register()
    history = mesh.History()
    session = None
    try:
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_cube_add()
        ctx = bpy.context
        obj = ctx.object
        original_mesh = obj.data
        uv_names = tuple(layer.name for layer in obj.data.uv_layers)
        original_vertex_count = len(obj.data.vertices)

        # Both modifiers exist before XR opens. They must be EDITED, not cloned.
        unrelated = obj.modifiers.new('Existing Bevel', 'BEVEL')
        unrelated.width = .23
        mirror = obj.modifiers.new('Creator Mirror', 'MIRROR')
        mirror.use_axis = (True, False, False)
        mirror.use_clip = False
        arr = obj.modifiers.new('Creator Array', 'ARRAY')
        arr.count = 5
        arr.constant_offset_displace = (-.05, 0.0, 0.0)
        old_stack = [x.name for x in obj.modifiers]

        ref = bpy.data.objects.new('XR Offset Reference', None)
        ctx.scene.collection.objects.link(ref)
        ctx.view_layer.update()
        obj.select_set(True)
        ctx.view_layer.objects.active = obj

        session = runtime.Runtime.__new__(runtime.Runtime)
        session.menu = drawing.Menu()
        session.history = history
        session.status = ''
        session.settings = ctx.scene.blender_xr
        session.transaction = session.grab = session.air_grab = None
        session.axis_move = session._xr_gesture = session._weight_stroke = None
        assert runtime.Runtime._xr_native_modifiers_patched
        assert len(menus.PAGES['MODIFIER_MENU']) <= 12
        for name in ('XR_MIRROR_EDIT', 'XR_ARRAY_EDIT', 'XR_ARRAY_MODES'):
            assert 0 < len(menus.PAGES[name]) <= 12

        session.menu.page = 'CREATOR'
        session.command(ctx, 'MODIFIER_MENU')
        assert session.menu.page == 'MODIFIER_MENU'
        session.command(ctx, 'MOD_MIRROR_EDIT_MENU')
        assert session.menu.page == 'XR_MIRROR_EDIT'
        assert session._xr_native_modifier[3] == mirror.name
        assert [mod.name for mod in obj.modifiers] == old_stack
        session.command(ctx, 'XR_MIRROR_Y')
        assert tuple(mirror.use_axis) == (True, True, False)
        assert history.undo[-1][0] == 'XR_NATIVE_MODIFIER'
        assert history.step(True)
        assert tuple(mirror.use_axis) == (True, False, False)
        assert history.step(False)
        assert tuple(mirror.use_axis) == (True, True, False)
        assert [mod.name for mod in obj.modifiers] == old_stack
        session.command(ctx, 'XR_MIRROR_CLIP')
        assert mirror.use_clip
        session.command(ctx, 'XR_MIRROR_MERGE')
        assert not mirror.use_mirror_merge
        before_threshold = mirror.merge_threshold
        session.command(ctx, 'XR_MIRROR_THRESHOLD_UP')
        assert mirror.merge_threshold > before_threshold
        assert history.step(True)
        assert abs(mirror.merge_threshold - before_threshold) < 1e-8

        refusal(lambda: session.command(ctx, 'XR_MIRROR_TARGET'), 'exactly one other')
        ref.select_set(True)
        session.command(ctx, 'XR_MIRROR_TARGET')
        assert mirror.mirror_object == ref
        assert history.step(True)
        assert mirror.mirror_object is None
        assert history.step(False)
        assert mirror.mirror_object == ref
        session.command(ctx, 'XR_MIRROR_TARGET_CLEAR')
        assert mirror.mirror_object is None
        assert history.step(True)
        assert mirror.mirror_object == ref
        assert history.step(False)
        assert mirror.mirror_object is None

        # Explicit NEW is the only way to add a second Mirror.
        count_before = len(obj.modifiers)
        session.command(ctx, 'XR_MIRROR_NEW')
        added = obj.modifiers.get(session._xr_native_modifier[3])
        assert added is not None and added.type == 'MIRROR'
        added_name = added.name  # RNA wrapper becomes invalid when Undo removes it
        assert len(obj.modifiers) == count_before + 1
        assert history.step(True)
        assert obj.modifiers.get(added_name) is None
        assert history.step(False)
        assert obj.modifiers.get(added_name) is not None
        assert [m.name for m in obj.modifiers][:len(old_stack)] == old_stack

        session.command(ctx, 'BACK')
        assert session.menu.page == 'MODIFIER_MENU'
        session.command(ctx, 'MOD_ARRAY_EDIT_MENU')
        assert session._xr_native_modifier[3] == arr.name
        assert [m.name for m in obj.modifiers][:len(old_stack)] == old_stack
        session.command(ctx, 'XR_ARRAY_COUNT_UP')
        assert arr.count == 6
        assert history.step(True)
        assert arr.count == 5
        assert history.step(False)
        assert arr.count == 6

        # Safe undo rejects changes made outside XR.
        session.command(ctx, 'XR_ARRAY_COUNT_UP')
        arr.count = 11
        refusal(lambda: history.step(True), 'outside XR history')
        assert arr.count == 11
        arr.count = 7
        assert history.step(True)
        assert arr.count == 6

        session.command(ctx, 'XR_ARRAY_MODES_MENU')
        assert session.menu.page == 'XR_ARRAY_MODES'
        session.command(ctx, 'XR_ARRAY_MODE_CONSTANT')
        assert arr.use_constant_offset and not arr.use_relative_offset
        session.command(ctx, 'BACK')
        assert session.menu.page == 'XR_ARRAY_EDIT'
        session.command(ctx, 'XR_ARRAY_X_DOWN')
        assert arr.constant_offset_displace[0] < -.1
        assert arr.constant_offset_displace[0] < 0.0
        assert history.step(True)
        assert abs(arr.constant_offset_displace[0] + .05) < 1e-7
        assert history.step(False)
        assert arr.constant_offset_displace[0] < -.1

        session.command(ctx, 'XR_ARRAY_MODES_MENU')
        session.command(ctx, 'XR_ARRAY_MODE_OBJECT')
        assert arr.use_object_offset and arr.offset_object == ref
        assert not arr.use_relative_offset and not arr.use_constant_offset
        session.command(ctx, 'BACK')
        refusal(lambda: session.command(ctx, 'XR_ARRAY_X_UP'), 'Relative or Constant')
        session.command(ctx, 'XR_ARRAY_MODES_MENU')
        session.command(ctx, 'XR_ARRAY_MODE_RELATIVE')
        assert arr.use_relative_offset and not arr.use_object_offset
        assert abs(unrelated.width - .23) < 1e-6
        assert obj.data == original_mesh
        assert tuple(x.name for x in obj.data.uv_layers) == uv_names
        assert len(obj.data.vertices) == original_vertex_count

        # New Array creation is reversible and does not remove any other modifier.
        session.command(ctx, 'BACK')
        session.command(ctx, 'XR_ARRAY_NEW')
        new_name = session._xr_native_modifier[3]
        assert obj.modifiers.get(new_name) is not None
        assert history.step(True)
        assert obj.modifiers.get(new_name) is None
        assert history.step(False)
        assert obj.modifiers.get(new_name) is not None
        assert abs(unrelated.width - .23) < 1e-6

        # Editing a locked mesh should be refused; untouched data is preserved.
        obj.hide_select = True
        old_count = arr.count
        try:
            session.command(ctx, 'XR_ARRAY_COUNT_UP')
        except ValueError as exc:
            assert 'unlock' in str(exc).lower() or 'select a mesh' in str(exc).lower()
        else:
            raise AssertionError('Selection-locked mesh was edited')
        assert arr.count == old_count
        obj.hide_select = False
        obj.select_set(True)
        ctx.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        refusal(lambda: session.command(ctx, 'XR_ARRAY_COUNT_UP'), 'Object Mode')
        bpy.ops.object.mode_set(mode='OBJECT')

        with TemporaryDirectory() as folder:
            path = Path(folder) / 'xr-native-modifiers.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(path), copy=True)
            assert path.exists()
            with bpy.data.libraries.load(str(path)) as (library, imported):
                imported.objects = [obj.name]
            saved = imported.objects[0]
            assert saved is not None
            assert any(m.type == 'ARRAY' and m.use_relative_offset
                       for m in saved.modifiers)
            assert any(m.type == 'MIRROR' for m in saved.modifiers)
        print('PASS native Mirror/Array edit controls, XR history and save/reopen')
    finally:
        history.clear()
        if session is not None:
            session.settings = None
            session.menu = None
            session = None
        if bpy.context.object is not None and bpy.context.object.mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')
        blender_xr.unregister()


run()
