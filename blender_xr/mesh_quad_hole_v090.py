# SPDX-License-Identifier: GPL-3.0-or-later
"""Preview and confirm one native quad across a four-edge open boundary.

Requires exactly four selected boundary/wire edges forming a simple convex
cycle. No automatic retopology, modifier, vertex insertion or interpolation
of existing UVs. Newly created quad UVs must be unwrapped by the artist.
"""
import math

import bpy
from mathutils import Vector

from . import (input_ownership_v080, menus, mesh, mesh_selection_tools_v086,
               mesh_topology_audit_v090, mesh_weld_preview_v090, runtime,
               selection, v065)

_PAGE = 'XR_QUAD_HOLE_090'
_CONFIRM_PAGE = 'XR_QUAD_HOLE_CONFIRM_090'
_ENTRY = 'XR_QUAD_HOLE_MENU'
_PREVIEW = 'XR_QUAD_HOLE_PREVIEW'
_COMMIT = 'XR_QUAD_HOLE_COMMIT'
_CANCEL = 'XR_QUAD_HOLE_CANCEL'
_MAX_FACES = 150000


def _eligible(context):
    obj = mesh_selection_tools_v086._editable(context)
    if selection.mode(context) != 'EDGE':
        raise ValueError('Select Edge Mode and exactly four boundary edges')
    if obj.data.users != 1 or obj.data.shape_keys is not None:
        raise ValueError('Quad fill requires a local single-user mesh without shape keys')
    bm, edges = mesh_selection_tools_v086._current(obj, 'EDGE')
    if len(bm.faces) > _MAX_FACES:
        raise ValueError('Quad fill supports up to 150,000 existing faces')
    picked = tuple(edge for edge in edges if edge.is_valid and edge.select
                   and not edge.hide)
    if len(picked) != 4:
        raise ValueError('Select exactly four visible open boundary edges')
    if any(len(edge.link_faces) > 1 or not edge.is_valid
           for edge in picked):
        raise ValueError('Quad fill cannot overlap a manifold or non-manifold edge')
    if any(edge.seam for edge in picked):
        # Marked seams are retained, but crossing a seam with new face can
        # create an artist-unexpected UV patch. Require explicit unseaming.
        raise ValueError('A selected boundary edge is a UV seam; clear it first')
    return obj, bm, edges, picked


def _cycle(edges):
    links = {}
    for edge in edges:
        a, b = edge.verts
        if a is b or not a.is_valid or not b.is_valid:
            raise ValueError('Quad boundary contains degenerate mesh edges')
        links.setdefault(a, []).append(b)
        links.setdefault(b, []).append(a)
    if len(links) != 4 or any(len(group) != 2 for group in links.values()):
        raise ValueError('Selected edges must form a closed four-vertex boundary')
    start = min(links, key=lambda v: v.index)
    first = min(links[start], key=lambda v: v.index)
    verts = [start, first]
    while len(verts) < 4:
        nexts = [v for v in links[verts[-1]] if v is not verts[-2]]
        if len(nexts) != 1 or nexts[0] in verts:
            raise ValueError('Selected edge ring is not a simple four-sided cycle')
        verts.append(nexts[0])
    if start not in links[verts[-1]]:
        raise ValueError('Four-edge boundary does not close')
    return tuple(verts)


def _choose_orientation(cycle, edges):
    """New quad winding must oppose all existing adjacent edge directions."""
    def supports(verts):
        next_by_vert = {verts[i]: verts[(i+1)%4] for i in range(4)}
        for edge in edges:
            if not edge.link_faces:
                continue
            existing = edge.link_faces[0]
            old_loop = next((loop for loop in existing.loops
                             if loop.edge is edge), None)
            if old_loop is None:
                return False
            # Across a manifold edge, the new face must use the opposite
            # directed half-edge to the existing face.
            if next_by_vert.get(old_loop.link_loop_next.vert) is not old_loop.vert:
                return False
        return True
    backwards = (cycle[0], cycle[3], cycle[2], cycle[1])
    if supports(cycle):
        return cycle
    if supports(backwards):
        return backwards
    raise ValueError('Adjacent faces have incompatible winding around this boundary')


def _geometry(cycle):
    pts = [vertex.co.copy() for vertex in cycle]
    if any(not all(math.isfinite(float(v)) for v in point) for point in pts):
        raise ValueError('Boundary vertices have invalid coordinates')
    lengths = [(pts[(i+1)%4]-pts[i]).length for i in range(4)]
    scale = sum(lengths) / 4
    if scale <= 1e-8 or any(length <= 1e-8 for length in lengths):
        raise ValueError('Boundary has degenerate edges')
    normal = (pts[1]-pts[0]).cross(pts[2]-pts[0])
    if normal.length_squared < 1e-16:
        raise ValueError('Quad boundary is collinear or degenerate')
    normal.normalize()
    if max(abs((point-pts[0]).dot(normal)) for point in pts) > max(1e-6, scale*.02):
        raise ValueError('Boundary is too nonplanar for one safe quad')
    signs = []
    for i in range(4):
        v0 = pts[i]-pts[i-1]
        v1 = pts[(i+1)%4]-pts[i]
        cross = v0.cross(v1).dot(normal)
        if abs(cross) <= max(1e-12, scale*scale*1e-8):
            raise ValueError('Boundary contains a collinear or flattened corner')
        signs.append(cross > 0)
    if len(set(signs)) != 1:
        raise ValueError('Selected boundary would form a concave or crossed quad')


def plan(context):
    obj, bm, edges, picked = _eligible(context)
    ring = _choose_orientation(_cycle(picked), picked)
    _geometry(ring)
    # Do not cap a boundary already covered by native triangles/ngons. A
    # second coincident surface is especially dangerous in VR: it looks
    # correct from one side but causes z-fighting and non-manifold topology.
    # This catches triangulated four-corner holes as well as existing quads.
    ring_set = set(ring)
    if any(set(face.verts).issubset(ring_set) for face in bm.faces):
        raise ValueError('Existing faces already occupy this four-corner region')
    # An internal diagonal, even without faces, would be buried beneath the
    # new quad. Refuse it instead of silently making a hidden wire edge.
    for edge in bm.edges:
        if edge not in picked and set(edge.verts).issubset(ring_set):
            raise ValueError('An existing diagonal crosses the proposed quad')
    neighbors = set(face for edge in picked for face in edge.link_faces)
    material_state = {(face.material_index, bool(face.smooth))
                      for face in neighbors}
    if len(material_state) > 1:
        raise ValueError('Boundary faces have different materials or shading')
    mat, smooth = next(iter(material_state)) if material_state else (0, False)
    # Explicitly fingerprint each selected edge and the adjacent face's
    # properties. This is also read-only; Preview does not touch the BMesh.
    edge_info = tuple((
        edge.index, tuple(v.index for v in edge.verts),
        bool(edge.seam), bool(edge.smooth),
        tuple((face.index, face.material_index, bool(face.smooth))
              for face in edge.link_faces)
    ) for edge in picked)
    stamp = (
        mesh_selection_tools_v086._topology(bm),
        mesh_weld_preview_v090._geometry_stamp(bm),
        tuple(v.index for v in ring),
        edge_info,
        mat, smooth,
    )
    return {
        'scene': context.scene.name, 'scene_ptr': context.scene.as_pointer(),
        'layer': context.view_layer.name,
        'obj': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'signature': stamp,
        'face_count': len(bm.faces),
        'edge_count': len(bm.edges),
        'vertex_count': len(bm.verts),
        'material': mat,
        'smooth': smooth,
        'uv_maps': len(obj.data.uv_layers),
    }


def _verify(context, previous):
    current = plan(context)
    if any(current[key] != previous[key] for key in (
            'scene', 'scene_ptr', 'layer', 'obj', 'obj_ptr',
            'mesh', 'mesh_ptr', 'signature', 'face_count',
            'edge_count', 'vertex_count', 'material', 'smooth', 'uv_maps')):
        raise ValueError('Quad boundary changed; open a new preview before filling')
    obj, bm, _edges, picked = _eligible(context)
    ring = _choose_orientation(_cycle(picked), picked)
    return obj, bm, ring


def _mutate(context, proposal):
    obj, bm, ring = _verify(context, proposal)
    created = bm.faces.new(ring)
    # Reject an unexpected Blender BMesh result before committing the
    # transaction. snapshot_and_push owns restoration on any failure.
    if not created.is_valid or set(created.verts) != set(ring):
        raise ValueError('Blender returned an unexpected native quad')
    created.material_index = proposal['material']
    created.smooth = proposal['smooth']
    created.select_set(True)
    if (not created.is_valid or len(created.verts) != 4 or
            len(bm.faces) != proposal['face_count'] + 1 or
            len(bm.edges) != proposal['edge_count'] or
            len(bm.verts) != proposal['vertex_count']):
        raise ValueError('Native Blender did not produce exactly one quad')
    return obj


def commit(context, proposal, history=None):
    obj, _bm, _ring = _verify(context, proposal)
    if history is not None:
        mesh.snapshot_and_push(obj, lambda: _mutate(context, proposal), history)
    else:
        snapshot = mesh.snapshot(obj)
        try:
            _mutate(context, proposal)
            mesh.update(obj)
        except Exception:
            mesh.restore(obj, snapshot)
            raise
        finally:
            if snapshot.name in bpy.data.meshes:
                bpy.data.meshes.remove(snapshot)
    return proposal['face_count']+1


class BXR_OT_quad_hole(bpy.types.Operator):
    bl_idname = 'blender_xr.quad_hole'
    bl_label = 'Preview and Fill Four-Edge Quad Boundary'
    bl_description = 'Confirm one native face on a simple four-edge open boundary'
    bl_options = {'REGISTER', 'UNDO'}
    _proposal = None

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH')

    def invoke(self, context, event):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use XR Quad Hole wrist confirmation during VR')
            return {'CANCELLED'}
        try:
            self._proposal = plan(context)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=375)

    def draw(self, context):
        p = self._proposal
        if p:
            self.layout.label(text='New quad: face count {} to {}'.format(
                p['face_count'], p['face_count']+1))
            if p['uv_maps']:
                self.layout.label(text='New face needs UV unwrapping', icon='ERROR')
        self.layout.label(text='Existing vertices, faces and UVs stay intact')

    def execute(self, context):
        if runtime.CURRENT is not None or self._proposal is None:
            self.report({'WARNING'}, 'Preview the four-edge boundary before confirming')
            return {'CANCELLED'}
        try:
            count = commit(context, self._proposal)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'One native quad created / {} total faces'.format(count))
        return {'FINISHED'}


def install_pages():
    parent = mesh_topology_audit_v090._PAGE
    current = tuple(menus.PAGES[parent])
    if not current or current[-1][1] != 'BACK':
        raise ValueError('Quad Topology menu is unavailable')
    if not any(action == _ENTRY for _label, action in current):
        current = current[:-1] + (('FILL 4 EDGES', _ENTRY), current[-1])
    if len(current) > 12:
        raise ValueError('Quad Topology menu lacks capacity for hole fill')
    menus.PAGES[parent] = current
    menus.PAGES[_PAGE] = (('PREVIEW HOLE', _PREVIEW), ('BACK', 'BACK'))
    menus.PAGES[_CONFIRM_PAGE] = (
        ('MAKE ONE QUAD', _COMMIT), ('KEEP HOLE', _CANCEL), ('BACK', 'BACK'))
    menus.TITLES[_PAGE] = 'QUAD HOLE FILL'
    menus.TITLES[_CONFIRM_PAGE] = 'CONFIRM QUAD FILL'
    v065.TOOLTIPS.update({
        _ENTRY: ('Fill Four-Edge Hole', 'Inspect an existing four-edge boundary before one quad is made'),
        _PREVIEW: ('Preview Quad Hole', 'Validate boundary winding, convexity and materials without changing the mesh'),
        _COMMIT: ('Confirm One Quad', 'Make one native Blender face with XR snapshot Undo'),
        _CANCEL: ('Keep Original Hole', 'Leave mesh geometry untouched'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_native_quad_hole_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        page = getattr(menu, 'page', None)
        if page == mesh_topology_audit_v090._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gestures before filling a native quad')
            _eligible(context)
            self._xr_quad_hole_pending = None
            menu.page = _PAGE
            self.status = 'QUAD FILL / SELECT FOUR BOUNDARY EDGES / PREVIEW'
            return
        if page == _PAGE:
            if action == 'BACK':
                self._xr_quad_hole_pending = None
                menu.page = mesh_topology_audit_v090._PAGE
                return
            if action != _PREVIEW:
                raise ValueError('Preview a four-edge boundary before quad fill')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR controllers before boundary preview')
            proposal = plan(context)
            self._xr_quad_hole_pending = proposal
            menu.page = _CONFIRM_PAGE
            self.status = ('QUAD PREVIEW / FOUR OPEN EDGES / '
                           'NEW FACE UVS NEED UNWRAP / CONFIRM?')
            return
        if page == _CONFIRM_PAGE:
            if action in {_CANCEL, 'BACK'}:
                self._xr_quad_hole_pending = None
                menu.page = _PAGE
                self.status = 'QUAD FILL CANCELLED / NO BLENDER CHANGE'
                return
            if action != _COMMIT:
                raise ValueError('Confirm or cancel the proposed Quad Fill')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before making a quad')
            proposal = getattr(self, '_xr_quad_hole_pending', None)
            if proposal is None:
                raise ValueError('Quad preview expired; start a new preview')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('XR mesh Undo history is required for quad fill')
            count = commit(context, proposal, history)
            self._xr_quad_hole_pending = None
            menu.page = _PAGE
            self._xr_precision_last_ray = None
            self.status = 'NATIVE QUAD FILLED / {} FACES / XR UNDO READY'.format(count)
            return
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_native_quad_hole_090_patched = True


CLASSES = (BXR_OT_quad_hole,)
