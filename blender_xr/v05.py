# SPDX-License-Identifier: GPL-3.0-or-later
"""v0.5 mesh-mode extensions layered onto the stable XR runtime."""
import bpy
from mathutils import Vector
from . import mesh


def _selected_indices(obj, mode):
    bm = mesh.editable(obj)
    if mode == 'VERT':
        bm.verts.ensure_lookup_table();bm.verts.index_update()
        return [v.index for v in bm.verts if v.is_valid and v.select and not v.hide]
    if mode == 'EDGE':
        bm.edges.ensure_lookup_table();bm.edges.index_update()
        return [e.index for e in bm.edges if e.is_valid and e.select and not e.hide]
    bm.faces.ensure_lookup_table();bm.faces.index_update()
    return [f.index for f in bm.faces if f.is_valid and f.select and not f.hide]


def _restore_selection(obj, mode, indices):
    bm = mesh.editable(obj)
    mesh._clear_selection(bm)
    collection = {'VERT':bm.verts,'EDGE':bm.edges,'FACE':bm.faces}[mode]
    collection.ensure_lookup_table()
    for index in indices:
        if 0 <= index < len(collection) and collection[index].is_valid:
            collection[index].select_set(True)
    bm.select_mode = {'VERT': {'VERT'}, 'EDGE': {'EDGE'}, 'FACE': {'FACE'}}[mode]
    bm.select_flush_mode()
    mesh.update(obj)


def patch(Runtime):
    if getattr(Runtime, '_v05_patched', False):
        return
    original_init = Runtime.__init__
    original_command = Runtime.command
    OriginalTransaction = mesh.Transaction

    class V05Transaction(OriginalTransaction):
        """Keep vertex/edge selections stable across snapshot-based live previews."""
        def __init__(self, obj, tool, mode=None):
            self.mode = mode or mesh.selection_mode()
            self.selection = _selected_indices(obj, self.mode)
            super().__init__(obj, tool, self.mode)

        def preview(self, amount, segments=2, axis=None):
            mesh.restore(self.obj, self.before)
            _restore_selection(self.obj, self.mode, self.selection)
            mesh.apply_tool(self.obj, self.tool, amount, segments, axis, self.mode)
            self.amount = amount
            self.changed = abs(amount) > 1e-7

        def cancel(self):
            mesh.restore(self.obj, self.before)
            _restore_selection(self.obj, self.mode, self.selection)
            self.dispose()

    mesh.Transaction = V05Transaction

    def init(self, context):
        original_init(self, context)
        self.select_mode = mesh.selection_mode(context) if context.mode == 'EDIT_MESH' else 'FACE'

    def command(self, context, action):
        if not hasattr(self, 'select_mode'):
            self.select_mode = mesh.selection_mode(context) if context.mode == 'EDIT_MESH' else 'FACE'
        if action == 'EDIT_MORE':
            self.menu.page = 'EDIT_MORE'
            self.status = 'MORE EDIT TOOLS'
            return
        if action == 'BACK' and self.menu.page == 'EDIT_MORE':
            self.menu.page = 'EDIT'
            return
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
        mode = getattr(self, 'select_mode', 'FACE')
        self.select_mode = mode
        obj = context.view_layer.objects.active
        editing = bool(obj and obj.mode == 'EDIT')
        hit = self.object_hit(context, origin, direction)
        picked = mesh.element_hit(obj, origin, direction, mode) if editing else None
        edit_tools = {'SELECT','MOVE_FACE','SCALE_FACE'}
        if editing and self.tool in edit_tools and picked:
            if not hit or hit[0] == obj or (picked[1]-origin).length <= (hit[1]-origin).length:
                mesh.select_element(obj, mode, picked[0], additive)
                self.pointer = picked[1]
                self.status = mode + ' SELECTED / ' + self.tool.replace('_',' ')
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
            mesh.set_selection_mode(context, mode)
            picked = mesh.element_hit(target, origin, direction, mode)
            if picked:
                mesh.select_element(target, mode, picked[0])
        self.status = 'SELECTED ' + target.name.upper()

    def begin_tool(self, context, origin, rotation):
        mode = getattr(self, 'select_mode', mesh.selection_mode(context))
        self.select_mode = mode
        obj = context.view_layer.objects.active
        if not mesh.selected_geometry(obj, mode):
            raise ValueError('Select mesh geometry first')
        if self.tool == 'INSET' and mode != 'FACE':
            raise ValueError('Inset is only available in face selection mode')
        if self.tool == 'EXTRUDE':
            self.local_axis = mesh.selected_normal(obj, mode)
        else:
            self.local_axis = (obj.matrix_world.inverted().to_3x3() @
                               (rotation @ Vector((1,0,0)))).normalized()
        self.start_pos = origin.copy()
        self.start_step = self.settings.step
        self.transaction = mesh.Transaction(obj, self.tool, mode)
        self.last_amount = None

    Runtime.__init__ = init
    Runtime.command = command
    Runtime.select = select
    Runtime.begin_tool = begin_tool
    Runtime._v05_patched = True
