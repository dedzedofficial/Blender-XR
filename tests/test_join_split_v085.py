"""Mesh XR v0.8.5 Blender integration: Join/Join-as-copy/Unmerge and native Split."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import blender_xr
from blender_xr import drawing, join_split_v085 as parts, menus, mesh, runtime


def selected(ctx, *objs, active=None):
    for obj in tuple(ctx.selected_objects):
        obj.select_set(False)
    for obj in objs:
        obj.select_set(True)
    ctx.view_layer.objects.active = active or objs[0]


def refused(callback, part):
    try:
        callback()
    except ValueError as exc:
        assert part.lower() in str(exc).lower(), str(exc)
    else:
        raise AssertionError('Unsafe Join operation succeeded: ' + part)


def session_for(ctx, hist):
    session = runtime.Runtime.__new__(runtime.Runtime)
    session.menu = drawing.Menu()
    session.menu.page = 'XR_ASSEMBLY_085'
    session.history = hist
    session.settings = ctx.scene.blender_xr
    session.status = ''
    session.transaction = session.grab = session.air_grab = session.axis_move = None
    session._xr_gesture = session._weight_stroke = session.bone_drag = None
    return session


def run():
    blender_xr.register()
    hist = mesh.History()
    session = None
    try:
        ctx = bpy.context
        assert runtime.Runtime._xr_parts_085_patched
        assert len(menus.PAGES['XR_JOIN_SPLIT_085']) <= 12
        assert any(action == 'XR_JOIN_MENU' for _, action in menus.PAGES['XR_ASSEMBLY_085'])
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_cube_add(location=(2., 0., 0.))
        source1 = ctx.object
        source1.name = 'XR Joined Source A'
        bpy.ops.mesh.primitive_cube_add(location=(5., 0., 0.))
        source2 = ctx.object
        source2.name = 'XR Joined Source B'
        mat = bpy.data.materials.new('XR Joined Material')
        source1.data.materials.append(mat)
        original1, original2 = source1.data, source2.data
        original_positions = tuple(obj.matrix_world.translation.copy() for obj in (source1, source2))
        original_uv = tuple(layer.name for layer in original1.uv_layers)
        session = session_for(ctx, hist)
        selected(ctx, source1, source2, active=source1)
        session.command(ctx, 'XR_JOIN_MENU')
        assert session.menu.page == 'XR_JOIN_SPLIT_085'
        session.command(ctx, 'XR_JOIN_JOIN')
        joined = ctx.view_layer.objects.active
        assert joined.type == 'MESH' and joined not in (source1, source2)
        assert len(joined.data.vertices) == len(original1.vertices)+len(original2.vertices)
        assert source1.hide_select and source2.hide_select
        assert source1.hide_get(view_layer=ctx.view_layer)
        assert source2.hide_get(view_layer=ctx.view_layer)
        assert joined.get(parts._META)
        output_name = joined.name
        assert hist.undo[-1][0] == 'XR_PARTS_085'
        assert hist.step(True)
        assert ctx.view_layer.objects.get(output_name) is None
        assert not source1.hide_get(view_layer=ctx.view_layer)
        assert not source2.hide_select
        assert hist.step(False)
        joined = ctx.view_layer.objects.get(output_name)
        assert joined is not None and joined.type == 'MESH'
        assert source1.hide_get(view_layer=ctx.view_layer)
        assert joined.get(parts._META)

        # External mesh edits must not be silently discarded by Unmerge.
        first = joined.data.vertices[0]
        first.co.x += 1.
        selected(ctx, joined)
        refused(lambda: session.command(ctx, 'XR_JOIN_RESTORE'), 'changed')
        first.co.x -= 1.
        session.command(ctx, 'XR_JOIN_RESTORE')
        assert ctx.view_layer.objects.get(output_name) is None
        assert source1.data == original1 and source2.data == original2
        assert all((obj.matrix_world.translation - old).length < 1e-5
                   for obj, old in zip((source1, source2), original_positions))
        assert tuple(layer.name for layer in source1.data.uv_layers) == original_uv
        assert source1.data.materials[0] == mat
        assert not source1.hide_get(view_layer=ctx.view_layer)
        assert not source2.hide_get(view_layer=ctx.view_layer)
        assert hist.step(True)  # Undo Unmerge -> restore joined result
        joined = ctx.view_layer.objects.get(output_name)
        assert joined is not None
        assert source1.hide_select and source2.hide_select
        assert hist.step(False)
        assert ctx.view_layer.objects.get(output_name) is None

        # Copy joins keep originals visible rather than hiding them.
        selected(ctx, source1, source2, active=source1)
        session.command(ctx, 'XR_JOIN_COPY')
        copy_join = ctx.view_layer.objects.active
        copy_join_name = copy_join.name
        assert copy_join not in (source1, source2)
        assert not source1.hide_get(view_layer=ctx.view_layer)
        assert not source2.hide_get(view_layer=ctx.view_layer)
        session.command(ctx, 'XR_JOIN_RESTORE')
        assert ctx.view_layer.objects.get(copy_join_name) is None
        assert source1.data == original1 and source2.data == original2

        # Native Blender loose-part separation: keep source mesh so the same
        # restore-originals operation can reverse the separation after a save.
        bpy.ops.mesh.primitive_cube_add(location=(0., 2., 0.))
        piece_a = ctx.object
        bpy.ops.mesh.primitive_cube_add(location=(5., 2., 0.))
        piece_b = ctx.object
        selected(ctx, piece_a, piece_b, active=piece_a)
        assert 'FINISHED' in bpy.ops.object.join()
        loose = ctx.view_layer.objects.active
        loose_data = loose.data
        assert len(loose.data.vertices) == 16
        selected(ctx, loose)
        session.command(ctx, 'XR_JOIN_LOOSE')
        produced = tuple(obj for obj in ctx.view_layer.objects
                         if obj.get(parts._META) and obj.get(parts._MARKER))
        names_produced = tuple(obj.name for obj in produced)
        assert len(produced) == 2
        assert all(len(obj.data.vertices) == 8 for obj in produced)
        assert loose.data == loose_data and loose.hide_select
        selected(ctx, produced[0])
        session.command(ctx, 'XR_JOIN_RESTORE')
        assert not loose.hide_select and not loose.hide_get(view_layer=ctx.view_layer)
        assert all(ctx.view_layer.objects.get(name) is None for name in names_produced)

        # Original mesh's native materials survive save/append, not a parallel
        # proprietary scene format.
        selected(ctx, source1, source2, active=source1)
        session.command(ctx, 'XR_JOIN_JOIN')
        current_join = ctx.view_layer.objects.active
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'xr-join-unmerge.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(path), copy=True)
            assert path.exists()
            with bpy.data.libraries.load(str(path)) as (lib, imported):
                imported.objects = [current_join.name, source1.name, source2.name]
            assert imported.objects[0] is not None
            assert imported.objects[0].get(parts._META) is not None
            assert imported.objects[0].get(parts._MARKER)
        assert source1.data == original1 and source2.data == original2
        print('PASS v0.8.5 native Join, Copy, exact Unmerge, Loose split and save')
    finally:
        hist.clear()
        if session is not None:
            session.settings = None
            session.menu = None
        blender_xr.unregister()


run()
