"""Blender 4.2–5.2 integration: native Bézier XR curves and local undo."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy
from mathutils import Vector

import blender_xr
from blender_xr import drawing, input_ownership_v080 as ownership
from blender_xr import menus, mesh, native_curves_v080 as curves, runtime


def refused(command, expected):
    try:
        command()
    except ValueError as exc:
        assert expected.lower() in str(exc).lower(), str(exc)
    else:
        raise AssertionError('Expected refusal: ' + expected)


def near(a, b, tolerance=2e-5):
    return all(abs(float(x)-float(y)) < tolerance for x, y in zip(a, b))


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
        mesh_data = cube.data
        original_count = len(mesh_data.vertices)
        assert len(menus.PAGES['PRIMITIVES']) == 8
        assert any(action == 'CURVE_MENU' for _, action in menus.PAGES['PRIMITIVES'])
        assert all(0 < len(menus.PAGES[name]) <= 12 for name in
                   ('XR_CURVE_MAIN', 'XR_CURVE_HANDLES', 'XR_CURVE_DISPLAY'))
        assert runtime.Runtime._xr_native_curves_patched

        session = runtime.Runtime.__new__(runtime.Runtime)
        session.menu = drawing.Menu()
        session.history = history
        session.settings = ctx.scene.blender_xr
        session.status = ''
        session.tool = 'SELECT'
        session.transaction = session.grab = session.air_grab = session.axis_move = None
        session._xr_gesture = session._weight_stroke = None
        session.two_hand_scale = session.axis_drag = session.bone_drag = None
        session.radial = None
        session.ray = (Vector((0, 0, 1.5)), Vector((0, 1, 0)))
        session._xr_rearm_required = False

        session.menu.page = 'PRIMITIVES'
        session.command(ctx, 'CURVE_MENU')
        assert session.menu.page == 'XR_CURVE_MAIN'
        assert 'PRESS NEW' in session.status
        session.command(ctx, 'CURVE_NEW')
        obj = ctx.view_layer.objects.active
        assert obj.type == 'CURVE'
        assert obj.data.dimensions == '3D'
        assert obj.data.users == 1 and len(obj.data.splines) == 1
        assert obj.data.splines[0].type == 'BEZIER'
        assert len(obj.data.splines[0].bezier_points) == 2
        assert history.undo[-1][0] == 'XR_CURVE_CREATE'
        assert near(obj.location, (0, session.settings.placement_distance, 1.5))
        assert cube.data == mesh_data and len(mesh_data.vertices) == original_count
        curve_name, data_name = obj.name, obj.data.name
        curve_data = obj.data
        assert history.step(True)
        assert bpy.data.objects.get(curve_name) is None
        assert bpy.data.curves.get(data_name) == curve_data
        assert history.step(False)
        obj = bpy.data.objects[curve_name]
        assert obj.data == curve_data
        assert len(obj.data.splines[0].bezier_points) == 2
        # Redo creates a fresh Object identity; reopening the curve page
        # deliberately refreshes the stale selection token.
        session.command(ctx, 'CURVE_MENU')
        assert session._xr_curve_target[0] == obj.name
        session.command(ctx, 'CURVE_NEXT')
        assert session._xr_curve_index == 1

        mat = bpy.data.materials.new('XR Curve Material')
        obj.data.materials.append(mat)
        old_mat_name = obj.data.materials[0].name
        before = curves._state(obj)
        session.command(ctx, 'CURVE_CYCLIC')
        assert obj.data.splines[0].use_cyclic_u
        assert history.undo[-1][0] == 'XR_CURVE_EDIT'
        assert history.step(True)
        assert curves._float_equal(curves._state(obj), before)
        assert history.step(False)
        assert obj.data.splines[0].use_cyclic_u

        session.command(ctx, 'CURVE_HANDLE_MENU')
        assert session.menu.page == 'XR_CURVE_HANDLES'
        session.command(ctx, 'CURVE_HANDLE_TYPE_VECTOR')
        assert obj.data.splines[0].bezier_points[0].handle_left_type == 'AUTO'
        assert obj.data.splines[0].bezier_points[1].handle_left_type == 'VECTOR'
        assert history.step(True)
        assert obj.data.splines[0].bezier_points[1].handle_left_type == 'AUTO'
        assert history.step(False)
        assert obj.data.splines[0].bezier_points[1].handle_left_type == 'VECTOR'

        # A hand menu command arms but does not mutate the Curve. Commit only
        # happens after release/aim/trigger on the real headset.
        state_before_arm = curves._state(obj)
        session.command(ctx, 'CURVE_HANDLE_LEFT')
        assert ownership.owner(session) == 'CURVE_POINT'
        assert not session.menu.visible
        assert curves._float_equal(curves._state(obj), state_before_arm)
        curves._cancel_pending(session)
        assert session.menu.visible
        assert curves._float_equal(curves._state(obj), state_before_arm)
        session._xr_curve_release_required = False
        assert ownership.owner(session) == 'IDLE'
        # Simulate the confirmed controller world point (headset-independent).
        left_world = obj.matrix_world @ Vector((.3, .2, .1))
        curves._edit(session, ctx, 'CURVE_HANDLE_LEFT', left_world)
        point = obj.data.splines[0].bezier_points[1]
        assert near(point.handle_left, (.3, .2, .1))
        assert point.handle_left_type == 'FREE'
        assert history.step(True)
        assert point.handle_left_type == 'VECTOR'

        session.command(ctx, 'BACK')
        assert session.menu.page == 'XR_CURVE_MAIN'
        new_world = obj.matrix_world @ Vector((.75, .1, .2))
        curves._edit(session, ctx, 'CURVE_ADD_POINT', new_world)
        assert len(obj.data.splines[0].bezier_points) == 3
        assert near(obj.data.splines[0].bezier_points[2].co, (.75, .1, .2))
        assert history.step(True)
        assert len(obj.data.splines[0].bezier_points) == 2
        assert history.step(False)
        assert len(obj.data.splines[0].bezier_points) == 3
        assert obj.data.splines[0].use_cyclic_u

        # Move point with controller world->object transform.
        session._xr_curve_index = 1
        moved_world = obj.matrix_world @ Vector((.5, .35, .3))
        curves._edit(session, ctx, 'CURVE_MOVE_POINT', moved_world)
        assert near(obj.data.splines[0].bezier_points[1].co, (.5, .35, .3))
        assert history.step(True)
        assert near(obj.data.splines[0].bezier_points[1].co, (.25, 0, 0))
        assert history.step(False)
        assert near(obj.data.splines[0].bezier_points[1].co, (.5, .35, .3))

        session.command(ctx, 'CURVE_DEL_POINT')
        assert len(obj.data.splines[0].bezier_points) == 2
        assert obj.data.splines[0].use_cyclic_u
        assert history.step(True)
        assert len(obj.data.splines[0].bezier_points) == 3
        assert history.step(False)
        assert len(obj.data.splines[0].bezier_points) == 2
        refused(lambda: session.command(ctx, 'CURVE_DEL_POINT'), 'two points')

        session.command(ctx, 'CURVE_DISPLAY_MENU')
        assert session.menu.page == 'XR_CURVE_DISPLAY'
        old_depth = obj.data.bevel_depth
        session.command(ctx, 'CURVE_BEVEL_UP')
        assert obj.data.bevel_depth > old_depth
        assert history.step(True)
        assert abs(obj.data.bevel_depth - old_depth) < 2e-5
        old_resolution = obj.data.resolution_u
        session.command(ctx, 'CURVE_RES_UP')
        assert obj.data.resolution_u == old_resolution + 2
        assert history.step(True)
        assert obj.data.resolution_u == old_resolution
        session.command(ctx, 'CURVE_BEVEL_RES_UP')
        assert obj.data.bevel_resolution == 1
        assert history.step(True)
        assert obj.data.bevel_resolution == 0

        # Undo refuses to silently overwrite out-of-band desktop edits.
        session.command(ctx, 'CURVE_BEVEL_UP')
        obj.data.bevel_depth = .25
        refused(lambda: history.step(True), 'outside XR')
        assert abs(obj.data.bevel_depth - .25) < 1e-6
        obj.data.bevel_depth = history.undo[-1][6][2]
        assert history.step(True)

        # Linked/shared curve data is rejected without cloning or overwriting.
        second = bpy.data.objects.new('Other Curve User', obj.data)
        ctx.scene.collection.objects.link(second)
        refused(lambda: session.command(ctx, 'CURVE_BEVEL_UP'), 'single-user')
        bpy.data.objects.remove(second, do_unlink=True)
        obj.hide_select = True
        refused(lambda: session.command(ctx, 'CURVE_BEVEL_UP'), 'Unlock')
        obj.hide_select = False
        obj.select_set(True)
        ctx.view_layer.objects.active = obj

        assert obj.data.materials[0].name == old_mat_name
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'xr-curve.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(path), copy=True)
            assert path.exists()
            with bpy.data.libraries.load(str(path)) as (library, imported):
                imported.objects = [curve_name]
            restored = imported.objects[0]
            assert restored.type == 'CURVE'
            assert len(restored.data.splines[0].bezier_points) == 2
            assert restored.data.splines[0].use_cyclic_u
            assert restored.data.materials[0].name == old_mat_name
        assert cube.data == mesh_data
        print('PASS native Curve/Bezier creation, points, handles, cancellation, undo and save')
    finally:
        history.clear()
        if session is not None:
            session.settings = None
            session.menu = None
            session = None
        blender_xr.unregister()


run()
