# SPDX-License-Identifier: GPL-3.0-or-later
"""Freeform Blender armature editing in XR (v0.7.6 preview).

Blender remains the source of truth for bone topology, parenting and undo.
Controller-ray picking works on armature bones (unlike scene.ray_cast, which only
intersects mesh surfaces). Native Blender armature operators implement the edit
commands; Mesh XR provides a compact headset and sidebar front end.
"""
import math

import bpy
from bpy.props import StringProperty
from mathutils import Vector

from . import menus, v075_features


# Each page has at most twelve 2-column VR buttons, leaving the bottom status
# and controller guide unobstructed.
ARMATURE_PAGES = {
    'ARMATURE_EDIT': (
        ('SELECT','SELECT'), ('MOVE','BONE_MOVE'),
        ('HEAD','BONE_MOVE_HEAD'), ('TAIL','BONE_MOVE_TAIL'),
        ('ADD','RIG_ADD_BONE'), ('EXTRUDE','BONE_EXTRUDE'),
        ('DUPLICATE','BONE_DUPLICATE'), ('DELETE','BONE_DELETE'),
        ('SELECT TOOLS','BONE_SELECT_MENU'), ('EDIT TOOLS','BONE_EDIT_MENU'),
        ('SETTINGS','BONE_SETTINGS_MENU'), ('FINISH','RIG_EDIT_TOGGLE'),
    ),
    'ARMATURE_SELECT': (
        ('ALL','BONE_SEL_ALL'), ('NONE','BONE_SEL_NONE'),
        ('INVERT','BONE_SEL_INVERT'), ('PARENT','BONE_SEL_PARENT'),
        ('CHILD','BONE_SEL_CHILD'), ('LINKED','BONE_SEL_LINKED'),
        ('MIRROR','BONE_SEL_MIRROR'), ('HIDE','BONE_HIDE'),
        ('HIDE OTHERS','BONE_HIDE_OTHER'), ('REVEAL','BONE_REVEAL'),
        ('BACK','BACK'),
    ),
    'ARMATURE_OPERATIONS': (
        ('SUBDIVIDE','BONE_SUBDIVIDE'), ('SYMMETRIZE','BONE_SYMMETRIZE'),
        ('FLIP DIR','BONE_FLIP_DIRECTION'), ('DISSOLVE','BONE_DISSOLVE'),
        ('SPLIT','BONE_SPLIT'), ('SEPARATE','BONE_SEPARATE'),
        ('MAKE PARENT','BONE_PARENT'), ('CLEAR PARENT','BONE_CLEAR_PARENT'),
        ('RECALC ROLL','BONE_RECALC_ROLL'), ('FILL','BONE_FILL'),
        ('BACK','BACK'),
    ),
    'ARMATURE_SETTINGS': (
        ('CONNECT','BONE_CONNECT'), ('DEFORM','BONE_DEFORM'),
        ('LOCK','BONE_LOCK'), ('ROLL +','BONE_ROLL_UP'),
        ('ROLL -','BONE_ROLL_DOWN'), ('AUTO NAMES','BONE_AUTO_NAMES'),
        ('FLIP NAMES','BONE_FLIP_NAMES'), ('BACK','BACK'),
    ),
}
PAGES_RETURN = {
    'ARMATURE_SELECT': 'ARMATURE_EDIT',
    'ARMATURE_OPERATIONS': 'ARMATURE_EDIT',
    'ARMATURE_SETTINGS': 'ARMATURE_EDIT',
}
EDIT_TOOLS = {'BONE_SELECT', 'BONE_MOVE', 'BONE_MOVE_HEAD', 'BONE_MOVE_TAIL'}
EDIT_ACTIONS = {
    'BONE_SEL_ALL': ('select_all', {'action': 'SELECT'}),
    'BONE_SEL_NONE': ('select_all', {'action': 'DESELECT'}),
    'BONE_SEL_INVERT': ('select_all', {'action': 'INVERT'}),
    'BONE_SEL_PARENT': ('select_hierarchy', {'direction': 'PARENT', 'extend': False}),
    'BONE_SEL_CHILD': ('select_hierarchy', {'direction': 'CHILD', 'extend': False}),
    'BONE_SEL_LINKED': ('select_linked', {}),
    'BONE_SEL_MIRROR': ('select_mirror', {'extend': False}),
    'BONE_HIDE': ('hide', {'unselected': False}),
    'BONE_HIDE_OTHER': ('hide', {'unselected': True}),
    'BONE_REVEAL': ('reveal', {}),
    'BONE_SUBDIVIDE': ('subdivide', {'number_cuts': 1}),
    'BONE_SYMMETRIZE': ('symmetrize', {}),
    'BONE_FLIP_DIRECTION': ('switch_direction', {}),
    'BONE_DISSOLVE': ('dissolve', {}),
    'BONE_SPLIT': ('split', {}),
    'BONE_SEPARATE': ('separate', {}),
    'BONE_PARENT': ('parent_set', {'type': 'OFFSET'}),
    'BONE_CLEAR_PARENT': ('parent_clear', {'type': 'CLEAR'}),
    'BONE_RECALC_ROLL': ('calculate_roll', {'type': 'GLOBAL_POS_Z'}),
    'BONE_FILL': ('fill', {}),
    'BONE_AUTO_NAMES': ('autoside_names', {'type': 'XAXIS'}),
    'BONE_FLIP_NAMES': ('flip_names', {}),
    'BONE_DELETE': ('delete', {}),
    'BONE_DUPLICATE': ('duplicate', {}),
}
BONE_ACTIONS = tuple(EDIT_ACTIONS) + (
    'BONE_CONNECT', 'BONE_DEFORM', 'BONE_LOCK',
    'BONE_ROLL_UP', 'BONE_ROLL_DOWN', 'BONE_EXTRUDE',
)



def install_pages():
    for page, entries in ARMATURE_PAGES.items():
        menus.PAGES[page] = entries
    menus.TITLES.update({
        'ARMATURE_EDIT': 'BONE EDIT',
        'ARMATURE_SELECT': 'BONE SELECT',
        'ARMATURE_OPERATIONS': 'BONE OPERATIONS',
        'ARMATURE_SETTINGS': 'BONE SETTINGS',
    })
    menus.PAGES['RIGGING'] = (
        ('ARMATURE','RIG_CREATE'), ('SELECT RIG','RIG_SELECT_ARMATURE'),
        ('EDIT BONES','RIG_EDIT_TOGGLE'), ('ADD BONE','RIG_ADD_BONE'),
        ('EMPTY GROUPS','RIG_BIND_EMPTY'), ('AUTO WEIGHTS','RIG_BIND'),
        ('WEIGHT PAINT','RIG_WEIGHT'), ('CLEAN WEIGHTS','RIG_CLEAN'),
        ('POSE TEST','RIG_POSE'), ('AUDIT MESH','RIG_AUDIT'),
        ('BACK','BACK'),
    )


def active_armature(context, *, edit=False):
    obj = context.view_layer.objects.active
    if obj is None or obj.type != 'ARMATURE' or (edit and obj.mode != 'EDIT'):
        raise ValueError('Select an armature and enter Bone Edit Mode')
    if obj.library or obj.data.library:
        raise ValueError('Linked armatures cannot be edited')
    return obj


def _closest_segment(origin, direction, head, tail):
    """Nearest positive ray-to-segment distance, point and ray depth."""
    ray = Vector(direction).normalized()
    start = Vector(head)
    vector = Vector(tail) - start
    length_sq = vector.length_squared
    if length_sq <= 1e-12:
        return None
    difference = start - Vector(origin)
    b = ray.dot(vector)
    d = ray.dot(difference)
    e = vector.dot(difference)
    denom = length_sq - b * b
    if abs(denom) > 1e-10:
        portion = max(0.0, min(1.0, (b * d - e) / denom))
    else:
        portion = max(0.0, min(1.0, -e / length_sq))
    point = start + vector * portion
    depth = (point - Vector(origin)).dot(ray)
    if depth <= 0:
        return None
    nearest = Vector(origin) + ray * depth
    return (nearest - point).length, depth, point, portion


def ray_pick_bone(context, origin, direction, *, only_active=False):
    """Pick visible bones by ray; Blender's mesh ray_cast cannot pick armatures."""
    active = context.view_layer.objects.active
    candidates = ([active] if only_active and active is not None else
                  [obj for obj in context.view_layer.objects if obj.type == 'ARMATURE'])
    hits = []
    for obj in candidates:
        if obj.type != 'ARMATURE' or not obj.visible_get(view_layer=context.view_layer):
            continue
        bones = obj.data.edit_bones if obj.mode == 'EDIT' else obj.data.bones
        for bone in bones:
            if bone.hide:
                continue
            head = obj.matrix_world @ bone.head
            tail = obj.matrix_world @ bone.tail
            hit = _closest_segment(origin, direction, head, tail)
            if hit is None:
                continue
            distance, depth, location, portion = hit
            radius = max(0.03, min(0.14, depth * 0.018))
            if distance <= radius:
                which = ('HEAD' if portion < 0.18 else
                         'TAIL' if portion > 0.82 else 'BODY')
                hits.append((depth, distance, obj, bone.name, location, which))
    return min(hits, key=lambda item: (item[0], item[1])) if hits else None


def activate_armature(context):
    """Choose an existing armature unambiguously, including a mesh's bound rig."""
    obj = context.view_layer.objects.active
    if obj and obj.type == 'ARMATURE':
        arm = obj
    else:
        candidates = []
        if obj and obj.type == 'MESH':
            if obj.parent and obj.parent.type == 'ARMATURE':
                candidates.append(obj.parent)
            candidates.extend(mod.object for mod in obj.modifiers
                              if mod.type == 'ARMATURE' and mod.object is not None)
            candidates.extend(candidate for candidate in context.view_layer.objects
                              if candidate.type == 'ARMATURE'
                              and candidate.get('mesh_xr_target_mesh') == obj.name)
        candidates.extend(candidate for candidate in context.selected_objects
                          if candidate.type == 'ARMATURE')
        if not candidates:
            visible = [candidate for candidate in context.view_layer.objects
                       if candidate.type == 'ARMATURE' and candidate.visible_get()]
            if len(visible) == 1:
                candidates = visible
            elif obj and obj.type == 'MESH' and visible:
                # A newly-created, unbound rig is often inside the mesh and
                # impossible to ray-select. Prefer the closest rig to its
                # bounding box, provided the choice is unambiguous.
                center = obj.matrix_world @ (
                    sum((Vector(v) for v in obj.bound_box), Vector()) / 8.0)
                ranked = sorted((arm.matrix_world.translation - center).length
                                for arm in visible)
                if len(ranked) == 1 or ranked[0] + 0.01 < ranked[1]:
                    candidates = [min(visible,
                                      key=lambda rig:
                                      (rig.matrix_world.translation - center).length)]
        unique = {item.name: item for item in candidates}
        if len(unique) != 1:
            raise ValueError('Cannot choose a rig: use a bound mesh or select one rig')
        arm = next(iter(unique.values()))
    if arm.mode not in {'OBJECT', 'EDIT'}:
        raise ValueError('Leave Pose Mode before editing armature bones')
    if obj and obj.mode != 'OBJECT' and obj != arm:
        bpy.ops.object.mode_set(mode='OBJECT')
    paired_mesh = obj if obj and obj.type == 'MESH' else None
    if paired_mesh is None:
        meshes = [candidate for candidate in context.selected_objects
                  if candidate.type == 'MESH' and candidate.visible_get()]
        if len(meshes) == 1:
            paired_mesh = meshes[0]
    if paired_mesh:
        arm['mesh_xr_target_mesh'] = paired_mesh.name
    for selected in context.selected_objects:
        selected.select_set(False)
    arm.select_set(True)
    if paired_mesh and arm.mode == 'OBJECT':
        paired_mesh.select_set(True)
    context.view_layer.objects.active = arm
    return arm


def pick_edit_bone(context, origin, direction, *, additive=False):
    hit = ray_pick_bone(context, origin, direction, only_active=True)
    if not hit:
        return None
    _, _, arm, name, point, which = hit
    bones = arm.data.edit_bones
    if not additive:
        for bone in bones:
            bone.select = False
            bone.select_head = False
            bone.select_tail = False
    bone = bones[name]
    bone.select = True
    bone.select_head = True
    bone.select_tail = True
    bones.active = bone
    return bone, point, which


def perform_edit_action(context, action):
    arm = active_armature(context, edit=True)
    if action == 'BONE_EXTRUDE':
        # Extrude from active tip with a repeatable length. Blender's modal
        # extrude_move operator cannot be used by a controller-bound menu.
        active = arm.data.edit_bones.active
        if active is None:
            raise ValueError('Select the bone to extend first')
        for bone in arm.data.edit_bones:
            bone.select = False
            bone.select_head = False
            bone.select_tail = False
        child = arm.data.edit_bones.new('Bone')
        child.parent = active
        child.use_connect = True
        child.head = active.tail.copy()
        direction = active.tail - active.head
        child.tail = child.head + (direction if direction.length > 0.001
                                  else Vector((0, 0, 0.5)))
        child.select = True
        child.select_head = True
        child.select_tail = True
        arm.data.edit_bones.active = child
        return 'Bone extruded; use MOVE/HEAD/TAIL to position'
    if action in {'BONE_CONNECT','BONE_DEFORM','BONE_LOCK','BONE_ROLL_UP','BONE_ROLL_DOWN'}:
        selected = [bone for bone in arm.data.edit_bones if bone.select]
        if not selected:
            raise ValueError('Select one or more edit bones first')
        for bone in selected:
            if action == 'BONE_CONNECT':
                if bone.parent is not None:
                    bone.use_connect = not bone.use_connect
            elif action == 'BONE_DEFORM':
                bone.use_deform = not bone.use_deform
            elif action == 'BONE_LOCK':
                bone.lock = not bone.lock
            else:
                bone.roll += math.radians(15 if action == 'BONE_ROLL_UP' else -15)
        return action.replace('_', ' ')
    if action not in EDIT_ACTIONS:
        raise ValueError('Unknown armature edit action: ' + action)
    operator, arguments = EDIT_ACTIONS[action]
    result = getattr(bpy.ops.armature, operator)(**arguments)
    if 'FINISHED' not in result:
        raise ValueError('Blender could not perform ' + action.replace('_', ' '))
    return action.replace('_', ' ')


def step_bone_drag(arm, drag, world_location, snap=0):
    """Update a selected bone's head/tail in local coordinates from VR motion."""
    bone = arm.data.edit_bones.get(drag['bone'])
    if bone is None:
        raise ValueError('The selected bone no longer exists')
    world_delta = Vector(world_location) - drag['origin']
    delta = arm.matrix_world.inverted().to_3x3() @ world_delta
    if snap:
        delta = Vector(tuple(round(c / snap) * snap for c in delta))
    if drag['part'] == 'HEAD':
        bone.head = drag['head'] + delta
    elif drag['part'] == 'TAIL':
        bone.tail = drag['tail'] + delta
    else:
        bone.head = drag['head'] + delta
        bone.tail = drag['tail'] + delta


class BXR_OT_select_armature(bpy.types.Operator):
    bl_idname = 'blender_xr.select_armature'
    bl_label = 'Select Armature'
    bl_description = 'Select the rig linked to the current mesh, or the only visible armature'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            arm = activate_armature(context)
            self.report({'INFO'}, 'Selected armature: ' + arm.name)
            return {'FINISHED'}
        except (ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class BXR_OT_bone_action(bpy.types.Operator):
    bl_idname = 'blender_xr.bone_action'
    bl_label = 'Armature Edit Tool'
    bl_description = 'Apply a native Blender Edit Bone operation in the active armature'
    bl_options = {'REGISTER', 'UNDO'}
    action: StringProperty(name='Edit Bone Action')

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return obj is not None and obj.type == 'ARMATURE' and obj.mode == 'EDIT'

    def execute(self, context):
        try:
            result = perform_edit_action(context, self.action)
            self.report({'INFO'}, result)
            return {'FINISHED'}
        except (ValueError, RuntimeError, AttributeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class BXR_PT_armature_edit(bpy.types.Panel):
    bl_idname = 'BXR_PT_armature_edit'
    bl_label = 'Edit Bone Tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Blender XR'
    bl_parent_id = 'BXR_PT_panel'

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        settings = getattr(context.scene, 'blender_xr', None)
        return (bool(settings and settings.ui_section == 'MODEL') and obj is not None
                and obj.type == 'ARMATURE' and obj.mode == 'EDIT')

    def draw(self, context):
        layout = self.layout
        obj = context.view_layer.objects.active
        layout.label(text='Active: ' + (obj.data.edit_bones.active.name
                                      if obj.data.edit_bones.active else 'None'), icon='BONE_DATA')
        for title, icon, actions in (
            ('Selection', 'RESTRICT_SELECT_OFF', (
                'BONE_SEL_ALL', 'BONE_SEL_NONE', 'BONE_SEL_INVERT',
                'BONE_SEL_PARENT', 'BONE_SEL_CHILD', 'BONE_SEL_LINKED',
                'BONE_SEL_MIRROR', 'BONE_HIDE', 'BONE_HIDE_OTHER', 'BONE_REVEAL')),
            ('Create / Delete', 'BONE_DATA', (
                'BONE_EXTRUDE', 'BONE_DUPLICATE', 'BONE_DELETE', 'BONE_FILL',
                'BONE_DISSOLVE', 'BONE_SUBDIVIDE')),
            ('Modify / Organize', 'ARMATURE_DATA', (
                'BONE_SYMMETRIZE', 'BONE_FLIP_DIRECTION', 'BONE_RECALC_ROLL',
                'BONE_SPLIT', 'BONE_SEPARATE', 'BONE_PARENT', 'BONE_CLEAR_PARENT')),
            ('Bone Settings', 'PROPERTIES', (
                'BONE_CONNECT', 'BONE_DEFORM', 'BONE_LOCK',
                'BONE_ROLL_UP', 'BONE_ROLL_DOWN',
                'BONE_AUTO_NAMES', 'BONE_FLIP_NAMES')),
        ):
            box = layout.box()
            box.label(text=title, icon=icon)
            for i in range(0, len(actions), 2):
                row = box.row(align=True)
                for action in actions[i:i + 2]:
                    icon_name = ('ADD' if action in {'BONE_EXTRUDE','BONE_FILL'}
                                 else 'X' if action in {'BONE_DELETE','BONE_DISSOLVE'}
                                 else 'DUPLICATE' if action == 'BONE_DUPLICATE'
                                 else 'ARMATURE_DATA' if action in {'BONE_PARENT','BONE_CLEAR_PARENT'}
                                 else 'RESTRICT_SELECT_OFF' if action.startswith('BONE_SEL')
                                 else 'BONE_DATA')
                    row.operator('blender_xr.bone_action',
                                 text=action.replace('BONE_', '').replace('_', ' ').title(),
                                 icon=icon_name).action = action
        if hasattr(bpy.types, 'VIEW3D_MT_edit_armature'):
            layout.menu('VIEW3D_MT_edit_armature',
                        text='All Blender Armature Edit Tools', icon='ARMATURE_DATA')
        if hasattr(bpy.types, 'VIEW3D_MT_select_edit_armature'):
            layout.menu('VIEW3D_MT_select_edit_armature',
                        text='All Blender Bone Selection', icon='RESTRICT_SELECT_OFF')
        layout.label(text='F3 also searches native Blender bone tools', icon='VIEWZOOM')


def patch_runtime(Runtime):
    if getattr(Runtime, '_v076_armature_patched', False):
        return
    old_hit = Runtime.object_hit
    old_select = Runtime.select
    old_begin_tool = Runtime.begin_tool
    old_tick = Runtime.tick
    old_command = Runtime.command
    old_cancel = Runtime.cancel_work

    def object_hit(self, context, origin, direction):
        surface = old_hit(self, context, origin, direction)
        active = context.view_layer.objects.active
        if active and active.type == 'MESH' and active.mode == 'WEIGHT_PAINT':
            # In Paint mode, the pointer must hit mesh polygons instead of
            # jumping forward to an overlaid armature bone.
            return surface
        bone = ray_pick_bone(context, origin, direction)
        if bone is not None:
            _, _, obj, _name, point, _part = bone
            # Bone overlays are displayed in front of the skinned mesh.
            if (surface is None or obj.show_in_front or
                    bone[0] <= (surface[1] - Vector(origin)).length + 0.15):
                return obj, point
        return surface

    def select(self, context, origin, direction, additive=False):
        obj = context.view_layer.objects.active
        if obj and obj.type == 'ARMATURE' and obj.mode == 'EDIT':
            selected = pick_edit_bone(context, origin, direction, additive=additive)
            self.status = ('BONE ' + selected[0].name.upper()) if selected else 'POINT AT A BONE'
            return
        return old_select(self, context, origin, direction, additive=additive)

    def begin_tool(self, context, origin, rotation):
        arm = context.view_layer.objects.active
        if arm and arm.type == 'ARMATURE' and arm.mode == 'EDIT':
            if self.tool == 'BONE_SELECT':
                self.select(context, origin, rotation @ Vector((0, 0, -1)),
                            additive=self.grip.down)
                return
            if self.tool in {'BONE_MOVE', 'BONE_MOVE_HEAD', 'BONE_MOVE_TAIL'}:
                picked = pick_edit_bone(context, origin,
                                        rotation @ Vector((0, 0, -1)),
                                        additive=False)
                bone = picked[0] if picked else arm.data.edit_bones.active
                if bone is None:
                    raise ValueError('Select an edit bone before moving it')
                self.bone_drag = {
                    'armature': arm.name,
                    'bone': bone.name,
                    'head': bone.head.copy(),
                    'tail': bone.tail.copy(),
                    'origin': Vector(origin),
                    'part': ('HEAD' if self.tool == 'BONE_MOVE_HEAD' else
                             'TAIL' if self.tool == 'BONE_MOVE_TAIL' else 'BODY'),
                }
                self.status = 'MOVE BONE / RELEASE TRIGGER TO APPLY'
                return
        return old_begin_tool(self, context, origin, rotation)

    def cancel_work(self):
        drag = getattr(self, 'bone_drag', None)
        if drag:
            arm = bpy.data.objects.get(drag['armature'])
            if arm is not None and arm.mode == 'EDIT':
                bone = arm.data.edit_bones.get(drag['bone'])
                if bone is not None:
                    bone.head = drag['head']
                    bone.tail = drag['tail']
            self.bone_drag = None
        return old_cancel(self)

    def tick(self, context):
        drag = getattr(self, 'bone_drag', None)
        if drag:
            from . import actions, runtime
            state = context.window_manager.xr_session_state
            arm = bpy.data.objects.get(drag['armature'])
            if not arm or arm.mode != 'EDIT':
                self.cancel_work()
                raise ValueError('Armature editing stopped; bone move cancelled')
            if self.bridge:
                inputs = self.bridge.read()
                if inputs is None:
                    self.cancel_work()
                    return
                pressed = inputs[self.dom][0] >= 0.45
            else:
                pressed = actions.read(context, 'trigger', self.dom)[0] >= 0.45
            position = Vector(state.controller_aim_location_get(context, self.dom))
            if pressed:
                step_bone_drag(arm, drag, position,
                               self.settings.step if self.settings.precision_mode else 0)
                self.status = 'MOVING ' + drag['bone'].upper()
            else:
                self.bone_drag = None
                self.trigger.update(0.0)
                runtime.haptic_pulse(context, self.settings, self.dom)
                self.status = 'BONE MOVED'
            return
        return old_tick(self, context)

    def command(self, context, action):
        if action == 'RIG_SELECT_ARMATURE':
            arm = activate_armature(context)
            self.status = 'SELECTED ' + arm.name.upper()
            return
        if action == 'RIG_EDIT_TOGGLE':
            arm = activate_armature(context)
            if arm.mode == 'OBJECT':
                bpy.ops.blender_xr.edit_bones()
                self.menu.page = 'ARMATURE_EDIT'
                self.tool = 'BONE_SELECT'
                self.status = 'POINT AT A BONE / TRIGGER TO SELECT'
            elif arm.mode == 'EDIT':
                bpy.ops.blender_xr.finish_bones()
                self.menu.page = 'RIGGING'
                self.tool = 'SELECT'
                self.status = 'ARMATURE OBJECT MODE'
            return
        if action in {'BONE_SELECT_MENU','BONE_EDIT_MENU','BONE_SETTINGS_MENU'}:
            active_armature(context, edit=True)
            self.menu.page = {
                'BONE_SELECT_MENU':'ARMATURE_SELECT',
                'BONE_EDIT_MENU':'ARMATURE_OPERATIONS',
                'BONE_SETTINGS_MENU':'ARMATURE_SETTINGS',
            }[action]
            return
        if action == 'BACK' and self.menu.page in PAGES_RETURN:
            self.menu.page = 'ARMATURE_EDIT'
            self.status = 'BONE EDIT'
            return
        if action in EDIT_TOOLS:
            active_armature(context, edit=True)
            self.tool = action
            self.menu.page = 'ARMATURE_EDIT'
            self.status = action.replace('_', ' ')
            return
        if action in BONE_ACTIONS:
            if getattr(self, 'bone_drag', None):
                raise ValueError('Release your bone move before using another tool')
            if action == 'RIG_ADD_BONE':
                return old_command(self, context, action)
            self.status = perform_edit_action(context, action).upper()
            return
        if action == 'RIG_ADD_BONE' and context.view_layer.objects.active:
            arm = context.view_layer.objects.active
            if arm.type == 'ARMATURE' and arm.mode == 'EDIT':
                result = bpy.ops.blender_xr.add_bone()
                if 'FINISHED' not in result:
                    raise ValueError('Blender could not add a bone')
                self.status = 'BONE ADDED'
                return
        return old_command(self, context, action)

    Runtime.object_hit = object_hit
    Runtime.select = select
    Runtime.begin_tool = begin_tool
    Runtime.tick = tick
    Runtime.command = command
    Runtime.cancel_work = cancel_work
    Runtime._v076_armature_patched = True


CLASSES = (BXR_OT_select_armature, BXR_OT_bone_action, BXR_PT_armature_edit)
