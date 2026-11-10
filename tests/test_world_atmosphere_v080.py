"""Real Blender integration for native XR World, background and fog controls."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import blender_xr
from blender_xr import drawing, menus, mesh, runtime
from blender_xr import world_atmosphere_v080 as atmosphere


def refused(fn, contains):
    try:
        fn()
    except ValueError as exc:
        assert contains.lower() in str(exc).lower(), str(exc)
    else:
        raise AssertionError('Unsafe World operation was permitted: ' + contains)


def close(first, second, tol=3e-5):
    return len(first) == len(second) and all(abs(float(a)-float(b)) < tol
                                             for a, b in zip(first, second))


def find_bg(world):
    return next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')


def find_output(world):
    return next(n for n in world.node_tree.nodes if n.type == 'OUTPUT_WORLD')


def init_world(name):
    world = bpy.data.worlds.new(name)
    world.use_nodes = True
    tree = world.node_tree
    output = next((n for n in tree.nodes if n.type == 'OUTPUT_WORLD'), None)
    if output is None:
        output = tree.nodes.new('ShaderNodeOutputWorld')
    bg = next((n for n in tree.nodes if n.type == 'BACKGROUND'), None)
    if bg is None:
        bg = tree.nodes.new('ShaderNodeBackground')
    if not output.inputs['Surface'].is_linked:
        tree.links.new(bg.outputs['Background'], output.inputs['Surface'])
    return world


def run():
    blender_xr.register()
    history = mesh.History()
    session = None
    previous_world = bpy.context.scene.world
    try:
        ctx = bpy.context
        assert runtime.Runtime._xr_world_atmosphere_patched
        assert 'XR_WORLD_MENU' in [a for _, a in menus.PAGES['XR_LIGHT_HOME']]
        assert all(1 <= len(menus.PAGES[p]) <= 12 for p in (
            'XR_WORLD_EDIT', 'XR_WORLD_COLORS', 'XR_WORLD_FOG'))

        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_cube_add()
        cube = ctx.object
        mesh_data = cube.data

        world = init_world('XR World Native')
        ctx.scene.world = world
        assert world.users == 1
        background = find_bg(world)
        output = find_output(world)
        material = bpy.data.materials.new('Unrelated Material')
        cube.data.materials.append(material)
        # Custom disconnected world nodes are never touched by XR.
        unrelated = world.node_tree.nodes.new('ShaderNodeValue')
        unrelated.name = 'Unrelated World Node'
        unrelated.outputs[0].default_value = .37
        unrelated_nodes = len(world.node_tree.nodes)
        original_surface = output.inputs['Surface'].links[0].from_node
        original_background = atmosphere._background_state(world)

        session = runtime.Runtime.__new__(runtime.Runtime)
        session.menu = drawing.Menu()
        session.history = history
        session.settings = ctx.scene.blender_xr
        session.status = ''
        session.tool = 'SELECT'
        session.transaction = session.grab = session.air_grab = session.axis_move = None
        session._xr_gesture = session._weight_stroke = session.bone_drag = None
        session._xr_curve_pending = session._xr_light_pending = None

        session.menu.page = 'XR_LIGHT_HOME'
        session.command(ctx, 'XR_WORLD_MENU')
        assert session.menu.page == 'XR_WORLD_EDIT'
        assert atmosphere._active(session, ctx)[1] == world

        session.command(ctx, 'XR_WORLD_POWER_UP')
        assert find_bg(world).inputs['Strength'].default_value > original_background[-1]
        assert history.undo[-1][0] == 'XR_WORLD_EDIT'
        assert history.step(True)
        assert atmosphere._same(atmosphere._background_state(world), original_background)
        assert history.step(False)
        assert find_bg(world).inputs['Strength'].default_value > original_background[-1]

        session.command(ctx, 'XR_WORLD_COLOR_MENU')
        assert session.menu.page == 'XR_WORLD_COLORS'
        session.command(ctx, 'XR_WORLD_COLOR_DUSK')
        assert close(background.inputs['Color'].default_value,
                     atmosphere._COLORS['DUSK'])
        assert history.step(True)
        assert history.step(False)
        session.settings.object_color = (.3, .7, .8, 1)
        session.command(ctx, 'XR_WORLD_COLOR_PICK')
        assert close(background.inputs['Color'].default_value, (.3, .7, .8, 1))
        session.command(ctx, 'BACK')
        assert session.menu.page == 'XR_WORLD_EDIT'

        session.command(ctx, 'XR_WORLD_FOG_MENU')
        assert session.menu.page == 'XR_WORLD_FOG'
        assert atmosphere._fog_state(world) is None
        session.command(ctx, 'XR_FOG_ADD')
        assert atmosphere._fog_state(world) is not None
        assert len(world.node_tree.nodes) == unrelated_nodes + 1
        assert len(output.inputs['Volume'].links) == 1
        fog = output.inputs['Volume'].links[0].from_node
        assert fog.type == 'VOLUME_SCATTER'
        assert fog.name == atmosphere._FOG_NAME
        assert history.step(True)
        assert atmosphere._fog_state(world) is None
        assert len(output.inputs['Volume'].links) == 0
        assert history.step(False)
        assert atmosphere._fog_state(world) is not None

        density_before = atmosphere._fog_state(world)[1]
        session.command(ctx, 'XR_FOG_DENSITY_UP')
        assert atmosphere._fog_state(world)[1] > density_before
        assert history.step(True)
        assert abs(atmosphere._fog_state(world)[1] - density_before) < 3e-5
        assert history.step(False)
        session.command(ctx, 'XR_FOG_SCATTER_UP')
        assert atmosphere._fog_state(world)[2] > 0
        assert history.step(True)
        assert abs(atmosphere._fog_state(world)[2]) < 3e-5
        session.command(ctx, 'XR_FOG_COLOR_PICK')
        assert close(atmosphere._fog_state(world)[0], (.3, .7, .8, 1))

        session.command(ctx, 'XR_FOG_TOGGLE')
        assert atmosphere._fog_state(world)[1] == 0
        assert history.step(True)
        assert atmosphere._fog_state(world)[1] > 0
        session.command(ctx, 'XR_FOG_REMOVE')
        assert atmosphere._fog_state(world) is None
        assert history.step(True)
        assert atmosphere._fog_state(world) is not None
        assert history.step(False)
        assert atmosphere._fog_state(world) is None

        # Existing unrelated nodes and the original World Surface stay intact.
        assert world.node_tree.nodes.get('Unrelated World Node') == unrelated
        assert abs(unrelated.outputs[0].default_value - .37) < 3e-5
        assert output.inputs['Surface'].links[0].from_node == original_surface
        assert cube.data == mesh_data and cube.data.materials[0] == material

        # Existing custom volume links must never be replaced.
        custom = world.node_tree.nodes.new('ShaderNodeVolumeScatter')
        custom.name = 'Creator Volume'
        world.node_tree.links.new(custom.outputs['Volume'], output.inputs['Volume'])
        snapshot_links = len(world.node_tree.links)
        refused(lambda: session.command(ctx, 'XR_FOG_ADD'), 'custom')
        assert len(world.node_tree.links) == snapshot_links
        assert output.inputs['Volume'].links[0].from_node == custom
        world.node_tree.nodes.remove(custom)

        # Preserve existing environment textures or other linked background inputs.
        tex = world.node_tree.nodes.new('ShaderNodeTexEnvironment')
        world.node_tree.links.new(tex.outputs['Color'], background.inputs['Color'])
        links_before = len(world.node_tree.links)
        session.command(ctx, 'BACK')
        refused(lambda: session.command(ctx, 'XR_WORLD_POWER_UP'), 'linked')
        assert len(world.node_tree.links) == links_before
        assert background.inputs['Color'].is_linked
        world.node_tree.nodes.remove(tex)

        # External desktop changes cannot be silently undone by XR history.
        history.clear()
        session.command(ctx, 'XR_WORLD_POWER_UP')
        after = atmosphere._background_state(world)
        background.inputs['Strength'].default_value = .33
        refused(lambda: history.step(True), 'outside XR')
        atmosphere._restore_background(world, after)
        assert history.step(True)

        # A World used by multiple scenes must not be edited silently.
        other_scene = bpy.data.scenes.new('XR Other Scene')
        other_scene.world = world
        refused(lambda: session.command(ctx, 'XR_WORLD_POWER_UP'), 'single-user')
        bpy.data.scenes.remove(other_scene)

        # Renderer warnings are informative rather than a false preview promise.
        old_engine = ctx.scene.render.engine
        ctx.scene.render.engine = 'BLENDER_WORKBENCH'
        session.command(ctx, 'XR_WORLD_FOG_MENU')
        assert 'UNVERIFIED' in session.status
        ctx.scene.render.engine = old_engine
        session.command(ctx, 'BACK')

        # Explicitly create a missing World and undo/redo the assignment.
        history.clear()
        ctx.scene.world = None
        session.command(ctx, 'XR_WORLD_MENU')
        assert 'NO WORLD' in session.status
        session.command(ctx, 'XR_WORLD_NEW')
        created = ctx.scene.world
        assert created is not None and created.use_nodes
        assert atmosphere._background(created)
        assert history.undo[-1][0] == 'XR_WORLD_CREATE'
        assert history.step(True)
        assert ctx.scene.world is None
        assert history.step(False)
        assert ctx.scene.world == created

        # Native World graphs persist in Blender saves, with no custom format.
        session.command(ctx, 'XR_WORLD_FOG_MENU')
        session.command(ctx, 'XR_FOG_ADD')
        fog_state = atmosphere._fog_state(created)
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'xr-world-atmosphere.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(path), copy=True)
            assert path.exists()
            with bpy.data.libraries.load(str(path)) as (src, loaded):
                loaded.worlds = [created.name]
            restored = loaded.worlds[0]
            assert restored is not None and restored.use_nodes
            assert len(atmosphere._output(restored).inputs['Volume'].links) == 1
            assert atmosphere._same(atmosphere._fog_state(restored), fog_state)

        print('PASS native World colour/strength, reversible fog and renderer warnings')
    finally:
        history.clear()
        bpy.context.scene.world = previous_world
        if session is not None:
            session.menu = None
            session.settings = None
        blender_xr.unregister()


run()
