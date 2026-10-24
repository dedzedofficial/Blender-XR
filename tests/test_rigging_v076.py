"""Blender integration: object selection, armature pairs, weight groups, VR brush.

This test deliberately alternates Object / Armature Edit / Weight Paint / Pose /
Mesh Edit modes, reproducing the two reported 0.7.6 headset blockers.
"""
import sys
from pathlib import Path
from mathutils import Vector, Quaternion
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy
import blender_xr
from blender_xr import armature_v076, drawing, menus, rigging_v076, runtime


def main():
    assert blender_xr.VERSION == (0, 7, 6)
    blender_xr.register()
    try:
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        obj.name = 'VR rigging target'
        obj.scale = (1.5, 0.5, 0.3)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        assert 'FINISHED' in bpy.ops.blender_xr.create_basic_rig()
        rig = bpy.context.view_layer.objects.active
        assert rig.type == 'ARMATURE'
        assert rig.get('mesh_xr_target_mesh') == obj.name
        assert rigging_v076.mesh_for_rig(bpy.context, rig) == obj

        # The old Select Rig button cleared the target mesh, leaving binding
        # unable to find a selected mesh and Weight Paint without groups.
        for selected in bpy.context.selected_objects:
            selected.select_set(False)
        rig.select_set(True)
        bpy.context.view_layer.objects.active = rig
        session = runtime.Runtime.__new__(runtime.Runtime)
        session.menu = SimpleNamespace(page='RIGGING')
        session.tool = 'SELECT'
        session.status = ''
        session.settings = bpy.context.scene.blender_xr
        session.transaction = session.grab = session.air_grab = session.axis_move = None

        session.command(bpy.context, 'RIG_SELECT_MESH')
        assert bpy.context.view_layer.objects.active == obj
        session.command(bpy.context, 'RIG_SELECT_ARMATURE')
        assert bpy.context.view_layer.objects.active == rig
        assert obj.select_get() and rig.select_get()
        session.command(bpy.context, 'RIG_BIND_EMPTY')
        assert obj.parent == rig
        assert obj.vertex_groups.active is not None
        assert obj.vertex_groups.active.name == rig.data.bones[0].name

        # Enter, exit and re-enter native armature Edit Mode while retaining
        # the target mesh. No extra desktop Shift-selection required.
        session.command(bpy.context, 'RIG_EDIT_TOGGLE')
        assert rig.mode == 'EDIT'
        session.command(bpy.context, 'BONE_SEL_ALL')
        session.command(bpy.context, 'RIG_EDIT_TOGGLE')
        assert rig.mode == 'OBJECT'
        session.command(bpy.context, 'RIG_WEIGHT')
        assert obj.mode == 'WEIGHT_PAINT'
        assert obj.vertex_groups.active is not None
        assert session.menu.page == 'WEIGHT_PAINT'
        session.command(bpy.context, 'WEIGHT_BRUSH')

        # Paint a ray at the cube's front surface onto the real native vertex
        # group, and verify Blender sees the resulting vertex weights.
        origin = Vector((0, -3, 0))
        direction = Vector((0, 1, 0))
        count = rigging_v076.paint_vertices(obj, origin, direction, 1.0, 0.6)
        assert count > 0, 'Controller brush could not reach mesh'
        group = obj.vertex_groups.active
        weighted = [vert.index for vert in obj.data.vertices
                    if any(item.group == group.index and item.weight > 0
                           for item in vert.groups)]
        assert weighted, 'Weight Paint did not write native vertex groups'
        count = rigging_v076.paint_vertices(obj, origin, direction, 1.0, 0.5, erase=True)
        assert count > 0
        session.command(bpy.context, 'WEIGHT_GROUP_NEXT')
        assert obj.vertex_groups.active is not None
        session.command(bpy.context, 'WEIGHT_STRENGTH_UP')
        session.command(bpy.context, 'WEIGHT_RADIUS_DOWN')
        session.command(bpy.context, 'RIG_EXIT_PAINT')
        assert obj.mode == 'OBJECT'
        before_weights = {v.index: tuple((item.group, round(item.weight, 4))
                                         for item in v.groups)
                          for v in obj.data.vertices}
        session.command(bpy.context, 'RIG_BIND_EMPTY')
        assert obj.parent == rig
        assert before_weights == {v.index: tuple(
            (item.group, round(item.weight, 4)) for item in v.groups
        ) for v in obj.data.vertices}, 'Repeated binding destroyed painted weights'

        # The mesh/rigger may now switch to Pose and back without manually
        # reconstructing a temporary multi-object selection.
        session.command(bpy.context, 'RIG_POSE')
        assert rig.mode == 'POSE'
        session.command(bpy.context, 'RIG_POSE')
        assert rig.mode == 'OBJECT'
        session.command(bpy.context, 'RIG_SELECT_MESH')
        assert bpy.context.view_layer.objects.active == obj
        session.command(bpy.context, 'RIG_SELECT_ARMATURE')
        assert bpy.context.view_layer.objects.active == rig
        session.command(bpy.context, 'RIG_CLEAN')
        assert bpy.context.view_layer.objects.active == obj
        assert obj.mode == 'OBJECT'

        # Original mesh editor still works after rigging has been active.
        for selected in bpy.context.selected_objects:
            selected.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        assert 'FINISHED' in bpy.ops.object.mode_set(mode='EDIT')
        assert obj.mode == 'EDIT'
        bpy.ops.object.mode_set(mode='OBJECT')

        assert len(menus.PAGES['RIGGING']) <= 12
        assert len(menus.PAGES['WEIGHT_PAINT']) <= 12
        for page in ('RIGGING', 'WEIGHT_PAINT'):
            for _, action in menus.PAGES[page]:
                icon = drawing._ICON_BY_ACTION.get(action)
                assert icon and (Path(drawing.__file__).parent / 'icons' / (icon + '.png')).is_file(), (page, action)
        print('PASS v0.7.6 paired selection, bind, group, VR brush, mode coexistence')
    finally:
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        blender_xr.unregister()


if __name__ == '__main__':
    main()
