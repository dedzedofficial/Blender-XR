# SPDX-License-Identifier: GPL-3.0-or-later
"""Conservative two-ring native BMesh quad bridge for Blender XR.

Preview is read-only. Only two disjoint closed boundary edge loops with the
same number of vertices (3..64) may be bridged, and a separate confirmation
must approve the topology change. The existing mesh snapshot owns Undo/Redo.
No vertex replacement, auto-unwrap, custom geometry or background modifier.
"""
import math

import bpy
import bmesh

from . import (input_ownership_v080, menus, mesh, mesh_axis_snap_v090,
               mesh_selection_tools_v086, mesh_topology_audit_v090,
               mesh_weld_preview_v090, runtime, selection, v065)

_PAGE = 'XR_BRIDGE_QUADS_090'
_CONFIRM_PAGE = 'XR_BRIDGE_QUADS_CONFIRM_090'
_ENTRY = 'XR_BRIDGE_QUADS_MENU'
_PREVIEW = 'XR_BRIDGE_QUADS_PREVIEW'
_COMMIT = 'XR_BRIDGE_QUADS_COMMIT'
_CANCEL = 'XR_BRIDGE_QUADS_CANCEL'
_MIN_RING = 3
_MAX_RING = 64
_MAX_VERTS = 150000


def _eligible(context):
    obj = mesh_selection_tools_v086._editable(context)
    if selection.mode(context) != 'EDGE':
        raise ValueError('Switch to Edge Select Mode for native quad bridging')
    if (obj.library or obj.override_library or obj.data.library or
            obj.data.override_library or obj.data.users != 1 or
            obj.data.shape_keys is not None):
        raise ValueError('Bridge requires a local single-user mesh without shape keys')
    bm, edges = mesh_selection_tools_v086._current(obj, 'EDGE')
    if len(bm.verts) > _MAX_VERTS:
        raise ValueError('Quad bridge supports up to 150,000 mesh vertices')
    picked = tuple(edge for edge in edges
                   if edge.is_valid and edge.select and not edge.hide)
    if not (2 * _MIN_RING <= len(picked) <= 2 * _MAX_RING):
        raise ValueError('Select two closed boundary loops, 3 to 64 edges each')
    if any(len(edge.link_faces) != 1 or edge.seam or not edge.smooth
           for edge in picked):
        raise ValueError('Selected loops must be unseamed, smooth, one-face boundary edges')
    return obj, bm, picked


def _rings(edges):
    """Return two complete, vertex-disjoint cycles; reject forks/open chains."""
    by_vertex = {}
    for edge in edges:
        a, b = edge.verts
        if not a.is_valid or not b.is_valid or a is b or a.hide or b.hide:
            raise ValueError('Selected loop contains a hidden or invalid vertex')
        by_vertex.setdefault(a, []).append(edge)
        by_vertex.setdefault(b, []).append(edge)
    if any(len(incident) != 2 for incident in by_vertex.values()):
        raise ValueError('Selected edges contain a fork or an open chain')
    remaining = set(edges)
    components = []
    while remaining:
        seed = min(remaining, key=lambda edge: edge.index)
        stack = [seed]
        component = set()
        vertices = set()
        while stack:
            edge = stack.pop()
            if edge in component:
                continue
            component.add(edge)
            remaining.discard(edge)
            for vertex in edge.verts:
                vertices.add(vertex)
                stack.extend(other for other in by_vertex[vertex]
                             if other not in component)
        if len(component) != len(vertices):
            raise ValueError('Each bridge ring must be a simple closed cycle')
        components.append((component, vertices))
    if len(components) != 2:
        raise ValueError('Exactly two disconnected edge loops are required')
    components.sort(key=lambda part: min(v.index for v in part[1]))
    first, second = components
    if (len(first[1]) != len(second[1]) or
            not (_MIN_RING <= len(first[1]) <= _MAX_RING) or
            first[1].intersection(second[1])):
        raise ValueError('Quad bridge requires two disjoint equal-length loops')
    return components


def _source_signature(obj, bm, picked):
    """Capture boundary edge flags, adjacent faces and their UV corner data."""
    uv_layers = tuple((layer.name, bm.loops.layers.uv.get(layer.name))
                      for layer in obj.data.uv_layers)
    if any(layer is None for _name, layer in uv_layers):
        raise ValueError('Native UV map is unavailable in the Edit BMesh')
    signature = []
    for edge in sorted(picked, key=lambda item: item.index):
        face = edge.link_faces[0]
        uv = tuple((name, tuple(
            (loop.vert.index, tuple(float(v) for v in loop[layer].uv))
            for loop in face.loops))
            for name, layer in uv_layers)
        if any(not all(math.isfinite(v) for v in coords)
               for _name, loops in uv for _idx, coords in loops):
            raise ValueError('Native UV map has invalid coordinates')
        signature.append((
            edge.index, tuple(sorted(v.index for v in edge.verts)),
            bool(edge.seam), bool(edge.smooth), face.index,
            int(face.material_index), bool(face.smooth), uv))
    return tuple(signature)


def plan(context):
    obj, bm, picked = _eligible(context)
    components = _rings(picked)
    first, second = components
    # An existing edge joining the rims would make bridge output ambiguous;
    # never overwrite or retriangulate an already-connected surface.
    if any((edge.verts[0] in first[1] and edge.verts[1] in second[1]) or
           (edge.verts[1] in first[1] and edge.verts[0] in second[1])
           for edge in bm.edges):
        raise ValueError('Bridge rims are already connected by mesh edges')
    adjacent = {edge.link_faces[0] for edge in picked}
    appearances = {(int(face.material_index), bool(face.smooth))
                   for face in adjacent}
    if len(appearances) != 1:
        raise ValueError('Bridge boundary faces have different materials or shading')
    if any(not math.isfinite(float(v)) for vertex in first[1].union(second[1])
           for v in vertex.co):
        raise ValueError('Boundary loop has non-finite vertex coordinates')
    mat, smooth = next(iter(appearances))
    stamps = (
        mesh_selection_tools_v086._topology(bm),
        mesh_weld_preview_v090._geometry_stamp(bm),
        mesh_axis_snap_v090._matrix_stamp(obj.matrix_world),
        tuple(sorted(edge.index for edge in picked)),
        tuple(tuple(sorted(v.index for v in part[1])) for part in components),
        _source_signature(obj, bm, picked),
    )
    return {
        'scene': context.scene.name, 'scene_ptr': context.scene.as_pointer(),
        'layer': context.view_layer.name,
        'obj': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'stamps': stamps, 'ring_size': len(first[1]),
        'faces': len(bm.faces), 'edges': len(bm.edges), 'verts': len(bm.verts),
        'material': mat, 'smooth': smooth, 'uv_maps': len(obj.data.uv_layers),
    }


def _verify(context, proposal):
    new = plan(context)
    if new != proposal:
        raise ValueError('Bridge source, UVs or geometry changed; preview again')
    obj, bm, picked = _eligible(context)
    parts = _rings(picked)
    return obj, bm, picked, parts


def _mutate(context, proposal):
    obj, bm, picked, parts = _verify(context, proposal)
    a, b = (part[1] for part in parts)
    result = bmesh.ops.bridge_loops(
        bm, edges=list(picked), use_pairs=False, use_cyclic=False,
        use_merge=False, twist_offset=0)
    faces = tuple(face for face in result.get('faces', ())
                  if face.is_valid)
    count = proposal['ring_size']
    if (len(faces) != count or
            len(bm.faces) != proposal['faces'] + count or
            len(bm.verts) != proposal['verts'] or
            len(bm.edges) != proposal['edges'] + count):
        raise ValueError('Blender bridge did not make the expected quad strip')
    faces_set = set(faces)
    if len(faces_set) != count:
        raise ValueError('Native Blender bridge produced duplicate face references')
    for face in faces:
        vertices = set(face.verts)
        if (len(vertices) != 4 or len(vertices & a) != 2 or
                len(vertices & b) != 2 or
                not math.isfinite(float(face.calc_area())) or
                face.calc_area() <= 1e-12):
            raise ValueError('Blender produced a non-quad or degenerate bridge face')
        # A bridge must oppose the existing boundary face's directed edge.
        # Reversed winding would make adjacent normals inconsistent.
        for edge in face.edges:
            if edge not in picked:
                continue
            old_faces = [neighbor for neighbor in edge.link_faces
                         if neighbor not in faces_set]
            if len(old_faces) != 1:
                raise ValueError('Bridge lost a source boundary face')
            current_loop = next((loop for loop in face.loops if loop.edge is edge), None)
            original_loop = next((loop for loop in old_faces[0].loops
                                  if loop.edge is edge), None)
            if (current_loop is None or original_loop is None or
                    current_loop.vert is not original_loop.link_loop_next.vert or
                    current_loop.link_loop_next.vert is not original_loop.vert):
                raise ValueError('Bridge created reversed boundary winding')
        face.material_index = proposal['material']
        face.smooth = proposal['smooth']
    return obj


def commit(context, proposal, history=None):
    obj, _bm, _picked, _parts = _verify(context, proposal)
    if history is not None:
        mesh.snapshot_and_push(obj, lambda: _mutate(context, proposal), history)
    else:
        saved = mesh.snapshot(obj)
        try:
            _mutate(context, proposal)
            mesh.update(obj)
        except Exception:
            mesh.restore(obj, saved)
            raise
        finally:
            if saved.name in bpy.data.meshes:
                bpy.data.meshes.remove(saved)
    return proposal['ring_size']


class BXR_OT_bridge_quads(bpy.types.Operator):
    bl_idname = 'blender_xr.bridge_quads'
    bl_label = 'Preview and Confirm Native Quad Loop Bridge'
    bl_description = 'Join two equal closed boundary loops with native Blender quads'
    bl_options = {'REGISTER', 'UNDO'}
    _proposal = None

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH')

    def invoke(self, context, event):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use headset Quad Bridge preview while XR is running')
            return {'CANCELLED'}
        try:
            self._proposal = plan(context)
        except (RuntimeError, ValueError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=390)

    def draw(self, context):
        p = self._proposal
        if p:
            self.layout.label(text='Two loops: {} edges each'.format(p['ring_size']))
            self.layout.label(text='Expected {} new quads'.format(p['ring_size']))
            if p['uv_maps']:
                self.layout.label(text='New bridge UVs may need manual unwrapping',
                                  icon='ERROR')
        self.layout.label(text='No original vertices or faces are removed')

    def execute(self, context):
        if runtime.CURRENT is not None or self._proposal is None:
            self.report({'WARNING'}, 'Preview the two loops before approving')
            return {'CANCELLED'}
        try:
            count = commit(context, self._proposal)
        except (RuntimeError, ValueError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Native Blender bridge created {} quads'.format(count))
        return {'FINISHED'}


def install_pages():
    page = mesh_topology_audit_v090._PAGE
    original = tuple(menus.PAGES[page])
    if not original or original[-1][1] != 'BACK':
        raise ValueError('Quad Topology menu is unavailable')
    if not any(action == _ENTRY for _label, action in original):
        original = original[:-1] + (('BRIDGE LOOPS', _ENTRY), original[-1])
    if len(original) > 12:
        raise ValueError('Topology menu has no capacity for Loop Bridge')
    menus.PAGES[page] = original
    menus.PAGES[_PAGE] = (
        ('PREVIEW LOOPS', _PREVIEW), ('BACK', 'BACK'))
    menus.PAGES[_CONFIRM_PAGE] = (
        ('MAKE QUADS', _COMMIT), ('KEEP LOOPS', _CANCEL), ('BACK', 'BACK'))
    menus.TITLES[_PAGE] = 'QUAD LOOP BRIDGE'
    menus.TITLES[_CONFIRM_PAGE] = 'CONFIRM QUAD STRIP'
    v065.TOOLTIPS.update({
        _ENTRY: ('Bridge Two Quad Loops',
                 'Preview two separate closed, equal-length boundary edge loops'),
        _PREVIEW: ('Preview Quad Strip',
                   'Check manifold rims, edge count, UV state and materials without editing'),
        _COMMIT: ('Confirm Native Quad Strip',
                  'Bridge the two rings with quads and native XR mesh Undo'),
        _CANCEL: ('Keep Original Edge Loops',
                  'Cancel without changing Blender mesh geometry'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_quad_loop_bridge_090_patched', False):
        return
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        page = getattr(menu, 'page', None)
        if page == mesh_topology_audit_v090._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before inspecting bridge loops')
            _eligible(context)
            self._xr_bridge_quads_pending = None
            menu.page = _PAGE
            self.status = 'BRIDGE QUADS / SELECT TWO CLOSED BOUNDARY LOOPS'
            return
        if page == _PAGE:
            if action == 'BACK':
                self._xr_bridge_quads_pending = None
                menu.page = mesh_topology_audit_v090._PAGE
                return
            if action != _PREVIEW:
                raise ValueError('Preview the two boundary loops first')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before Bridge Preview')
            proposal = plan(context)
            self._xr_bridge_quads_pending = proposal
            menu.page = _CONFIRM_PAGE
            self.status = ('QUAD PREVIEW / TWO RINGS / {} QUADS / '
                           'NEW UVS MAY NEED UNWRAP / CONFIRM?').format(
                proposal['ring_size'])
            return
        if page == _CONFIRM_PAGE:
            if action in {_CANCEL, 'BACK'}:
                self._xr_bridge_quads_pending = None
                menu.page = _PAGE
                self.status = 'BRIDGE CANCELLED / NO BLENDER DATA CHANGED'
                return
            if action != _COMMIT:
                raise ValueError('Confirm bridge or keep original loops')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before Quad Bridge')
            proposal = getattr(self, '_xr_bridge_quads_pending', None)
            if proposal is None:
                raise ValueError('Bridge approval expired; preview again')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('Native XR history required to bridge quads')
            count = commit(context, proposal, history)
            self._xr_bridge_quads_pending = None
            menu.page = _PAGE
            self._xr_precision_last_ray = None
            self.status = 'BRIDGED {} QUADS / XR UNDO READY'.format(count)
            return
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_quad_loop_bridge_090_patched = True


CLASSES = (BXR_OT_bridge_quads,)
