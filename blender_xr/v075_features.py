# SPDX-License-Identifier: GPL-3.0-or-later
"""Mesh XR v0.7.5: rigging helpers and non-destructive asset diagnostics."""
import bpy
import bmesh
from mathutils import Vector


def active_mesh(context):
    obj = context.view_layer.objects.active
    if not obj or obj.type != 'MESH':
        raise ValueError('Select an active mesh object')
    if obj.library or obj.data.library:
        raise ValueError('Linked meshes cannot be changed by these tools')
    return obj


def _selection_snapshot(context):
    return tuple(context.selected_objects), context.view_layer.objects.active


def _restore_selection(context, selected, active):
    """Best-effort restoration so a failed operator does not strand the UI."""
    try:
        for obj in context.view_layer.objects:
            obj.select_set(False)
    except (ReferenceError, RuntimeError):
        pass
    for obj in selected:
        try:
            if obj.name in context.view_layer.objects:
                obj.select_set(True)
        except (ReferenceError, RuntimeError):
            pass
    try:
        context.view_layer.objects.active = (
            active if active is not None and active.name in context.view_layer.objects else None
        )
    except (ReferenceError, RuntimeError):
        pass


def mesh_health(obj, depsgraph=None):
    """Read-only source and evaluated-mesh audit; never applies modifiers."""
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        # Boundary edges (one linked face) are open borders, not the same
        # issue as edges shared by more than two faces. Report separately.
        boundary_edges = sum(1 for edge in bm.edges if edge.is_boundary)
        non_manifold = sum(1 for edge in bm.edges if edge.link_faces and not edge.is_boundary and not edge.is_manifold)
        loose_verts = sum(1 for vert in bm.verts if not vert.link_edges)
        loose_edges = sum(1 for edge in bm.edges if not edge.link_faces)
        degenerate_faces = sum(1 for face in bm.faces if face.calc_area() <= 1e-12)
        base_triangles = sum(max(0, len(face.verts) - 2) for face in bm.faces)
        data = {
            'vertices': len(bm.verts), 'edges': len(bm.edges), 'faces': len(bm.faces),
            'base_triangles': base_triangles, 'non_manifold_edges': non_manifold,
            'boundary_edges': boundary_edges,
            'loose_vertices': loose_verts, 'loose_edges': loose_edges,
            'degenerate_faces': degenerate_faces,
            'has_uvs': bool(obj.data.uv_layers),
            'materials': len(obj.data.materials),
            'missing_material_faces': sum(1 for face in bm.faces if not obj.data.materials or face.material_index >= len(obj.data.materials)),
            'modifiers': len(obj.modifiers),
        }
    finally:
        bm.free()

    # Count the evaluated mesh so viewport modifiers such as Subdivision,
    # Mirror and Solidify are reflected in the triangle-budget warning.
    evaluated_triangles = None
    evaluation_error = None
    evaluated_obj = None
    try:
        graph = depsgraph or bpy.context.evaluated_depsgraph_get()
        evaluated_obj = obj.evaluated_get(graph)
        evaluated_mesh = evaluated_obj.to_mesh()
        if evaluated_mesh is None:
            raise RuntimeError('Blender did not return an evaluated mesh')
        try:
            evaluated_mesh.calc_loop_triangles()
            evaluated_triangles = len(evaluated_mesh.loop_triangles)
        finally:
            evaluated_obj.to_mesh_clear()
    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError) as exc:
        evaluation_error = str(exc)

    data['evaluated_triangles'] = evaluated_triangles
    data['evaluation_error'] = evaluation_error
    data['triangles'] = evaluated_triangles if evaluated_triangles is not None else data['base_triangles']
    return data


def _report_health(operator, obj, triangle_budget=0):
    data = mesh_health(obj, bpy.context.evaluated_depsgraph_get())
    evaluated = data['evaluated_triangles']
    triangle_label = (
        '{} evaluated tris ({} base)'.format(evaluated, data['base_triangles'])
        if evaluated is not None else '{} base tris (modifier evaluation unavailable)'.format(data['base_triangles'])
    )
    operator.report({'INFO'}, '{} verts, {} faces, {}'.format(data['vertices'], data['faces'], triangle_label))
    issues = []
    if data['non_manifold_edges']:
        issues.append('{} non-manifold edges (shared by 3+ faces)'.format(data['non_manifold_edges']))
    if data['boundary_edges']:
        issues.append('{} boundary/open edges'.format(data['boundary_edges']))
    if data['loose_vertices']:
        issues.append('{} loose vertices'.format(data['loose_vertices']))
    if data['loose_edges']:
        issues.append('{} loose edges'.format(data['loose_edges']))
    if data['degenerate_faces']:
        issues.append('{} degenerate faces'.format(data['degenerate_faces']))
    if not data['has_uvs']:
        issues.append('no UV map')
    if not data['materials']:
        issues.append('no materials')
    if data['missing_material_faces']:
        issues.append('{} faces without a valid material slot'.format(data['missing_material_faces']))
    budget_triangles = evaluated if evaluated is not None else data['base_triangles']
    if evaluated is None:
        issues.append('evaluated triangle count unavailable; budget check is using the base mesh')
    if triangle_budget and budget_triangles > triangle_budget:
        issues.append('triangle budget exceeded: {} > {}'.format(budget_triangles, triangle_budget))
    operator.report({'WARNING'} if issues else {'INFO'},
                    ('Needs review: ' + '; '.join(issues)) if issues else 'No basic mesh-health issues detected')
    return data


class BXR_OT_asset_audit(bpy.types.Operator):
    bl_idname = 'blender_xr.asset_audit'
    bl_label = 'Audit Selected Mesh'
    bl_description = 'Read-only check for topology, UVs, materials and modifier count'
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            obj = active_mesh(context)
            if obj.mode != 'OBJECT':
                raise ValueError('Switch to Object Mode before running the asset audit')
            _report_health(self, obj, context.scene.blender_xr.triangle_budget)
            return {'FINISHED'}
        except (ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class BXR_OT_create_basic_rig(bpy.types.Operator):
    """Retain the old operator ID for saved shortcuts; use a plain armature now."""
    bl_idname = 'blender_xr.create_basic_rig'
    bl_label = 'Create Armature'
    bl_description = 'Create a regular Blender armature with one editable bone; no humanoid shape required'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return (obj is None or obj.mode == 'OBJECT') and context.mode == 'OBJECT'

    def execute(self, context):
        selected_before, active_before = _selection_snapshot(context)
        arm_obj = None
        arm_data = None
        try:
            source = context.view_layer.objects.active
            mesh_obj = source if source is not None and source.type == 'MESH' else None
            if mesh_obj and (mesh_obj.library or mesh_obj.data.library):
                raise ValueError('A linked mesh cannot be edited')
            # Use world-space mesh bounds. This supports upright, wide, flat,
            # asymmetrical or rotated meshes without a humanoid assumption.
            if mesh_obj and mesh_obj.type == 'MESH' and mesh_obj.data.vertices:
                points = [mesh_obj.matrix_world @ Vector(corner)
                          for corner in mesh_obj.bound_box]
                lowest = Vector(tuple(min(p[i] for p in points) for i in range(3)))
                highest = Vector(tuple(max(p[i] for p in points) for i in range(3)))
                middle = (lowest + highest) * 0.5
                sizes = highest - lowest
                axis = max(range(3), key=lambda i: sizes[i])
                distance = max(sizes[axis] * 0.5, 0.25)
            else:
                middle = context.scene.cursor.location.copy()
                axis = 2
                distance = 1.0
            direction = Vector((1.0 if axis == 0 else 0.0,
                                1.0 if axis == 1 else 0.0,
                                1.0 if axis == 2 else 0.0))
            arm_data = bpy.data.armatures.new('Mesh XR Armature')
            arm_obj = bpy.data.objects.new('Mesh XR Armature', arm_data)
            context.collection.objects.link(arm_obj)
            arm_obj.location = middle
            arm_obj.show_in_front = True
            if mesh_obj:
                arm_obj['mesh_xr_target_mesh'] = mesh_obj.name
            bpy.ops.object.select_all(action='DESELECT')
            arm_obj.select_set(True)
            context.view_layer.objects.active = arm_obj
            bpy.ops.object.mode_set(mode='EDIT')
            bone = arm_data.edit_bones.new('Bone')
            bone.head = -direction * (distance * 0.5)
            bone.tail = direction * (distance * 0.5)
            arm_data.edit_bones.active = bone
            bone.select = True
            bpy.ops.object.mode_set(mode='OBJECT')
            if mesh_obj:
                mesh_obj.select_set(True)
            context.view_layer.objects.active = arm_obj
            self.report({'INFO'}, 'Armature created. Edit Bones to add, move or extrude bones; then bind and paint weights.')
            return {'FINISHED'}
        except Exception as exc:
            try:
                current = context.view_layer.objects.active
                if current is not None and current.mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
            except (ReferenceError, RuntimeError):
                pass
            if arm_obj is not None:
                try:
                    datablock = arm_obj.data
                    bpy.data.objects.remove(arm_obj, do_unlink=True)
                    if datablock and datablock.users == 0:
                        bpy.data.armatures.remove(datablock)
                except (ReferenceError, RuntimeError, TypeError):
                    pass
            elif arm_data is not None:
                try:
                    if arm_data.users == 0:
                        bpy.data.armatures.remove(arm_data)
                except (ReferenceError, RuntimeError, TypeError):
                    pass
            _restore_selection(context, selected_before, active_before)
            self.report({'ERROR'}, 'Armature creation failed: ' + str(exc))
            return {'CANCELLED'}


class BXR_OT_edit_bones(bpy.types.Operator):
    bl_idname = 'blender_xr.edit_bones'
    bl_label = 'Edit Bones'
    bl_description = 'Enter Blender Armature Edit Mode to position, extrude, rename and parent bones'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return obj is not None and obj.type == 'ARMATURE' and obj.mode == 'OBJECT'

    def execute(self, context):
        try:
            bpy.ops.object.mode_set(mode='EDIT')
            return {'FINISHED'}
        except RuntimeError as exc:
            self.report({'ERROR'}, 'Cannot edit bones: ' + str(exc))
            return {'CANCELLED'}


class BXR_OT_finish_bones(bpy.types.Operator):
    bl_idname = 'blender_xr.finish_bones'
    bl_label = 'Finish Bones'
    bl_description = 'Leave armature Edit Mode and return to Object Mode'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return obj is not None and obj.type == 'ARMATURE' and obj.mode == 'EDIT'

    def execute(self, context):
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
            return {'FINISHED'}
        except RuntimeError as exc:
            self.report({'ERROR'}, 'Cannot finish editing bones: ' + str(exc))
            return {'CANCELLED'}


class BXR_OT_add_bone(bpy.types.Operator):
    bl_idname = 'blender_xr.add_bone'
    bl_label = 'Add Bone'
    bl_description = 'Add a normal Blender bone; extend the selected bone or add one at the armature origin'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return obj is not None and obj.type == 'ARMATURE' and obj.mode in {'OBJECT', 'EDIT'}

    def execute(self, context):
        arm_obj = context.view_layer.objects.active
        was_object = arm_obj.mode == 'OBJECT'
        try:
            if was_object:
                bpy.ops.object.mode_set(mode='EDIT')
            bones = arm_obj.data.edit_bones
            parent = bones.active if bones.active and bones.active.select else None
            if parent:
                head = parent.tail.copy()
                delta = parent.tail - parent.head
                if delta.length < 0.01:
                    delta = Vector((0, 0, 0.5))
            else:
                head = Vector((0, 0, 0))
                delta = Vector((0, 0, 0.5))
            for existing in bones:
                existing.select = False
                existing.select_head = False
                existing.select_tail = False
            bone = bones.new('Bone')
            bone.head = head
            bone.tail = head + delta
            if parent:
                bone.parent = parent
                bone.use_connect = True
            bone.select = True
            bone.select_head = True
            bone.select_tail = True
            bones.active = bone
            self.report({'INFO'}, 'Bone created. Select and position it in Blender Armature Edit Mode.')
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, 'Could not add bone: ' + str(exc))
            return {'CANCELLED'}
        finally:
            if was_object and arm_obj.mode == 'EDIT':
                try:
                    bpy.ops.object.mode_set(mode='OBJECT')
                except RuntimeError:
                    pass


class BXR_OT_bind_auto_weights(bpy.types.Operator):
    bl_idname = 'blender_xr.bind_auto_weights'
    bl_label = 'Bind with Automatic Weights'
    bl_description = 'Parent the selected mesh to the selected armature using Blender automatic weights'
    bl_options = {'REGISTER', 'UNDO'}
    binding_type = 'ARMATURE_AUTO'

    @classmethod
    def poll(cls, context):
        selected = context.selected_objects
        return (len(selected) >= 2 and context.view_layer.objects.active is not None
                and context.view_layer.objects.active.type == 'ARMATURE'
                and any(obj.type == 'MESH' for obj in selected))

    def execute(self, context):
        armature = context.view_layer.objects.active
        meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        selected_before, active_before = _selection_snapshot(context)
        original_state = {}
        original_groups = {}
        try:
            if armature is None or armature.type != 'ARMATURE':
                raise ValueError('Select an armature and make it active')
            if armature.mode != 'OBJECT':
                raise ValueError('Armature must be in Object Mode')
            if armature.library or armature.data.library:
                raise ValueError('Linked armatures cannot be used for automatic binding')
            if not meshes:
                raise ValueError('Select at least one mesh to bind')
            for obj in meshes:
                if obj.mode != 'OBJECT':
                    raise ValueError(obj.name + ' must be in Object Mode')
                if obj.library or obj.data.library:
                    raise ValueError('Linked meshes cannot be bound')
                if obj.parent and obj.parent != armature:
                    raise ValueError(obj.name + ' already has another parent; resolve it first')
                original_state[obj] = (
                    obj.parent, obj.matrix_parent_inverse.copy(), obj.matrix_world.copy()
                )
                original_groups[obj] = {group.name for group in obj.vertex_groups}

            # Ensure Blender's parent operator only processes the intended mesh
            # objects and the selected active armature.
            for obj in context.view_layer.objects:
                obj.select_set(False)
            armature.select_set(True)
            for obj in meshes:
                obj.select_set(True)
            context.view_layer.objects.active = armature
            result = bpy.ops.object.parent_set(type=self.binding_type)
            if 'FINISHED' not in result:
                raise RuntimeError('Blender cancelled automatic weight binding')
            unbound = [obj.name for obj in meshes if obj.parent != armature]
            if unbound:
                raise RuntimeError('Blender did not bind: ' + ', '.join(unbound))
            self.report({'INFO'},
                        'Empty bone groups ready: select the mesh and paint weights manually.'
                        if self.binding_type == 'ARMATURE_NAME'
                        else 'Automatic weights assigned. Test deformation and correct weights before export.')
            return {'FINISHED'}
        except Exception as exc:
            # Restore object relationships and remove newly-created groups if the
            # automatic-weight operator fails after partially processing a mesh.
            for obj, state in original_state.items():
                parent, parent_inverse, world_matrix = state
                try:
                    obj.parent = parent
                    obj.matrix_parent_inverse = parent_inverse
                    obj.matrix_world = world_matrix
                    existing_names = original_groups.get(obj, set())
                    for group in list(obj.vertex_groups):
                        if group.name not in existing_names:
                            obj.vertex_groups.remove(group)
                except (ReferenceError, RuntimeError, TypeError, ValueError):
                    pass
            _restore_selection(context, selected_before, active_before)
            self.report({'ERROR'}, 'Automatic weights failed: ' + str(exc))
            return {'CANCELLED'}

class BXR_OT_bind_empty_weights(BXR_OT_bind_auto_weights):
    """Same guarded binding and rollback path, but without automatic weights."""
    bl_idname = 'blender_xr.bind_empty_weights'
    bl_label = 'Bind with Empty Groups'
    bl_description = 'Create bone-named vertex groups with zero weights for manual weight painting'
    binding_type = 'ARMATURE_NAME'


class BXR_OT_weight_cleanup(bpy.types.Operator):
    bl_idname = 'blender_xr.weight_cleanup'
    bl_label = 'Normalize and Clean Weights'
    bl_description = 'Normalize and clean vertex-group weights on selected meshes without changing rig structure'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        selected_before, active_before = _selection_snapshot(context)
        if not meshes:
            self.report({'ERROR'}, 'Select one or more meshes with vertex groups')
            return {'CANCELLED'}
        try:
            for obj in meshes:
                if obj.mode != 'OBJECT':
                    raise ValueError(obj.name + ' must be in Object Mode')
                if obj.library or obj.data.library:
                    raise ValueError('Linked meshes cannot be modified')
            meshes = [obj for obj in meshes if obj.vertex_groups]
            if not meshes:
                raise ValueError('Selected meshes do not have vertex groups')

            completed = 0
            for obj in meshes:
                for candidate in context.view_layer.objects:
                    candidate.select_set(False)
                obj.select_set(True)
                context.view_layer.objects.active = obj
                clean_result = bpy.ops.object.vertex_group_clean(
                    group_select_mode='ALL', limit=0.001, keep_single=True
                )
                if 'FINISHED' not in clean_result:
                    raise RuntimeError('Blender could not clean weights on ' + obj.name)
                normalize_result = bpy.ops.object.vertex_group_normalize_all(
                    group_select_mode='ALL', lock_active=False
                )
                if 'FINISHED' not in normalize_result:
                    raise RuntimeError('Blender could not normalize weights on ' + obj.name)
                completed += 1
            self.report({'INFO'}, 'Normalized and cleaned weights on {} mesh(es)'.format(completed))
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, 'Weight cleanup failed: ' + str(exc))
            return {'CANCELLED'}
        finally:
            _restore_selection(context, selected_before, active_before)

class BXR_OT_pose_test(bpy.types.Operator):
    bl_idname = 'blender_xr.pose_test'
    bl_label = 'Enter Pose Mode'
    bl_description = 'Select the active armature and enter Pose Mode to test deformation'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return obj is not None and obj.type == 'ARMATURE' and obj.mode == 'OBJECT'

    def execute(self, context):
        try:
            bpy.ops.object.mode_set(mode='POSE')
            return {'FINISHED'}
        except RuntimeError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}




class BXR_OT_weight_paint(bpy.types.Operator):
    bl_idname = 'blender_xr.weight_paint'
    bl_label = 'Enter Weight Paint'
    bl_description = 'Show vertex weights and enter Blender Weight Paint mode'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return obj is not None and obj.type == 'MESH' and obj.mode == 'OBJECT' and bool(obj.vertex_groups)

    def execute(self, context):
        obj = context.view_layer.objects.active
        selected_before, active_before = _selection_snapshot(context)
        old_mask_vertex = obj.data.use_paint_mask_vertex
        old_mask_face = obj.data.use_paint_mask
        try:
            if not obj.vertex_groups:
                raise ValueError('Mesh has no vertex groups yet. Bind it to an armature first.')
            # Empty vertex groups exist after ARMATURE_NAME binding, but no
            # active group may have been selected. Native Blender weight tools
            # need one; select a real bone group before switching modes.
            if obj.vertex_groups.active is None:
                obj.vertex_groups.active_index = 0
            if obj.vertex_groups.active is None:
                raise ValueError('Choose a vertex group to paint')
            result = bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
            if 'FINISHED' not in result:
                raise RuntimeError('Blender could not enter Weight Paint mode')
            obj.data.use_paint_mask_vertex = False
            obj.data.use_paint_mask = False
            return {'FINISHED'}
        except Exception as exc:
            try:
                if obj.mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
            except (ReferenceError, RuntimeError):
                pass
            try:
                obj.data.use_paint_mask_vertex = old_mask_vertex
                obj.data.use_paint_mask = old_mask_face
            except (ReferenceError, RuntimeError):
                pass
            _restore_selection(context, selected_before, active_before)
            self.report({'ERROR'}, 'Could not enter Weight Paint mode: ' + str(exc))
            return {'CANCELLED'}


class BXR_PT_workflow(bpy.types.Panel):
    bl_label = 'Mesh XR Workflow'
    bl_idname = 'BXR_PT_workflow'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mesh XR'
    bl_parent_id = 'BXR_PT_panel'

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, 'blender_xr', None)
        return settings is not None and settings.ui_section == 'MODEL'

    def draw(self, context):
        layout = self.layout
        obj = context.view_layer.objects.active
        layout.label(text='Asset readiness', icon='CHECKMARK')
        layout.prop(context.scene.blender_xr, 'triangle_budget', icon='MESH_DATA')
        row = layout.row(align=True)
        row.operator('blender_xr.asset_audit', icon='VIEWZOOM')
        row.operator('wm.search_menu', text='Search Tools', icon='VIEWZOOM')
        layout.separator()
        layout.label(text='Rigging / weight painting', icon='ARMATURE_DATA')
        layout.operator('blender_xr.create_basic_rig', text='Create Armature', icon='ARMATURE_DATA')
        if obj and obj.type == 'ARMATURE':
            if obj.mode == 'OBJECT':
                layout.operator('blender_xr.edit_bones', text='Edit Bones', icon='EDITMODE_HLT')
            if obj.mode in {'OBJECT', 'EDIT'}:
                layout.operator('blender_xr.add_bone', text='Add Bone', icon='BONE_DATA')
            if obj.mode == 'EDIT':
                layout.operator('blender_xr.finish_bones', text='Finish Editing', icon='CHECKMARK')
        layout.label(text='Rig and mesh pairing works without Shift-select', icon='INFO')
        layout.label(text='Use Select in the headset to pick mesh or rig', icon='RESTRICT_SELECT_OFF')
        row = layout.row(align=True)
        row.operator('blender_xr.bind_paired', text='Empty Groups', icon='GROUP_VERTEX').binding = 'EMPTY'
        row.operator('blender_xr.bind_paired', text='Auto Weights', icon='CONSTRAINT_BONE').binding = 'AUTO'
        layout.operator('blender_xr.weight_cleanup', icon='GROUP_VERTEX')
        if obj and obj.type == 'MESH' and obj.mode == 'OBJECT' and obj.vertex_groups:
            layout.operator('blender_xr.weight_paint', icon='WPAINT_HLT')
        if obj and obj.type == 'ARMATURE' and obj.mode == 'OBJECT':
            layout.operator('blender_xr.pose_test', icon='POSE_HLT')
        layout.separator()
        layout.label(text='Controller modelling', icon='HAND')
        layout.label(text='Grip: grab / move objects', icon='HAND')
        layout.label(text='Edit: select, move, scale, extrude', icon='EDITMODE_HLT')
        layout.label(text='PC mirror: Session workspace', icon='WINDOW')


CLASSES = (
    BXR_OT_asset_audit, BXR_OT_create_basic_rig, BXR_OT_edit_bones,
    BXR_OT_add_bone, BXR_OT_finish_bones, BXR_OT_bind_auto_weights,
    BXR_OT_bind_empty_weights, BXR_OT_weight_cleanup, BXR_OT_pose_test, BXR_OT_weight_paint, BXR_PT_workflow,
)
