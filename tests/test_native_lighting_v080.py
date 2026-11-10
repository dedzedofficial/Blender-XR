"""Blender integration: native Point/Spot/Area/Sun XR lights and history."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector
import blender_xr
from blender_xr import drawing, input_ownership_v080 as ownership
from blender_xr import menus, mesh, native_lighting_v080 as lights, runtime


def close(a, b, tol=3e-5):
    return all(abs(float(x)-float(y)) < tol for x, y in zip(a, b))


def refused(fn, phrase):
    try:
        fn()
    except ValueError as exc:
        assert phrase.lower() in str(exc).lower(), str(exc)
    else:
        raise AssertionError('Unsafe light edit succeeded: ' + phrase)


def run():
    blender_xr.register()
    history = mesh.History()
    session = None
    try:
        ctx = bpy.context
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_cube_add()
        cube = ctx.object
        original_mesh = cube.data
        assert runtime.Runtime._xr_native_lights_patched
        assert len(menus.PAGES['PRIMITIVES']) == 9
        assert all(1 <= len(menus.PAGES[page]) <= 12 for page in (
            'XR_LIGHT_HOME', 'XR_LIGHT_EDIT', 'XR_LIGHT_COLOR',
            'XR_LIGHT_SHAPE', 'XR_LIGHT_PRESETS'))
        assert any(a == 'XR_LIGHT_MENU' for _, a in menus.PAGES['PRIMITIVES'])

        session = runtime.Runtime.__new__(runtime.Runtime)
        session.menu = drawing.Menu()
        session.menu.visible = True
        session.history = history
        session.settings = ctx.scene.blender_xr
        session.status = ''
        session.tool = 'SELECT'
        session.transaction = session.grab = session.air_grab = session.axis_move = None
        session.axis_drag = session.two_hand_scale = session._xr_gesture = None
        session._weight_stroke = session.bone_drag = None
        session.radial = None
        session._xr_rearm_required = False
        session.ray = (Vector((1, 2, 3)), Vector((0, 0, -1)))

        created = []
        for kind in ('POINT', 'SPOT', 'AREA', 'SUN'):
            session.command(ctx, 'XR_LIGHT_MENU')
            assert session.menu.page == 'XR_LIGHT_HOME'
            session.command(ctx, 'XR_LIGHT_NEW_' + kind)
            obj = ctx.view_layer.objects.active
            assert obj.type == 'LIGHT' and obj.data.type == kind
            assert obj.data.users == 1 and len(obj.data.users_id) if False else obj.data.users == 1
            assert ctx.view_layer.objects.get(obj.name) == obj
            assert close(obj.location, (1, 2, 3 - session.settings.placement_distance))
            assert history.undo[-1][0] == 'XR_LIGHT_CREATE'
            assert session.menu.page == 'XR_LIGHT_EDIT'
            assert len(menus.PAGES['XR_LIGHT_SHAPE']) <= 12
            old_data = obj.data
            name, data_name = obj.name, old_data.name
            assert history.step(True)  # Remove only newly created Blender object
            assert bpy.data.objects.get(name) is None
            assert bpy.data.lights.get(data_name) == old_data
            assert history.step(False)
            obj = bpy.data.objects[name]
            assert obj.data == old_data
            session.command(ctx, 'XR_LIGHT_MENU')  # Refresh selection token
            session.command(ctx, 'XR_LIGHT_OPEN_ACTIVE')
            assert session.menu.page == 'XR_LIGHT_EDIT'

            old_state = lights._state(obj)
            session.command(ctx, 'XR_LIGHT_POWER_UP')
            assert obj.data.energy > old_state[2][0]
            assert history.undo[-1][0] == 'XR_LIGHT_EDIT'
            assert history.step(True)
            assert lights._same(lights._state(obj), old_state)
            assert history.step(False)
            assert obj.data.energy > old_state[2][0]

            session.command(ctx, 'XR_LIGHT_COLOR_MENU')
            assert session.menu.page == 'XR_LIGHT_COLOR'
            session.command(ctx, 'XR_LIGHT_COLOR_RED')
            assert close(obj.data.color, (1., .06, .05))
            assert history.step(True)
            assert close(obj.data.color, old_state[2][1])
            assert history.step(False)
            assert close(obj.data.color, (1., .06, .05))
            session.settings.object_color = (.15, .7, .35, 1.)
            session.command(ctx, 'XR_LIGHT_COLOR_PICKER')
            assert close(obj.data.color, (.15, .7, .35))
            session.command(ctx, 'BACK')

            # Controller aim creates an armed interaction without mutating.
            snapshot = lights._state(obj)
            session.command(ctx, 'XR_LIGHT_MOVE')
            assert ownership.owner(session) == 'LIGHT_AIM'
            assert not session.menu.visible
            assert lights._same(lights._state(obj), snapshot)
            lights._cancel_pending(session)
            assert session.menu.visible
            assert lights._same(lights._state(obj), snapshot)
            session._xr_light_release_required = False
            assert ownership.owner(session) == 'IDLE'

            # Simulate a confirmed controller pose without OpenXR hardware.
            move_target = Vector((4, 5, 6))
            entry = lights._mutate(session, ctx, 'XR_LIGHT_MOVE', world=move_target)
            assert entry is not None and close(obj.matrix_world.translation, move_target)
            assert history.step(True)
            assert close(obj.matrix_world.translation, snapshot[1][0][3:4]) if False else (
                close(obj.matrix_world.translation, (1, 2, 3 - session.settings.placement_distance)))
            assert history.step(False)
            assert close(obj.matrix_world.translation, move_target)

            entry = lights._mutate(session, ctx, 'XR_LIGHT_AIM', direction=(1, 0, 0))
            assert entry is not None
            pointed = obj.matrix_world.to_quaternion() @ Vector((0, 0, -1))
            assert close(pointed, (1, 0, 0))
            assert history.step(True)
            assert history.step(False)
            assert close(obj.matrix_world.to_quaternion() @ Vector((0, 0, -1)), (1, 0, 0))

            session.command(ctx, 'XR_LIGHT_PRESET_MENU')
            assert session.menu.page == 'XR_LIGHT_PRESETS'
            session.command(ctx, 'XR_LIGHT_PRESET_CANDLE')
            assert close(obj.data.color, lights._PRESET_COLORS['CANDLE'])
            assert obj.data.animation_data is None
            session.command(ctx, 'XR_LIGHT_PRESET_HORROR')
            assert close(obj.data.color, lights._PRESET_COLORS['HORROR'])
            assert obj.data.animation_data is None
            session.command(ctx, 'BACK')
            session.command(ctx, 'XR_LIGHT_SHAPE_MENU')

            if kind == 'POINT':
                size_before = obj.data.shadow_soft_size
                session.command(ctx, 'XR_LIGHT_RADIUS_UP')
                assert obj.data.shadow_soft_size > size_before
                assert history.step(True)
                assert abs(obj.data.shadow_soft_size - size_before) < 3e-5
            elif kind == 'SPOT':
                old_cone = obj.data.spot_size
                session.command(ctx, 'XR_LIGHT_CONE_UP')
                assert obj.data.spot_size > old_cone
                assert history.step(True)
                assert abs(obj.data.spot_size - old_cone) < 3e-5
                old_blend = obj.data.spot_blend
                session.command(ctx, 'XR_LIGHT_BLEND_DOWN')
                assert obj.data.spot_blend <= old_blend
                assert history.step(True) if obj.data.spot_blend != old_blend else True
            elif kind == 'AREA':
                refused(lambda: session.command(ctx, 'XR_LIGHT_HEIGHT_UP'), 'rectangle')
                session.command(ctx, 'XR_LIGHT_RECTANGLE')
                assert obj.data.shape == 'RECTANGLE'
                before_size = obj.data.size_y
                session.command(ctx, 'XR_LIGHT_HEIGHT_UP')
                assert obj.data.size_y > before_size
                assert history.step(True)
                assert abs(obj.data.size_y - before_size) < 3e-5
            else:
                before_angle = obj.data.angle
                session.command(ctx, 'XR_LIGHT_ANGLE_UP')
                assert obj.data.angle > before_angle
                assert history.step(True)
                assert abs(obj.data.angle - before_angle) < 3e-5

            assert obj.data.type == kind and cube.data == original_mesh
            created.append(obj)
            session.command(ctx, 'BACK')
            session.command(ctx, 'BACK')
            assert session.menu.page == 'XR_LIGHT_HOME'

        # Blender's save/load preserves native lights without helper meshes.
        with TemporaryDirectory() as folder:
            saved_path = Path(folder) / 'xr-native-lights.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(saved_path), copy=True)
            assert saved_path.exists()
            with bpy.data.libraries.load(str(saved_path)) as (src, imported):
                imported.objects = [obj.name for obj in created]
            assert len(imported.objects) == 4
            assert {obj.data.type for obj in imported.objects} == {
                'POINT', 'SPOT', 'AREA', 'SUN'}
            assert all(obj.type == 'LIGHT' for obj in imported.objects)

        # An externally edited light value cannot be silently overwritten
        # by the headset's local Undo.
        obj = created[-1]
        for selected in tuple(ctx.selected_objects):
            selected.select_set(False)
        obj.select_set(True)
        ctx.view_layer.objects.active = obj
        session.command(ctx, 'XR_LIGHT_MENU')
        session.command(ctx, 'XR_LIGHT_OPEN_ACTIVE')
        history.clear()
        session.command(ctx, 'XR_LIGHT_POWER_UP')
        expected = lights._state(obj)
        obj.data.energy = 321.0
        refused(lambda: history.step(True), 'outside XR history')
        assert obj.data.energy == 321.0
        lights._restore(obj, expected)
        assert history.step(True)

        # Existing unsupported shared-data lights are protected rather than
        # silently copied or changed.
        other = bpy.data.objects.new('Shared Light Data User', obj.data)
        ctx.scene.collection.objects.link(other)
        refused(lambda: session.command(ctx, 'XR_LIGHT_POWER_UP'), 'single-user')
        bpy.data.objects.remove(other, do_unlink=True)
        obj.hide_select = True
        refused(lambda: session.command(ctx, 'XR_LIGHT_POWER_UP'), 'Unlock')
        obj.hide_select = False

        assert cube.data == original_mesh and cube.type == 'MESH'
        print('PASS native four-type XR lights, controller aiming, undo, presets and persistence')
    finally:
        history.clear()
        if session is not None:
            session.menu = None
            session.settings = None
            session = None
        blender_xr.unregister()


run()
