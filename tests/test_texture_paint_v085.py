"""Blender 4.2–5.2 v0.8.5 native UV texture painting integration."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector
import blender_xr
from blender_xr import drawing, mesh, menus, runtime
from blender_xr import texture_paint_v085 as paint
from blender_xr import input_ownership_v080 as ownership


def refused(fn, phrase):
    try:
        fn()
    except ValueError as exc:
        assert phrase.lower() in str(exc).lower(), str(exc)
    else:
        raise AssertionError('Unsafe paint operation accepted: ' + phrase)


def rgba_at(image, x, y):
    buf = paint._pixel_data(image)
    p = (y*image.size[0]+x)*4
    return tuple(buf[p:p+4])


def run():
    blender_xr.register()
    history = mesh.History()
    session = None
    try:
        ctx = bpy.context
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_plane_add(size=2.0)
        obj = ctx.object
        assert obj.data.uv_layers.active is not None
        mat = bpy.data.materials.new('XR Texture Paint Test Material')
        mat.use_nodes = True
        obj.data.materials.append(mat)
        bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        rgb = mat.node_tree.nodes.new('ShaderNodeRGB')
        rgb.outputs[0].default_value = (.2, .5, .9, 1.0)
        mat.node_tree.links.new(rgb.outputs['Color'], bsdf.inputs['Base Color'])

        session = runtime.Runtime.__new__(runtime.Runtime)
        session.menu = drawing.Menu()
        session.history = history
        session.settings = ctx.scene.blender_xr
        session.status = ''
        session.transaction = session.grab = session.air_grab = session.axis_move = None
        session._xr_gesture = session._weight_stroke = session.bone_drag = None
        session._xr_curve_pending = session._xr_light_pending = None
        session._xr_rearm_required = False

        assert runtime.Runtime._xr_paint_085_patched
        assert 'XR_PAINT_MENU' in [action for _, action in menus.PAGES['MATERIAL_TEXTURES']]
        assert all(0 < len(menus.PAGES[page]) <= 12 for page in (
            'XR_TEXTURE_PAINT_085', 'XR_TEXTURE_RES_085'))
        session.menu.page = 'MATERIAL_TEXTURES'
        session.command(ctx, 'XR_PAINT_MENU')
        assert session.menu.page == 'XR_TEXTURE_PAINT_085'
        assert 'CREATE A LAYER' in session.status
        session.command(ctx, 'XR_PAINT_RES_MENU')
        session.command(ctx, 'XR_PAINT_RES_256')
        session.command(ctx, 'BACK')
        session.command(ctx, 'XR_PAINT_NEW')
        obj_, mat_, tex, image = paint._selected(session, ctx)
        assert obj_ == obj and mat_ == mat
        assert image.size[:] == (256, 256)
        assert image.channels == 4 and tex.image == image
        assert tex.inputs['Vector'].is_linked
        assert tex.inputs['Vector'].links[0].from_node.type == 'UVMAP'
        mix = bsdf.inputs['Base Color'].links[0].from_node
        assert mix.type == 'MIX_RGB'
        assert mix.inputs[1].is_linked
        assert mix.inputs[1].links[0].from_node == rgb
        assert mat.node_tree.nodes.get(rgb.name) == rgb
        assert history.undo[-1][0] == 'XR_PAINT_LAYER_085'
        uv = paint._uv_hit(ctx, obj, Vector((0, 0, 2)), Vector((0, 0, -1)))
        assert uv is not None and all(.45 < v < .55 for v in uv)

        before = paint._pixel_data(image)
        stroke = paint.PaintStroke(session, ctx, 'PAINT')
        assert stroke.dab(ctx, (0, 0, 2), (0, 0, -1))
        assert rgba_at(image, 128, 128)[3] > 0
        entry = stroke.finish()
        assert entry and entry[0] == 'XR_PAINT_STROKE_085'
        history.push(entry)
        changed = paint._pixel_data(image)
        assert changed != before
        assert history.step(True)
        assert paint._pixel_data(image) == before
        assert history.step(False)
        assert paint._pixel_data(image) == changed

        eraser = paint.PaintStroke(session, ctx, 'ERASE')
        assert eraser.dab(ctx, (0, 0, 2), (0, 0, -1))
        assert rgba_at(image, 128, 128)[3] < 1.
        eraser.cancel()
        assert paint._pixel_data(image) == changed
        session.command(ctx, 'XR_PAINT_BRUSH')
        assert ownership.owner(session) == 'TEXTURE_PAINT'
        assert not session.menu.visible
        paint._cancel(session, rollback=True)
        assert session.menu.visible
        session._xr_paint_release_required = False
        assert ownership.owner(session) == 'IDLE'

        session.command(ctx, 'XR_PAINT_MIRROR_U')
        assert session._xr_paint_mirror_u
        session.settings.object_color = (.7, .1, .3, 1.)
        session.command(ctx, 'XR_PAINT_FILL')
        assert rgba_at(image, 30, 40)[3] > .99
        assert history.undo[-1][0] == 'XR_PAINT_IMAGE_085'
        assert history.step(True)
        assert paint._pixel_data(image) == changed
        assert history.step(False)
        assert rgba_at(image, 30, 40)[3] > .99
        session.command(ctx, 'XR_PAINT_CLEAR')
        assert rgba_at(image, 30, 40)[3] == 0.
        assert history.step(True)
        assert rgba_at(image, 30, 40)[3] > .99

        # New native image layers must preserve the original shader graph.
        session.command(ctx, 'XR_PAINT_NEW')
        second = paint._selected(session, ctx)[3]
        assert second != image
        assert len(paint._layers(mat)) == 2
        assert history.step(True)
        assert len(paint._layers(mat)) == 1
        assert mat.node_tree.nodes.get(rgb.name) == rgb
        assert history.step(False)
        assert len(paint._layers(mat)) == 2

        # Refuse to modify a shared material without explicit single-user copy.
        bpy.ops.mesh.primitive_plane_add(size=2.0, location=(4., 0, 0))
        other = ctx.object
        other.data.materials.append(mat)
        ctx.view_layer.objects.active = obj
        refused(lambda: session.command(ctx, 'XR_PAINT_NEW'), 'duplicate shared')
        other.data.materials.clear()
        bpy.data.objects.remove(other, do_unlink=True)
        ctx.view_layer.objects.active = obj

        with TemporaryDirectory() as folder:
            path = Path(folder) / 'xr-texture-paint.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(path))
            assert path.exists()
            session.command(ctx, 'XR_PAINT_SAVE')
            folder_tex = Path(folder) / 'textures'
            assert len(list(folder_tex.glob('*.png'))) >= 1
            verify_copy = Path(folder) / 'xr-texture-paint-verify.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(verify_copy), copy=True)
            with bpy.data.libraries.load(str(verify_copy)) as (library, imported):
                imported.materials = [mat.name]
            loaded = imported.materials[0]
            assert loaded is not None and loaded.use_nodes
            img_nodes = [n for n in loaded.node_tree.nodes
                         if n.type == 'TEX_IMAGE' and n.get(paint._TAG)]
            assert len(img_nodes) == 2
            assert img_nodes[0].image is not None
            assert img_nodes[0].inputs['Vector'].is_linked

        print('PASS v0.8.5 native paint layers, UV brush, undo/cancel, PNG and saved .blend')
    finally:
        history.clear()
        if session is not None:
            session.menu = None
            session.settings = None
        blender_xr.unregister()


run()
