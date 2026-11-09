"""Blender runtime tests for v0.7.6 armature ray selection and bone editing."""
import sys
from pathlib import Path
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy
import blender_xr
from blender_xr import armature_v076, menus, drawing, runtime


def test():
    assert blender_xr.VERSION >= (0, 7, 6)
    blender_xr.register()
    try:
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_cube_add()
        mesh = bpy.context.object
        mesh.name = 'Armature XR Test Mesh'
        mesh.scale = (2.0, 1.0, 0.2)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        assert 'FINISHED' in bpy.ops.blender_xr.create_basic_rig()
        arm = bpy.context.view_layer.objects.active
        assert arm and arm.type == 'ARMATURE' and arm.show_in_front
        assert armature_v076.activate_armature(bpy.context) is arm

        center = arm.matrix_world @ arm.data.bones[0].head.lerp(
            arm.data.bones[0].tail, 0.5)
        origin = center + Vector((0, -3, 0))
        direction = Vector((0, 1, 0))
        picked = armature_v076.ray_pick_bone(bpy.context, origin, direction)
        assert picked is not None and picked[2] is arm, picked
        assert picked[3] == 'Bone'
        empty = armature_v076.ray_pick_bone(
            bpy.context, origin + Vector((0, 0, 3)), direction)
        assert empty is None

        # VR object's picker must select armature bones; previous code only
        # called scene.ray_cast and therefore ignored non-mesh rigs entirely.
        sess = runtime.Runtime.__new__(runtime.Runtime)
        hit = sess.object_hit(bpy.context, origin, direction)
        assert hit is not None and hit[0] is arm, hit
        assert 'FINISHED' in bpy.ops.blender_xr.edit_bones()
        assert arm.mode == 'EDIT'

        edit = armature_v076.pick_edit_bone(bpy.context, origin, direction)
        assert edit and edit[0].name == 'Bone'
        assert arm.data.edit_bones.active.name == edit[0].name
        assert armature_v076.perform_edit_action(bpy.context, 'BONE_SEL_NONE')
        assert not any(item.select for item in arm.data.edit_bones)
        assert armature_v076.perform_edit_action(bpy.context, 'BONE_SEL_ALL')
        assert all(item.select for item in arm.data.edit_bones)

        picked_bone = arm.data.edit_bones.active
        initial_head = picked_bone.head.copy()
        initial_tail = picked_bone.tail.copy()
        drag = {
            'bone': picked_bone.name,
            'head': initial_head,
            'tail': initial_tail,
            'origin': Vector((0, 0, 0)),
            'part': 'BODY',
        }
        armature_v076.step_bone_drag(arm, drag, Vector((0.2, 0, 0)))
        assert (picked_bone.head - initial_head).length > .1
        assert (picked_bone.tail - initial_tail).length > .1
        picked_bone.head = initial_head
        picked_bone.tail = initial_tail

        assert armature_v076.perform_edit_action(bpy.context, 'BONE_SUBDIVIDE')
        assert len(arm.data.edit_bones) == 2
        assert armature_v076.perform_edit_action(bpy.context, 'BONE_SEL_ALL')
        assert armature_v076.perform_edit_action(bpy.context, 'BONE_ROLL_UP')
        assert armature_v076.perform_edit_action(bpy.context, 'BONE_DEFORM')

        assert 'FINISHED' in bpy.ops.blender_xr.finish_bones()
        assert arm.mode == 'OBJECT'
        assert len(arm.data.bones) == 2
        # All in-headset armature pages are icon mapped, with bounded height.
        for page, buttons in armature_v076.ARMATURE_PAGES.items():
            assert 0 < len(buttons) <= 12, (page, len(buttons))
            for label, action in buttons:
                assert drawing._ICON_BY_ACTION.get(action), (page, action)
        assert armature_v076.PAGES_RETURN['ARMATURE_OPERATIONS'] == 'ARMATURE_EDIT'
        assert [action for _, action in menus.PAGES['RIGGING']].count('SELECT') == 1

        # Reproduce the original complaint: an active mesh and one rig can
        # recover the armature, even when there is no editable bone selected.
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        mesh.select_set(True)
        bpy.context.view_layer.objects.active = mesh
        assert 'FINISHED' in bpy.ops.blender_xr.select_armature()
        assert bpy.context.view_layer.objects.active is arm
        print('PASS Mesh XR 0.7.6 armature ray selection and edit-mode tools')
    finally:
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        blender_xr.unregister()


if __name__ == '__main__':
    test()
