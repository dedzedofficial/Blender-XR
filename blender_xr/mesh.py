# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def editable(obj):
    if not obj or obj.type != 'MESH':
        raise ValueError('Select a mesh object first')
    if obj.library or obj.data.library or obj.data.users > 1:
        raise ValueError('Use a local, single-user mesh for v0.3 editing')
    if obj.data.shape_keys:
        raise ValueError('Mesh editing with shape keys is outside v0.3')
    if obj.mode != 'EDIT':
        raise ValueError('Enter face edit mode first')
    if abs(obj.matrix_world.determinant()) < 1e-10:
        raise ValueError('Object scale must be non-zero')
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


def face_hit(obj, origin, direction):
    """Raycast editable cage, not evaluated modifiers or hidden faces."""
    bm = editable(obj)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    faces = [f for f in bm.faces if not f.hide]
    if not faces:
        return None
    tree = BVHTree.FromPolygons([v.co for v in bm.verts],
                               [[v.index for v in f.verts] for f in faces])
    inv = obj.matrix_world.inverted()
    hit, _, index, _ = tree.ray_cast(inv @ origin,
                                    (inv.to_3x3() @ direction).normalized())
    return (faces[index].index, obj.matrix_world @ hit) if hit is not None else None


def select_face(obj, index, additive=False):
    bm = editable(obj)
    bm.faces.ensure_lookup_table()
    face = bm.faces[index]
    if not additive:
        for f in bm.faces:
            f.select_set(False)
        for e in bm.edges:
            e.select_set(False)
        for v in bm.verts:
            v.select_set(False)
    face.select_set(not face.select if additive else True)
    bm.select_flush_mode()
    update(obj)


def apply_tool(obj, tool, amount, segments=2):
    bm = editable(obj)
    faces = [f for f in bm.faces if f.select and not f.hide]
    if not faces:
        raise ValueError('Select at least one face')
    if abs(amount) < 1e-7:
        return
    if tool == 'EXTRUDE':
        normal = sum((f.normal * f.calc_area() for f in faces), Vector())
        if normal.length < 1e-8:
            raise ValueError('Selected faces need a common extrusion direction')
        normal.normalize()
        result = bmesh.ops.extrude_face_region(bm, geom=faces,
                                             use_keep_orig=False)
        # BMesh's region operation retains the source cap when only faces
        # are supplied. Remove that cap, preserving shared boundary edges.
        old_edges = list({e for f in faces if f.is_valid for e in f.edges})
        old_verts = list({v for f in faces if f.is_valid for v in f.verts})
        bmesh.ops.delete(bm, geom=[f for f in faces if f.is_valid], context='FACES_ONLY')
        loose_edges = [e for e in old_edges if e.is_valid and not e.link_faces]
        if loose_edges:
            bmesh.ops.delete(bm, geom=loose_edges, context='EDGES')
        loose_verts = [v for v in old_verts if v.is_valid and not v.link_edges]
        if loose_verts:
            bmesh.ops.delete(bm, geom=loose_verts, context='VERTS')
        verts = [v for v in result['geom'] if isinstance(v, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=verts, vec=normal * amount)
        new_faces = [f for f in result['geom'] if isinstance(f, bmesh.types.BMFace)]
        for f in bm.faces:
            f.select_set(False)
        for f in new_faces:
            f.select_set(True)
    elif tool == 'INSET':
        bmesh.ops.inset_region(bm, faces=faces, thickness=max(0.0, amount),
                              depth=0.0, use_even_offset=True,
                              use_boundary=True, use_relative_offset=False)
    elif tool == 'BEVEL':
        edges = list({e for f in faces for e in f.edges if not e.hide})
        result = bmesh.ops.bevel(bm, geom=edges, offset=max(0.0, amount),
                       segments=segments, affect='EDGES',
                       clamp_overlap=True, profile=0.5)
        for face in result['faces']:
            face.select_set(True)
    else:
        raise ValueError('Unknown mesh tool: ' + tool)
    bm.normal_update()
    bm.select_flush_mode()
    update(obj)


class Transaction:
    """Each preview comes from the same baseline: no accumulated topology."""
    def __init__(self, obj, tool):
        bm = editable(obj)
        if not any(f.select and not f.hide for f in bm.faces):
            raise ValueError('Select a face first')
        self.obj = obj
        self.tool = tool
        self.before = snapshot(obj)
        self.amount = 0.0
        self.changed = False

    def preview(self, amount, segments=2):
        restore(self.obj, self.before)
        apply_tool(self.obj, self.tool, amount, segments)
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


class History:
    """VR-local undo/redo; does not invoke Blender undo from inside a modal loop."""
    def __init__(self):
        self.undo = []
        self.redo = []

    @staticmethod
    def release(entry):
        if entry[0] == 'MESH':
            for mesh in entry[3:5]:
                if mesh and mesh.name in bpy.data.meshes:
                    bpy.data.meshes.remove(mesh)

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
