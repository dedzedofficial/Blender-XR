# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded controller-driven IK positioning of native Blender PoseBones.

This solver rotates a short existing bone chain directly in Pose Mode. It
creates no temporary Empty objects, constraints, rest-bone edits, or custom
project data. Interaction_v076 owns gesture cancel and XR history.
"""
import math

from mathutils import Matrix, Quaternion, Vector


def _finite_vector(value):
    return all(math.isfinite(float(v)) for v in value)


def pose_chain(obj, count):
    """Return proximal-to-distal unlocked pose bones ending at active bone."""
    if obj is None or obj.type != 'ARMATURE' or obj.mode != 'POSE':
        raise ValueError('Enter Armature Pose Mode to use direct IK')
    if (obj.library or obj.override_library or obj.data.library or
            obj.data.override_library or obj.hide_select):
        raise ValueError('Use a local unlocked armature for IK posing')
    if obj.data.bones.active is None:
        raise ValueError('Select the IK endpoint bone first')
    active = obj.pose.bones.get(obj.data.bones.active.name)
    if active is None:
        raise ValueError('The selected pose bone is unavailable')
    chain = []
    while active is not None and len(chain) < int(count):
        if active.bone.hide or active.bone.hide_select:
            raise ValueError('Reveal and unlock the entire IK chain')
        if (active.constraints or any(active.lock_rotation) or
                getattr(active, 'lock_rotation_w', False)):
            raise ValueError('IK chain uses locked or constrained bones')
        chain.append(active)
        active = active.parent
    if len(chain) < 2:
        raise ValueError('Direct IK requires a bone with a parent')
    chain.reverse()
    if not _finite_vector(obj.pose.bones[chain[-1].name].tail):
        raise ValueError('IK endpoint has an invalid pose')
    return tuple(bone.name for bone in chain)


def chain_snapshot(obj, names):
    """Store native armature-space pose matrices for one XR transaction."""
    return {name: obj.pose.bones[name].matrix.copy() for name in names}


def solve_pose_chain(context, obj, drag, world_target):
    """A limited CCD pass for a controller-driven 2/3-bone chain.

    The input gesture layer has already preflighted original bone matrices,
    object identity, and current XR poses before calling this solver. Each
    update starts from the exact baseline, so the same controller position
    always produces the same pose, even after interrupted motion.
    """
    names = drag['ik_chain']
    target = obj.matrix_world.inverted_safe() @ Vector(world_target)
    if not _finite_vector(target):
        raise ValueError('Controller IK target has invalid coordinates')

    bones = obj.pose.bones
    for name in names:
        bones[name].matrix = drag['before'][name].copy()
    context.view_layer.update()

    tip_name = names[-1]
    # A few short passes avoid long blocking dependency-graph evaluations
    # inside headset frames; more subtle movement improves across frames.
    for _ in range(5):
        if (bones[tip_name].tail - target).length <= .002:
            break
        moved = False
        # Rotate both the endpoint and its ancestors, so a two-bone chain
        # has two controllable joints rather than acting like a rigid arm.
        for name in reversed(names):
            joint = bones[name]
            joint_pos = joint.head.copy()
            to_tip = bones[tip_name].tail - joint_pos
            to_target = target - joint_pos
            if to_tip.length_squared < 1e-10 or to_target.length_squared < 1e-10:
                continue
            rotation = to_tip.rotation_difference(to_target)
            angle = rotation.angle
            if not math.isfinite(angle) or angle < 1e-5:
                continue
            if angle > .45:
                rotation = Quaternion(rotation.axis, .45)
            change = (Matrix.Translation(joint_pos) @
                      rotation.to_matrix().to_4x4() @
                      Matrix.Translation(-joint_pos))
            joint.matrix = change @ joint.matrix
            context.view_layer.update()
            moved = True
            if (bones[tip_name].tail - target).length <= .002:
                break
        if not moved:
            break
    if any(not _finite_vector(row) for name in names
           for row in bones[name].matrix):
        raise ValueError('IK produced an invalid pose matrix')
    return (bones[tip_name].tail - target).length
