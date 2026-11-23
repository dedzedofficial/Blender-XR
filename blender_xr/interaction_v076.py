# SPDX-License-Identifier: GPL-3.0-or-later
"""Single Blender-style XR selection and controller transforms, 0.7.6.

Select always picks the object / mesh element / bone appropriate to Blender
mode. Trigger on a transform tool or Grip while selecting starts an undoable
controller transform. This is deliberately separate from topology tools.
"""
import math

import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

from . import armature_v076, mesh, selection, rigging_v076

TRANSFORMS = {'MOVE', 'SCALE', 'ROTATE', 'MOVE_FACE', 'SCALE_FACE',
              'ROTATE_EDIT', 'BONE_MOVE', 'BONE_MOVE_HEAD',
              'BONE_MOVE_TAIL', 'BONE_SCALE', 'BONE_ROTATE',
              'BONE_IK_2', 'BONE_IK_3'}
MOVE = {'MOVE', 'MOVE_FACE', 'BONE_MOVE', 'BONE_MOVE_HEAD', 'BONE_MOVE_TAIL'}
SCALE = {'SCALE', 'SCALE_FACE', 'BONE_SCALE'}
ROTATE = {'ROTATE', 'ROTATE_EDIT', 'BONE_ROTATE'}


def ray_element(obj, origin, direction, mode, radius=0.075):
    """Pick visible edit-cage elements with stable BMesh indices.

    Compare candidates in world space, including loose geometry. Invalid or
    degenerate controller rays must never select a nearby arbitrary element.
    """
    if obj is None or obj.type != 'MESH' or obj.mode != 'EDIT':
        return None
    if mode not in {'VERT', 'EDGE', 'FACE'}:
        return None
    origin, direction = Vector(origin), Vector(direction)
    if not all(math.isfinite(v) for v in (*origin, *direction)):
        return None
    if direction.length_squared < 1e-12:
        return None
    direction.normalize()
    if not math.isfinite(radius) or radius <= 0:
        return None
    if mode == 'FACE':
        return mesh.element_hit(obj, origin, direction, 'FACE')

    # The first visible edit-cage surface bounds depth selection. Keep a
    # world-space tolerance for vertices and edges lying on that surface;
    # loose geometry remains selectable when there is no face hit.
    surface = mesh.face_hit(obj, origin, direction)
    surface_depth = None
    if surface is not None:
        surface_point = Vector(surface[1])
        if all(math.isfinite(v) for v in surface_point):
            depth = (surface_point - origin).dot(direction)
            if depth > 0:
                surface_depth = depth

    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    bm.edges.ensure_lookup_table()
    bm.edges.index_update()
    candidates = []
    if mode == 'VERT':
        for vert in bm.verts:
            if not vert.is_valid or vert.hide:
                continue
            world = obj.matrix_world @ vert.co
            if not all(math.isfinite(v) for v in world):
                continue
            along = (world - origin).dot(direction)
            if along <= 0:
                continue
            distance = (origin + along * direction - world).length
            if distance <= max(radius, along * .013):
                candidates.append((along, distance, vert.index, world.copy()))
    else:
        for edge in bm.edges:
            if not edge.is_valid or edge.hide or any(v.hide for v in edge.verts):
                continue
            start = obj.matrix_world @ edge.verts[0].co
            end = obj.matrix_world @ edge.verts[1].co
            if not all(math.isfinite(v) for v in (*start, *end)):
                continue
            hit = armature_v076._closest_segment(origin, direction, start, end)
            if hit and hit[1] > 0 and math.isfinite(hit[0]) and math.isfinite(hit[1]):
                if hit[0] <= max(radius, hit[1] * .013):
                    candidates.append((hit[1], hit[0], edge.index, hit[2]))
    if surface_depth is not None:
        # A small allowance preserves surface-boundary picking at grazing
        # angles without selecting elements behind the frontmost face.
        candidates = [item for item in candidates
                      if item[0] <= surface_depth + max(radius, surface_depth * .013)]
    if candidates:
        # Depth first, then distance to ray and stable cage index.
        best = min(candidates, key=lambda item: (item[0], item[1], item[2]))
        return best[2], best[3]
    # A fallback may only select geometry within the same controller radius.
    # In particular, do not select a distant face corner just because the
    # controller ray happened to intersect the middle of a large polygon.
    fallback = mesh.element_hit(obj, origin, direction, mode)
    if fallback is None:
        return None
    point = Vector(fallback[1])
    if not all(math.isfinite(v) for v in point):
        return None
    depth = (point - origin).dot(direction)
    if depth <= 0 or (surface_depth is not None and
                      depth > surface_depth + max(radius, surface_depth * .013)):
        return None
    distance = (point - (origin + depth * direction)).length
    if distance > max(radius, depth * .013):
        return None
    return fallback


def select_mesh_element(context, origin, direction, additive=False):
    obj = context.view_layer.objects.active
    mode = selection.mode(context)
    hit = ray_element(obj, Vector(origin), Vector(direction), mode)
    if not hit:
        return None
    mesh.select_element(obj, mode, hit[0], additive)
    return hit


def choose_object(context, origin, direction, old_hit):
    """Clicking the same overlapping bone/mesh a second time switches target."""
    hit = old_hit(context, origin, direction)
    mesh_target = None
    raw = context.scene.ray_cast(context.evaluated_depsgraph_get(), origin, direction)
    if raw[0] and raw[4].original.type == 'MESH' and raw[4].original.visible_get():
        mesh_target = (raw[4].original, raw[1])
    arm_target = armature_v076.ray_pick_bone(context, origin, direction)
    active = context.view_layer.objects.active
    if arm_target and mesh_target:
        arm, point = arm_target[2], arm_target[4]
        if active == arm:
            # A rig displayed in front of its skinned mesh must not trap
            # selection: a second click can select that underlying mesh.
            return mesh_target
        if active == mesh_target[0]:
            return arm, point
    return hit or mesh_target


def select_context(session, context, origin, direction, additive=False, old_hit=None):
    obj = context.view_layer.objects.active
    if obj is not None and obj.type == 'MESH' and obj.mode == 'EDIT':
        hit = select_mesh_element(context, origin, direction, additive=additive)
        session.status = 'SELECTED ' + selection.mode(context) if hit else 'AIM AT VERTEX / EDGE / FACE'
        return hit
    if obj is not None and obj.type == 'ARMATURE' and obj.mode == 'EDIT':
        hit = armature_v076.pick_edit_bone(context, origin, direction, additive=additive)
        session.status = 'SELECTED BONE ' + hit[0].name if hit else 'AIM AT A BONE'
        return hit
    if obj is not None and obj.type == 'ARMATURE' and obj.mode == 'POSE':
        hit = armature_v076.ray_pick_bone(context, origin, direction, only_active=True)
        if not hit:
            session.status = 'AIM AT POSE BONE'
            return None
        for bone in obj.data.bones:
            if not additive and hasattr(bone, 'select'):
                bone.select = False
        bone = obj.data.bones.get(hit[3])
        if hasattr(bone, 'select'):
            bone.select = True
        obj.data.bones.active = bone
        session.status = 'POSE BONE ' + bone.name
        return hit
    if old_hit is None:
        old_hit = session.object_hit
    hit = choose_object(context, origin, direction, old_hit)
    if not hit:
        session.status = 'AIM AT MESH OR ARMATURE'
        return None
    target, point = hit
    previous = obj
    previous_mesh = previous if previous and previous.type == 'MESH' else None
    previous_arm = previous if previous and previous.type == 'ARMATURE' else None
    if not additive:
        for selected in context.selected_objects:
            selected.select_set(False)
    target.select_set(True)
    context.view_layer.objects.active = target
    if previous_mesh and target.type == 'ARMATURE':
        target['mesh_xr_target_mesh'] = previous_mesh.name
    elif previous_arm and target.type == 'MESH':
        previous_arm['mesh_xr_target_mesh'] = target.name
    # Selection remains standard Blender selection. The pair is remembered
    # independently, so no phantom multi-select or duplicate button is needed.
    session.pointer = point
    session.status = 'SELECTED ' + target.name.upper()
    return hit


def _mode_kind(obj):
    if obj.mode == 'EDIT':
        if obj.type == 'MESH':
            return 'MESH'
        if obj.type == 'ARMATURE':
            return 'BONE'
    if obj.mode == 'POSE' and obj.type == 'ARMATURE':
        return 'POSE'
    if obj.mode == 'OBJECT':
        return 'OBJECT'
    raise ValueError('Cannot transform in this Blender mode')


def _bone_entries(arm, kind):
    if kind == 'BONE':
        collection = arm.data.edit_bones
        selected = [b for b in collection if b.select]
        if not selected and collection.active:
            selected = [collection.active]
        return {b.name: (b.head.copy(), b.tail.copy(), float(b.roll))
                for b in selected}
    collection = arm.pose.bones
    selected = [b for b in collection if getattr(b.bone, 'select', False)]
    if not selected and arm.data.bones.active:
        selected = [collection[arm.data.bones.active.name]]
    return {b.name: b.matrix.copy() for b in selected}


def _object_guard(obj):
    """Retain the actual Blender object, not only its reusable name."""
    return (obj.as_pointer(), obj.name, obj.type)


def _assert_object_guard(obj, guard):
    if obj.as_pointer() != guard[0] or obj.name != guard[1] or obj.type != guard[2]:
        raise ValueError('XR object was replaced, renamed or changed type')


def _assert_object_state(obj, expected):
    if any(not math.isfinite(float(v)) for row in obj.matrix_world for v in row):
        raise ValueError('XR object matrix contains non-finite values')
    if _changed(expected, obj.matrix_world, 'OBJECT'):
        raise ValueError('Object moved outside XR controller transform')


def _finite_object_matrix(matrix):
    if not all(math.isfinite(float(v)) for row in matrix for v in row):
        raise ValueError('XR controller produced an invalid object matrix')


def _mesh_guard(obj):
    """Identify the exact editable mesh connectivity without mesh snapshots."""
    from . import mesh_selection_tools_v086
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    for group in (bm.verts, bm.edges, bm.faces):
        group.index_update()
    return (obj.as_pointer(), obj.data.as_pointer(),
            mesh_selection_tools_v086._topology(bm))


def _assert_mesh_guard(obj, guard):
    if obj.type != 'MESH' or obj.mode != 'EDIT' or _mesh_guard(obj) != guard:
        raise ValueError('Mesh identity, topology or visibility changed during XR transform')


def _armature_guard(obj, kind, names):
    """Identify the live armature and its selected bone names for this gesture."""
    if obj.type != 'ARMATURE' or obj.mode != ('EDIT' if kind == 'BONE' else 'POSE'):
        raise ValueError('Armature mode changed during XR transform')
    if obj.data is None:
        raise ValueError('Armature datablock was removed')
    collection = obj.data.edit_bones if kind == 'BONE' else obj.pose.bones
    if any(collection.get(name) is None for name in names):
        raise ValueError('A held XR bone was removed or renamed')
    return (obj.as_pointer(), obj.data.as_pointer(), tuple(sorted(names)))


def _assert_armature_guard(obj, kind, guard):
    if _armature_guard(obj, kind, guard[2]) != guard:
        raise ValueError('Armature identity or bone names changed during XR transform')


def _bone_state(obj, kind, names):
    collection = obj.data.edit_bones if kind == 'BONE' else obj.pose.bones
    if kind == 'BONE':
        return {name: (collection[name].head.copy(), collection[name].tail.copy(),
                       float(collection[name].roll)) for name in names}
    return {name: collection[name].matrix.copy() for name in names}


def _assert_bone_state(obj, kind, expected):
    current = _bone_state(obj, kind, expected)
    if _changed(expected, current, kind):
        raise ValueError('Bones changed outside XR controller transform')


def _finite_bone_state(kind, state):
    for value in state.values():
        if kind == 'BONE':
            values = tuple(value[0]) + tuple(value[1]) + (value[2],)
        else:
            values = tuple(component for row in value for component in row)
        if not all(math.isfinite(float(component)) for component in values):
            raise ValueError('Bone transform produced non-finite coordinates')


def begin_transform(context, tool, pos, rotation, source='grip', target=None, part=None):
    obj = target or context.view_layer.objects.active
    if obj is None:
        raise ValueError('Select an object or geometry first')
    kind = _mode_kind(obj)
    if obj.library or (obj.data is not None and obj.data.library):
        raise ValueError('Linked objects cannot be transformed')
    if obj.hide_select:
        raise ValueError('Selection is locked: unlock the object before grabbing it')
    before = None
    ik_chain = None
    ik_tip_world = None
    if kind == 'OBJECT':
        before = obj.matrix_world.copy()
        pivot = before.translation.copy()
    elif kind == 'MESH':
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        mode = selection.mode(context)
        selected = mesh.selected_transform_vertices(obj, mode)
        if not selected:
            raise ValueError('Select vertices, edges or faces before transforming')
        before = {v.index: v.co.copy() for v in selected}
        topology_guard = _mesh_guard(obj)
        pivot = obj.matrix_world @ (sum(before.values(), Vector()) / len(before))
    else:
        if kind == 'POSE' and tool in {'BONE_IK_2', 'BONE_IK_3'}:
            from . import pose_ik_v086
            ik_chain = pose_ik_v086.pose_chain(obj, int(tool[-1]))
            before = pose_ik_v086.chain_snapshot(obj, ik_chain)
            ik_tip_world = (obj.matrix_world @ obj.pose.bones[ik_chain[-1]].tail)
            pivot = ik_tip_world.copy()
        else:
            before = _bone_entries(obj, kind)
            if not before:
                raise ValueError('Select bones first')
            if kind == 'BONE':
                points = [(head + tail) * .5 for head, tail, _ in before.values()]
            else:
                points = [matrix.translation for matrix in before.values()]
            pivot = obj.matrix_world @ (sum(points, Vector()) / len(points))
    # Freeze fine-movement sensitivity at the beginning of each gesture.
    settings = getattr(context.scene, 'blender_xr', None)
    fine = (max(0.02, min(1.0, float(settings.fine_grab_factor)))
            if settings and settings.fine_grab_enabled else 1.0)
    position = Vector(pos)
    if part is None and tool in {'BONE_MOVE_HEAD', 'BONE_MOVE_TAIL'}:
        part = 'HEAD' if tool == 'BONE_MOVE_HEAD' else 'TAIL'
    return {
        'object': obj.name, 'kind': kind, 'tool': tool,
        'source': source, 'start': position.copy(),
        'rotation': Quaternion(rotation).copy(), 'pivot': pivot,
        'before': before, 'part': part,
        'ik_chain': ik_chain, 'ik_tip_world': ik_tip_world,
        'mode': obj.mode, 'fine_factor': fine,
        'object_guard': _object_guard(obj),
        'last_object_matrix': before.copy() if kind == 'OBJECT' else None,
        'mesh_guard': topology_guard if kind == 'MESH' else None,
        'last_mesh_coords': {i: co.copy() for i, co in before.items()}
                            if kind == 'MESH' else None,
        'armature_guard': _armature_guard(obj, kind, before)
                          if kind in {'BONE', 'POSE'} else None,
        'last_bone_state': _bone_state(obj, kind, before)
                           if kind in {'BONE', 'POSE'} else None,
    }


def _delta_matrix(drag, position, rotation):
    tool = drag['tool']
    pivot = drag['pivot']
    precision = max(0.02, min(1.0, float(drag.get('fine_factor', 1.0))))
    if tool in MOVE or tool == 'SELECT' or tool in {'BONE_IK_2', 'BONE_IK_3'}:
        offset = (Vector(position) - drag['start']) * precision
        return Matrix.Translation(offset)
    if tool in SCALE:
        start = max((drag['start'] - pivot).length, .10)
        distance = (Vector(position) - pivot).length
        factor = max(.02, min(20.0, distance / start))
        factor = 1.0 + (factor - 1.0) * precision
        return (Matrix.Translation(pivot) @ Matrix.Scale(factor, 4) @
                Matrix.Translation(-pivot))
    if tool in ROTATE:
        difference = Quaternion(rotation) @ drag['rotation'].inverted()
        if precision < 1.0:
            difference = Quaternion().slerp(difference, precision)
        return (Matrix.Translation(pivot) @ difference.to_matrix().to_4x4() @
                Matrix.Translation(-pivot))
    raise ValueError('Unsupported transform: ' + tool)


def update_transform(context, drag, position, rotation):
    obj = bpy.data.objects.get(drag['object'])
    if obj is None or obj.mode != drag['mode']:
        raise ValueError('Object or mode changed while grabbing')
    delta = _delta_matrix(drag, position, rotation)
    kind = drag['kind']
    if kind == 'OBJECT':
        _assert_object_guard(obj, drag['object_guard'])
        _assert_object_state(obj, drag['last_object_matrix'])
        planned = delta @ drag['before']
        _finite_object_matrix(planned)
        obj.matrix_world = planned
        drag['last_object_matrix'] = obj.matrix_world.copy()
    elif kind == 'MESH':
        _assert_mesh_guard(obj, drag['mesh_guard'])
        inv = obj.matrix_world.inverted_safe()
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        # Check the entire held selection before writing any vertex. If a
        # different Blender tool edited it mid-gesture, cancel rather than
        # silently overwriting unrelated work.
        previous = drag['last_mesh_coords']
        if any(index >= len(bm.verts) or not bm.verts[index].is_valid or
               bm.verts[index].hide or
               (bm.verts[index].co - previous[index]).length > 1e-6
               for index in drag['before']):
            raise ValueError('Selected vertices changed outside XR controller drag')
        updated = {}
        for index, co in drag['before'].items():
            target = inv @ delta @ (obj.matrix_world @ co)
            if not all(math.isfinite(float(value)) for value in target):
                raise ValueError('Controller transform produced invalid coordinates')
            updated[index] = target
        for index, target in updated.items():
            bm.verts[index].co = target
        drag['last_mesh_coords'] = {i: co.copy() for i, co in updated.items()}
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    elif kind in {'BONE', 'POSE'}:
        _assert_armature_guard(obj, kind, drag['armature_guard'])
        _assert_bone_state(obj, kind, drag['last_bone_state'])
        inv = obj.matrix_world.inverted_safe()
        planned = {}
        if kind == 'BONE':
            for name, (head, tail, roll) in drag['before'].items():
                part = drag['part']
                new_head = head if part == 'TAIL' else inv @ delta @ (obj.matrix_world @ head)
                new_tail = tail if part == 'HEAD' else inv @ delta @ (obj.matrix_world @ tail)
                if (new_tail - new_head).length < .0001:
                    new_tail = new_head + Vector((0, 0, .001))
                planned[name] = (new_head, new_tail,
                                 roll if drag['tool'] not in ROTATE else
                                 obj.data.edit_bones[name].roll)
            _finite_bone_state(kind, planned)
            for name, (head, tail, roll) in planned.items():
                bone = obj.data.edit_bones[name]
                bone.head, bone.tail, bone.roll = head, tail, roll
        elif drag['tool'] in {'BONE_IK_2', 'BONE_IK_3'}:
            from . import pose_ik_v086
            target_world = (drag['ik_tip_world'] +
                            (Vector(position) - drag['start']) *
                            drag['fine_factor'])
            pose_ik_v086.solve_pose_chain(context, obj, drag, target_world)
        else:
            planned = {name: inv @ delta @ obj.matrix_world @ prior
                       for name, prior in drag['before'].items()}
            _finite_bone_state(kind, planned)
            for name, matrix in planned.items():
                obj.pose.bones[name].matrix = matrix
    if kind in {'BONE', 'POSE'}:
        drag['last_bone_state'] = _bone_state(obj, kind, drag['before'])
    context.view_layer.update()


def restore_transform(context, drag):
    obj = bpy.data.objects.get(drag['object'])
    if obj is None or obj.mode != drag['mode']:
        return
    if drag['kind'] == 'OBJECT':
        _assert_object_guard(obj, drag['object_guard'])
        _assert_object_state(obj, drag['last_object_matrix'])
        obj.matrix_world = drag['before']
    elif drag['kind'] == 'MESH':
        # Never write old indices into unrelated replacement geometry.
        _assert_mesh_guard(obj, drag['mesh_guard'])
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        previous = drag['last_mesh_coords']
        if any(i >= len(bm.verts) or not bm.verts[i].is_valid or
               bm.verts[i].hide or
               (bm.verts[i].co - previous[i]).length > 1e-6
               for i in drag['before']):
            raise ValueError('Mesh changed externally; cannot safely restore XR drag')
        for i, co in drag['before'].items():
            bm.verts[i].co = co
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    elif drag['kind'] == 'BONE':
        _assert_armature_guard(obj, 'BONE', drag['armature_guard'])
        _assert_bone_state(obj, 'BONE', drag['last_bone_state'])
        for name, (head, tail, roll) in drag['before'].items():
            bone = obj.data.edit_bones.get(name)
            if bone:
                bone.head, bone.tail, bone.roll = head, tail, roll
    else:
        _assert_armature_guard(obj, 'POSE', drag['armature_guard'])
        _assert_bone_state(obj, 'POSE', drag['last_bone_state'])
        for name, matrix in drag['before'].items():
            bone = obj.pose.bones.get(name)
            if bone:
                bone.matrix = matrix
    context.view_layer.update()


def _current_coords(obj, drag):
    kind = drag['kind']
    if kind == 'OBJECT':
        _assert_object_guard(obj, drag['object_guard'])
        return obj.matrix_world.copy()
    if kind == 'MESH':
        _assert_mesh_guard(obj, drag['mesh_guard'])
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        return {i: bm.verts[i].co.copy() for i in drag['before']
                if i < len(bm.verts) and bm.verts[i].is_valid}
    if kind in {'BONE', 'POSE'} and drag.get('armature_guard') is not None:
        _assert_armature_guard(obj, kind, drag['armature_guard'])
    if kind == 'BONE':
        return {name: (obj.data.edit_bones[name].head.copy(),
                       obj.data.edit_bones[name].tail.copy(),
                       float(obj.data.edit_bones[name].roll))
                for name in drag['before'] if name in obj.data.edit_bones}
    return {name: obj.pose.bones[name].matrix.copy()
            for name in drag['before'] if name in obj.pose.bones}


def _changed(before, after, kind):
    if before.keys() != after.keys() if kind != 'OBJECT' else False:
        return True
    if kind == 'OBJECT':
        return any(abs(before[i][j] - after[i][j]) > 1e-7
                   for i in range(4) for j in range(4))
    if kind in {'MESH', 'POSE'}:
        return any((before[name] - after[name]).length > 1e-7 if kind == 'MESH'
                   else any(abs(before[name][i][j] - after[name][i][j]) > 1e-7
                            for i in range(4) for j in range(4))
                   for name in before)
    return any((before[name][0] - after[name][0]).length > 1e-7 or
               (before[name][1] - after[name][1]).length > 1e-7 or
               abs(before[name][2] - after[name][2]) > 1e-7
               for name in before)


def _push_transform_history(session, context, drag):
    obj = bpy.data.objects.get(drag['object'])
    if obj is None or obj.mode != drag['mode']:
        return
    after = _current_coords(obj, drag)
    if drag['kind'] == 'OBJECT':
        _assert_object_state(obj, drag['last_object_matrix'])
    if drag['kind'] == 'MESH' and (
            set(after) != set(drag['last_mesh_coords']) or
            any((after[i] - co).length > 1e-6
                for i, co in drag['last_mesh_coords'].items())):
        raise ValueError('Mesh changed outside XR before transform commit')
    if drag['kind'] in {'BONE', 'POSE'} and drag.get('last_bone_state') is not None:
        if _changed(drag['last_bone_state'], after, drag['kind']):
            raise ValueError('Bones changed outside XR before transform commit')
    if not _changed(drag['before'], after, drag['kind']):
        return
    kind = {'OBJECT': 'OBJECT', 'MESH': 'XR_VERTS', 'BONE': 'XR_BONES',
            'POSE': 'XR_POSE'}[drag['kind']]
    entry = (kind, obj.name, obj.data.name if kind != 'OBJECT' else None,
             drag['before'], after,
             drag['mesh_guard'] if kind == 'XR_VERTS' else
             drag.get('armature_guard') if kind in {'XR_BONES', 'XR_POSE'} else
             drag.get('object_guard') if kind == 'OBJECT' else None)
    if hasattr(session, 'history') and session.history is not None:
        session.history.push(entry)
    elif getattr(context, 'area', None) and context.area.type == 'VIEW_3D':
        try:
            bpy.ops.ed.undo_push(message='Mesh XR Controller Transform')
        except (RuntimeError, AttributeError):
            pass


def _apply_history_entry(entry, backwards):
    kind, obj_name, data_name, before, after = entry[:5]
    guard = entry[5] if len(entry) > 5 else None
    obj = bpy.data.objects.get(obj_name)
    if obj is None:
        raise ValueError('Transformed object no longer exists')
    if kind == 'OBJECT':
        if obj.mode != 'OBJECT':
            raise ValueError('Enter Object Mode before restoring an XR object transform')
        if guard is not None:
            _assert_object_guard(obj, guard)
        expected = after if backwards else before
        data = before if backwards else after
        _finite_object_matrix(expected)
        _finite_object_matrix(data)
        _assert_object_state(obj, expected)
        obj.matrix_world = data.copy()
        bpy.context.view_layer.update()
        return
    if obj.data is None or obj.data.name != data_name:
        raise ValueError('Transformed object or its data has changed')
    data = before if backwards else after
    if kind == 'XR_VERTS':
        if obj.type != 'MESH' or obj.mode != 'EDIT':
            raise ValueError('Enter Mesh Edit Mode before undoing vertex changes')
        if guard is not None:
            _assert_mesh_guard(obj, guard)
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        if any(i < 0 or i >= len(bm.verts) or not bm.verts[i].is_valid
               or bm.verts[i].hide for i in data):
            raise ValueError('Mesh topology changed; cannot restore these vertex indices')
        # Reject unrelated edits before changing any vertex. The expected
        # state is the opposite side of this history operation.
        expected = after if backwards else before
        if set(expected) != set(data) or any(
                (bm.verts[i].co - co).length > 1e-6
                for i, co in expected.items()):
            raise ValueError('Mesh coordinates changed outside XR transform history')
        for i, co in data.items():
            bm.verts[i].co = co
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    elif kind == 'XR_BONES':
        if obj.type != 'ARMATURE' or obj.mode != 'EDIT':
            raise ValueError('Enter Armature Edit Mode to undo bone changes')
        if guard is not None:
            _assert_armature_guard(obj, 'BONE', guard)
        if set(data) != set(before) or set(data) != set(after):
            raise ValueError('Armature history has inconsistent bone names')
        _finite_bone_state('BONE', data)
        _assert_bone_state(obj, 'BONE', after if backwards else before)
        for name, (head, tail, roll) in data.items():
            bone = obj.data.edit_bones[name]
            bone.head, bone.tail, bone.roll = head, tail, roll
    elif kind == 'XR_POSE':
        if obj.type != 'ARMATURE' or obj.mode != 'POSE':
            raise ValueError('Enter Pose Mode to undo pose changes')
        if guard is not None:
            _assert_armature_guard(obj, 'POSE', guard)
        if set(data) != set(before) or set(data) != set(after):
            raise ValueError('Pose history has inconsistent bone names')
        _finite_bone_state('POSE', data)
        _assert_bone_state(obj, 'POSE', after if backwards else before)
        for name, matrix in data.items():
            obj.pose.bones[name].matrix = matrix
    bpy.context.view_layer.update()


def patch_history():
    if getattr(mesh.History, '_v076_controller_transform_history', False):
        return
    original_step = mesh.History.step
    original_release = mesh.History.release
    types = {'XR_VERTS', 'XR_BONES', 'XR_POSE'}

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] not in types:
            return original_step(self, backwards)
        entry = source[-1]
        _apply_history_entry(entry, backwards)
        dest.append(source.pop())
        return True

    def release(entry):
        if entry[0] not in types:
            return original_release(entry)

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._v076_controller_transform_history = True


def install_pages():
    from . import menus
    # Preserve all other Blender tools; make rotations accessible by controller.
    tools = [('', 'ROTATE') if act == 'DELETE_OBJECT' else (label, act)
             for label, act in menus.PAGES['TOOLS']]
    menus.PAGES['TOOLS'] = tuple(tools)
    edits = list(menus.PAGES['EDIT'])
    more = list(menus.PAGES['EDIT_MORE'])
    if not any(action == 'ROTATE_EDIT' for _, action in edits + more):
        # Existing Edit and Edit More both have twelve buttons. Preserve the
        # sole Edit Mode Materials entry, Undo/Redo and every modelling tool:
        # group the two step-size controls under a small Step category, then
        # expose Rotate Selection in the freed More cell.
        if len(edits) >= 12:
            if sum(action in {'LESS', 'MORE'} for _, action in more) != 2:
                raise RuntimeError('Edit More must include both step controls')
            more = [(label, action) for label, action in more
                    if action not in {'LESS', 'MORE'}]
            more[-1:-1] = [('', 'ROTATE_EDIT'), ('', 'STEP_MENU')]
            menus.PAGES['STEP_MENU'] = (
                ('STEP -', 'LESS'), ('STEP +', 'MORE'), ('BACK', 'BACK'))
            menus.TITLES['STEP_MENU'] = 'EDIT STEP SIZE'
        else:
            edits.append(('', 'ROTATE_EDIT'))
    menus.PAGES['EDIT'] = tuple(edits)
    menus.PAGES['EDIT_MORE'] = tuple(more)
    operations = list(menus.PAGES['ARMATURE_EDIT'])
    operations = [(label, 'SELECT') if action == 'BONE_SELECT' else (label, action)
                  for label, action in operations]
    # Every tool stays reachable; head and tail move to the Edit Tools page
    # instead of silently dropping Settings from the twelve-button front page.
    operations = [(label, action) for label, action in operations
                  if action not in {'BONE_MOVE_HEAD', 'BONE_MOVE_TAIL'}]
    operations = operations[:2] + [
        ('SCALE', 'BONE_SCALE'), ('ROTATE', 'BONE_ROTATE')] + operations[2:]
    assert len(operations) == 12
    menus.PAGES['ARMATURE_EDIT'] = tuple(operations)
    menus.PAGES['POSE_EDIT'] = (
        ('SELECT', 'SELECT'), ('MOVE', 'BONE_MOVE'),
        ('SCALE', 'BONE_SCALE'), ('ROTATE', 'BONE_ROTATE'),
        ('FINISH POSE', 'RIG_EXIT_POSE'),
    )
    menus.TITLES['POSE_EDIT'] = 'POSE BONES'
    edit_operations = list(menus.PAGES['ARMATURE_OPERATIONS'])
    edit_operations[-1:-1] = [('HEAD', 'BONE_MOVE_HEAD'),
                             ('TAIL', 'BONE_MOVE_TAIL')]
    # Split/Separate remain available on a small More page; otherwise the
    # bone operations panel has thirteen entries and the last is invisible.
    edit_operations = [(label, action) for label, action in edit_operations
                       if action not in {'BONE_SPLIT', 'BONE_SEPARATE'}]
    edit_operations[-1:-1] = [('MORE', 'BONE_OPERATIONS_MORE_MENU')]
    assert len(edit_operations) == 12
    menus.PAGES['ARMATURE_OPERATIONS'] = tuple(edit_operations)
    for page in ('TOOLS','EDIT','EDIT_MORE','ARMATURE_EDIT','POSE_EDIT','RIGGING','WEIGHT_PAINT'):
        actions = [action for _, action in menus.PAGES[page]]
        if len(actions) != len(set(actions)):
            raise RuntimeError('Duplicate XR menu action in ' + page)
    # Object deletion remains available on Creator Hub; the old replacement
    # relied on a duplicate Object Mode button and could hide Quick Layout.


def patch_runtime(Runtime):
    if getattr(Runtime, '_v076_unified_interaction', False):
        return
    patch_history()
    old_tick = Runtime.tick
    old_select = Runtime.select
    old_command = Runtime.command
    old_cancel = Runtime.cancel_work

    def command(self, context, action):
        if action == 'STEP_MENU':
            self.menu.page = 'STEP_MENU'
            self.status = 'EDIT STEP / DECREASE OR INCREASE'
            return
        if action == 'BACK' and self.menu.page == 'STEP_MENU':
            self.menu.page = 'EDIT_MORE'
            return
        if action == 'SELECT':
            self.tool = 'SELECT'
            self.status = 'SELECT MESH / ARMATURE / BONE'
            return
        if action == 'RIG_POSE':
            result = old_command(self, context, action)
            active = context.view_layer.objects.active
            if active and active.type == 'ARMATURE' and active.mode == 'POSE':
                self.menu.page = 'POSE_EDIT'
                self.tool = 'SELECT'
            return result
        if action == 'BACK' and self.menu.page == 'POSE_EDIT':
            return old_command(self, context, 'RIG_EXIT_POSE')
        if action == 'BONE_MOVE':
            obj = context.view_layer.objects.active
            if obj and obj.type == 'ARMATURE' and obj.mode == 'POSE':
                self.tool = 'BONE_MOVE'
                self.status = 'POSE BONE MOVE'
                return
        if action in {'ROTATE','ROTATE_EDIT','BONE_SCALE','BONE_ROTATE'}:
            obj = context.view_layer.objects.active
            if obj is None:
                raise ValueError('Select an object or bone first')
            if action == 'ROTATE' and obj.mode != 'OBJECT':
                raise ValueError('Rotate Object requires Object Mode')
            if action == 'ROTATE_EDIT' and not (obj.type == 'MESH' and obj.mode == 'EDIT'):
                raise ValueError('Rotate Selection needs Mesh Edit Mode')
            if action in {'BONE_SCALE','BONE_ROTATE'} and not (
                obj.type == 'ARMATURE' and obj.mode in {'EDIT','POSE'}):
                raise ValueError('Enter Armature Edit or Pose Mode')
            self.tool = action
            self.status = action.replace('_', ' ')
            return
        return old_command(self, context, action)

    def _tracked_pose(self, context, source):
        """Read the current validated frame, never a second OpenXR pose.

        Input router preflights both hands before dispatch. If a legacy
        selection path is called outside that router, fail closed rather than
        silently accepting a potentially stale controller position.
        """
        from . import input_safety_v086
        poses = getattr(self, '_xr_validated_poses', None)
        if poses is None or self.dom not in poses:
            raise ValueError('No validated XR controller frame for transform')
        rotation, position = poses[self.dom][0 if source == 'trigger' else 1]
        input_safety_v086.validate_pose(rotation, position)
        return position.copy(), rotation.copy()

    def select(self, context, origin, direction, additive=False):
        obj = context.view_layer.objects.active
        tool = self.tool
        if tool in TRANSFORMS and obj and obj.mode in {'OBJECT','EDIT','POSE'}:
            # Validate tracking before changing object/mesh/bone selection.
            # A missing frame must not leave a changed selection with no drag.
            try:
                tracked_origin, quat = _tracked_pose(self, context, 'trigger')
            except (RuntimeError, TypeError, ValueError, IndexError,
                    AttributeError, ReferenceError, OverflowError):
                from . import input_ownership_v080
                input_ownership_v080.cancel_tracking_loss(self)
                self.status = 'DIRECT TRANSFORM / TRACKING LOST / RELEASE CONTROLS'
                return
            if obj.type == 'MESH' and obj.mode == 'EDIT' and tool in {'MOVE','SCALE','ROTATE'}:
                hit_other = self.object_hit(context, origin, direction)
                if hit_other and hit_other[0] != obj:
                    return old_select(self, context, origin, direction,
                                      additive=additive)
            if getattr(self, '_xr_gesture', None):
                raise ValueError('Release the current transform first')
            if obj.mode == 'OBJECT':
                hit = self.object_hit(context, origin, direction)
                if not hit or hit[0] != obj:
                    hit = choose_object(context, origin, direction, self.object_hit)
                if hit:
                    target = hit[0]
                    if not target.select_get():
                        for selected in context.selected_objects:
                            selected.select_set(False)
                        target.select_set(True)
                    context.view_layer.objects.active = target
                    obj = target
                elif not obj.select_get():
                    raise ValueError('Aim at an object before transforming')
            elif obj.type == 'MESH' and obj.mode == 'EDIT':
                hit = ray_element(obj, origin, direction, selection.mode(context))
                if hit:
                    # Preserve a multi-point selection if the hit belongs to it.
                    selected = selection.selected_indices(obj, selection.mode(context))
                    if hit[0] not in selected:
                        mesh.select_element(obj, selection.mode(context), hit[0])
            elif obj.type == 'ARMATURE' and obj.mode == 'EDIT':
                hit = armature_v076.ray_pick_bone(context, origin, direction, only_active=True)
                if hit and not obj.data.edit_bones[hit[3]].select:
                    armature_v076.pick_edit_bone(context, origin, direction)
            else:
                if obj.type == 'ARMATURE':
                    select_context(self, context, origin, direction)
            self._xr_gesture = begin_transform(
                context, tool, tracked_origin, quat, source='trigger')
            self.status = tool + ' / HOLD TRIGGER AND MOVE CONTROLLER'
            return
        if tool == 'SELECT':
            if obj and obj.type == 'MESH' and obj.mode == 'EDIT':
                picked = ray_element(obj, origin, direction, selection.mode(context))
                target = self.object_hit(context, origin, direction)
                # Preserve Blender's existing edit-object switch semantics.
                # A controller aimed at another mesh must be able to make that
                # mesh active, not get trapped in the current edit cage.
                if picked and (not target or target[0] == obj or
                               (picked[1] - origin).length <=
                               (target[1] - origin).length):
                    mesh.select_element(obj, selection.mode(context),
                                        picked[0], additive)
                    self.status = 'SELECTED ' + selection.mode(context)
                    return
                return old_select(self, context, origin, direction,
                                  additive=additive)
            return select_context(self, context, origin, direction,
                                  additive=additive, old_hit=self.object_hit)
        return old_select(self, context, origin, direction, additive=additive)

    def cancel_work(self):
        gesture = getattr(self, '_xr_gesture', None)
        failure = None
        if gesture:
            try:
                restore_transform(self.context, gesture)
            except (RuntimeError, TypeError, ValueError, IndexError,
                    AttributeError, ReferenceError, OverflowError) as exc:
                failure = exc
            finally:
                self._xr_gesture = None
        # Even if a mesh was replaced mid-gesture and cannot safely be
        # restored, the other active edit owners still need cancellation.
        try:
            return old_cancel(self)
        finally:
            if failure is not None:
                self.status = 'TRANSFORM CANCEL / MESH CHANGED / REVIEW GEOMETRY'


    def tick(self, context):
        state = context.window_manager.xr_session_state
        gesture = getattr(self, '_xr_gesture', None)
        if gesture:
            from . import actions, runtime, input_ownership_v080, input_safety_v086
            try:
                running = state is not None and bpy.types.XrSessionState.is_running(context)
            except (RuntimeError, TypeError, ValueError, AttributeError, ReferenceError):
                running = False
            if not running:
                input_ownership_v080.cancel_session_loss(self)
                return
            source = gesture['source']
            try:
                pos, rot = _tracked_pose(self, context, source)
                sample = getattr(self, '_xr_validated_controls', None)
                if sample is not None:
                    pressed = sample[self.dom][0 if source == 'trigger' else 1]
                elif self.bridge:
                    pressed = input_safety_v086.controller_sample(
                        context, self.bridge)[self.dom][0 if source == 'trigger' else 1]
                else:
                    pressed = input_safety_v086.control_value(
                        actions.read(context,
                                     'trigger' if source == 'trigger' else 'grab',
                                     self.dom)[0])
            except (RuntimeError, TypeError, ValueError, IndexError, AttributeError):
                # An unreadable grip/trigger is tracking loss, NOT release.
                # Roll back before the transform can be marked applied.
                input_ownership_v080.cancel_tracking_loss(self)
                return
            held = pressed >= .45
            if held:
                try:
                    update_transform(context, gesture, pos, rot)
                except (RuntimeError, TypeError, ValueError, IndexError,
                        AttributeError, ReferenceError, OverflowError):
                    input_ownership_v080.cancel_tracking_loss(self)
                    self.status = 'TRANSFORM INVALID / RESTORED / RELEASE CONTROLS'
                    return
                self.status = gesture['tool'] + ' / RELEASE TO APPLY'
            else:
                # Keep the gesture live until the undo entry is safely stored.
                # A history failure must roll back, not leave un-undoable data.
                try:
                    _push_transform_history(self, context, gesture)
                except (RuntimeError, TypeError, ValueError, IndexError,
                        AttributeError, ReferenceError, OverflowError):
                    input_ownership_v080.cancel_tracking_loss(self)
                    self.status = 'TRANSFORM HISTORY FAILED / RESTORED'
                    return
                self._xr_gesture = None
                (self.trigger if source == 'trigger' else self.grip).update(0.0)
                runtime.haptic_pulse(context, self.settings, self.dom)
                self.status = 'TRANSFORM APPLIED'
            return
        # Grip directly grabs a vertex/edge/face, bone, pose bone, or whole
        # armature/object using the *same* Select tool. No context-specific
        # selection buttons and no need to enter a second edit panel.
        if (state is not None and hasattr(context, 'temp_override')
                and bpy.types.XrSessionState.is_running(context)
                and getattr(self, 'navigation_initialized', False)
                and not self.transaction and not self.grab and
                not self.axis_move and not self.air_grab):
            from . import actions, input_ownership_v080, input_safety_v086
            try:
                sample = getattr(self, '_xr_validated_controls', None)
                if sample is not None:
                    grip_value = sample[self.dom][1]
                elif self.bridge:
                    grip_value = input_safety_v086.controller_sample(
                        context, self.bridge)[self.dom][1]
                else:
                    grip_value = input_safety_v086.control_value(
                        actions.read(context, 'grab', self.dom)[0])
            except (RuntimeError, TypeError, ValueError, IndexError, AttributeError):
                input_ownership_v080.cancel_tracking_loss(self)
                return
            grip_held = grip_value >= .45
            if grip_held and not self.grip.down:
                obj = context.view_layer.objects.active
                try:
                    origin, rotation = _tracked_pose(self, context, 'trigger')
                    grip_pos, grip_rot = _tracked_pose(self, context, 'grip')
                except (RuntimeError, TypeError, ValueError, IndexError,
                        AttributeError, ReferenceError, OverflowError):
                    input_ownership_v080.cancel_tracking_loss(self)
                    return
                direction = rotation @ Vector((0, 0, -1))
                if not self.menu.hit(origin, direction)[0]:
                    hit = False
                    if obj and obj.type == 'MESH' and obj.mode == 'EDIT':
                        picked = ray_element(obj, origin, direction, selection.mode(context))
                        if picked:
                            indices = selection.selected_indices(obj, selection.mode(context))
                            if picked[0] not in indices:
                                mesh.select_element(obj, selection.mode(context), picked[0])
                            hit = True
                    elif obj and obj.type == 'ARMATURE' and obj.mode == 'EDIT':
                        picked = armature_v076.ray_pick_bone(context, origin, direction, only_active=True)
                        if picked:
                            if not obj.data.edit_bones[picked[3]].select:
                                armature_v076.pick_edit_bone(context, origin, direction)
                            hit = True
                    elif obj and obj.type == 'ARMATURE' and obj.mode == 'POSE':
                        hit = bool(armature_v076.ray_pick_bone(
                            context, origin, direction, only_active=True))
                        if hit:
                            select_context(self, context, origin, direction)
                    elif obj and obj.mode == 'OBJECT':
                        # Grab the object under the ray, not the alternate
                        # overlap-cycling selection (that belongs to Select).
                        picked = self.object_hit(context, origin, direction)
                        if picked:
                            if picked[0] != obj:
                                for selected in context.selected_objects:
                                    selected.select_set(False)
                                picked[0].select_set(True)
                                context.view_layer.objects.active = picked[0]
                            hit = True
                    if hit:
                        active = context.view_layer.objects.active
                        mode = (self.tool if self.tool in TRANSFORMS else 'MOVE')
                        if active.mode == 'EDIT' and active.type == 'MESH':
                            if mode not in {'MOVE_FACE','SCALE_FACE','ROTATE_EDIT'}:
                                mode = {'SCALE':'SCALE_FACE','ROTATE':'ROTATE_EDIT'}.get(mode, 'MOVE_FACE')
                        elif active.mode in {'EDIT','POSE'} and active.type == 'ARMATURE':
                            mode = ({'SCALE':'BONE_SCALE','ROTATE':'BONE_ROTATE'}
                                    .get(mode, 'BONE_MOVE'))
                        else:
                            mode = {'SCALE_FACE':'SCALE', 'ROTATE_EDIT':'ROTATE'}.get(mode,mode)
                        self._xr_gesture = begin_transform(
                            context, mode, grip_pos, grip_rot, source='grip')
                        self.status = 'GRABBED ' + active.name.upper()
                        return
        return old_tick(self, context)

    Runtime.command = command
    Runtime.select = select
    Runtime.tick = tick
    Runtime.cancel_work = cancel_work
    Runtime._v076_unified_interaction = True
