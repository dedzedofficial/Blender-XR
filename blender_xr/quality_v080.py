# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only game-readiness audit, VR measurements and native object protection."""
import math
import bpy
from mathutils import Vector
from bpy.props import EnumProperty


def measurement(context):
    """No scene edits, uses actual Blender scene unit scale."""
    scale = float(context.scene.unit_settings.scale_length) or 1.0
    selected = tuple(context.selected_objects)
    active = context.view_layer.objects.active
    if len(selected) == 2:
        a, b = sorted(selected, key=lambda x: x.name)
        distance = (a.matrix_world.translation - b.matrix_world.translation).length * scale
        return 'Origins: %.4f scene metres (%s / %s)' % (distance, a.name, b.name)
    if len(selected) == 3:
        points = [o.matrix_world.translation for o in sorted(selected, key=lambda x: x.name)]
        a = points[0] - points[1]
        b = points[2] - points[1]
        if a.length < 1e-7 or b.length < 1e-7:
            return 'Selected origins coincide'
        return 'Angle at middle object: %.2f degrees' % math.degrees(a.angle(b))
    if active and active.type == 'ARMATURE' and active.mode == 'POSE':
        bone = active.data.bones.active
        if bone:
            return '%s: %.4f scene metres' % (bone.name, bone.length * scale)
    if active:
        dimensions = tuple(float(v) * scale for v in active.dimensions)
        return '%s dimensions: X %.4f / Y %.4f / Z %.4f scene metres' % (
            active.name, *dimensions)
    return 'Select an object, two origins for distance or three for angle'


def pre_export_findings(obj, budget=70000):
    """Return a list of informational/warning findings, never change any datablocks."""
    findings = []
    if obj is None:
        return [('ERROR', 'Select an object first')]
    if obj.type != 'MESH':
        return [('INFO', 'Select a mesh to inspect export readiness')]
    data = obj.data
    triangles = sum(max(0, len(poly.vertices) - 2) for poly in data.polygons)
    if budget and triangles > budget:
        findings.append(('WARNING', 'Triangles %d exceed budget %d' % (triangles, budget)))
    if any(abs(s - 1.0) > 0.0001 for s in obj.scale):
        findings.append(('WARNING', 'Unapplied object scale'))
    if any(abs(a) > 0.0001 for a in obj.rotation_euler):
        findings.append(('INFO', 'Object has unapplied Euler rotation'))
    if not data.polygons:
        findings.append(('WARNING', 'Mesh has no polygons'))
    empty = sum(1 for slot in obj.material_slots if slot.material is None)
    if empty:
        findings.append(('WARNING', '%d empty material slots' % empty))
    for slot in obj.material_slots:
        mat = slot.material
        if mat and mat.use_nodes and mat.node_tree:
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    img = node.image
                    if (img.source == 'FILE' and not img.packed_file and
                            not bpy.path.exists(img.filepath, library=img.library)):
                        findings.append(('WARNING', 'Missing texture: ' + img.name))
    armatures = [mod for mod in obj.modifiers if mod.type == 'ARMATURE']
    for mod in armatures:
        if mod.object is None or mod.object.type != 'ARMATURE':
            findings.append(('ERROR', 'Armature modifier has no valid rig: ' + mod.name))
    if len(armatures) > 1:
        findings.append(('WARNING', '%d armature modifiers; check duplicates' % len(armatures)))
    if obj.vertex_groups:
        weights = [[] for _ in obj.data.vertices]
        for vert in obj.data.vertices:
            for g in vert.groups:
                if g.weight > 1e-6:
                    weights[vert.index].append(g.weight)
        unweighted = sum(not influences for influences in weights)
        overloaded = sum(len(influences) > 4 for influences in weights)
        if unweighted and armatures:
            findings.append(('WARNING', '%d unweighted vertices' % unweighted))
        if overloaded:
            findings.append(('WARNING', '%d vertices have more than 4 influences' % overloaded))
    if not findings:
        findings.append(('INFO', 'No issues found in basic mesh/rig readiness checks'))
    return findings


class BXR_OT_measure(bpy.types.Operator):
    bl_idname = 'blender_xr.measure'
    bl_label = 'Measure Selection'
    bl_description = 'Read only: distance between two origins, angle between three, or size of active object'

    def execute(self, context):
        message = measurement(context)
        context.scene.blender_xr.status = message
        self.report({'INFO'}, message)
        return {'FINISHED'}


class BXR_OT_export_check(bpy.types.Operator):
    bl_idname = 'blender_xr.export_check'
    bl_label = 'Pre-Export Check'
    bl_description = 'Read-only game readiness audit: triangles, textures, transforms, rigs and influences'

    def execute(self, context):
        target = context.view_layer.objects.active
        issues = pre_export_findings(target, context.scene.blender_xr.triangle_budget)
        count = sum(level in ('WARNING', 'ERROR') for level, _ in issues)
        message = '%d export finding(s): %s' % (count, ' | '.join(t for _, t in issues[:3]))
        context.scene.blender_xr.status = message[:250]
        for level, finding in issues[:16]:
            self.report({'WARNING'} if level in ('WARNING', 'ERROR') else {'INFO'}, finding)
        return {'FINISHED'}


class BXR_OT_object_lock(bpy.types.Operator):
    bl_idname = 'blender_xr.object_lock'
    bl_label = 'Toggle Object Selection Lock'
    bl_description = 'Toggle native Blender hide_select protection; no custom lock metadata'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.view_layer.objects.active
        if obj is None or obj.mode != 'OBJECT':
            self.report({'WARNING'}, 'Select an object in Object Mode first')
            return {'CANCELLED'}
        obj.hide_select = not obj.hide_select
        context.scene.blender_xr.status = ('Locked ' if obj.hide_select else 'Unlocked ') + obj.name
        return {'FINISHED'}


def draw_inspector(layout, context):
    obj = context.view_layer.objects.active
    if not obj:
        layout.label(text='Select an object to inspect', icon='INFO')
        return
    layout.prop(obj, 'name', text='Name', icon='OBJECT_DATA')
    row = layout.row(align=True)
    row.enabled = obj.mode == 'OBJECT'
    row.operator('blender_xr.object_lock',
                 text='Unlock selection' if obj.hide_select else 'Lock selection',
                 icon='RESTRICT_SELECT_ON' if obj.hide_select else 'RESTRICT_SELECT_OFF')
    row = layout.row(align=True)
    row.prop(obj, 'hide_viewport', text='Hide in viewport', icon='HIDE_ON')
    layout.label(text='Type: %s  |  Polygons: %d' %
                 (obj.type, len(obj.data.polygons) if obj.type == 'MESH' else 0))
    layout.label(text='Parent: ' + (obj.parent.name if obj.parent else '(none)'), icon='OUTLINER_DATA_EMPTY')


class BXR_OT_reset_hand_calibration(bpy.types.Operator):
    bl_idname = 'blender_xr.reset_hand_calibration'
    bl_label = 'Reset Hand Calibration'
    bl_description = 'Restore neutral hand offsets and 100% hand size'

    def execute(self, context):
        settings = context.scene.blender_xr
        settings.hand_offset_x = 0.0
        settings.hand_offset_y = 0.0
        settings.hand_offset_z = 0.0
        settings.hand_scale = 1.0
        self.report({'INFO'}, 'Hand visual calibration reset')
        return {'FINISHED'}


CLASSES = (BXR_OT_measure, BXR_OT_export_check, BXR_OT_object_lock,
           BXR_OT_reset_hand_calibration)
