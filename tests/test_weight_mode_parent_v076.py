"""v0.7.6 Blender native Weight Paint mode + Ctrl+P armature parenting."""
import sys
from pathlib import Path
from types import SimpleNamespace
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import blender_xr
from blender_xr import drawing, menus, rigging_v076, runtime

def _reset():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def _cube_and_rig():
    bpy.ops.mesh.primitive_cube_add()
    mesh = bpy.context.object
    mesh.scale = (1.5, 0.8, 0.3)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assert 'FINISHED' in bpy.ops.blender_xr.create_basic_rig()
    rig = bpy.context.object
    assert rig.type == 'ARMATURE'
    return mesh, rig

def _session():
    session = runtime.Runtime.__new__(runtime.Runtime)
    session.menu = SimpleNamespace(page='TOOLS')
    session.tool = 'SELECT'
    session.settings = bpy.context.scene.blender_xr
    session.transaction = session.grab = session.air_grab = session.axis_move = None
    session.status = ''
    return session

def run():
    assert blender_xr.VERSION == (0, 7, 6)
    blender_xr.register()
    try:
        s = _session()
        _reset()
        mesh, rig = _cube_and_rig()
        assert 'MODE_WEIGHT_PAINT' in [a for _,a in menus.PAGES['MODE_SELECT']]
        assert 'PARENT_MENU' in [a for _,a in menus.PAGES['RIGGING']]
        assert {'PARENT_AUTO','PARENT_EMPTY','PARENT_ENVELOPE','PARENT_ARMATURE',
                'PARENT_OBJECT','PARENT_CLEAR'} <= {
                a for _,a in menus.PAGES['PARENT_RIG']}
        for page in ('MODE_SELECT','PARENT_RIG','WEIGHT_PAINT'):
            entries = menus.PAGES[page]
            actions = [a for _,a in entries]
            assert len(entries) <= 12 and len(actions) == len(set(actions))
            assert all(drawing._ICON_BY_ACTION.get(a) for a in actions)

        # Ctrl+P: Empty Groups. Mesh world transform preserved.
        start = mesh.matrix_world.copy()
        s.command(bpy.context, 'PARENT_MENU')
        assert s.menu.page == 'PARENT_RIG'
        s.command(bpy.context, 'PARENT_EMPTY')
        assert mesh.parent == rig
        assert any(mod.type == 'ARMATURE' and mod.object == rig
                   for mod in mesh.modifiers)
        assert mesh.vertex_groups.get('Bone')
        assert all(abs(start[i][j]-mesh.matrix_world[i][j]) < 1e-5
                   for i in range(4) for j in range(4))
        assert s.menu.page == 'RIGGING'

        # Weight Paint through *Mode* picker, even with an active armature.
        s.command(bpy.context, 'MODE_WEIGHT_PAINT')
        assert mesh.mode == 'WEIGHT_PAINT' and s.menu.page == 'WEIGHT_PAINT'
        assert s.tool == 'WEIGHT_BRUSH'
        assert bpy.context.active_object == mesh
        assert mesh.vertex_groups.active is not None
        s.command(bpy.context, 'WEIGHT_ERASE')
        assert s.settings.weight_erase
        s.command(bpy.context, 'WEIGHT_BRUSH')
        assert not s.settings.weight_erase

        before = mesh.vertex_groups.active
        hit = rigging_v076.paint_vertices(
            mesh, Vector((0,-4,0)), Vector((0,1,0)), .32, .95)
        assert hit > 0
        group = mesh.vertex_groups.active
        assert any(any(w.group == group.index and w.weight > 0
                   for w in vert.groups) for vert in mesh.data.vertices)
        # Paint from the back too; verify erasing actually changes weights.
        index = next(v.index for v in mesh.data.vertices if any(
            w.group == group.index and w.weight > 0 for w in v.groups))
        prior = group.weight(index)
        assert rigging_v076.paint_vertices(
            mesh, Vector((0,-4,0)), Vector((0,1,0)), 2.0, .85, erase=True) > 0
        assert group.weight(index) < prior

        s.command(bpy.context, 'MODE_OBJECT')
        assert mesh.mode == 'OBJECT' and s.menu.page == 'TOOLS'
        assert s.tool == 'SELECT'

        # Re-entering Mode via the popup is symmetrical and never reparents.
        s.command(bpy.context, 'MODE_MENU')
        assert s.menu.page == 'MODE_SELECT'
        s.command(bpy.context, 'MODE_WEIGHT_PAINT')
        assert mesh.mode == 'WEIGHT_PAINT'
        s.command(bpy.context, 'RIG_EXIT_PAINT')
        assert mesh.mode == 'OBJECT'

        # Preserve groups/weight paint when parenting is requested twice.
        state = {v.index: tuple((x.group, round(x.weight,5)) for x in v.groups)
                 for v in mesh.data.vertices}
        s.command(bpy.context, 'PARENT_EMPTY')
        assert state == {v.index: tuple((x.group, round(x.weight,5)) for x in v.groups)
                         for v in mesh.data.vertices}

        # Blender Ctrl+P Object type also works without inventing weights.
        s.command(bpy.context, 'PARENT_CLEAR')
        assert mesh.parent is None
        s.command(bpy.context, 'PARENT_OBJECT')
        assert mesh.parent == rig
        assert state == {v.index: tuple((x.group, round(x.weight,5)) for x in v.groups)
                         for v in mesh.data.vertices}
        s.command(bpy.context, 'PARENT_CLEAR')
        assert mesh.parent is None

        # Native Armature Deform and Envelope types remain available.
        for method in ('PARENT_ARMATURE','PARENT_ENVELOPE'):
            s.command(bpy.context, method)
            assert mesh.parent == rig, method
            s.command(bpy.context, 'PARENT_CLEAR')
            assert mesh.parent is None

        # Automatic Weights works on a separate ordinary cube.
        _reset()
        auto_mesh, auto_arm = _cube_and_rig()
        s.command(bpy.context, 'PARENT_AUTO')
        assert auto_mesh.parent == auto_arm
        assert auto_mesh.vertex_groups
        assert sum(group.weight(v.index) for group in auto_mesh.vertex_groups
                   for v in auto_mesh.data.vertices
                   if any(item.group == group.index for item in v.groups)) > 0
        print('PASS 0.7.6 native Weight Paint mode, real brush and Blender parent variants')
    finally:
        _reset()
        blender_xr.unregister()

if __name__ == '__main__':
    run()
