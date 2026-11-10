"""v0.8.5 Boolean Shape Builder: Blender 4.2+ integration."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy
import blender_xr
from blender_xr import booleans_v085 as boolean, drawing, menus, mesh, runtime


def selected(ctx, target, cutter):
    for obj in tuple(ctx.selected_objects):
        obj.select_set(False)
    target.select_set(True)
    cutter.select_set(True)
    ctx.view_layer.objects.active = target


def refused(fn, phrase):
    try:
        fn()
    except ValueError as exc:
        assert phrase.lower() in str(exc).lower(), str(exc)
    else:
        raise AssertionError('Should have refused: ' + phrase)


def run():
    blender_xr.register()
    history = mesh.History()
    session = None
    try:
        ctx = bpy.context
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
        target = ctx.object
        target.name = 'XR Boolean Target'
        bpy.ops.mesh.primitive_cube_add(size=2, location=(.75, 0, 0))
        cutter = ctx.object
        cutter.name = 'XR Boolean Cutter'
        target_material = bpy.data.materials.new('XR Boolean Material')
        target.data.materials.append(target_material)
        uv_names = tuple(layer.name for layer in target.data.uv_layers)
        original_mesh = target.data
        selected(ctx, target, cutter)

        session = runtime.Runtime.__new__(runtime.Runtime)
        session.menu = drawing.Menu()
        session.history = history
        session.settings = ctx.scene.blender_xr
        session.status = ''
        session.transaction = session.grab = session.air_grab = session.axis_move = None
        session._xr_gesture = session._weight_stroke = session.bone_drag = None
        session.menu.page = 'XR_ASSEMBLY_085'
        assert len(menus.PAGES['XR_BOOLEAN_085']) <= 12
        assert 'XR_BOOL_MENU' in [action for _, action in menus.PAGES['XR_ASSEMBLY_085']]
        assert runtime.Runtime._xr_bool_085_patched

        cutter_visual = boolean._visual(cutter)
        session.command(ctx, 'XR_BOOL_MENU')
        assert session.menu.page == 'XR_BOOLEAN_085'
        session.command(ctx, 'XR_BOOL_DIFFERENCE')
        mod = boolean._mod(target, cutter)
        assert mod is not None and mod.type == 'BOOLEAN'
        assert mod.operation == 'DIFFERENCE' and mod.solver == 'EXACT'
        assert cutter.hide_render and cutter.display_type == 'WIRE'
        assert history.undo[-1][0] == 'XR_BOOL_EDIT'
        assert history.step(True)
        assert boolean._mod(target, cutter) is None
        assert boolean._visual(cutter) == cutter_visual
        assert history.step(False)
        assert boolean._mod(target, cutter) is not None

        session.command(ctx, 'XR_BOOL_UNION')
        assert boolean._mod(target, cutter).operation == 'UNION'
        assert len([mod for mod in target.modifiers if mod.type == 'BOOLEAN']) == 1
        assert history.step(True)
        assert boolean._mod(target, cutter).operation == 'DIFFERENCE'
        assert history.step(False)
        assert boolean._mod(target, cutter).operation == 'UNION'
        session.command(ctx, 'XR_BOOL_INTERSECT')
        assert boolean._mod(target, cutter).operation == 'INTERSECT'

        session.command(ctx, 'XR_BOOL_TOGGLE')
        assert not boolean._mod(target, cutter).show_viewport
        assert history.step(True)
        assert boolean._mod(target, cutter).show_viewport
        assert history.step(False)
        assert not boolean._mod(target, cutter).show_viewport
        session.command(ctx, 'XR_BOOL_TOGGLE')
        assert boolean._mod(target, cutter).show_viewport

        # Refuse to silently overwrite artist-created Boolean modifiers.
        artist = target.modifiers.new('Artist Boolean', 'BOOLEAN')
        artist.operation = 'DIFFERENCE'
        artist.object = cutter
        assert artist != boolean._mod(target, cutter)
        session.command(ctx, 'XR_BOOL_UNION')
        assert artist.operation == 'DIFFERENCE'
        assert artist.object == cutter
        target.modifiers.remove(artist)

        before_apply_count = len(target.data.vertices)
        session.command(ctx, 'XR_BOOL_APPLY')
        assert boolean._mod(target, cutter) is None
        assert target.type == 'MESH' and cutter.type == 'MESH'
        assert history.undo[-1][0] == 'XR_BOOL_APPLY'
        assert len(target.data.vertices) != before_apply_count
        assert history.step(True)
        assert boolean._mod(target, cutter) is not None
        assert len(target.data.vertices) == before_apply_count
        assert history.step(False)
        assert boolean._mod(target, cutter) is None
        assert len(target.data.vertices) != before_apply_count
        assert cutter.type == 'MESH'
        assert tuple(x.name for x in target.data.uv_layers) == uv_names
        assert target.data.materials[0] == target_material

        # A new Boolean after applying is non-destructive; remove safely.
        session.command(ctx, 'XR_BOOL_DIFFERENCE')
        assert boolean._mod(target, cutter) is not None
        session.command(ctx, 'XR_BOOL_REMOVE')
        assert boolean._mod(target, cutter) is None
        assert history.step(True)
        assert boolean._mod(target, cutter) is not None
        assert history.step(False)
        assert boolean._mod(target, cutter) is None

        selected(ctx, target, cutter)
        target.hide_select = True
        try:
            session.command(ctx, 'XR_BOOL_DIFFERENCE')
        except ValueError as exc:
            assert 'unlock' in str(exc).lower() or 'select a mesh' in str(exc).lower()
        else:
            raise AssertionError('Selection-locked target was modified')
        target.hide_select = False
        selected(ctx, target, cutter)
        # Existing shape keys prevent destructive Apply.
        if target.data.shape_keys is None:
            target.shape_key_add(name='Basis')
        session.command(ctx, 'XR_BOOL_DIFFERENCE')
        refused(lambda: session.command(ctx, 'XR_BOOL_APPLY'), 'shape keys')

        with TemporaryDirectory() as folder:
            path = Path(folder) / 'xr-native-boolean.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(path), copy=True)
            with bpy.data.libraries.load(str(path)) as (library, loaded):
                loaded.objects = [target.name, cutter.name]
            check = [obj for obj in loaded.objects if obj.type == 'MESH']
            assert len(check) == 2
            assert any(mod.type == 'BOOLEAN' for mod in check[0].modifiers)
        print('PASS v0.8.5 native Boolean modifier, Apply history, guardrails, save')
    finally:
        history.clear()
        if session is not None:
            session.settings = None
            session.menu = None
        blender_xr.unregister()


run()
