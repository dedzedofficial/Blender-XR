# SPDX-License-Identifier: GPL-3.0-or-later
"""Mesh XR 0.7.1: advanced VR modeling, reversible modifiers and UV history."""
import math

import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

from . import material_uv, menus, mesh, v065

_MANAGED = 'Mesh XR '
_UV_EDITS = {
    'UV_UNWRAP', 'UV_SMART', 'UV_CUBE', 'UV_PLANAR',
    'UV_MARK_SEAM', 'UV_CLEAR_SEAM', 'UV_RESET', 'UV_PACK',
    'UV_U_DOWN', 'UV_U_UP', 'UV_V_DOWN', 'UV_V_UP',
    'UV_ROT_DOWN', 'UV_ROT_UP', 'UV_SCALE_DOWN', 'UV_SCALE_UP',
}


def editable_object(obj):
    if not obj or obj.type != 'MESH' or obj.mode != 'OBJECT':
        raise ValueError('Select a mesh in Object Mode')
    if obj.library or obj.data.library or obj.data.users > 1:
        raise ValueError('Use a local single-user mesh')
    return obj


def _idle(session):
    if any(getattr(session, name, None) for name in
           ('transaction', 'grab', 'air_grab', 'axis_move')):
        raise ValueError('Finish or cancel the active operation first')


def _rotate_object(obj, axis, degrees):
    editable_object(obj)
    if obj.parent or obj.constraints:
        raise ValueError('Rotation requires an unparented, unconstrained object')
    before = obj.matrix_world.copy()
    pivot = before.translation.copy()
    rot = Matrix.Rotation(math.radians(degrees), 4, axis)
    obj.matrix_world = Matrix.Translation(pivot) @ rot @ Matrix.Translation(-pivot) @ before
    return ('OBJECT', obj.name, None, before, obj.matrix_world.copy())


def _rotate_edit(obj, axis, degrees):
    def operation():
        bm = mesh.editable(obj)
        verts = mesh.selected_transform_vertices(obj, mesh.selection_mode())
        if not verts:
            raise ValueError('Select geometry to rotate')
        center = sum((v.co for v in verts), Vector()) / len(verts)
        rotation = Matrix.Rotation(math.radians(degrees), 3, axis)
        for vert in verts:
            vert.co = center + rotation @ (vert.co - center)
    return mesh._snapshot_operation(obj, operation)


def rotate(obj, axis, degrees):
    if obj and obj.mode == 'EDIT':
        return _rotate_edit(obj, axis, degrees)
    return _rotate_object(obj, axis, degrees)


def edit_geometry(obj, action):
    if action == 'GEO_RECALC':
        return mesh.recalc_normals(obj)

    def operation():
        bm = mesh.editable(obj)
        if action == 'GEO_DISSOLVE_VERT':
            verts = [v for v in bm.verts if v.is_valid and v.select and not v.hide]
            if not verts:
                raise ValueError('Select vertices to dissolve')
            bmesh.ops.dissolve_verts(bm, verts=verts, use_face_split=False,
                                     use_boundary_tear=False)
        elif action == 'GEO_DISSOLVE_EDGE':
            edges = [e for e in bm.edges if e.is_valid and e.select and not e.hide]
            if not edges:
                raise ValueError('Select edges to dissolve')
            bmesh.ops.dissolve_edges(bm, edges=edges, use_verts=False,
                                     use_face_split=False)
        elif action == 'GEO_FILL':
            edges = [e for e in bm.edges if e.is_valid and e.select and
                     not e.hide and len(e.link_faces) == 1]
            if not edges:
                raise ValueError('Select boundary edges around a hole')
            bmesh.ops.holes_fill(bm, edges=edges, sides=0)
        elif action == 'GEO_BRIDGE':
            edges = [e for e in bm.edges if e.is_valid and e.select and not e.hide]
            if len(edges) < 4:
                raise ValueError('Select two edge loops to bridge')
            bmesh.ops.bridge_loops(bm, edges=edges)
        else:
            raise ValueError('Unknown geometry operation')
    return mesh._snapshot_operation(obj, operation)


def snap_to_grid(obj, step):
    editable_object(obj)
    if obj.parent or obj.constraints:
        raise ValueError('Grid snapping requires an unparented object')
    step = max(0.0001, float(step))
    before = obj.matrix_world.copy()
    after = before.copy()
    after.translation = Vector(tuple(round(v / step) * step for v in before.translation))
    if all(abs(a-b) < 1e-8 for a, b in zip(before.translation, after.translation)):
        return None
    obj.matrix_world = after
    return ('OBJECT', obj.name, None, before, after)


def reset_object_rotation(obj):
    editable_object(obj)
    if obj.parent or obj.constraints:
        raise ValueError('Reset rotation requires an unparented object')
    before = obj.matrix_world.copy()
    loc, _rotation, scale = before.decompose()
    obj.matrix_world = Matrix.LocRotScale(loc, Quaternion((1, 0, 0, 0)), scale)
    return ('OBJECT', obj.name, None, before, obj.matrix_world.copy())


def _managed_modifiers(obj):
    return [mod for mod in obj.modifiers if mod.name.startswith(_MANAGED)
            and mod.type in {'MIRROR', 'ARRAY', 'SOLIDIFY'}]


def modifier_state(obj):
    state = []
    for mod in _managed_modifiers(obj):
        values = {'visible': bool(mod.show_viewport)}
        if mod.type == 'MIRROR':
            values.update(axes=tuple(mod.use_axis), clip=bool(mod.use_clip),
                          merge=bool(mod.use_mirror_merge))
        elif mod.type == 'ARRAY':
            values.update(count=int(mod.count),
                          relative=tuple(mod.relative_offset_displace),
                          relative_enabled=bool(mod.use_relative_offset))
        elif mod.type == 'SOLIDIFY':
            values.update(thickness=float(mod.thickness), offset=float(mod.offset))
        state.append((mod.name, mod.type, values))
    return tuple(state)


def restore_modifiers(obj, state):
    editable_object(obj)
    for mod in reversed(_managed_modifiers(obj)):
        obj.modifiers.remove(mod)
    for name, kind, values in state:
        mod = obj.modifiers.new(name=name, type=kind)
        mod.show_viewport = values['visible']
        if kind == 'MIRROR':
            mod.use_axis = values['axes']
            mod.use_clip = values['clip']
            mod.use_mirror_merge = values['merge']
        elif kind == 'ARRAY':
            mod.count = values['count']
            mod.use_relative_offset = values['relative_enabled']
            mod.relative_offset_displace = values['relative']
        elif kind == 'SOLIDIFY':
            mod.thickness = values['thickness']
            mod.offset = values['offset']


def modifier_action(obj, action):
    editable_object(obj)
    before = modifier_state(obj)
    managed = _managed_modifiers(obj)
    current = managed[-1] if managed else None
    if action.startswith('MOD_MIRROR_'):
        axis = action.rsplit('_', 1)[-1]
        if axis not in {'X', 'Y', 'Z'}:
            raise ValueError('Invalid mirror axis')
        mod = obj.modifiers.new(name=_MANAGED + 'Mirror ' + axis, type='MIRROR')
        mod.use_axis = (axis == 'X', axis == 'Y', axis == 'Z')
        mod.use_clip = True
    elif action == 'MOD_ARRAY':
        mod = obj.modifiers.new(name=_MANAGED + 'Array', type='ARRAY')
        mod.count = 2
    elif action == 'MOD_SOLIDIFY':
        mod = obj.modifiers.new(name=_MANAGED + 'Solidify', type='SOLIDIFY')
        mod.thickness = 0.02
    elif action == 'MOD_REMOVE':
        if current is None:
            raise ValueError('Add a Mesh XR modifier first')
        obj.modifiers.remove(current)
    elif action == 'MOD_TOGGLE':
        if current is None:
            raise ValueError('Add a Mesh XR modifier first')
        current.show_viewport = not current.show_viewport
    elif action.startswith('MOD_COUNT_'):
        if current is None or current.type != 'ARRAY':
            raise ValueError('Add an Array modifier first')
        current.count = max(1, min(128, current.count +
                                 (1 if action == 'MOD_COUNT_UP' else -1)))
    elif action.startswith('MOD_THICK_'):
        if current is None or current.type != 'SOLIDIFY':
            raise ValueError('Add a Solidify modifier first')
        current.thickness = max(-10, min(10, current.thickness +
                                       (0.01 if action == 'MOD_THICK_UP' else -0.01)))
    else:
        raise ValueError('Unknown modifier command')
    after = modifier_state(obj)
    if before == after:
        return None
    return ('MODIFIERS', obj.name, None, before, after)


def duplicate_object(obj, step):
    editable_object(obj)
    if not obj.users_collection:
        raise ValueError('Object must belong to a collection')
    created = obj.copy()
    created.data = obj.data.copy()
    for coll in obj.users_collection:
        coll.objects.link(created)
    matrix = obj.matrix_world.copy()
    matrix.translation.x += max(0.01, float(step))
    created.matrix_world = matrix
    name, data_name = created.name, created.data.name
    template = created.copy()
    template.data = created.data.copy()
    for selected in bpy.context.selected_objects:
        selected.select_set(False)
    created.select_set(True)
    bpy.context.view_layer.objects.active = created
    return ('CREATE_CLONE', name, data_name, template, tuple(created.users_collection))


def _history_patch():
    if getattr(mesh.History, '_v071_history', False):
        return
    previous_step = mesh.History.step
    previous_release = mesh.History.release

    def release(entry):
        if entry[0] == 'CREATE_CLONE':
            template = entry[3]
            try:
                data = template.data
                if bpy.data.objects.get(template.name) == template:
                    bpy.data.objects.remove(template, do_unlink=True)
                if data and data.users == 0 and bpy.data.meshes.get(data.name) == data:
                    bpy.data.meshes.remove(data)
            except ReferenceError:
                pass
        elif entry[0] != 'MODIFIERS':
            previous_release(entry)

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] not in {'MODIFIERS', 'CREATE_CLONE'}:
            return previous_step(self, backwards)
        entry = source[-1]
        obj = bpy.data.objects.get(entry[1])
        if entry[0] == 'MODIFIERS':
            restore_modifiers(obj, entry[3] if backwards else entry[4])
        elif backwards:
            editable_object(obj)
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if data.users == 0:
                bpy.data.meshes.remove(data)
        else:
            if obj is not None:
                raise ValueError('Duplicate object name is occupied')
            template = entry[3]
            collections = [c for c in entry[4] if c and
                           bpy.data.collections.get(c.name) == c]
            if not collections:
                raise ValueError('Original collection was removed')
            obj = template.copy()
            obj.data = template.data.copy()
            obj.name, obj.data.name = entry[1], entry[2]
            for coll in collections:
                coll.objects.link(obj)
            for selected in bpy.context.selected_objects:
                selected.select_set(False)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
        dest.append(source.pop())
        return True

    mesh.History.release = staticmethod(release)
    mesh.History.step = step
    mesh.History._v071_history = True


def _install_pages():
    menus.PAGES['MODE_SELECT'] += (('', 'OBJECT_ADVANCED'),)
    menus.PAGES['EDIT_MORE'] = tuple(
        ('', 'GEOMETRY_ADVANCED') if action == 'RECALC' else (label, action)
        for label, action in menus.PAGES['EDIT_MORE'])
    menus.PAGES['OBJECT_ADVANCED'] = (
        ('X +15', 'ROT_X_POS'), ('X -15', 'ROT_X_NEG'),
        ('Y +15', 'ROT_Y_POS'), ('Y -15', 'ROT_Y_NEG'),
        ('Z +15', 'ROT_Z_POS'), ('Z -15', 'ROT_Z_NEG'),
        ('SNAP GRID', 'OBJ_SNAP'), ('RESET ROT', 'OBJ_RESET_ROT'),
        ('DUPLICATE', 'OBJ_DUPLICATE'), ('MODIFIERS', 'MODIFIER_MENU'),
        ('OBJECT', 'MODE_OBJECT'), ('BACK', 'BACK'),
    )
    menus.PAGES['GEOMETRY_ADVANCED'] = (
        ('X +15', 'ROT_X_POS'), ('X -15', 'ROT_X_NEG'),
        ('Y +15', 'ROT_Y_POS'), ('Y -15', 'ROT_Y_NEG'),
        ('Z +15', 'ROT_Z_POS'), ('Z -15', 'ROT_Z_NEG'),
        ('DISS VERT', 'GEO_DISSOLVE_VERT'), ('DISS EDGE', 'GEO_DISSOLVE_EDGE'),
        ('FILL HOLE', 'GEO_FILL'), ('BRIDGE', 'GEO_BRIDGE'),
        ('RECALC', 'GEO_RECALC'), ('BACK', 'BACK'),
    )
    menus.PAGES['MODIFIER_MENU'] = (
        ('MIRROR X', 'MOD_MIRROR_X'), ('MIRROR Y', 'MOD_MIRROR_Y'),
        ('MIRROR Z', 'MOD_MIRROR_Z'), ('ARRAY', 'MOD_ARRAY'),
        ('SOLIDIFY', 'MOD_SOLIDIFY'), ('COUNT +', 'MOD_COUNT_UP'),
        ('COUNT -', 'MOD_COUNT_DOWN'), ('THICK +', 'MOD_THICK_UP'),
        ('THICK -', 'MOD_THICK_DOWN'), ('SHOW/HIDE', 'MOD_TOGGLE'),
        ('REMOVE', 'MOD_REMOVE'), ('BACK', 'BACK'),
    )
    menus.TITLES.update(OBJECT_ADVANCED='OBJECT TOOLS',
                        GEOMETRY_ADVANCED='GEOMETRY TOOLS',
                        MODIFIER_MENU='MODIFIERS')
    v065.TOOLTIPS['OBJECT_ADVANCED'] = ('Object Tools', 'Rotation, grid, duplication and modifiers')


def patch(Runtime):
    if getattr(Runtime, '_v071_patched', False):
        return
    _history_patch()
    _install_pages()
    original_command = Runtime.command

    def command(self, context, action):
        if action in {'OBJECT_ADVANCED', 'GEOMETRY_ADVANCED', 'MODIFIER_MENU'}:
            _idle(self)
            obj = context.view_layer.objects.active
            if action == 'OBJECT_ADVANCED':
                editable_object(obj)
            elif action == 'GEOMETRY_ADVANCED':
                mesh.editable(obj)
            else:
                editable_object(obj)
            self.menu.page = action
            self.status = menus.TITLES[action]
            return
        if action == 'BACK' and self.menu.page in {'OBJECT_ADVANCED', 'GEOMETRY_ADVANCED', 'MODIFIER_MENU'}:
            self.menu.page = ('OBJECT_ADVANCED' if self.menu.page == 'MODIFIER_MENU'
                              else 'EDIT_MORE' if self.menu.page == 'GEOMETRY_ADVANCED'
                              else 'TOOLS')
            return
        if action.startswith('ROT_') and action.endswith(('_POS', '_NEG')):
            _idle(self)
            parts = action.split('_')
            entry = rotate(context.view_layer.objects.active, parts[1],
                           15 if parts[2] == 'POS' else -15)
            self.history.push(entry)
            self.status = 'ROTATE ' + parts[1] + ' 15 DEG'
            return
        if action.startswith('GEO_'):
            _idle(self)
            self.history.push(edit_geometry(context.view_layer.objects.active, action))
            self.status = action.replace('_', ' ')
            return
        if action in {'OBJ_SNAP', 'OBJ_RESET_ROT', 'OBJ_DUPLICATE'}:
            _idle(self)
            obj = context.view_layer.objects.active
            if action == 'OBJ_SNAP':
                entry = snap_to_grid(obj, self.settings.step)
            elif action == 'OBJ_RESET_ROT':
                entry = reset_object_rotation(obj)
            else:
                entry = duplicate_object(obj, self.settings.step)
            self.history.push(entry)
            self.status = action.replace('_', ' ')
            return
        if action.startswith('MOD_'):
            _idle(self)
            self.history.push(modifier_action(context.view_layer.objects.active, action))
            self.status = action.replace('_', ' ')
            return
        # UV operations use mesh snapshots so the whole edit (including seams)
        # is undoable without relying on Blender's global undo inside a modal XR loop.
        if action in _UV_EDITS or action == 'SLOT_ASSIGN':
            if getattr(self, 'history', None) is not None:
                _idle(self)
                obj = context.view_layer.objects.active
                before = mesh.snapshot(obj)
                try:
                    result = original_command(self, context, action)
                    after = mesh.snapshot(obj)
                except Exception:
                    bpy.data.meshes.remove(before)
                    raise
                self.history.push(('MESH', obj.name, obj.data.name, before, after))
                return result
        return original_command(self, context, action)

    Runtime.command = command
    Runtime._v071_patched = True
