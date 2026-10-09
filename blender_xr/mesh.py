# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

SELECT_MODES = ('VERT', 'EDGE', 'FACE')


def check_editable(obj):
    if not obj or obj.type != 'MESH':
        raise ValueError('Select a mesh object first')
    if obj.library or obj.data.library or obj.data.users > 1:
        raise ValueError('Use a local, single-user mesh for v0.5 editing')
    if obj.data.shape_keys:
        raise ValueError('Mesh editing with shape keys is outside v0.5')
    if abs(obj.matrix_world.determinant()) < 1e-10:
        raise ValueError('Object scale must be non-zero')


def editable(obj):
    check_editable(obj)
    if obj.mode != 'EDIT':
        raise ValueError('Enter edit mode first')
    return bmesh.from_edit_mesh(obj.data)


def update(obj):
    bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)


def restore(obj, snapshot):
    bm = editable(obj)
    bm.clear()
    bm.from_mesh(snapshot)
    bm.normal_update()
    update(obj)
    return bm


def snapshot(obj):
    bm = editable(obj)
    result = bpy.data.meshes.new('.BlenderXR_Snapshot')
    bm.to_mesh(result)
    return result


def selection_mode(context=None):
    context = context or bpy.context
    mode = tuple(bool(v) for v in context.tool_settings.mesh_select_mode)
    if mode[0]:
        return 'VERT'
    if mode[1]:
        return 'EDGE'
    return 'FACE'


def set_selection_mode(context, mode):
    if mode not in SELECT_MODES:
        raise ValueError('Unknown mesh selection mode')
    context.tool_settings.mesh_select_mode = {
        'VERT': (True, False, False),
        'EDGE': (False, True, False),
        'FACE': (False, False, True),
    }[mode]
    obj = context.view_layer.objects.active
    if obj and obj.type == 'MESH' and obj.mode == 'EDIT':
        bm = editable(obj)
        bm.select_mode = {'VERT': {'VERT'}, 'EDGE': {'EDGE'}, 'FACE': {'FACE'}}[mode]
        bm.select_flush_mode()
        update(obj)


def face_hit(obj, origin, direction):
    """Raycast the editable base cage, ignoring hidden faces."""
    bm = editable(obj)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    faces = [f for f in bm.faces if f.is_valid and not f.hide]
    if not faces:
        return None
    tree = BVHTree.FromPolygons([v.co for v in bm.verts if v.is_valid],
                                [[v.index for v in f.verts] for f in faces])
    inv = obj.matrix_world.inverted()
    hit, _, index, _ = tree.ray_cast(inv @ origin,
                                     (inv.to_3x3() @ direction).normalized())
    return (faces[index].index, obj.matrix_world @ hit) if hit is not None else None


def element_hit(obj, origin, direction, mode='FACE'):
    """Pick a visible face, or the nearest vertex/edge on the ray-hit face."""
    face_pick = face_hit(obj, origin, direction)
    if not face_pick:
        return None
    face_index, world_hit = face_pick
    if mode == 'FACE':
        return face_index, world_hit
    bm = editable(obj)
    bm.faces.ensure_lookup_table()
    face = bm.faces[face_index]
    if not face.is_valid:
        return None
    if mode == 'VERT':
        vert = min((v for v in face.verts if v.is_valid and not v.hide),
                   key=lambda v: (obj.matrix_world @ v.co - world_hit).length,
                   default=None)
        return (vert.index, obj.matrix_world @ vert.co) if vert else None
    if mode == 'EDGE':
        best = None
        for edge in face.edges:
            if not edge.is_valid or edge.hide:
                continue
            a = obj.matrix_world @ edge.verts[0].co
            b = obj.matrix_world @ edge.verts[1].co
            ab = b - a
            length2 = ab.length_squared
            t = 0.0 if length2 < 1e-12 else max(0.0, min(1.0, (world_hit-a).dot(ab)/length2))
            point = a + ab*t
            distance = (point-world_hit).length
            if best is None or distance < best[0]:
                best = (distance, edge.index, point)
        return (best[1], best[2]) if best else None
    raise ValueError('Unknown mesh selection mode')


def _clear_selection(bm):
    for face in bm.faces:
        if face.is_valid:
            face.select_set(False)
    for edge in bm.edges:
        if edge.is_valid:
            edge.select_set(False)
    for vert in bm.verts:
        if vert.is_valid:
            vert.select_set(False)


def select_element(obj, mode, index, additive=False):
    bm = editable(obj)
    if not additive:
        _clear_selection(bm)
    if mode == 'VERT':
        bm.verts.ensure_lookup_table()
        element = bm.verts[index]
    elif mode == 'EDGE':
        bm.edges.ensure_lookup_table()
        element = bm.edges[index]
    elif mode == 'FACE':
        bm.faces.ensure_lookup_table()
        element = bm.faces[index]
    else:
        raise ValueError('Unknown mesh selection mode')
    if not element.is_valid:
        raise ValueError('Selected mesh element is no longer valid')
    element.select_set(not element.select if additive else True)
    bm.select_flush_mode()
    update(obj)


def select_face(obj, index, additive=False):
    select_element(obj, 'FACE', index, additive)


def selected_faces(obj):
    bm = editable(obj)
    return [f for f in bm.faces if f.is_valid and f.select and not f.hide]


def selected_edges(obj):
    bm = editable(obj)
    return [e for e in bm.edges if e.is_valid and e.select and not e.hide]


def selected_vertices(obj):
    bm = editable(obj)
    return [v for v in bm.verts if v.is_valid and v.select and not v.hide]


def selected_geometry(obj, mode=None):
    mode = mode or selection_mode()
    bm = editable(obj)
    if mode == 'VERT':
        return [v for v in bm.verts if v.is_valid and v.select and not v.hide]
    if mode == 'EDGE':
        return [e for e in bm.edges if e.is_valid and e.select and not e.hide]
    return [f for f in bm.faces if f.is_valid and f.select and not f.hide]


def selected_transform_vertices(obj, mode=None):
    mode = mode or selection_mode()
    bm = editable(obj)
    if mode == 'VERT':
        return [v for v in bm.verts if v.is_valid and v.select and not v.hide]
    if mode == 'EDGE':
        return list({v for e in bm.edges if e.is_valid and e.select and not e.hide
                     for v in e.verts if v.is_valid})
    return list({v for f in bm.faces if f.is_valid and f.select and not f.hide
                 for v in f.verts if v.is_valid})


def _selected_vertices_current_bmesh(bm, mode):
    if mode == 'VERT':
        return [v for v in bm.verts if v.is_valid and v.select and not v.hide]
    if mode == 'EDGE':
        return list({v for e in bm.edges if e.is_valid and e.select and not e.hide
                     for v in e.verts if v.is_valid})
    return list({v for f in bm.faces if f.is_valid and f.select and not f.hide
                 for v in f.verts if v.is_valid})


def selected_center(obj, mode=None):
    mode = mode or selection_mode()
    bm = editable(obj)
    verts = _selected_vertices_current_bmesh(bm, mode)
    if not verts:
        raise ValueError('Select mesh geometry first')
    # Copy coordinates while this exact edit BMesh is current. Preview/restore can
    # invalidate BMVert wrappers, so never carry their references into another call.
    coords = [v.co.copy() for v in verts if v.is_valid]
    if not coords:
        raise ValueError('Select mesh geometry first')
    return sum(coords, Vector()) / len(coords)


def selected_normal(obj, mode=None):
    mode = mode or selection_mode()
    bm = editable(obj)
    faces = [f for f in bm.faces if f.is_valid and f.select and not f.hide]
    if faces:
        normals = [(f.normal.copy(), max(f.calc_area(), 1e-9)) for f in faces if f.is_valid]
        normal = sum((n*area for n,area in normals), Vector())
    else:
        verts = _selected_vertices_current_bmesh(bm, mode)
        normal = sum((v.normal.copy() for v in verts if v.is_valid), Vector())
    if normal.length < 1e-8:
        return Vector((0, 0, 1))
    return normal.normalized()


def _translate_selected(bm, obj, amount, axis, mode):
    direction = Vector(axis) if axis is not None else Vector((0, 0, 1))
    if direction.length < 1e-9:
        raise ValueError('Movement axis is invalid')
    direction.normalize()
    verts = _selected_vertices_current_bmesh(bm, mode)
    if not verts:
        raise ValueError('Select mesh geometry first')
    bmesh.ops.translate(bm, verts=verts, vec=direction * amount)


def _scale_selected(obj, amount, mode):
    bm = editable(obj)
    verts = _selected_vertices_current_bmesh(bm, mode)
    if not verts:
        raise ValueError('Select mesh geometry first')
    coords = [v.co.copy() for v in verts if v.is_valid]
    center = sum(coords, Vector()) / len(coords)
    factor = max(0.02, 1.0 + amount)
    for vert in verts:
        if vert.is_valid:
            vert.co = center + (vert.co-center) * factor


def _extrude_selected(bm, obj, amount, axis, mode):
    direction = Vector(axis) if axis is not None else selected_normal(obj, mode)
    if direction.length < 1e-8:
        raise ValueError('Selected geometry needs an extrusion direction')
    direction.normalize()
    if mode == 'FACE':
        faces = [f for f in bm.faces if f.is_valid and f.select and not f.hide]
        if not faces:
            raise ValueError('Select faces before extruding')
        result = bmesh.ops.extrude_face_region(bm, geom=faces, use_keep_orig=False)
        old_edges = list({e for f in faces if f.is_valid for e in f.edges if e.is_valid})
        old_verts = list({v for f in faces if f.is_valid for v in f.verts if v.is_valid})
        bmesh.ops.delete(bm, geom=[f for f in faces if f.is_valid], context='FACES_ONLY')
        loose_edges = [e for e in old_edges if e.is_valid and not e.link_faces]
        if loose_edges:
            bmesh.ops.delete(bm, geom=loose_edges, context='EDGES')
        loose_verts = [v for v in old_verts if v.is_valid and not v.link_edges]
        if loose_verts:
            bmesh.ops.delete(bm, geom=loose_verts, context='VERTS')
        verts = [v for v in result['geom'] if isinstance(v, bmesh.types.BMVert) and v.is_valid]
        new_faces = [f for f in result['geom'] if isinstance(f, bmesh.types.BMFace) and f.is_valid]
        _clear_selection(bm)
        for face in new_faces:
            face.select_set(True)
    elif mode == 'EDGE':
        edges = [e for e in bm.edges if e.is_valid and e.select and not e.hide]
        if not edges:
            raise ValueError('Select edges before extruding')
        result = bmesh.ops.extrude_edge_only(bm, edges=edges, use_normal_flip=False)
        verts = [v for v in result['geom'] if isinstance(v, bmesh.types.BMVert) and v.is_valid]
        new_edges = [e for e in result['geom'] if isinstance(e, bmesh.types.BMEdge) and e.is_valid]
        _clear_selection(bm)
        for edge in new_edges:
            edge.select_set(True)
    else:
        verts0 = [v for v in bm.verts if v.is_valid and v.select and not v.hide]
        if not verts0:
            raise ValueError('Select vertices before extruding')
        result = bmesh.ops.extrude_vert_indiv(bm, verts=verts0)
        verts = [v for v in result.get('verts', []) if v.is_valid]
        _clear_selection(bm)
        for vert in verts:
            vert.select_set(True)
    if verts:
        bmesh.ops.translate(bm, verts=verts, vec=direction*amount)


def apply_tool(obj, tool, amount, segments=2, axis=None, mode=None):
    bm = editable(obj)
    mode = mode or selection_mode()
    if not selected_geometry(obj, mode):
        raise ValueError('Select mesh geometry first')
    if abs(amount) < 1e-7 and tool not in {'INSET', 'BEVEL'}:
        return
    if tool in {'MOVE_FACE', 'MOVE_EDIT'}:
        _translate_selected(bm, obj, amount, axis, mode)
    elif tool in {'SCALE_FACE', 'SCALE_EDIT'}:
        _scale_selected(obj, amount, mode)
    elif tool == 'EXTRUDE':
        _extrude_selected(bm, obj, amount, axis, mode)
    elif tool == 'INSET':
        if mode != 'FACE':
            raise ValueError('Inset is available in face selection mode')
        faces = [f for f in bm.faces if f.is_valid and f.select and not f.hide]
        bmesh.ops.inset_region(bm, faces=faces, thickness=max(0.0, amount), depth=0.0,
                               use_even_offset=True, use_boundary=True,
                               use_relative_offset=False)
    elif tool == 'BEVEL':
        if mode == 'VERT':
            geom = [v for v in bm.verts if v.is_valid and v.select and not v.hide]
            affect = 'VERTICES'
        elif mode == 'EDGE':
            geom = [e for e in bm.edges if e.is_valid and e.select and not e.hide]
            affect = 'EDGES'
        else:
            geom = list({e for f in bm.faces if f.is_valid and f.select and not f.hide
                         for e in f.edges if e.is_valid})
            affect = 'EDGES'
        if not geom:
            raise ValueError('Select geometry before beveling')
        result = bmesh.ops.bevel(bm, geom=geom, offset=max(0.0, amount),
                                 segments=segments, affect=affect,
                                 clamp_overlap=True, profile=0.5)
        for face in result.get('faces', []):
            if face.is_valid:
                face.select_set(True)
    else:
        raise ValueError('Unknown mesh tool: ' + tool)
    bm.normal_update()
    bm.select_flush_mode()
    update(obj)


def _snapshot_operation(obj, callback):
    before = snapshot(obj)
    try:
        callback()
        bm = editable(obj)
        bm.normal_update()
        bm.select_flush_mode()
        update(obj)
        after = snapshot(obj)
        return ('MESH', obj.name, obj.data.name, before, after)
    except Exception:
        restore(obj, before)
        bpy.data.meshes.remove(before)
        raise


def delete_selected(obj, mode=None):
    mode = mode or selection_mode()
    bm = editable(obj)
    if mode == 'VERT':
        geom = [v for v in bm.verts if v.is_valid and v.select and not v.hide]
    elif mode == 'EDGE':
        geom = [e for e in bm.edges if e.is_valid and e.select and not e.hide]
    else:
        geom = [f for f in bm.faces if f.is_valid and f.select and not f.hide]
    if not geom:
        raise ValueError('Select geometry before deleting')
    context = {'VERT': 'VERTS', 'EDGE': 'EDGES', 'FACE': 'FACES'}[mode]
    return _snapshot_operation(obj, lambda: bmesh.ops.delete(bm, geom=geom, context=context))


def merge_selected(obj):
    bm = editable(obj)
    mode = selection_mode()
    verts = _selected_vertices_current_bmesh(bm, mode)
    if len(verts) < 2:
        raise ValueError('Select at least two vertices to merge')
    center = sum((v.co.copy() for v in verts if v.is_valid), Vector()) / len(verts)
    return _snapshot_operation(obj, lambda: bmesh.ops.pointmerge(bm, verts=verts, merge_co=center))


def subdivide_selected(obj, cuts=1):
    bm = editable(obj)
    mode = selection_mode()
    if mode == 'VERT':
        edges = list({e for v in bm.verts if v.is_valid and v.select and not v.hide
                      for e in v.link_edges if e.is_valid and not e.hide})
    elif mode == 'EDGE':
        edges = [e for e in bm.edges if e.is_valid and e.select and not e.hide]
    else:
        edges = list({e for f in bm.faces if f.is_valid and f.select and not f.hide
                      for e in f.edges if e.is_valid and not e.hide})
    if not edges:
        raise ValueError('Select connected geometry to subdivide')
    return _snapshot_operation(obj, lambda: bmesh.ops.subdivide_edges(
        bm, edges=edges, cuts=max(1, int(cuts)), use_grid_fill=True))


def duplicate_selected(obj):
    bm = editable(obj)
    mode = selection_mode()
    if mode == 'VERT':
        geom = [v for v in bm.verts if v.is_valid and v.select and not v.hide]
    elif mode == 'EDGE':
        edges = [e for e in bm.edges if e.is_valid and e.select and not e.hide]
        geom = list({item for edge in edges for item in (*edge.verts, edge) if item.is_valid})
    else:
        faces = [f for f in bm.faces if f.is_valid and f.select and not f.hide]
        geom = list({item for face in faces for item in (*face.verts, *face.edges, face) if item.is_valid})
    if not geom:
        raise ValueError('Select geometry before duplicating')

    def operation():
        result = bmesh.ops.duplicate(bm, geom=geom)
        _clear_selection(bm)
        for item in result.get('geom', []):
            if getattr(item, 'is_valid', False) and hasattr(item, 'select_set'):
                item.select_set(True)
    return _snapshot_operation(obj, operation)


def recalc_normals(obj):
    bm = editable(obj)
    faces = [f for f in bm.faces if f.is_valid and f.select and not f.hide]
    if not faces:
        raise ValueError('Select faces before recalculating normals')
    return _snapshot_operation(obj, lambda: bmesh.ops.recalc_face_normals(bm, faces=faces))


def flip_normals(obj):
    bm = editable(obj)
    faces = [f for f in bm.faces if f.is_valid and f.select and not f.hide]
    if not faces:
        raise ValueError('Select faces before flipping normals')
    return _snapshot_operation(obj, lambda: bmesh.ops.reverse_faces(bm, faces=faces))


class Transaction:
    """Each preview comes from the same baseline: no accumulated topology."""
    def __init__(self, obj, tool, mode=None):
        self.obj = obj
        self.tool = tool
        self.mode = mode or selection_mode()
        if not selected_geometry(obj, self.mode):
            raise ValueError('Select mesh geometry first')
        self.before = snapshot(obj)
        self.amount = 0.0
        self.changed = False

    def preview(self, amount, segments=2, axis=None):
        restore(self.obj, self.before)
        apply_tool(self.obj, self.tool, amount, segments, axis, self.mode)
        self.amount = amount
        self.changed = abs(amount) > 1e-7

    def cancel(self):
        restore(self.obj, self.before)
        self.dispose()

    def finish(self):
        if not self.changed:
            self.dispose()
            return None
        after = snapshot(self.obj)
        result = ('MESH', self.obj.name, self.obj.data.name, self.before, after)
        self.before = None
        return result

    def dispose(self):
        if self.before is not None:
            bpy.data.meshes.remove(self.before)
            self.before = None


def creation_entry(obj):
    data = obj.data.copy()
    return ('CREATE', obj.name, obj.data.name, data,
            tuple(obj.users_collection), obj.matrix_world.copy())


class History:
    """VR-local undo/redo; does not invoke Blender undo from inside a modal loop."""
    def __init__(self):
        self.undo = []
        self.redo = []

    @staticmethod
    def release(entry):
        if entry[0] == 'MESH':
            for mesh_data in entry[3:5]:
                if mesh_data and mesh_data.name in bpy.data.meshes:
                    bpy.data.meshes.remove(mesh_data)
        elif entry[0] == 'CREATE':
            bpy.data.meshes.remove(entry[3])

    def push(self, entry):
        if not entry:
            return
        for old in self.redo:
            self.release(old)
        self.redo.clear()
        self.undo.append(entry)
        while len(self.undo) > 20:
            self.release(self.undo.pop(0))

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source:
            return False
        entry = source[-1]
        obj = bpy.data.objects.get(entry[1])
        if entry[0] == 'CREATE':
            if backwards:
                if obj is None or obj.mode != 'OBJECT' or obj.data.name != entry[2]:
                    raise ValueError('Switch to object mode and select the original created mesh')
                data = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if data.users == 0:
                    bpy.data.meshes.remove(data)
            else:
                if obj is not None or bpy.data.meshes.get(entry[2]) is not None:
                    raise ValueError('A name used by the created object is occupied; restart VR')
                if bpy.context.mode != 'OBJECT':
                    raise ValueError('Switch to object mode before restoring a primitive')
                try:
                    collections = [c for c in entry[4] if not c.library and c.name]
                except ReferenceError:
                    raise ValueError('The original collection was removed; restart VR') from None
                if not collections:
                    raise ValueError('The original collection was removed; restart VR')
                obj = bpy.data.objects.new(entry[1], entry[3].copy())
                obj.data.name = entry[2]
                obj.matrix_world = entry[5]
                for collection in collections:
                    collection.objects.link(obj)
                for selected in bpy.context.selected_objects:
                    selected.select_set(False)
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
            dest.append(source.pop())
            return True
        if obj is None:
            raise ValueError('The edited object was removed; restart VR to clear history')
        if entry[0] == 'MESH':
            if obj.data.name != entry[2]:
                raise ValueError('The mesh changed outside VR; restart VR')
            restore(obj, entry[3] if backwards else entry[4])
        else:
            if obj.mode != 'OBJECT':
                raise ValueError('Switch to object mode before undoing object movement')
            obj.matrix_world = entry[3 if backwards else 4]
        dest.append(source.pop())
        return True

    def clear(self):
        for entry in self.undo + self.redo:
            self.release(entry)
        self.undo.clear()
        self.redo.clear()
