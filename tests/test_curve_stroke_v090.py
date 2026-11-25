"""Blender integration coverage for controller-drawn native Bézier curves."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy
from mathutils import Vector

import blender_xr
from blender_xr import curve_stroke_v090 as stroke
from blender_xr import drawing, mesh, menus, native_curves_v080, runtime
from blender_xr import input_ownership_v080 as ownership


def refused(command, expected):
    try:
        command()
    except ValueError as exc:
        assert expected.lower() in str(exc).lower(), str(exc)
    else:
        raise AssertionError('Expected refusal: ' + expected)


def near(a, b, tolerance=2e-5):
    return all(abs(float(x) - float(y)) < tolerance for x, y in zip(a, b))


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
        curves_before = len(bpy.data.curves)

        session = runtime.Runtime.__new__(runtime.Runtime)
        session.menu = drawing.Menu()
        session.history = history
        session.settings = ctx.scene.blender_xr
        session.status = ''
        session.dom = 0
        session.off = 1
        session.radial = None
        session.ray = (Vector((0, 0, 1)), Vector((0, 0, -1)))
        session._xr_rearm_required = False
        session._xr_neutral_count = 0
        session.menu.page = 'PRIMITIVES'
        session.menu.visible = True

        session.command(ctx, 'CURVE_MENU')
        assert session.menu.page == native_curves_v080._MAIN
        session.command(ctx, 'CURVE_STROKE_START')
        assert ownership.owner(session) == 'CURVE_STROKE'
        assert session._xr_curve_stroke['phase'] == 'WAIT_RELEASE'
        assert not session.menu.visible
        assert len(menus.PAGES[native_curves_v080._MAIN]) <= 12

        # The menu Trigger must be released before drawing can begin.
        stroke._advance_stroke(session, ctx, False, False, (0, 0, 0), 1.0)
        assert session._xr_curve_stroke['phase'] == 'READY'
        stroke._advance_stroke(session, ctx, True, False, (0, 0, 0), 1.0)
        stroke._advance_stroke(session, ctx, True, False, (0.03, 0, 0), 1.0)
        stroke._advance_stroke(session, ctx, True, False, (0.06, 0.02, 0), 1.0)
        # Small movements are filtered rather than producing jitter points.
        stroke._advance_stroke(session, ctx, True, False, (0.065, 0.02, 0), 1.0)
        stroke._advance_stroke(session, ctx, False, False, (0.06, 0.02, 0), 1.0)
        preview = session._xr_curve_stroke_preview
        assert preview is not None
        assert len(preview['points']) == 3
        assert session.menu.page == stroke._PAGE
        assert session.menu.visible
        assert ownership.owner(session) == 'IDLE'
        assert len(bpy.data.curves) == curves_before  # GPU preview only; no scene data yet.

        # A changed selection invalidates the preview before native data is created.
        bpy.ops.mesh.primitive_cube_add(location=(2, 0, 0))
        second = ctx.object
        refused(lambda: session.command(ctx, 'CURVE_STROKE_CONFIRM'), 'selection changed')
        assert session._xr_curve_stroke_preview is not None
        second.select_set(False)
        cube.select_set(True)
        ctx.view_layer.objects.active = cube
        bpy.data.objects.remove(second, do_unlink=True)

        # Close/open is an explicit preview choice and needs three points.
        session.command(ctx, 'CURVE_STROKE_CYCLE')
        assert session._xr_curve_stroke_preview['cyclic']
        session.command(ctx, 'CURVE_STROKE_CYCLE')
        assert not session._xr_curve_stroke_preview['cyclic']

        session.command(ctx, 'CURVE_STROKE_CONFIRM')
        obj = ctx.view_layer.objects.active
        assert obj.type == 'CURVE'
        assert obj.data.dimensions == '3D'
        assert obj.data.users == 1
        spline = obj.data.splines[0]
        assert spline.type == 'BEZIER'
        assert len(spline.bezier_points) == 3
        assert all(point.handle_left_type == 'AUTO' for point in spline.bezier_points)
        assert near(obj.location, (0, 0, 0))
        assert history.undo[-1][0] == 'XR_CURVE_CREATE'
        assert len(bpy.data.curves) == curves_before + 1
        assert not spline.use_cyclic_u
        assert cube.data is not None

        curve_name = obj.name
        assert history.step(True)
        assert bpy.data.objects.get(curve_name) is None
        assert history.step(False)
        obj = bpy.data.objects.get(curve_name)
        assert obj is not None and obj.type == 'CURVE'
        assert len(obj.data.splines[0].bezier_points) == 3

        # Saved .blend contains the native editable spline, not a preview helper.
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'drawn-curve.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(path), copy=True)
            assert path.exists()
            with bpy.data.libraries.load(str(path)) as (library, imported):
                imported.objects = [curve_name]
            restored = imported.objects[0]
            assert restored.type == 'CURVE'
            assert len(restored.data.splines[0].bezier_points) == 3
            assert restored.data.splines[0].type == 'BEZIER'

        # The explicit preview Cancel discards the path without adding data.
        session.command(ctx, 'CURVE_MENU')
        session.command(ctx, 'CURVE_STROKE_START')
        stroke._advance_stroke(session, ctx, False, False, (0, 0, 0), 1.0)
        stroke._advance_stroke(session, ctx, True, False, (0, 0, 0), 1.0)
        stroke._advance_stroke(session, ctx, True, False, (0.03, 0, 0), 1.0)
        stroke._advance_stroke(session, ctx, False, False, (0.03, 0, 0), 1.0)
        assert session._xr_curve_stroke_preview is not None
        session.command(ctx, 'CURVE_STROKE_CANCEL')
        assert session._xr_curve_stroke_preview is None
        assert len(bpy.data.curves) == curves_before + 1

        # Offhand Trigger cancels a live stroke and requires neutral rearm.
        session.command(ctx, 'CURVE_STROKE_START')
        stroke._advance_stroke(session, ctx, False, False, (0, 0, 0), 1.0)
        stroke._advance_stroke(session, ctx, True, False, (0, 0, 0), 1.0)
        stroke._advance_stroke(session, ctx, True, True, (0.03, 0, 0), 1.0)
        assert session._xr_curve_stroke is None
        assert session._xr_curve_stroke_preview is None
        assert session._xr_rearm_required

        # A stroke with fewer than two distinct samples never creates a preview.
        session._xr_rearm_required = False
        session.menu.page = native_curves_v080._MAIN
        session.command(ctx, 'CURVE_STROKE_START')
        stroke._advance_stroke(session, ctx, False, False, (0, 0, 0), 1.0)
        stroke._advance_stroke(session, ctx, True, False, (0, 0, 0), 1.0)
        stroke._advance_stroke(session, ctx, False, False, (0, 0, 0), 1.0)
        assert session._xr_curve_stroke is None
        assert session._xr_curve_stroke_preview is None
        assert 'TWO DISTINCT POINTS' in session.status

        print('PASS controller-drawn native Curve preview, cancel, Undo/Redo and save/reopen')
    finally:
        history.clear()
        if session is not None:
            session.settings = None
            session.menu = None
            session = None
        blender_xr.unregister()


run()
