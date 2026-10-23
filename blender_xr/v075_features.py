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
    bl_idname = 'blender_xr.create_basic_rig'
    bl_label = 'Create Basic Human Rig'
    bl_description = 'Create a starter humanoid armature fitted to an upright mesh bounding box; review bone placement before binding'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return obj is not None and obj.type == 'MESH' and obj.mode == 'OBJECT'

    def execute(self, context):
        selected_before, active_before = _selection_snapshot(context)
        arm_obj = None
        arm_data = None
        try:
            obj = active_mesh(context)
            if obj.mode != 'OBJECT':
                raise ValueError('Switch to Object Mode first')
            bounds = [Vector(corner) for corner in obj.bound_box]
            min_v = Vector(tuple(min(v[i] for v in bounds) for i in range(3)))
            max_v = Vector(tuple(max(v[i] for v in bounds) for i in range(3)))
            height = max_v.z - min_v.z
            width = max_v.x - min_v.x
            depth = max_v.y - min_v.y
            if height <= 1e-6 or width <= 1e-6 or depth <= 1e-6:
                raise ValueError('Mesh needs non-zero dimensions on all axes')
            if height < width * 1.15:
                raise ValueError('This starter rig expects an upright humanoid mesh taller than it is wide')
            center_x = (min_v.x + max_v.x) * 0.5
            center_y = (min_v.y + max_v.y) * 0.5
            z0, z1 = min_v.z, max_v.z
            w = width * 0.5
            # A deliberately simple starter rig. Bone placement is a proportion-based
            # guide only; users should inspect and adjust it before automatic binding.
            points = {
                'root': (center_x, center_y, z0 + height * 0.08),
                'pelvis': (center_x, center_y, z0 + height * 0.48),
                'spine': (center_x, center_y, z0 + height * 0.62),
                'chest': (center_x, center_y, z0 + height * 0.73),
                'neck': (center_x, center_y, z0 + height * 0.82),
                'head': (center_x, center_y, z0 + height * 0.96),
                'shoulder.L': (center_x - w * 0.62, center_y, z0 + height * 0.74),
                'elbow.L': (center_x - w * 1.05, center_y, z0 + height * 0.59),
                'hand.L': (center_x - w * 1.18, center_y, z0 + height * 0.46),
                'shoulder.R': (center_x + w * 0.62, center_y, z0 + height * 0.74),
                'elbow.R': (center_x + w * 1.05, center_y, z0 + height * 0.59),
                'hand.R': (center_x + w * 1.18, center_y, z0 + height * 0.46),
                'hip.L': (center_x - w * 0.30, center_y, z0 + height * 0.47),
                'knee.L': (center_x - w * 0.31, center_y, z0 + height * 0.26),
                'foot.L': (center_x - w * 0.31, center_y - depth * 0.18, z0 + height * 0.04),
                'hip.R': (center_x + w * 0.30, center_y, z0 + height * 0.47),
                'knee.R': (center_x + w * 0.31, center_y, z0 + height * 0.26),
                'foot.R': (center_x + w * 0.31, center_y - depth * 0.18, z0 + height * 0.04),
            }
            links = [
                ('root','pelvis'), ('pelvis','spine'), ('spine','chest'),
                ('chest','neck'), ('neck','head'),
                ('chest','shoulder.L'), ('shoulder.L','elbow.L'), ('elbow.L','hand.L'),
                ('chest','shoulder.R'), ('shoulder.R','elbow.R'), ('elbow.R','hand.R'),
                ('pelvis','hip.L'), ('hip.L','knee.L'), ('knee.L','foot.L'),
                ('pelvis','hip.R'), ('hip.R','knee.R'), ('knee.R','foot.R'),
            ]
            # Standard, predictable bone names make the starter rig easier to
            # inspect, weight-paint, retarget and adapt for common export workflows.
            points.update({
                'root_tip': (center_x, center_y, z0 + height * 0.12),
                'pelvis_base': (center_x, center_y, z0 + height * 0.42),
                'hand_end.L': (center_x - w * 1.35, center_y, z0 + height * 0.45),
                'hand_end.R': (center_x + w * 1.35, center_y, z0 + height * 0.45),
                'ankle.L': (center_x - w * 0.31, center_y, z0 + height * 0.08),
                'ankle.R': (center_x + w * 0.31, center_y, z0 + height * 0.08),
            })
            bone_specs = [
                ('root', 'root', 'root_tip', None, False),
                ('pelvis', 'pelvis_base', 'pelvis', 'root', False),
                ('spine', 'pelvis', 'spine', 'pelvis', True),
                ('chest', 'spine', 'chest', 'spine', True),
                ('neck', 'chest', 'neck', 'chest', True),
                ('head', 'neck', 'head', 'neck', True),
                ('upper_arm.L', 'shoulder.L', 'elbow.L', 'chest', False),
                ('forearm.L', 'elbow.L', 'hand.L', 'upper_arm.L', True),
                ('hand.L', 'hand.L', 'hand_end.L', 'forearm.L', True),
                ('upper_arm.R', 'shoulder.R', 'elbow.R', 'chest', False),
                ('forearm.R', 'elbow.R', 'hand.R', 'upper_arm.R', True),
                ('hand.R', 'hand.R', 'hand_end.R', 'forearm.R', True),
                ('thigh.L', 'hip.L', 'knee.L', 'pelvis', False),
                ('shin.L', 'knee.L', 'ankle.L', 'thigh.L', True),
                ('foot.L', 'ankle.L', 'foot.L', 'shin.L', True),
                ('thigh.R', 'hip.R', 'knee.R', 'pelvis', False),
                ('shin.R', 'knee.R', 'ankle.R', 'thigh.R', True),
                ('foot.R', 'ankle.R', 'foot.R', 'shin.R', True),
            ]
            arm_data = bpy.data.armatures.new(obj.name + ' Mesh XR Rig')
            arm_obj = bpy.data.objects.new(obj.name + ' Mesh XR Rig', arm_data)
            context.collection.objects.link(arm_obj)
            arm_obj.matrix_world = obj.matrix_world.copy()
            bpy.ops.object.select_all(action='DESELECT')
            arm_obj.select_set(True)
            context.view_layer.objects.active = arm_obj
            bpy.ops.object.mode_set(mode='EDIT')
            bones = {}
            for name, start, end, _parent, _connected in bone_specs:
                bone = arm_data.edit_bones.new(name)
                bone.head = points[start]
                bone.tail = points[end]
                bones[name] = bone
            for name, _start, _end, parent_name, connected in bone_specs:
                bone = bones[name]
                if parent_name:
                    bone.parent = bones[parent_name]
                    bone.use_connect = connected
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj
            self.report({'INFO'}, 'Starter rig created. Inspect bone placement before binding weights.')
            return {'FINISHED'}
        except Exception as exc:
            # If construction failed halfway through, delete the incomplete rig
            # and return selection/active-object state to where the user started.
            try:
                active_now = context.view_layer.objects.active
                if active_now is not None and active_now.mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
            except (ReferenceError, RuntimeError):
                pass
            if arm_obj is not None:
                try:
                    data_block = arm_obj.data
                    bpy.data.objects.remove(arm_obj, do_unlink=True)
                    if data_block is not None and data_block.users == 0:
                        bpy.data.armatures.remove(data_block)
                except (ReferenceError, RuntimeError, TypeError):
                    pass
            elif arm_data is not None:
                try:
                    if arm_data.users == 0:
                        bpy.data.armatures.remove(arm_data)
                except (ReferenceError, RuntimeError, TypeError):
                    pass
            _restore_selection(context, selected_before, active_before)
            self.report({'ERROR'}, 'Starter rig creation failed: ' + str(exc))
            return {'CANCELLED'}



class BXR_OT_bind_auto_weights(bpy.types.Operator):
    bl_idname = 'blender_xr.bind_auto_weights'
    bl_label = 'Bind with Automatic Weights'
    bl_description = 'Parent the selected mesh to the selected armature using Blender automatic weights'
    bl_options = {'REGISTER', 'UNDO'}

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
            result = bpy.ops.object.parent_set(type='ARMATURE_AUTO')
            if 'FINISHED' not in result:
                raise RuntimeError('Blender cancelled automatic weight binding')
            unbound = [obj.name for obj in meshes if obj.parent != armature]
            if unbound:
                raise RuntimeError('Blender did not bind: ' + ', '.join(unbound))
            self.report({'INFO'}, 'Automatic weights assigned. Test deformation and correct weights before export.')
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
        old_show_weight = obj.show_weight
        try:
            if not obj.vertex_groups:
                raise ValueError('Mesh has no vertex groups yet. Bind it to an armature first.')
            result = bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
            if 'FINISHED' not in result:
                raise RuntimeError('Blender could not enter Weight Paint mode')
            obj.data.use_paint_mask_vertex = False
            obj.data.use_paint_mask = False
            obj.show_weight = True
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
                obj.show_weight = old_show_weight
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

    def draw(self, context):
        layout = self.layout
        obj = context.view_layer.objects.active
        layout.label(text='Asset readiness', icon='CHECKMARK')
        layout.prop(context.scene.blender_xr, 'triangle_budget')
        row = layout.row(align=True)
        row.operator('blender_xr.asset_audit', icon='VIEWZOOM')
        row.operator('wm.search_menu', text='Search Tools', icon='VIEWZOOM')
        layout.separator()
        layout.label(text='Rigging / weight painting', icon='ARMATURE_DATA')
        layout.operator('blender_xr.create_basic_rig', icon='ARMATURE_DATA')
        layout.label(text='To bind: select mesh + armature, make armature active')
        layout.operator('blender_xr.bind_auto_weights', icon='CONSTRAINT_BONE')
        layout.operator('blender_xr.weight_cleanup', icon='GROUP_VERTEX')
        if obj and obj.type == 'MESH' and obj.mode == 'OBJECT' and obj.vertex_groups:
            layout.operator('blender_xr.weight_paint', icon='WPAINT_HLT')
        if obj and obj.type == 'ARMATURE' and obj.mode == 'OBJECT':
            layout.operator('blender_xr.pose_test', icon='POSE_HLT')
        layout.separator()
        layout.label(text='Controller modelling', icon='HAND')
        layout.label(text='Use Grip to grab/move objects; point and drag gizmos for axis precision.')
        layout.label(text='Edit Mode supports face selection and controller-driven move/scale/extrude.')
        layout.label(text='Use the PC View Mode toggle above to teach or observe the live XR view.')


CLASSES = (
    BXR_OT_asset_audit, BXR_OT_create_basic_rig, BXR_OT_bind_auto_weights,
    BXR_OT_weight_cleanup, BXR_OT_pose_test, BXR_OT_weight_paint, BXR_PT_workflow,
)
