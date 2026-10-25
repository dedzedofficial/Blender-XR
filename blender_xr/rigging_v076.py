# SPDX-License-Identifier: GPL-3.0-or-later
"""v0.7.6: shared VR object selection, armature/mesh pairing, vertex groups.

Keep standard Blender Object, Armature Edit, Weight Paint and Pose modes intact:
XR menu commands only prepare the native selection/mode state Blender expects.
"""
import time

import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree
from . import armature_v076, menus

WEIGHT_PAGE = (
    ('PAINT', 'WEIGHT_BRUSH'), ('ERASE', 'WEIGHT_ERASE'),
    ('GROUP -', 'WEIGHT_GROUP_PREV'), ('GROUP +', 'WEIGHT_GROUP_NEXT'),
    ('WEIGHT -', 'WEIGHT_STRENGTH_DOWN'), ('WEIGHT +', 'WEIGHT_STRENGTH_UP'),
    ('SIZE -', 'WEIGHT_RADIUS_DOWN'), ('SIZE +', 'WEIGHT_RADIUS_UP'),
    ('DONE', 'RIG_EXIT_PAINT'),
)

PARENT_PAGE = (
    ('AUTO WEIGHTS', 'PARENT_AUTO'),
    ('EMPTY GROUPS', 'PARENT_EMPTY'),
    ('ENVELOPES', 'PARENT_ENVELOPE'),
    ('ARMATURE', 'PARENT_ARMATURE'),
    ('OBJECT PARENT', 'PARENT_OBJECT'),
    ('CLEAR PARENT', 'PARENT_CLEAR'),
    ('BACK', 'BACK'),
)


def install_pages():
    # Weight Paint is a first-class Blender mode, not just a rigging action.
    mode = list(menus.PAGES['MODE_SELECT'])
    if not any(action == 'MODE_WEIGHT_PAINT' for _, action in mode):
        mode.insert(2, ('WEIGHT PAINT', 'MODE_WEIGHT_PAINT'))
    menus.PAGES['MODE_SELECT'] = tuple(mode)
    menus.PAGES['RIGGING'] = (
        ('ARMATURE', 'RIG_CREATE'), ('SELECT', 'SELECT'),
        ('EDIT BONES', 'RIG_EDIT_TOGGLE'),
        ('ADD BONE', 'RIG_ADD_BONE'), ('PARENT', 'PARENT_MENU'),
        ('WEIGHT PAINT', 'MODE_WEIGHT_PAINT'),
        ('CLEAN', 'RIG_CLEAN'), ('POSE', 'RIG_POSE'),
        ('AUDIT', 'RIG_AUDIT'), ('BACK', 'BACK'),
    )
    menus.PAGES['PARENT_RIG'] = PARENT_PAGE
    menus.PAGES['WEIGHT_PAINT'] = WEIGHT_PAGE
    menus.TITLES['PARENT_RIG'] = 'PARENT TO ARMATURE'
    menus.TITLES['WEIGHT_PAINT'] = 'WEIGHT PAINT MODE'


def _valid(context, obj, kind):
    return (obj is not None and obj.type == kind
            and obj.name in context.view_layer.objects
            and obj.visible_get(view_layer=context.view_layer))

def mesh_for_rig(context, arm=None):
    """Resolve a mesh even when Blender currently has only the rig selected.

    A remembered mesh name is stable across Mode switches and works before
    parenting, unlike relying on context.selected_objects alone.
    """
    current = context.view_layer.objects.active
    if _valid(context, current, 'MESH'):
        return current
    if arm is None and _valid(context, current, 'ARMATURE'):
        arm = current
    if arm is not None:
        candidate = bpy.data.objects.get(arm.get('mesh_xr_target_mesh', ''))
        if _valid(context, candidate, 'MESH'):
            return candidate
    meshes = [obj for obj in context.selected_objects
              if _valid(context, obj, 'MESH')]
    if len(meshes) == 1:
        return meshes[0]
    if arm:
        paired = [obj for obj in context.view_layer.objects
                  if obj.type == 'MESH' and obj.visible_get(view_layer=context.view_layer)
                  and (obj.parent == arm or any(
                      mod.type == 'ARMATURE' and mod.object == arm for mod in obj.modifiers))]
        if len(paired) == 1:
            return paired[0]
    visible = [obj for obj in context.view_layer.objects
               if obj.type == 'MESH' and obj.visible_get(view_layer=context.view_layer)]
    if len(visible) == 1:
        return visible[0]
    if arm and visible:
        center = arm.matrix_world.translation
        ranked = sorted(visible, key=lambda obj:
                        (obj.matrix_world.translation - center).length)
        if len(ranked) == 1 or (
            (ranked[1].matrix_world.translation - center).length -
            (ranked[0].matrix_world.translation - center).length > 0.01):
            return ranked[0]
    raise ValueError('Select the intended mesh, or bind it to the rig first')

def ensure_object_mode(context):
    current = context.view_layer.objects.active
    if current and current.mode != 'OBJECT':
        result = bpy.ops.object.mode_set(mode='OBJECT')
        if 'FINISHED' not in result:
            raise ValueError('Could not leave ' + current.mode + ' mode')

def paired_selection(context, arm, target, *, mesh_active=False):
    """Atomic Blender-style Object Mode selection for the two rigging targets."""
    ensure_object_mode(context)
    if not _valid(context, arm, 'ARMATURE') or not _valid(context, target, 'MESH'):
        raise ValueError('A visible mesh and armature are required')
    if arm.library or arm.data.library or target.library or target.data.library:
        raise ValueError('Linked assets cannot be rigged')
    for obj in context.selected_objects:
        obj.select_set(False)
    arm.select_set(True)
    target.select_set(True)
    context.view_layer.objects.active = target if mesh_active else arm
    arm['mesh_xr_target_mesh'] = target.name
    return arm, target

def select_mesh(context):
    active = context.view_layer.objects.active
    arm = active if _valid(context, active, 'ARMATURE') else None
    target = mesh_for_rig(context, arm)
    ensure_object_mode(context)
    for obj in context.selected_objects:
        obj.select_set(False)
    target.select_set(True)
    if arm:
        arm.select_set(True)
        arm['mesh_xr_target_mesh'] = target.name
    context.view_layer.objects.active = target
    return target

def ensure_deform_groups(mesh, arm):
    """Extend, never replace existing paint when bones are added to a rig."""
    for bone in arm.data.bones:
        if bone.use_deform and mesh.vertex_groups.get(bone.name) is None:
            mesh.vertex_groups.new(name=bone.name)
    return active_group(mesh)


def already_bound(mesh, arm):
    return (mesh.parent == arm
            and any(mod.type == 'ARMATURE' and mod.object == arm
                    for mod in mesh.modifiers))


def resolve_pair(context):
    """Use regular Blender selection or remembered armature/mesh pairing."""
    current = context.view_layer.objects.active
    if _valid(context, current, 'ARMATURE'):
        arm = current
    elif _valid(context, current, 'MESH'):
        arm = armature_v076.activate_armature(context)
    else:
        raise ValueError('Select a mesh or armature with the normal Select tool')
    mesh = mesh_for_rig(context, arm)
    return arm, mesh


def parent_to_armature(context, method):
    """Blender Ctrl+P types, including parenting without deformation."""
    if method not in {'ARMATURE_AUTO', 'ARMATURE_NAME', 'ARMATURE_ENVELOPE',
                      'ARMATURE', 'OBJECT'}:
        raise ValueError('Unsupported parenting method: ' + str(method))
    ensure_object_mode(context)
    arm, target = resolve_pair(context)
    if target.parent and target.parent != arm:
        raise ValueError('Mesh has a different parent; clear that relationship first')
    paired_selection(context, arm, target)
    if method != 'OBJECT' and already_bound(target, arm):
        # Reparenting must never wipe vertex weights the artist has painted.
        ensure_deform_groups(target, arm)
        return target, arm, False
    if method == 'OBJECT' and target.parent == arm:
        return target, arm, False
    result = bpy.ops.object.parent_set(type=method, keep_transform=True)
    if 'FINISHED' not in result or target.parent != arm:
        raise ValueError('Blender could not parent the mesh to the armature')
    if method == 'ARMATURE_NAME':
        ensure_deform_groups(target, arm)
    return target, arm, True


def clear_mesh_parent(context):
    """Native Blender Clear Parent (Keep Transform); retain any weight groups."""
    ensure_object_mode(context)
    target = mesh_for_rig(context)
    if target.parent is None:
        raise ValueError('Selected mesh has no parent')
    for obj in context.selected_objects:
        obj.select_set(False)
    target.select_set(True)
    context.view_layer.objects.active = target
    result = bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    if 'FINISHED' not in result or target.parent is not None:
        raise ValueError('Clear Parent failed')
    return target


def enter_weight_mode(context):
    """Enter native Weight Paint without implicitly parenting anything."""
    ensure_object_mode(context)
    active = context.view_layer.objects.active
    arm = active if _valid(context, active, 'ARMATURE') else None
    if arm is None and _valid(context, active, 'MESH'):
        target = active
        try:
            arm = armature_v076.activate_armature(context)
        except ValueError:
            arm = None
    else:
        target = mesh_for_rig(context, arm)
    if target is None or target.type != 'MESH':
        raise ValueError('Select a mesh to enter Weight Paint mode')
    if arm is not None:
        arm['mesh_xr_target_mesh'] = target.name
        ensure_deform_groups(target, arm)
    if not target.vertex_groups:
        target.vertex_groups.new(name='Group')
    for item in context.selected_objects:
        item.select_set(False)
    target.select_set(True)
    context.view_layer.objects.active = target
    active_group(target)
    result = bpy.ops.blender_xr.weight_paint()
    if 'FINISHED' not in result or target.mode != 'WEIGHT_PAINT':
        raise ValueError('Blender refused Weight Paint mode; see its error report')
    context.view_layer.update()
    return target


def active_group(obj):
    if not obj.vertex_groups:
        raise ValueError('Mesh has no vertex groups; use Empty Groups to bind it')
    group = obj.vertex_groups.active
    if group is None or group.index < 0:
        obj.vertex_groups.active_index = 0
        group = obj.vertex_groups.active
    if group is None:
        raise ValueError('Could not activate a vertex group')
    return group

def paint_vertices(obj, world_origin, world_direction, radius, strength, erase=False):
    """Controller-ray brush on the selected Blender vertex group (no PC mouse).

    Uses a bounded KD query and writes real vertex-group weights so standard
    Blender Weight Paint and Pose Mode see the same data. No mesh topology edits.
    """
    if obj.type != 'MESH' or obj.mode != 'WEIGHT_PAINT':
        raise ValueError('Activate a mesh in Blender Weight Paint mode')
    group = active_group(obj)
    inv = obj.matrix_world.inverted_safe()
    local_origin = inv @ Vector(world_origin)
    local_direction = (inv.to_3x3() @ Vector(world_direction)).normalized()
    # Prefer the evaluated surface location where Armature modifiers deform
    # the mesh; use local cage raycast as a fallback for unmodified meshes.
    hit = False
    local_point = None
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        found, world_point, _normal, _face, surface, _matrix = (
            bpy.context.scene.ray_cast(depsgraph, world_origin, world_direction))
        if found and surface.original == obj:
            local_point = inv @ world_point
            hit = True
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass
    if not hit:
        hit, local_point, _normal, _face_index = (
            obj.ray_cast(local_origin, local_direction))
    if not hit:
        return 0
    verts = obj.data.vertices
    if not verts:
        return 0
    tree = KDTree(len(verts))
    for vert in verts:
        tree.insert(vert.co, vert.index)
    tree.balance()
    scale = max(1e-6, min(abs(v) for v in obj.matrix_world.to_scale()))
    search_radius = radius / scale
    changes = 0
    world_point = obj.matrix_world @ local_point
    for _co, index, _dist in tree.find_range(local_point, search_radius):
        falloff = 1 - (obj.matrix_world @ verts[index].co - world_point).length / radius
        if falloff <= 0:
            continue
        try:
            weight = group.weight(index)
        except RuntimeError:
            weight = 0.0
        influence = min(1.0, strength * falloff)
        result = (weight * (1.0 - influence) if erase
                  else weight + (1.0 - weight) * influence)
        group.add([index], max(0.0, min(1.0, result)), 'REPLACE')
        changes += 1
        if changes >= 256:
            break
    if not changes:
        # Low-poly meshes can have no vertex inside a narrow brush circle.
        # If the ray hit a visible polygon, paint the nearest vertex rather
        # than silently doing nothing (especially common for Quest assets).
        nearest = tree.find(local_point)
        if nearest:
            _co, index, _dist = nearest
            try:
                weight = group.weight(index)
            except RuntimeError:
                weight = 0.0
            influence = min(1.0, strength * 0.5)
            result = (weight * (1.0 - influence) if erase
                      else weight + (1.0 - weight) * influence)
            group.add([index], max(0.0, min(1.0, result)), 'REPLACE')
            changes = 1
    if changes:
        obj.data.update()
        bpy.context.view_layer.update()
    return changes

class BXR_OT_select_mesh(bpy.types.Operator):
    bl_idname = 'blender_xr.select_mesh'
    bl_label = 'Select Rigging Mesh'
    bl_description = 'Activate the mesh paired with the active armature'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            target = select_mesh(context)
            active_group(target) if target.vertex_groups else None
            self.report({'INFO'}, 'Mesh selected: ' + target.name)
            return {'FINISHED'}
        except (ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class BXR_OT_bind_paired(bpy.types.Operator):
    bl_idname = 'blender_xr.bind_paired'
    bl_label = 'Bind Rig and Mesh'
    bl_description = 'Select the paired armature and mesh, then bind in Blender'
    bl_options = {'REGISTER', 'UNDO'}
    binding: bpy.props.StringProperty(default='EMPTY')

    def execute(self, context):
        try:
            ensure_object_mode(context)
            current = context.view_layer.objects.active
            arm = (current if _valid(context, current, 'ARMATURE')
                   else armature_v076.activate_armature(context))
            mesh = mesh_for_rig(context, arm)
            paired_selection(context, arm, mesh)
            if already_bound(mesh, arm):
                ensure_deform_groups(mesh, arm)
                self.report({'INFO'}, 'Already bound; existing painted weights preserved')
                return {'FINISHED'}
            result = (bpy.ops.blender_xr.bind_empty_weights() if self.binding == 'EMPTY'
                      else bpy.ops.blender_xr.bind_auto_weights())
            if 'FINISHED' not in result:
                raise ValueError('Binding failed; inspect the Blender operator report')
            ensure_deform_groups(mesh, arm)
            self.report({'INFO'}, 'Bound ' + mesh.name + ' to ' + arm.name)
            return {'FINISHED'}
        except (ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class BXR_OT_parent_paired(bpy.types.Operator):
    bl_idname = 'blender_xr.parent_paired'
    bl_label = 'Parent Mesh to Armature'
    bl_description = 'Blender-style Ctrl+P parenting: automatic, empty, envelope, deform or object'
    bl_options = {'REGISTER', 'UNDO'}
    parent_type: bpy.props.StringProperty(default='ARMATURE_NAME')

    def execute(self, context):
        try:
            target, arm, changed = parent_to_armature(context, self.parent_type)
            self.report({'INFO'}, ('Parented ' if changed else 'Already parented: ') +
                        target.name + ' → ' + arm.name)
            return {'FINISHED'}
        except (RuntimeError, ValueError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class BXR_OT_clear_mesh_parent(bpy.types.Operator):
    bl_idname = 'blender_xr.clear_mesh_parent'
    bl_label = 'Clear Parent (Keep Transform)'
    bl_description = 'Use Blender Clear Parent while retaining the mesh world transform'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            mesh = clear_mesh_parent(context)
            self.report({'INFO'}, 'Cleared parent of ' + mesh.name)
            return {'FINISHED'}
        except (RuntimeError, ValueError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class BXR_OT_weight_mode(bpy.types.Operator):
    bl_idname = 'blender_xr.weight_mode'
    bl_label = 'Weight Paint Mode'
    bl_description = 'Switch to native Blender Weight Paint mode (like Object/Edit Mode)'
    bl_options = {'REGISTER', 'UNDO'}
    enabled: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        try:
            if self.enabled:
                target = enter_weight_mode(context)
                self.report({'INFO'}, 'Weight Paint: ' + active_group(target).name)
            else:
                ensure_object_mode(context)
            return {'FINISHED'}
        except (ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class BXR_OT_select_weight_group(bpy.types.Operator):
    bl_idname = 'blender_xr.select_weight_group'
    bl_label = 'Select Vertex Group'
    bl_options = {'REGISTER', 'UNDO'}
    direction: bpy.props.IntProperty(default=1)

    def execute(self, context):
        try:
            obj = context.view_layer.objects.active
            if not obj or obj.type != 'MESH':
                obj = select_mesh(context)
            active_group(obj)
            obj.vertex_groups.active_index = (
                obj.vertex_groups.active_index + self.direction) % len(obj.vertex_groups)
            self.report({'INFO'}, 'Vertex group: ' + active_group(obj).name)
            return {'FINISHED'}
        except (ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


def patch_runtime(Runtime):
    if getattr(Runtime, '_v076_rigging_paired', False):
        return
    original_command = Runtime.command
    original_select = Runtime.select
    original_begin = Runtime.begin_tool
    original_tick = Runtime.tick

    def select(self, context, origin, direction, additive=False):
        obj = context.view_layer.objects.active
        if additive and (obj is None or obj.mode == 'OBJECT'):
            if self.transaction or self.grab or self.axis_move or self.air_grab:
                raise ValueError('Finish the current tool before selecting')
            hit = self.object_hit(context, origin, direction)
            if not hit:
                self.status = 'AIM AT A MESH OR BONE'
                return
            selected = hit[0]
            if not selected.select_get():
                selected.select_set(True)
            # Grip + Trigger extends selection without losing either object.
            if selected.type == 'ARMATURE':
                context.view_layer.objects.active = selected
            elif not any(other.type == 'ARMATURE' for other in context.selected_objects):
                context.view_layer.objects.active = selected
            arm = next((other for other in context.selected_objects
                        if other.type == 'ARMATURE'), None)
            mesh = next((other for other in context.selected_objects
                         if other.type == 'MESH'), None)
            if arm and mesh:
                arm['mesh_xr_target_mesh'] = mesh.name
            self.status = 'ADDED ' + selected.name.upper()
            return
        # When selecting a rig by pointing at a bone, keep the mesh paired:
        # unlike conventional object picking, binding needs both objects.
        prior_mesh = obj if obj and obj.type == 'MESH' and obj.mode == 'OBJECT' else None
        result = original_select(self, context, origin, direction, additive=additive)
        active = context.view_layer.objects.active
        if prior_mesh and active and active.type == 'ARMATURE':
            active['mesh_xr_target_mesh'] = prior_mesh.name
            prior_mesh.select_set(True)
        return result

    def command(self, context, action):
        if action == 'RIG_CREATE':
            source = context.view_layer.objects.active
            result = original_command(self, context, action)
            arm = context.view_layer.objects.active
            if source and source.type == 'MESH' and arm and arm.type == 'ARMATURE':
                paired_selection(context, arm, source)
            return result
        if action == 'RIG_SELECT_MESH':
            target = select_mesh(context)
            self.menu.page = 'RIGGING'
            self.tool = 'SELECT'
            self.status = 'MESH: ' + target.name.upper()
            return
        if action == 'RIG_SELECT_ARMATURE':
            ensure_object_mode(context)
            result = original_command(self, context, action)
            self.menu.page = 'RIGGING'
            self.tool = 'SELECT'
            return result
        if action in {'RIG_BIND', 'RIG_BIND_EMPTY'}:
            ensure_object_mode(context)
            current = context.view_layer.objects.active
            arm = (current if _valid(context, current, 'ARMATURE')
                   else armature_v076.activate_armature(context))
            target = mesh_for_rig(context, arm)
            paired_selection(context, arm, target)
            if already_bound(target, arm):
                ensure_deform_groups(target, arm)
                self.status = 'ALREADY BOUND / PAINTED WEIGHTS PRESERVED'
                return
            result = original_command(self, context, action)
            arm['mesh_xr_target_mesh'] = target.name
            ensure_deform_groups(target, arm)
            self.status = 'BOUND ' + target.name.upper() + ' / GROUP ' + active_group(target).name.upper()
            return result
        if action == 'RIG_WEIGHT':
            ensure_object_mode(context)
            current = context.view_layer.objects.active
            arm = current if _valid(context, current, 'ARMATURE') else None
            if arm is None and current and current.type == 'MESH':
                try:
                    arm = armature_v076.activate_armature(context)
                except ValueError:
                    arm = None
            target = mesh_for_rig(context, arm)
            if not target.vertex_groups and arm:
                paired_selection(context, arm, target)
                result = bpy.ops.blender_xr.bind_empty_weights()
                if 'FINISHED' not in result:
                    raise ValueError('Could not create empty groups for manual painting')
            if not target.vertex_groups:
                raise ValueError('No deform groups. Select a rig and use Empty Groups first')
            if arm:
                arm['mesh_xr_target_mesh'] = target.name
            for candidate in context.selected_objects:
                candidate.select_set(False)
            target.select_set(True)
            context.view_layer.objects.active = target
            active_group(target)
            result = original_command(self, context, action)
            self.tool = 'WEIGHT_BRUSH'
            self.menu.page = 'WEIGHT_PAINT'
            self.status = 'PAINT ' + active_group(target).name.upper()
            return result
        if action == 'RIG_EXIT_PAINT':
            ensure_object_mode(context)
            self.tool = 'SELECT'
            self.menu.page = 'RIGGING'
            self.status = 'WEIGHT PAINT FINISHED'
            return
        if action in {'WEIGHT_BRUSH', 'WEIGHT_ERASE'}:
            obj = context.view_layer.objects.active
            if not obj or obj.type != 'MESH' or obj.mode != 'WEIGHT_PAINT':
                raise ValueError('Enter Weight Paint first')
            self.tool = 'WEIGHT_BRUSH'
            if action == 'WEIGHT_ERASE':
                self.settings.weight_erase = not self.settings.weight_erase
            self.status = ('ERASE' if self.settings.weight_erase else 'PAINT') + ' ' + active_group(obj).name.upper()
            return
        if action in {'WEIGHT_GROUP_PREV', 'WEIGHT_GROUP_NEXT'}:
            obj = context.view_layer.objects.active
            if not obj or obj.type != 'MESH' or obj.mode != 'WEIGHT_PAINT':
                raise ValueError('Select a weighted mesh in Weight Paint')
            active_group(obj)
            count = len(obj.vertex_groups)
            delta = -1 if action.endswith('PREV') else 1
            obj.vertex_groups.active_index = (obj.vertex_groups.active_index + delta) % count
            self.status = 'GROUP ' + active_group(obj).name.upper()
            return
        if action in {'WEIGHT_STRENGTH_UP', 'WEIGHT_STRENGTH_DOWN'}:
            factor = 1.25 if action.endswith('UP') else 0.8
            self.settings.weight_brush_strength = min(1.0, max(0.01,
                                               self.settings.weight_brush_strength * factor))
            self.status = 'STRENGTH ' + str(round(self.settings.weight_brush_strength, 2))
            return
        if action in {'WEIGHT_RADIUS_UP', 'WEIGHT_RADIUS_DOWN'}:
            factor = 1.25 if action.endswith('UP') else 0.8
            self.settings.weight_brush_radius = min(3.0, max(0.01,
                                              self.settings.weight_brush_radius * factor))
            self.status = 'BRUSH SIZE ' + str(round(self.settings.weight_brush_radius, 3))
            return
        if action in {'RIG_CLEAN', 'RIG_AUDIT'}:
            ensure_object_mode(context)
            target = select_mesh(context)
            result = original_command(self, context, action)
            self.menu.page = 'RIGGING'
            self.status = action.replace('_', ' ') + ' / ' + target.name.upper()
            return result
        if action == 'RIG_POSE':
            active = context.view_layer.objects.active
            if active and active.type == 'ARMATURE' and active.mode == 'POSE':
                return command(self, context, 'RIG_EXIT_POSE')
            ensure_object_mode(context)
            current = context.view_layer.objects.active
            if not _valid(context, current, 'ARMATURE'):
                armature_v076.activate_armature(context)
            result = original_command(self, context, action)
            self.tool = 'SELECT'
            self.menu.page = 'RIGGING'
            return result
        if action == 'RIG_EXIT_POSE':
            ensure_object_mode(context)
            self.menu.page = 'RIGGING'
            self.tool = 'SELECT'
            self.status = 'OBJECT MODE'
            return
        if action == 'RIG_EDIT_TOGGLE':
            current = context.view_layer.objects.active
            if current and current.mode == 'POSE':
                ensure_object_mode(context)
            return original_command(self, context, action)
        if action == 'BACK' and self.menu.page == 'WEIGHT_PAINT':
            return command(self, context, 'RIG_EXIT_PAINT')
        return original_command(self, context, action)

    def begin_tool(self, context, origin, rotation):
        obj = context.view_layer.objects.active
        if obj and obj.type == 'MESH' and obj.mode == 'WEIGHT_PAINT':
            if self.tool != 'WEIGHT_BRUSH':
                raise ValueError('Use Paint or Erase from the weight menu')
            changes = paint_vertices(obj, origin, rotation @ Vector((0, 0, -1)),
                                     self.settings.weight_brush_radius,
                                     self.settings.weight_brush_strength,
                                     self.settings.weight_erase)
            self.status = ('ERASED ' if self.settings.weight_erase else 'PAINTED ') + str(changes) + ' VERTS / ' + active_group(obj).name.upper()
            return
        return original_begin(self, context, origin, rotation)

    def tick(self, context):
        # Let the existing XR update own controllers, menu interaction, navigation
        # and haptics. Extend it only for held-trigger brush samples.
        result = original_tick(self, context)
        obj = context.view_layer.objects.active if hasattr(context, 'view_layer') else None
        if (obj and obj.type == 'MESH' and obj.mode == 'WEIGHT_PAINT'
                and self.tool == 'WEIGHT_BRUSH' and self.trigger.down
                and not self.hover and self.ray):
            now = time.monotonic()
            if now - getattr(self, '_weight_last_sample', 0.0) >= 0.07:
                origin, direction = self.ray
                paint_vertices(obj, origin, direction,
                               self.settings.weight_brush_radius,
                               self.settings.weight_brush_strength,
                               self.settings.weight_erase)
                self._weight_last_sample = now
        return result

    Runtime.command = command
    Runtime.select = select
    Runtime.begin_tool = begin_tool
    Runtime.tick = tick
    Runtime._v076_rigging_paired = True


CLASSES = (BXR_OT_select_mesh, BXR_OT_bind_paired, BXR_OT_parent_paired,
           BXR_OT_clear_mesh_parent, BXR_OT_weight_mode, BXR_OT_select_weight_group)
