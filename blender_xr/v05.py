# SPDX-License-Identifier: GPL-3.0-or-later
"""v0.5 mesh-mode extensions layered onto the stable XR runtime."""
import bpy
from mathutils import Vector
from . import mesh


def patch(Runtime):
    if getattr(Runtime, '_v05_patched', False):
        return
    original_init = Runtime.__init__
    original_command = Runtime.command

    def init(self, context):
        original_init(self, context)
        self.select_mode = mesh.selection_mode(context) if context.mode == 'EDIT_MESH' else 'FACE'

    def command(self, context, action):
        if action in {'SELECT_VERT','SELECT_EDGE','SELECT_FACE'}:
            obj = context.view_layer.objects.active
            if not obj or obj.type != 'MESH' or obj.mode != 'EDIT':
                raise ValueError('Enter EDIT MODE before changing selection type')
            mode = {'SELECT_VERT':'VERT','SELECT_EDGE':'EDGE','SELECT_FACE':'FACE'}[action]
            mesh.set_selection_mode(context, mode)
            self.select_mode = mode
            self.tool = 'SELECT'
            self.status = mode + ' SELECT MODE'
            return
        if action in {'DELETE_GEOM','MERGE','SUBDIVIDE','DUPLICATE','RECALC','FLIP_NORMALS'}:
            obj = context.view_layer.objects.active
            if not obj or obj.type != 'MESH' or obj.mode != 'EDIT':
                raise ValueError('Enter EDIT MODE before using mesh actions')
            if self.transaction or self.grab or self.axis_move or self.air_grab:
                raise ValueError('Finish or cancel the current operation first')
            if action == 'DELETE_GEOM':
                entry = mesh.delete_selected(obj, self.select_mode)
                message = self.select_mode + ' DELETED'
            elif action == 'MERGE':
                entry = mesh.merge_selected(obj)
                message = 'VERTICES MERGED'
            elif action == 'SUBDIVIDE':
                entry = mesh.subdivide_selected(obj)
                message = 'SELECTION SUBDIVIDED'
            elif action == 'DUPLICATE':
                entry = mesh.duplicate_selected(obj)
                message = 'SELECTION DUPLICATED'
            elif action == 'RECALC':
                entry = mesh.recalc_normals(obj)
                message = 'NORMALS RECALCULATED'
            else:
                entry = mesh.flip_normals(obj)
                message = 'NORMALS FLIPPED'
            self.history.push(entry)
            self.status = message + ' / UNDO TO RESTORE'
            return
        original_command(self, context, action)
        if action == 'MODE':
            obj = context.view_layer.objects.active
            if obj and obj.type == 'MESH' and obj.mode == 'EDIT':
                self.select_mode = 'FACE'
                mesh.set_selection_mode(context, 'FACE')

    def select(self, context, origin, direction, additive=False):
        if self.transaction or self.grab or self.air_grab or self.axis_move:
            raise ValueError('Finish or cancel the current operation before switching meshes')
        obj = context.view_layer.objects.active
        editing = bool(obj and obj.mode == 'EDIT')
        hit = self.object_hit(context, origin, direction)
        picked = mesh.element_hit(obj, origin, direction, self.select_mode) if editing else None
        edit_tools = {'SELECT','MOVE_FACE','SCALE_FACE'}
        if editing and self.tool in edit_tools and picked:
            if not hit or hit[0] == obj or (picked[1]-origin).length <= (hit[1]-origin).length:
                mesh.select_element(obj, self.select_mode, picked[0], additive)
                self.pointer = picked[1]
                self.status = self.select_mode + ' SELECTED / ' + self.tool.replace('_',' ')
                return
        if not hit:
            self.status = 'POINT AT A MESH'
            return
        target, point = hit
        keep_edit = editing and self.tool in edit_tools
        if keep_edit:
            mesh.check_editable(target)
        if editing:
            bpy.ops.object.mode_set(mode='OBJECT')
        for selected in context.selected_objects:
            selected.select_set(False)
        target.select_set(True)
        context.view_layer.objects.active = target
        self.pointer = point
        if keep_edit:
            bpy.ops.object.mode_set(mode='EDIT')
            mesh.set_selection_mode(context, self.select_mode)
            picked = mesh.element_hit(target, origin, direction, self.select_mode)
            if picked:
                mesh.select_element(target, self.select_mode, picked[0])
        self.status = 'SELECTED ' + target.name.upper()

    def begin_tool(self, context, origin, rotation):
        obj = context.view_layer.objects.active
        if not mesh.selected_geometry(obj, self.select_mode):
            raise ValueError('Select mesh geometry first')
        if self.tool == 'INSET' and self.select_mode != 'FACE':
            raise ValueError('Inset is only available in face selection mode')
        if self.tool == 'EXTRUDE':
            self.local_axis = mesh.selected_normal(obj)
        else:
            self.local_axis = (obj.matrix_world.inverted().to_3x3() @
                               (rotation @ Vector((1,0,0)))).normalized()
        self.start_pos = origin.copy()
        self.start_step = self.settings.step
        self.transaction = mesh.Transaction(obj, self.tool, self.select_mode)
        self.last_amount = None

    Runtime.__init__ = init
    Runtime.command = command
    Runtime.select = select
    Runtime.begin_tool = begin_tool
    Runtime._v05_patched = True
