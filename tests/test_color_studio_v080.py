"""Real Blender tests for native-material colour upgrades and preservation."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector
import blender_xr
from blender_xr import color_studio_v080 as studio, drawing, materials, menus, mesh, runtime, v056


def close(a, b, tolerance=1e-5):
    return len(a) == len(b) and all(abs(float(x) - float(y)) < tolerance
                                     for x, y in zip(a, b))


def expect_error(fn, expected):
    try:
        fn()
    except ValueError as exc:
        assert expected.lower() in str(exc).lower(), str(exc)
    else:
        raise AssertionError('Expected protective error: ' + expected)


def run():
    blender_xr.register()
    history = mesh.History()
    session = None
    try:
        assert getattr(runtime.Runtime, '_xr_color_studio_patched', False)
        assert len(menus.PAGES['MATERIAL_HOME']) == 12
        assert any(action == 'COLOR_STUDIO_MENU'
                   for _label, action in menus.PAGES['MATERIAL_HOME'])
        assert materials.to_hex((1.0, 0.0, 0.5, 1.0)) == '#FF0080'
        assert close(materials.from_hex('FF0080', alpha=0.6),
                     (1.0, 0.0, 128/255, 0.6))
        assert close(materials.from_hex('#8080FF80'),
                     (128/255, 128/255, 1.0, 128/255))
        for bad in ('#G00000', 'ZZZZZZ', 'FFFF', '#123456789'):
            expect_error(lambda: materials.from_hex(bad), 'hex')

        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        context = bpy.context
        settings = context.scene.blender_xr
        source = materials.create_material(obj, (.1, .3, .5, .7))[1]
        principled = source.node_tree.nodes.get('Principled BSDF')
        assert principled is not None
        roughness_node = source.node_tree.nodes.new('ShaderNodeValue')
        roughness_node.outputs[0].default_value = .32
        source.node_tree.links.new(roughness_node.outputs[0],
                                   principled.inputs['Roughness'])
        before_links = len(source.node_tree.links)
        before_nodes = len(source.node_tree.nodes)
        before_state = studio._state(source)
        uv = obj.data.uv_layers.new(name='XR Preserve UV')
        uv_identity = uv.name

        # A second mesh deliberately uses the same native Material.
        second = bpy.data.objects.new('XR Colour Other', bpy.data.meshes.new('XR Colour Other Mesh'))
        context.scene.collection.objects.link(second)
        second.data.materials.append(source)
        context.view_layer.objects.active = obj
        obj.select_set(True)
        assert source.users >= 2

        session = runtime.Runtime.__new__(runtime.Runtime)
        session.menu = drawing.Menu()
        session.settings = settings
        session.history = history
        session.status = ''
        session.tool = 'SELECT'
        session.transaction = session.grab = session.air_grab = session.axis_move = None
        session.two_hand_scale = None
        session._xr_rearm_required = False
        session.command(context, 'MATERIAL_MENU')
        assert session.menu.page == 'MATERIAL_HOME'
        session.command(context, 'COLOR_STUDIO_MENU')
        assert session.menu.page == 'COLOR_STUDIO'
        session.command(context, 'STUDIO_HSV')
        assert session.menu.page == 'COLOR_STUDIO_HSV'
        session.menu.position(Vector((0, 0, 0)), Vector((0, -1, .25)), 1.0)
        target = session.menu.world(v056.SLIDER_X + v056.SLIDER_W * .62, .117 + .02)
        action, _pos = session.menu.hit(target + session.menu.normal,
                                        -session.menu.normal)
        assert action == 'STUDIO_HUE_SLIDER', action
        session.command(context, 'STUDIO_HUE_SLIDER')
        assert abs(session.color_hsv[0] - .62) < .01
        preview = tuple(settings.object_color)
        assert studio._state(source) == before_state  # Pointer move previews only

        session.command(context, 'STUDIO_SWATCHES')
        assert session.menu.page == 'COLOR_STUDIO_SWATCHES'
        session.command(context, 'STUDIO_SAVE_2')
        assert close(settings.color_swatch_2, preview)
        settings.object_color = (.9, .1, .1, 1.0)
        session.command(context, 'STUDIO_LOAD_2')
        assert close(settings.object_color, preview)
        session.command(context, 'BACK')
        assert session.menu.page == 'COLOR_STUDIO_HSV'

        settings.color_hex = '#3366CC'
        session.command(context, 'STUDIO_HEX_LOAD')
        expected = materials.from_hex('3366CC', alpha=settings.object_color[3])
        assert close(settings.object_color, expected)
        settings.color_hex = 'not a hex'
        expect_error(lambda: session.command(context, 'STUDIO_HEX_LOAD'), 'hex')
        assert close(settings.object_color, expected)
        settings.color_hex = '#3366CC'
        assert bpy.ops.blender_xr.color_hex_preview() == {'FINISHED'}
        assert close(settings.object_color, expected)

        # LOCAL edit must split shared material data without changing the other
        # object's shader or any existing texture/roughness node links.
        session.command(context, 'STUDIO_LOCAL')
        local = obj.active_material
        assert local != source
        assert second.active_material == source
        assert studio._state(source) == before_state
        assert close(materials.material_color(local), expected)
        assert len(local.node_tree.links) == before_links
        assert len(source.node_tree.links) == before_links
        assert len(source.node_tree.nodes) == before_nodes
        assert obj.data.uv_layers.get(uv_identity) is not None
        assert history.undo[-1][0] == 'COLOR_EXISTING'
        assert history.step(True)
        assert obj.active_material == source
        assert history.step(False)
        assert obj.active_material == local
        assert close(materials.material_color(local), expected)
        assert history.step(True)
        assert obj.active_material == source

        # Explicit shared edit changes the original for both objects and is
        # reversible as one XR local undo without deleting any material nodes.
        settings.object_color = (.6, .2, .8, .9)
        session.command(context, 'STUDIO_SHARED')
        assert obj.active_material == second.active_material == source
        assert close(materials.material_color(second.active_material), settings.object_color)
        assert history.step(True)
        assert studio._state(source) == before_state
        assert history.step(False)
        assert close(materials.material_color(source), settings.object_color)
        assert history.step(True)
        assert studio._state(source) == before_state

        # Refuse out-of-band changes instead of overwriting a user's material.
        session.command(context, 'STUDIO_SHARED')
        source.diffuse_color = (.123, .456, .789, 1.0)
        expect_error(lambda: history.step(True), 'outside XR')
        assert close(source.diffuse_color, (.123, .456, .789, 1))
        studio._restore(source, history.undo[-1][6])
        assert history.step(True)

        # A Base Color texture connection must be preserved, not overwritten.
        tex = source.node_tree.nodes.new('ShaderNodeRGB')
        source.node_tree.links.new(tex.outputs['Color'], principled.inputs['Base Color'])
        links_now = len(source.node_tree.links)
        mats_now = len(bpy.data.materials)
        expect_error(lambda: session.command(context, 'STUDIO_LOCAL'), 'texture-linked')
        expect_error(lambda: session.command(context, 'STUDIO_SHARED'), 'texture-linked')
        assert len(source.node_tree.links) == links_now
        assert len(bpy.data.materials) == mats_now
        assert principled.inputs['Base Color'].is_linked

        # Bad HEX preview does not mutate selected material or XR colour.
        old_preview = tuple(settings.object_color)
        settings.color_hex = '#XX1234'
        assert bpy.ops.blender_xr.color_hex_preview() == {'CANCELLED'}
        assert close(settings.object_color, old_preview)

        with TemporaryDirectory() as temp:
            file = Path(temp) / 'xr-colour-scene.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(file))
            assert file.exists() and file.stat().st_size > 0
            # Loading the saved material proves nodes and their links are still
            # native Blender data. No reload into a new XR session is needed.
            with bpy.data.libraries.load(str(file)) as (source_data, loaded_data):
                loaded_data.materials = [source.name]
            saved_mat = loaded_data.materials[0]
            assert saved_mat is not None
            assert any(link.to_socket.name == 'Base Color'
                       for link in saved_mat.node_tree.links)

        print('PASS colour HEX/HSV/swatches and reversible native local/shared edits')
    finally:
        history.clear()
        if session is not None:
            session.menu = None
            session.settings = None
            session = None
        blender_xr.unregister()


run()
