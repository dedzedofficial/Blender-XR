"""Blender v0.7.6: one Select tool; grip/trigger transforms in every mode."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import bmesh
from mathutils import Quaternion, Vector
from blender_xr import interaction_v076 as interaction
from blender_xr import menus, selection, mesh as mesh_core
import blender_xr

Q = Quaternion((1, 0, 0, 0))


def test():
    assert blender_xr.VERSION >= (0, 7, 6)
    blender_xr.register()
    try:
        for page, items in menus.PAGES.items():
            actions = [action for _label, action in items if action != 'PANEL']
            assert len(actions) == len(set(actions)), (page, actions)
        for page in ('TOOLS', 'RIGGING', 'ARMATURE_EDIT', 'POSE_EDIT'):
            assert [action for _, action in menus.PAGES[page]].count('SELECT') == 1
        for page, items in menus.PAGES.items():
            assert not any(action in {'RIG_SELECT_MESH', 'RIG_SELECT_ARMATURE'}
                           for label, action in items), page
        for a in ('MOVE', 'SCALE', 'ROTATE'):
            assert any(action == a for _, action in menus.PAGES['TOOLS'])
        for a in ('MOVE_EDIT', 'SCALE_EDIT', 'ROTATE_EDIT'):
            assert any(action == a for _, action in menus.PAGES['EDIT'])
        for a in ('BONE_MOVE', 'BONE_SCALE', 'BONE_ROTATE'):
            assert any(action == a for _, action in menus.PAGES['ARMATURE_EDIT'])
            assert any(action == a for _, action in menus.PAGES['POSE_EDIT'])
        assert [action for _, action in menus.PAGES['POSE_EDIT']].count('RIG_EXIT_POSE') == 1

        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.object
        bpy.ops.object.mode_set(mode='EDIT')
        selection.set_mode(bpy.context, 'VERT')
        bm = bmesh.from_edit_mesh(cube.data)
        for v in bm.verts:
            v.select_set(False)
        bmesh.update_edit_mesh(cube.data, loop_triangles=False, destructive=False)
        vert = next(v for v in bm.verts if v.co.x > .5 and v.co.y < -.5 and v.co.z > .5)
        vertex_world = cube.matrix_world @ vert.co.copy()
        origin = vertex_world + Vector((0, -2.0, 0))
        pick = interaction.ray_element(cube, origin, Vector((0, 1, 0)), 'VERT', radius=.04)
        assert pick and pick[0] == vert.index, pick
        selected = interaction.select_mesh_element(
            bpy.context, origin, Vector((0,1,0)))
        assert selected and selected[0] == vert.index
        assert len(selection.selected_indices(cube, 'VERT')) == 1

        original_co = vert.co.copy()
        gesture = interaction.begin_transform(
            bpy.context, 'MOVE_FACE', origin, Q, source='grip')
        interaction.update_transform(bpy.context, gesture,
                                     origin + Vector((.27, 0, 0)), Q)
        assert abs(vert.co.x - (original_co.x + .27)) < 1e-5
        history = mesh_core.History()
        interaction._push_transform_history(type('Session', (), {'history': history})(),
                                            bpy.context, gesture)
        assert history.undo and history.undo[-1][0] == 'XR_VERTS'
        assert history.step(True) and abs(vert.co.x - original_co.x) < 1e-5
        assert history.step(False) and abs(vert.co.x - original_co.x - .27) < 1e-5
        history.clear()
        interaction.restore_transform(bpy.context, gesture)
        assert (vert.co - original_co).length < 1e-6
        gesture = interaction.begin_transform(
            bpy.context, 'SCALE_FACE', origin, Q, source='trigger')
        # Select an additional vertex for nonzero extent.
        another = next(v for v in bm.verts if v != vert and v.co.z > .5)
        another.select_set(True)
        bmesh.update_edit_mesh(cube.data, loop_triangles=False, destructive=False)
        gesture = interaction.begin_transform(
            bpy.context, 'SCALE_FACE', origin, Q, source='trigger')
        original_span = (vert.co - another.co).length
        interaction.update_transform(bpy.context, gesture,
                                     origin + Vector((0, -.4, 0)), Q)
        assert (vert.co - another.co).length > original_span + .05
        interaction.restore_transform(bpy.context, gesture)
        gesture = interaction.begin_transform(
            bpy.context, 'ROTATE_EDIT', origin, Q, source='trigger')
        original_verts = {v.index: v.co.copy() for v in (vert, another)}
        interaction.update_transform(
            bpy.context, gesture, origin,
            Quaternion((.9238795325, 0, 0, .3826834324)))
        assert any((bm.verts[i].co - co).length > .1
                   for i, co in original_verts.items())
        interaction.restore_transform(bpy.context, gesture)

        bpy.ops.object.mode_set(mode='OBJECT')
        matrix_before = cube.matrix_world.copy()
        gesture = interaction.begin_transform(
            bpy.context, 'MOVE', Vector((1,0,0)), Q)
        interaction.update_transform(bpy.context, gesture, Vector((1,.5,0)), Q)
        assert abs(cube.matrix_world.translation.y - .5) < 1e-5
        interaction.restore_transform(bpy.context, gesture)
        assert (cube.matrix_world.translation - matrix_before.translation).length < 1e-5
        gesture = interaction.begin_transform(
            bpy.context, 'ROTATE', Vector((1,0,0)), Q)
        interaction.update_transform(
            bpy.context, gesture, Vector((1,0,0)),
            Quaternion((.9238795325, 0, 0, .3826834324)))
        assert abs(cube.rotation_euler.z) > .2
        interaction.restore_transform(bpy.context, gesture)
        gesture = interaction.begin_transform(
            bpy.context, 'SCALE', Vector((2,0,0)), Q)
        interaction.update_transform(bpy.context, gesture, Vector((3,0,0)), Q)
        assert cube.scale.length > Vector((1,1,1)).length
        interaction.restore_transform(bpy.context, gesture)

        assert 'FINISHED' in bpy.ops.blender_xr.create_basic_rig()
        arm = bpy.context.object
        arm_before = arm.matrix_world.copy()
        gesture = interaction.begin_transform(
            bpy.context, 'ROTATE', Vector((1,0,0)), Q)
        interaction.update_transform(
            bpy.context, gesture, Vector((1,0,0)),
            Quaternion((.9238795325, 0, 0, .3826834324)))
        assert sum((arm.matrix_world[i][j] - arm_before[i][j]) ** 2 for i in range(4) for j in range(4)) > .04
        interaction.restore_transform(bpy.context, gesture)
        assert 'FINISHED' in bpy.ops.blender_xr.edit_bones()
        bone = arm.data.edit_bones[0]
        bone.select = True
        arm.data.edit_bones.active = bone
        original_length = bone.length
        start = (arm.matrix_world @ ((bone.head + bone.tail) * .5)) + Vector((1, 0, 0))
        gesture = interaction.begin_transform(
            bpy.context, 'BONE_SCALE', start, Q, source='grip')
        interaction.update_transform(
            bpy.context, gesture, start + Vector((1,0,0)), Q)
        assert bone.length > original_length * 1.4
        interaction.restore_transform(bpy.context, gesture)
        assert abs(bone.length - original_length) < 1e-5
        gesture = interaction.begin_transform(
            bpy.context, 'BONE_ROTATE', start, Q, source='trigger')
        old_tip = bone.tail.copy()
        interaction.update_transform(
            bpy.context, gesture, start,
            Quaternion((.9238795325, 0, 0, .3826834324)))
        assert (bone.tail - old_tip).length > .04
        interaction.restore_transform(bpy.context, gesture)
        assert (bone.tail - old_tip).length < 1e-5
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='POSE')
        pose = arm.pose.bones[0]
        if hasattr(pose.bone, 'select'):
            pose.bone.select = True
        arm.data.bones.active = pose.bone
        old_pose = pose.matrix.copy()
        gesture = interaction.begin_transform(
            bpy.context, 'BONE_MOVE', Vector((1,0,0)), Q)
        interaction.update_transform(
            bpy.context, gesture, Vector((1,.2,0)), Q)
        assert (pose.matrix.translation - old_pose.translation).length > .1
        history = mesh_core.History()
        interaction._push_transform_history(type('Session', (), {'history': history})(),
                                            bpy.context, gesture)
        assert history.undo and history.undo[-1][0] == 'XR_POSE'
        assert history.step(True)
        assert (pose.matrix.translation - old_pose.translation).length < 1e-4
        assert history.step(False)
        assert (pose.matrix.translation - old_pose.translation).length > .1
        history.clear()
        interaction.restore_transform(bpy.context, gesture)
        bpy.ops.object.mode_set(mode='OBJECT')
        print('PASS 0.7.6 unified Select and controller mesh, object, armature, pose transforms')
    finally:
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        blender_xr.unregister()


if __name__ == '__main__':
    test()
