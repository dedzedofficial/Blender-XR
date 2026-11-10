# SPDX-License-Identifier: GPL-3.0-or-later
"""Non-destructive native Blender World background and atmospheric volume controls.

Designed for the existing offhand Shapes > Lights > World menus. Mutations only
touch native World colour, a directly linked Background shader and a uniquely
named Mesh XR Volume Scatter node. Existing custom node links are never removed.
The fog node is optional, reversible and remains editable in Blender afterwards.
"""
import bpy

from . import menus, mesh, v065

_PAGE = 'XR_WORLD_EDIT'
_FOG_PAGE = 'XR_WORLD_FOG'
_COLOR_PAGE = 'XR_WORLD_COLORS'
_FOG_NAME = 'Mesh XR Atmosphere Fog'

_COLORS = {
    'WARM': (1.0, 0.69, 0.43, 1.0),
    'COOL': (0.55, 0.73, 1.0, 1.0),
    'DUSK': (0.35, 0.19, 0.42, 1.0),
    'DARK': (0.035, 0.045, 0.07, 1.0),
    'WHITE': (1.0, 1.0, 1.0, 1.0),
}


def _editable(context):
    if context.mode != 'OBJECT':
        raise ValueError('Switch to Object Mode to edit the World')
    scene = context.scene
    world = scene.world
    if world is None:
        raise ValueError('Scene has no World; choose NEW WORLD first')
    if world.library or world.override_library:
        raise ValueError('Linked or overridden Worlds cannot be edited')
    if world.users != 1:
        raise ValueError('Make this World single-user before editing it in XR')
    if (world.animation_data and
            (world.animation_data.action or world.animation_data.drivers)):
        raise ValueError('Animated Worlds require their original Blender editor')
    return scene, world


def _active(session, context):
    scene, world = _editable(context)
    token = getattr(session, '_xr_world_target', None)
    if token != (scene.name, scene.as_pointer(), world.name, world.as_pointer()):
        raise ValueError('World changed; reopen the World menu')
    return scene, world


def _output(world):
    if not world.use_nodes or world.node_tree is None:
        raise ValueError('World nodes are off; choose NODES ON to enable them')
    nodes = [node for node in world.node_tree.nodes if node.type == 'OUTPUT_WORLD']
    active = next((node for node in nodes if node.is_active_output), None)
    node = active or (nodes[0] if len(nodes) == 1 else None)
    if node is None:
        raise ValueError('World has no unambiguous active World Output')
    return node


def _background(world):
    output = _output(world)
    socket = output.inputs.get('Surface')
    if socket is None or len(socket.links) != 1:
        raise ValueError('World Surface has no single direct Background node')
    node = socket.links[0].from_node
    if node.type != 'BACKGROUND':
        raise ValueError('Custom World shader is preserved; edit it in Blender')
    color, strength = node.inputs.get('Color'), node.inputs.get('Strength')
    if color is None or strength is None or color.is_linked or strength.is_linked:
        raise ValueError('Linked World Background inputs are preserved')
    return node, color, strength


def _background_state(world):
    if not world.use_nodes:
        return ('SOLID', tuple(world.color))
    node, color, strength = _background(world)
    return ('NODES', tuple(world.color), node.name,
            tuple(color.default_value), float(strength.default_value))


def _fog_socket(world):
    output = _output(world)
    socket = output.inputs.get('Volume')
    if socket is None:
        raise ValueError('Renderer has no native World Volume socket')
    return socket


def _fog_state(world):
    socket = _fog_socket(world)
    if len(socket.links) > 1:
        raise ValueError('Custom World volume graph must be edited in Blender')
    if not socket.links:
        # Never overwrite a disconnected node with the reserved name.
        if world.node_tree.nodes.get(_FOG_NAME) is not None:
            raise ValueError('Disconnected Mesh XR fog node needs manual repair')
        return None
    link = socket.links[0]
    node = link.from_node
    if (node.type != 'VOLUME_SCATTER' or node.name != _FOG_NAME
            or link.from_socket.name != 'Volume'):
        raise ValueError('Existing custom World volume is preserved')
    color, density, anisotropy = (node.inputs.get('Color'),
                                 node.inputs.get('Density'),
                                 node.inputs.get('Anisotropy'))
    if (color is None or density is None or anisotropy is None
            or color.is_linked or density.is_linked or anisotropy.is_linked):
        raise ValueError('Custom linked fog inputs are preserved')
    return (tuple(color.default_value), float(density.default_value),
            float(anisotropy.default_value))


def _restore_background(world, state):
    if state[0] == 'SOLID':
        if world.use_nodes:
            raise ValueError('World node mode changed outside XR history')
        world.color = state[1]
        return
    _, rgb, node_name, color, strength = state
    node, color_socket, strength_socket = _background(world)
    if node.name != node_name:
        raise ValueError('World shader changed outside XR history')
    world.color = rgb
    color_socket.default_value = color
    strength_socket.default_value = strength


def _restore_fog(world, state):
    socket = _fog_socket(world)
    existing = _fog_state(world)
    if state is None:
        if existing is not None:
            node = socket.links[0].from_node
            world.node_tree.nodes.remove(node)  # removes only our owned link
        return
    if existing is None:
        output = _output(world)
        node = world.node_tree.nodes.new('ShaderNodeVolumeScatter')
        node.name = _FOG_NAME
        node.label = 'Mesh XR Fog (native editable volume)'
        node.location = (output.location.x - 280, output.location.y - 240)
        world.node_tree.links.new(node.outputs['Volume'], socket)
    else:
        node = socket.links[0].from_node
    color, density, anisotropy = state
    node.inputs['Color'].default_value = color
    node.inputs['Density'].default_value = density
    node.inputs['Anisotropy'].default_value = anisotropy


def _same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 2e-5
    if isinstance(a, tuple) and isinstance(b, tuple):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def _engine_notice(context):
    engine = context.scene.render.engine
    if engine == 'CYCLES':
        return ' / CYCLES: VOLUME RENDERS'
    if engine.startswith('BLENDER_EEVEE'):
        return ' / EEVEE: VIEWPORT VOLUME MAY DIFFER'
    return ' / VIEWPORT FOG UNVERIFIED IN ' + engine[:18]


def _world_create(session, context):
    if context.mode != 'OBJECT':
        raise ValueError('Switch to Object Mode before creating a World')
    scene = context.scene
    if scene.world is not None:
        raise ValueError('Scene already has a World; no replacement was made')
    world = bpy.data.worlds.new('Mesh XR World')
    try:
        world.use_nodes = True
        scene.world = world
        # Blender may start a new World without a default node graph.
        nodes = world.node_tree.nodes
        if not any(node.type == 'OUTPUT_WORLD' for node in nodes):
            output = nodes.new('ShaderNodeOutputWorld')
        else:
            output = next(node for node in nodes if node.type == 'OUTPUT_WORLD')
        surface = output.inputs.get('Surface')
        if surface is not None and not surface.is_linked:
            background = nodes.new('ShaderNodeBackground')
            world.node_tree.links.new(background.outputs['Background'], surface)
        _background(world)
        session._xr_world_target = (scene.name, scene.as_pointer(),
                                    world.name, world.as_pointer())
        session.history.push(('XR_WORLD_CREATE', scene, world))
        session.menu.page = _PAGE
        session.status = 'NEW NATIVE WORLD / EDIT BACKGROUND'
    except Exception:
        scene.world = None
        if world.users == 0:
            bpy.data.worlds.remove(world)
        raise


def _world_open(session, context):
    session.menu.page = _PAGE
    scene, world = _editable(context)
    session._xr_world_target = (scene.name, scene.as_pointer(),
                                world.name, world.as_pointer())
    session.status = 'WORLD / ' + world.name[:36] + _engine_notice(context)


def _nodes_on(session, context):
    scene, world = _active(session, context)
    if world.use_nodes:
        session.status = 'WORLD NODES ALREADY ENABLED'
        return
    if world.node_tree is not None and len(world.node_tree.nodes):
        raise ValueError('Existing disabled custom nodes need the Blender World editor')
    world.use_nodes = True
    try:
        output = next((n for n in world.node_tree.nodes if n.type == 'OUTPUT_WORLD'), None)
        if output is None:
            output = world.node_tree.nodes.new('ShaderNodeOutputWorld')
        if not output.inputs['Surface'].is_linked:
            bg = world.node_tree.nodes.new('ShaderNodeBackground')
            world.node_tree.links.new(bg.outputs['Background'], output.inputs['Surface'])
        _background(world)
    except Exception:
        world.use_nodes = False
        raise
    session.history.push(('XR_WORLD_NODE_MODE', scene, world, False, True))
    session.status = 'NATIVE WORLD SHADER ENABLED / UNDO TO DISABLE'


def _edit(session, context, action):
    _scene, world = _active(session, context)
    fog = (action.startswith('XR_FOG_'))
    before = _fog_state(world) if fog else _background_state(world)
    try:
        if action.startswith('XR_WORLD_COLOR_'):
            name = action.removeprefix('XR_WORLD_COLOR_')
            if name == 'PICK':
                value = tuple(float(v) for v in session.settings.object_color[:3]) + (1.0,)
            else:
                if name not in _COLORS:
                    raise ValueError('Unknown World colour')
                value = _COLORS[name]
            if world.use_nodes:
                _, socket, _ = _background(world)
                socket.default_value = value
            world.color = value[:3]
        elif action in {'XR_WORLD_POWER_UP', 'XR_WORLD_POWER_DOWN'}:
            _node, _color, strength = _background(world)
            strength.default_value = max(0.0, min(1000000.0,
                float(strength.default_value) * (1.25 if action.endswith('UP') else .8)))
        elif action == 'XR_FOG_ADD':
            if before is not None:
                raise ValueError('World fog already exists')
            _restore_fog(world, ((.72, .82, .94, 1.0), .02, 0.0))
        elif action in {'XR_FOG_DENSITY_UP', 'XR_FOG_DENSITY_DOWN'}:
            if before is None:
                raise ValueError('Add native fog first')
            color, density, anisotropy = before
            step = .005 if action.endswith('UP') else -.005
            _restore_fog(world, (color, max(0., min(10., density + step)), anisotropy))
        elif action in {'XR_FOG_SCATTER_UP', 'XR_FOG_SCATTER_DOWN'}:
            if before is None:
                raise ValueError('Add native fog first')
            color, density, anisotropy = before
            step = .1 if action.endswith('UP') else -.1
            _restore_fog(world, (color, density, max(-.99, min(.99, anisotropy + step))))
        elif action == 'XR_FOG_COLOR_PICK':
            if before is None:
                raise ValueError('Add native fog first')
            _restore_fog(world, (tuple(session.settings.object_color), before[1], before[2]))
        elif action == 'XR_FOG_TOGGLE':
            if before is None:
                raise ValueError('Add native fog first')
            color, density, anisotropy = before
            new_density = .02 if density < .0001 else 0.0
            _restore_fog(world, (color, new_density, anisotropy))
        elif action == 'XR_FOG_REMOVE':
            if before is None:
                raise ValueError('No native fog to remove')
            _restore_fog(world, None)
        else:
            raise ValueError('Unknown atmosphere control')
    except Exception:
        if fog:
            if not _same(_fog_state(world), before):
                _restore_fog(world, before)
        else:
            if not _same(_background_state(world), before):
                _restore_background(world, before)
        raise
    after = _fog_state(world) if fog else _background_state(world)
    if _same(before, after):
        session.status = 'WORLD UNCHANGED'
        return None
    kind = 'FOG' if fog else 'BACKGROUND'
    entry = ('XR_WORLD_EDIT', context.scene, world, kind, before, after)
    session.history.push(entry)
    session.status = ('WORLD FOG' if fog else 'WORLD BACKGROUND') + _engine_notice(context)
    return entry


def _patch_history():
    if getattr(mesh.History, '_xr_world_atmosphere_patched', False):
        return
    old_step, old_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] in {'XR_WORLD_EDIT', 'XR_WORLD_NODE_MODE'}:
            return
        if entry[0] == 'XR_WORLD_CREATE':
            world = entry[2]
            try:
                if world.users == 0 and bpy.data.worlds.get(world.name) == world:
                    bpy.data.worlds.remove(world)
            except ReferenceError:
                pass
            return
        return old_release(entry)

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] not in {
                'XR_WORLD_EDIT', 'XR_WORLD_CREATE', 'XR_WORLD_NODE_MODE'}:
            return old_step(self, backwards)
        entry = source[-1]
        if bpy.context.mode != 'OBJECT':
            raise ValueError('Return to Object Mode for XR World undo')
        kind = entry[0]
        scene, world = entry[1], entry[2]
        if bpy.context.scene != scene:
            raise ValueError('Original scene changed outside XR World history')
        if kind == 'XR_WORLD_CREATE':
            if backwards:
                if scene.world != world:
                    raise ValueError('World assignment changed outside XR history')
                scene.world = None
            else:
                if scene.world is not None or bpy.data.worlds.get(world.name) != world:
                    raise ValueError('New World was replaced outside XR history')
                scene.world = world
        else:
            if scene.world != world or world.library or world.override_library or world.users != 1:
                raise ValueError('World ownership changed outside XR history')
            if kind == 'XR_WORLD_NODE_MODE':
                expected, wanted = ((True, False) if backwards else (False, True))
                if world.use_nodes != expected:
                    raise ValueError('World node setting changed outside XR history')
                world.use_nodes = wanted
            else:
                _tag, _scene, _world, subsystem, before, after = entry
                now = (_fog_state(world) if subsystem == 'FOG'
                       else _background_state(world))
                if not _same(now, after if backwards else before):
                    raise ValueError('World settings changed outside XR history')
                if subsystem == 'FOG':
                    _restore_fog(world, before if backwards else after)
                else:
                    _restore_background(world, before if backwards else after)
        dest.append(source.pop())
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_world_atmosphere_patched = True


def install_pages():
    # World is part of the existing Lights group, not a new top-level tool.
    original = tuple(menus.PAGES['XR_LIGHT_HOME'])
    if not any(action == 'XR_WORLD_MENU' for _, action in original):
        menus.PAGES['XR_LIGHT_HOME'] = original[:-1] + (
            ('WORLD', 'XR_WORLD_MENU'), original[-1])
    menus.PAGES[_PAGE] = (
        ('NEW WORLD', 'XR_WORLD_NEW'),
        ('NODES ON', 'XR_WORLD_NODES'),
        ('BRIGHT -', 'XR_WORLD_POWER_DOWN'),
        ('BRIGHT +', 'XR_WORLD_POWER_UP'),
        ('COLOR', 'XR_WORLD_COLOR_MENU'),
        ('FOG', 'XR_WORLD_FOG_MENU'),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_COLOR_PAGE] = (
        ('PICKER', 'XR_WORLD_COLOR_PICK'),
        ('WARM', 'XR_WORLD_COLOR_WARM'), ('COOL', 'XR_WORLD_COLOR_COOL'),
        ('DUSK', 'XR_WORLD_COLOR_DUSK'), ('DARK', 'XR_WORLD_COLOR_DARK'),
        ('WHITE', 'XR_WORLD_COLOR_WHITE'), ('BACK', 'BACK'),
    )
    menus.PAGES[_FOG_PAGE] = (
        ('ADD', 'XR_FOG_ADD'), ('DENSITY -', 'XR_FOG_DENSITY_DOWN'),
        ('DENSITY +', 'XR_FOG_DENSITY_UP'), ('ON/OFF', 'XR_FOG_TOGGLE'),
        ('COLOR', 'XR_FOG_COLOR_PICK'),
        ('SCATTER -', 'XR_FOG_SCATTER_DOWN'),
        ('SCATTER +', 'XR_FOG_SCATTER_UP'),
        ('REMOVE', 'XR_FOG_REMOVE'), ('BACK', 'BACK'),
    )
    menus.TITLES.update({_PAGE: 'WORLD LIGHTING',
                         _COLOR_PAGE: 'WORLD COLOUR',
                         _FOG_PAGE: 'WORLD ATMOSPHERE'})
    v065.TOOLTIPS.update({
        'XR_WORLD_MENU': ('World & Atmosphere',
                          'Edit native World background and optional volumetric fog'),
        'XR_WORLD_NODES': ('Enable World Nodes',
                           'Explicitly enable nodes on a simple non-node World'),
        'XR_FOG_ADD': ('Add Native Fog',
                       'Connect an editable Volume Scatter node without changing custom volumes'),
        'XR_FOG_TOGGLE': ('Toggle Native Fog',
                          'Set volume density to zero or a small preset'),
        'XR_WORLD_COLOR_PICK': ('Apply Colour Picker',
                                'Apply the existing XR colour preview to World background'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_world_atmosphere_patched', False):
        return
    _patch_history()
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous_command(self, context, action)
        page = menu.page
        if action == 'XR_WORLD_MENU':
            if any(getattr(self, f, None) for f in (
                    'transaction', 'grab', 'air_grab', 'axis_move',
                    '_xr_gesture', '_xr_curve_pending', '_xr_light_pending',
                    'bone_drag')):
                raise ValueError('Finish the active XR interaction before editing World')
            if context.scene.world is None:
                self._xr_world_target = None
                menu.page = _PAGE
                self.status = 'NO WORLD / PRESS NEW WORLD'
            else:
                _world_open(self, context)
            return
        if page == _PAGE and action == 'XR_WORLD_NEW':
            _world_create(self, context)
            return
        if action == 'BACK' and page in {_PAGE, _COLOR_PAGE, _FOG_PAGE}:
            if page == _PAGE:
                menu.page = 'XR_LIGHT_HOME'
            else:
                menu.page = _PAGE
            return
        if page not in {_PAGE, _COLOR_PAGE, _FOG_PAGE}:
            return previous_command(self, context, action)
        if action == 'XR_WORLD_COLOR_MENU':
            _active(self, context)
            menu.page = _COLOR_PAGE
            return
        if action == 'XR_WORLD_FOG_MENU':
            _active(self, context)
            menu.page = _FOG_PAGE
            self.status = 'FOG / NATIVE VOLUME' + _engine_notice(context)
            return
        if action == 'XR_WORLD_NODES':
            _nodes_on(self, context)
            return
        if action.startswith('XR_WORLD_') or action.startswith('XR_FOG_'):
            _edit(self, context, action)
            return
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_world_atmosphere_patched = True
