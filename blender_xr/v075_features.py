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
    data = mesh_health(obj)
    operator.report({'INFO'}, 'Mesh XR audit: {vertices} verts, {faces} faces, {triangles} tris'.format(**data))
    issues = []
    if data['non_manifold_edges']:
        issues.append('{} non-manifold edges'.format(data['non_manifold_edges']))
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
    if triangle_budget and data['triangles'] > triangle_budget:
        issues.append('triangle budget exceeded: {} > {}'.format(data['triangles'], triangle_budget))
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
        except (ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
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
        try:
            if armature.mode != 'OBJECT':
                raise ValueError('Armature must be in Object Mode')
            for obj in meshes:
                if obj.library or obj.data.library:
                    raise ValueError('Linked meshes cannot be bound')
                if obj.parent and obj.parent != armature:
                    raise ValueError(obj.name + ' already has another parent; resolve it first')
            bpy.ops.object.parent_set(type='ARMATURE_AUTO')
            self.report({'INFO'}, 'Automatic weights assigned. Test deformation and correct weights before export.')
            return {'FINISHED'}
        except (ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, 'Automatic weights failed: ' + str(exc))
            return {'CANCELLED'}


class BXR_OT_weight_cleanup(bpy.types.Operator):
    bl_idname = 'blender_xr.weight_cleanup'
    bl_label = 'Normalize and Clean Weights'
    bl_description = 'Normalize and clean vertex-group weights on selected meshes without changing rig structure'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not meshes:
            self.report({'ERROR'}, 'Select one or more meshes with vertex groups')
            return {'CANCELLED'}
        completed = 0
        try:
            for obj in meshes:
                if not obj.vertex_groups:
                    continue
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                context.view_layer.objects.active = obj
                bpy.ops.object.vertex_group_clean(group_select_mode='ALL', limit=0.001, keep_single=True)
                bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
                completed += 1
            if not completed:
                raise ValueError('Selected meshes do not have vertex groups')
            self.report({'INFO'}, 'Normalized and cleaned weights on {} mesh(es)'.format(completed))
            return {'FINISHED'}
        except (RuntimeError, ValueError) as exc:
            self.report({'ERROR'}, 'Weight cleanup failed: ' + str(exc))
            return {'CANCELLED'}


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
        try:
            if not obj.vertex_groups:
                raise ValueError('Mesh has no vertex groups yet. Bind it to an armature first.')
            obj.data.use_paint_mask_vertex = False
            obj.data.use_paint_mask = False
            obj.show_weight = True
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
            return {'FINISHED'}
        except (RuntimeError, ValueError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class BXR_PT_workflow(bpy.types.Panel):
    bl_label = 'Mesh XR Workflow'
    bl_idname = 'BXR_PT_workflow'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mesh XR'
    bl_parent_id = 'BXR_PT_panel'
    bl_options = {'DEFAULT_CLOSED'}

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
