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
              'BONE_MOVE_TAIL', 'BONE_SCALE', 'BONE_ROTATE'}
MOVE = {'MOVE', 'MOVE_FACE', 'BONE_MOVE', 'BONE_MOVE_HEAD', 'BONE_MOVE_TAIL'}
SCALE = {'SCALE', 'SCALE_FACE', 'BONE_SCALE'}
ROTATE = {'ROTATE', 'ROTATE_EDIT', 'BONE_ROTATE'}


def ray_element(obj, origin, direction, mode, radius=0.075):
    """Pick vertices/edges within ray tolerance even when no face was hit.

    The old picker required hitting a polygon first, making loose vertices,
    isolated edges and small VR controller targets impossible to grab.
    """
    if obj is None or obj.type != 'MESH' or obj.mode != 'EDIT':
        return None
    if mode == 'FACE':
        return mesh.element_hit(obj, origin, direction, 'FACE')
    direction = Vector(direction).normalized()
    bm = bmesh.from_edit_mesh(obj.data)
    candidates = []
    if mode == 'VERT':
        for vert in bm.verts:
            if vert.hide or not vert.is_valid:
                continue
            world = obj.matrix_world @ vert.co
            along = (world - origin).dot(direction)
            if along <= 0:
                continue
            distance = (origin + along * direction - world).length
            if distance <= max(radius, along * .013):
                candidates.append((along, distance, vert.index, world.copy()))
    elif mode == 'EDGE':
        for edge in bm.edges:
            if edge.hide or not edge.is_valid:
                continue
            h = armature_v076._closest_segment(
                origin, direction, obj.matrix_world @ edge.verts[0].co,
                obj.matrix_world @ edge.verts[1].co)
            if h and h[0] <= max(radius, h[1] * .013):
                candidates.append((h[1], h[0], edge.index, h[2]))
    if candidates:
        best = min(candidates, key=lambda item: (item[0], item[1]))
        return best[2], best[3]
    return mesh.element_hit(obj, origin, direction, mode)


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
            if not additive:
                bone.select = False
        bone = obj.data.bones.get(hit[3])
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
    selected = [b for b in collection if b.bone.select]
    if not selected and arm.data.bones.active:
        selected = [collection[arm.data.bones.active.name]]
    return {b.name: b.matrix.copy() for b in selected}


def begin_transform(context, tool, pos, rotation, source='grip', target=None, part=None):
    obj = target or context.view_layer.objects.active
    if obj is None:
        raise ValueError('Select an object or geometry first')
    kind = _mode_kind(obj)
    if obj.library or obj.data.library:
        raise ValueError('Linked objects cannot be transformed')
    before = None
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
        pivot = obj.matrix_world @ (sum(before.values(), Vector()) / len(before))
    else:
        before = _bone_entries(obj, kind)
        if not before:
            raise ValueError('Select bones first')
        if kind == 'BONE':
            points = [(head + tail) * .5 for head, tail, _ in before.values()]
        else:
            points = [matrix.translation for matrix in before.values()]
        pivot = obj.matrix_world @ (sum(points, Vector()) / len(points))
    position = Vector(pos)
    return {
        'object': obj.name, 'kind': kind, 'tool': tool,
        'source': source, 'start': position.copy(),
        'rotation': Quaternion(rotation).copy(), 'pivot': pivot,
        'before': before, 'part': part,
        'mode': obj.mode,
    }


def _delta_matrix(drag, position, rotation):
    tool = drag['tool']
    pivot = drag['pivot']
    if tool in MOVE or tool == 'SELECT':
        offset = Vector(position) - drag['start']
        return Matrix.Translation(offset)
    if tool in SCALE:
        start = max((drag['start'] - pivot).length, .10)
        distance = (Vector(position) - pivot).length
        factor = max(.02, min(20.0, distance / start))
        return (Matrix.Translation(pivot) @ Matrix.Scale(factor, 4) @
                Matrix.Translation(-pivot))
    if tool in ROTATE:
        difference = Quaternion(rotation) @ drag['rotation'].inverted()
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
        obj.matrix_world = delta @ drag['before']
    elif kind == 'MESH':
        inv = obj.matrix_world.inverted_safe()
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        for index, co in drag['before'].items():
            if index < len(bm.verts) and bm.verts[index].is_valid:
                bm.verts[index].co = inv @ delta @ (obj.matrix_world @ co)
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    elif kind == 'BONE':
        inv = obj.matrix_world.inverted_safe()
        for name, (head, tail, roll) in drag['before'].items():
            bone = obj.data.edit_bones.get(name)
            if bone is None:
                continue
            part = drag['part']
            if part != 'TAIL':
                bone.head = inv @ delta @ (obj.matrix_world @ head)
            if part != 'HEAD':
                bone.tail = inv @ delta @ (obj.matrix_world @ tail)
            if (bone.tail - bone.head).length < .0001:
                bone.tail = bone.head + Vector((0, 0, .001))
            if drag['tool'] not in ROTATE:
                bone.roll = roll
    else:
        inv = obj.matrix_world.inverted_safe()
        for name, prior in drag['before'].items():
            bone = obj.pose.bones.get(name)
            if bone is not None:
                bone.matrix = inv @ delta @ obj.matrix_world @ prior
    context.view_layer.update()


def restore_transform(context, drag):
    obj = bpy.data.objects.get(drag['object'])
    if obj is None or obj.mode != drag['mode']:
        return
    if drag['kind'] == 'OBJECT':
        obj.matrix_world = drag['before']
    elif drag['kind'] == 'MESH':
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        for i, co in drag['before'].items():
            if i < len(bm.verts) and bm.verts[i].is_valid:
                bm.verts[i].co = co
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    elif drag['kind'] == 'BONE':
        for name, (head, tail, roll) in drag['before'].items():
            bone = obj.data.edit_bones.get(name)
            if bone:
                bone.head, bone.tail, bone.roll = head, tail, roll
    else:
        for name, matrix in drag['before'].items():
            bone = obj.pose.bones.get(name)
            if bone:
                bone.matrix = matrix
    context.view_layer.update()


def install_pages():
    from . import menus
    # Preserve all other Blender tools; make rotations accessible by controller.
    tools = [('', 'ROTATE') if act == 'DELETE_OBJECT' else (label, act)
             for label, act in menus.PAGES['TOOLS']]
    menus.PAGES['TOOLS'] = tuple(tools)
    edits = [('', 'ROTATE_EDIT') if act == 'INSET' else (label, act)
             for label, act in menus.PAGES['EDIT']]
    menus.PAGES['EDIT'] = tuple(edits)
    # Inset remains reachable through advanced editing rather than discarded.
    more = list(menus.PAGES['EDIT_MORE'])
    if not any(action == 'INSET' for _, action in more):
        more = [(label, 'INSET') if action == 'LESS' else (label, action)
                for label, action in more]
    menus.PAGES['EDIT_MORE'] = tuple(more)
    operations = list(menus.PAGES['ARMATURE_EDIT'])
    operations = [(label, 'SELECT') if action == 'BONE_SELECT' else (label, action)
                  for label, action in operations]
    # Remove tail-specific item from compact first page (still accessible by
    # hovering endpoints in Select), in favour of Scale and Rotate.
    operations = [(label, action) for label, action in operations if action == 'SELECT'
                  or action != 'BONE_MOVE_TAIL']
    operations = operations[:4] + [('SCALE','BONE_SCALE'), ('ROTATE','BONE_ROTATE')] + operations[4:]
    if len(operations) > 12:
        operations = operations[:11] + [('FINISH','RIG_EDIT_TOGGLE')]
    menus.PAGES['ARMATURE_EDIT'] = tuple(operations)
    for page in ('TOOLS','EDIT','EDIT_MORE','ARMATURE_EDIT','RIGGING','WEIGHT_PAINT'):
        actions = [action for _, action in menus.PAGES[page]]
        if len(actions) != len(set(actions)):
            raise RuntimeError('Duplicate XR menu action in ' + page)
    # Existing object deletion stays available in Object Advanced.
    advanced = list(menus.PAGES.get('OBJECT_ADVANCED', ()))
    if advanced and not any(action == 'DELETE_OBJECT' for _, action in advanced):
        advanced = [(label, 'DELETE_OBJECT') if action == 'MODE_OBJECT' else
                    (label, action) for label, action in advanced]
        menus.PAGES['OBJECT_ADVANCED'] = tuple(advanced)


def patch_runtime(Runtime):
    if getattr(Runtime, '_v076_unified_interaction', False):
        return
    old_tick = Runtime.tick
    old_select = Runtime.select
    old_command = Runtime.command
    old_cancel = Runtime.cancel_work

    def command(self, context, action):
        if action == 'SELECT':
            self.tool = 'SELECT'
            self.status = 'SELECT MESH / ARMATURE / BONE'
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

    def select(self, context, origin, direction, additive=False):
        obj = context.view_layer.objects.active
        tool = self.tool
        if tool in TRANSFORMS and obj and obj.mode in {'OBJECT','EDIT','POSE'}:
            if getattr(self, '_xr_gesture', None):
                raise ValueError('Release the current transform first')
            if obj.mode == 'OBJECT':
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
            xr = context.window_manager.xr_session_state
            quat = (Quaternion(xr.controller_aim_rotation_get(context, self.dom))
                    if xr is not None else Quaternion())
            self._xr_gesture = begin_transform(
                context, tool, origin, quat, source='trigger')
            self.status = tool + ' / HOLD TRIGGER AND MOVE CONTROLLER'
            return
        if tool == 'SELECT':
            return select_context(self, context, origin, direction,
                                  additive=additive, old_hit=self.object_hit)
        return old_select(self, context, origin, direction, additive=additive)

    def cancel_work(self):
        gesture = getattr(self, '_xr_gesture', None)
        if gesture:
            try:
                restore_transform(self.context, gesture)
            finally:
                self._xr_gesture = None
        return old_cancel(self)

    def tick(self, context):
        state = context.window_manager.xr_session_state
        gesture = getattr(self, '_xr_gesture', None)
        if gesture:
            from . import actions, runtime
            if state is None or not bpy.types.XrSessionState.is_running(context):
                restore_transform(context, gesture)
                self._xr_gesture = None
                return
            source = gesture['source']
            pos = Vector(state.controller_aim_location_get(context, self.dom)
                         if source == 'trigger' else
                         state.controller_grip_location_get(context, self.dom))
            rot = Quaternion(state.controller_aim_rotation_get(context, self.dom)
                             if source == 'trigger' else
                             state.controller_grip_rotation_get(context, self.dom))
            if self.bridge:
                sample = self.bridge.read()
                if sample is None:
                    restore_transform(context, gesture)
                    self._xr_gesture = None
                    return
                held = sample[self.dom][0 if source == 'trigger' else 1] >= .45
            else:
                held = actions.read(context,
                                    'trigger' if source == 'trigger' else 'grab',
                                    self.dom)[0] >= .45
            if held:
                update_transform(context, gesture, pos, rot)
                self.status = gesture['tool'] + ' / RELEASE TO APPLY'
            else:
                self._xr_gesture = None
                (self.trigger if source == 'trigger' else self.grip).update(0.0)
                if bpy.context.area and bpy.context.area.type == 'VIEW_3D':
                    try:
                        bpy.ops.ed.undo_push(message='Mesh XR Controller Transform')
                    except (RuntimeError, AttributeError):
                        pass
                runtime.haptic_pulse(context, self.settings, self.dom)
                self.status = 'TRANSFORM APPLIED'
            return
        # Grip directly grabs a vertex/edge/face, bone, pose bone, or whole
        # armature/object using the *same* Select tool. No context-specific
        # selection buttons and no need to enter a second edit panel.
        if (state is not None and getattr(context, 'view_layer', None) is not None
                and bpy.types.XrSessionState.is_running(context)
                and getattr(self, 'navigation_initialized', False)
                and not self.transaction and not self.grab and
                not self.axis_move and not self.air_grab):
            from . import actions
            grip_held = (self.bridge.read()[self.dom][1] >= .45 if self.bridge
                         else actions.read(context, 'grab', self.dom)[0] >= .45)
            if grip_held and not self.grip.down:
                obj = context.view_layer.objects.active
                origin = Vector(state.controller_aim_location_get(context, self.dom))
                rotation = Quaternion(state.controller_aim_rotation_get(context, self.dom))
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
                        picked = choose_object(context, origin, direction, self.object_hit)
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
                        grip_pos = Vector(state.controller_grip_location_get(context, self.dom))
                        grip_rot = Quaternion(state.controller_grip_rotation_get(context, self.dom))
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
