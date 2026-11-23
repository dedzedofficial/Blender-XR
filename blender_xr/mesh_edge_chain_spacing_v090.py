# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Blender open-edge-chain arc-length spacing with guarded XR Undo.

Resample selected vertices along the EXISTING polyline, rather than along a
single X/Y/Z axis. Both endpoints are fixed. Bounded interior displacements
avoid abrupt curvature changes. The operation never changes connectivity,
UVs, weights, materials or object transforms.
"""
import bisect
import math

import bpy
from mathutils import Vector

from . import (input_ownership_v080, menus, mesh,
               mesh_axis_snap_v090, mesh_even_spacing_v090,
               mesh_selection_tools_v086, mesh_weld_preview_v090,
               runtime, selection, v065)

_PAGE = 'XR_CHAIN_SPACING_090'
_CONFIRM = 'XR_CHAIN_SPACING_CONFIRM_090'
_ENTRY = 'XR_CHAIN_SPACING_MENU'
_PREVIEW = 'XR_CHAIN_SPACING_PREVIEW'
_COMMIT = 'XR_CHAIN_SPACING_COMMIT'
_CANCEL = 'XR_CHAIN_SPACING_CANCEL'
_PRESETS = {
    'XR_CHAIN_SPACING_GENTLE': ('GENTLE', 0.05),
    'XR_CHAIN_SPACING_MEDIUM': ('MEDIUM', 0.10),
    'XR_CHAIN_SPACING_STRONG': ('STRONG', 0.20),
}
_MAX_CHAIN_VERTS = 1025
_MAX_MESH_VERTS = 150000
_MAX_DOMAIN = 250000
_MIN_SEGMENT = 1e-8


def _source(context):
    if context.mode != 'EDIT_MESH' or selection.mode(context) != 'EDGE':
        raise ValueError('Use Mesh Edit Mode and select one open edge chain')
    obj = mesh_selection_tools_v086._editable(context)
    if (obj.library or obj.override_library or obj.data.library or
            obj.data.override_library or obj.data.users != 1 or
            obj.data.shape_keys is not None):
        raise ValueError('Chain Spacing requires a local single-user mesh without shape keys')
    bm, _all_edges = mesh_selection_tools_v086._current(obj, 'EDGE')
    if (len(bm.verts) > _MAX_MESH_VERTS or
            max(len(bm.edges), len(bm.faces)) > _MAX_DOMAIN):
        raise ValueError('Chain Spacing supports at most 150k vertices and 250k edges/faces')
    edges = tuple(e for e in bm.edges if e.is_valid and e.select and not e.hide)
    if not 2 <= len(edges) < _MAX_CHAIN_VERTS:
        raise ValueError('Select 2 to 1024 visible edges in exactly one open chain')
    adjacency = {}
    for edge in edges:
        if any(not v.is_valid or v.hide for v in edge.verts):
            raise ValueError('Selected chain includes invalid/hidden vertices')
        for vertex in edge.verts:
            adjacency.setdefault(vertex, []).append((edge, edge.other_vert(vertex)))
    if len(adjacency) != len(edges) + 1:
        raise ValueError('Chain must be open, unbranched and without loops')
    if any(len(neighbours) > 2 or not neighbours for neighbours in adjacency.values()):
        raise ValueError('Selected edge chain branches or has an isolated vertex')
    endpoints = tuple(sorted(
        (v for v, neighbours in adjacency.items() if len(neighbours) == 1),
        key=lambda vert: vert.index))
    if len(endpoints) != 2 or sum(len(neighbours) == 2
                                  for neighbours in adjacency.values()) != len(edges)-1:
        raise ValueError('Choose one open edge chain, not a closed ring or branches')
    if any(v.is_valid and not v.hide and v.select and v not in adjacency
           for v in bm.verts):
        raise ValueError('Deselect vertices outside the active edge chain')

    ordered = [endpoints[0]]
    chosen_edges = []
    previous = None
    current = endpoints[0]
    while True:
        follow = [(e, v) for e, v in adjacency[current] if v is not previous]
        if not follow:
            break
        if len(follow) != 1:
            raise ValueError('Ambiguous edge chain traversal')
        edge, neighbour = follow[0]
        if neighbour in ordered:
            raise ValueError('Chain selection contains a cycle')
        chosen_edges.append(edge)
        ordered.append(neighbour)
        previous, current = current, neighbour
        if len(ordered) > _MAX_CHAIN_VERTS:
            raise ValueError('Edge chain is too long')
    if len(ordered) != len(adjacency) or len(chosen_edges) != len(edges):
        raise ValueError('Chain has disconnected pieces or unvisited edges')

    affected = {face for vert in ordered for face in vert.link_faces}
    if len(affected) > 20000:
        raise ValueError('Chain Spacing affects too many neighbouring faces')
    if any(not face.is_valid or face.hide or
           any(not edge.is_valid or edge.hide for edge in face.edges)
           for face in affected):
        raise ValueError('Chain Spacing refuses hidden/invalid neighbouring geometry')
    return obj, bm, tuple(ordered), tuple(chosen_edges), affected


def _world(obj, vertices):
    matrix = obj.matrix_world.copy()
    det = float(matrix.determinant())
    if (not math.isfinite(det) or abs(det) <= 1e-10 or
            any(not math.isfinite(float(x)) for row in matrix for x in row)):
        raise ValueError('Chain spacing needs a finite invertible native object transform')
    points = tuple(matrix @ v.co for v in vertices)
    if any(not all(math.isfinite(float(x)) for x in point) for point in points):
        raise ValueError('Selected native vertex contains invalid coordinates')
    return matrix, points


def plan(context, preset='XR_CHAIN_SPACING_MEDIUM'):
    if preset not in _PRESETS:
        raise ValueError('Choose Gentle, Medium or Strong edge-chain spacing')
    obj, bm, vertices, edges, affected = _source(context)
    matrix, world = _world(obj, vertices)
    lengths = tuple((b-a).length for a, b in zip(world, world[1:]))
    if any(not math.isfinite(v) or v <= _MIN_SEGMENT for v in lengths):
        raise ValueError('Chain has a zero-length or invalid source edge')
    cumulative = [0.0]
    for length in lengths:
        cumulative.append(cumulative[-1] + length)
    total = cumulative[-1]
    if not math.isfinite(total) or total > 10000:
        raise ValueError('Chain has an invalid or excessively long world-space length')
    step = total / (len(vertices)-1)
    factor = _PRESETS[preset][1]
    inverse = matrix.inverted()
    changes = []
    for i in range(1, len(vertices)-1):
        distance = step * i
        segment = max(0, min(len(lengths)-1,
                             bisect.bisect_right(cumulative, distance)-1))
        ratio = (distance-cumulative[segment]) / lengths[segment]
        target_world = world[segment].lerp(world[segment+1], ratio)
        delta = target_world-world[i]
        bound = min(lengths[i-1], lengths[i]) * factor
        if delta.length > bound:
            delta = delta.normalized() * bound
        if delta.length <= max(1e-9, bound * 1e-6):
            continue
        result_world = world[i]+delta
        result_local = inverse @ result_world
        before = tuple(float(x) for x in vertices[i].co)
        after = tuple(float(x) for x in result_local)
        if not all(math.isfinite(x) for x in after):
            raise ValueError('Chain spacing would create invalid coordinates')
        changes.append((vertices[i].index, before, after))
    if not changes:
        raise ValueError('Selected edge chain is already evenly spaced at this strength')

    stamp = (
        mesh_selection_tools_v086._topology(bm),
        mesh_weld_preview_v090._geometry_stamp(bm),
        mesh_axis_snap_v090._matrix_stamp(matrix),
        tuple(edge.index for edge in edges),
        tuple(v.index for v in vertices),
        tuple(v.index for v in bm.verts if v.is_valid and v.select),
        tuple((f.index, int(f.material_index), bool(f.smooth))
              for f in sorted(affected, key=lambda face: face.index)),
    )
    return {
        'scene': context.scene.name, 'scene_ptr': context.scene.as_pointer(),
        'view_layer': context.view_layer.name,
        'obj': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'preset': preset, 'stamp': stamp,
        'chain_verts': len(vertices), 'chain_edges': len(edges),
        'changes': tuple(changes), 'total_length': total,
        'target_step': step, 'max_world_move': max(
            (matrix.to_3x3() @ (Vector(end)-Vector(start))).length
            for _index, start, end in changes),
    }


def _verify(context, proposal):
    if not isinstance(proposal, dict):
        raise ValueError('Edge Chain Spacing requires a fresh preview')
    if plan(context, proposal['preset']) != proposal:
        raise ValueError('Native chain selection or geometry changed; preview again')
    return _source(context)


def _mutate(context, proposal):
    obj, bm, vertices, edges, affected = _verify(context, proposal)
    before_faces = {}
    for face in affected:
        face.normal_update()
        area = float(face.calc_area())
        normal = face.normal.copy()
        if (not math.isfinite(area) or area <= 1e-12 or
                normal.length_squared <= 1e-12 or
                not all(math.isfinite(float(x)) for x in normal)):
            raise ValueError('Connected mesh contains a degenerate face')
        before_faces[face] = (area, normal)
    bm.verts.ensure_lookup_table()
    for index, before, _after in proposal['changes']:
        v = bm.verts[index]
        if not v.is_valid or v.hide or tuple(float(x) for x in v.co) != before:
            raise ValueError('Selected chain vertex changed before the edit')
    for index, _before, after in proposal['changes']:
        bm.verts[index].co = Vector(after)
    for edge in edges:
        if (not edge.is_valid or
                (edge.verts[0].co-edge.verts[1].co).length <= _MIN_SEGMENT):
            raise ValueError('Even Chain Spacing collapsed an existing edge')
    for face, (original_area, original_normal) in before_faces.items():
        face.normal_update()
        area = float(face.calc_area())
        if (not math.isfinite(area) or
                area <= max(1e-12, original_area*0.5) or
                face.normal.dot(original_normal) < 0.7):
            raise ValueError('Chain Spacing would invert or collapse a connected face')
    return obj


def commit(context, proposal, history=None):
    obj, _bm, _vertices, _edges, _affected = _verify(context, proposal)
    if history is not None:
        mesh.snapshot_and_push(obj, lambda: _mutate(context, proposal), history)
    else:
        saved = mesh.snapshot(obj)
        try:
            _mutate(context, proposal)
            mesh.update(obj)
        except BaseException:
            try:
                mesh.restore(obj, saved)
            except Exception as exc:
                raise mesh.MeshRollbackFailure(
                    'Edge Chain Spacing rollback failed; inspect the mesh') from exc
            raise
        finally:
            mesh._dispose_temporary_meshes(saved)
    return len(proposal['changes'])


class BXR_OT_edge_chain_spacing(bpy.types.Operator):
    bl_idname = 'blender_xr.edge_chain_spacing'
    bl_label = 'Preview and Confirm Native Edge Chain Spacing'
    bl_description = 'Redistribute an unbranched open edge chain along its existing path'
    bl_options = {'REGISTER', 'UNDO'}

    preset: bpy.props.EnumProperty(
        items=tuple(
            (key, title.title(), 'Maximum {}% of each vertex shortest path edge'.format(
                int(factor*100)))
            for key, (title, factor) in _PRESETS.items()),
        default='XR_CHAIN_SPACING_MEDIUM')
    _proposal = None

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and
                    context.mode == 'EDIT_MESH' and selection.mode(context) == 'EDGE')

    def invoke(self, context, event):
        self._proposal = None
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the headset Edge Chain wrist preview')
            return {'CANCELLED'}
        try:
            self._proposal = plan(context, self.preset)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=410)

    def draw(self, context):
        if self._proposal:
            self.layout.label(text='Open path: {} edges / {} vertices'.format(
                self._proposal['chain_edges'], self._proposal['chain_verts']))
            self.layout.label(text='Interior vertices moved: {}'.format(
                len(self._proposal['changes'])))
            self.layout.label(text='Max movement in world units: {:.6g}'.format(
                self._proposal['max_world_move']))
        self.layout.label(text='Endpoints fixed; topology and UVs unchanged')

    def execute(self, context):
        if (runtime.CURRENT is not None or self._proposal is None or
                self.preset != self._proposal['preset']):
            self.report({'WARNING'}, 'Preview the selected Edge Chain strength first')
            return {'CANCELLED'}
        try:
            changed = commit(context, self._proposal)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self._proposal = None
        self.report({'INFO'}, '{} chain vertices evenly adjusted'.format(changed))
        return {'FINISHED'}


def install_pages():
    parent = mesh_even_spacing_v090._PAGE
    entries = tuple(menus.PAGES[parent])
    if not entries or entries[-1][1] != 'BACK':
        raise ValueError('Native Even Spacing wrist menu unavailable')
    if not any(action == _ENTRY for _label, action in entries):
        entries = entries[:-1] + (('EDGE CHAIN', _ENTRY), entries[-1])
    if len(entries) > 12:
        raise ValueError('Even Spacing wrist menu cannot hold Edge Chain')
    menus.PAGES[parent] = entries
    menus.PAGES[_PAGE] = (
        ('GENTLE 5%', 'XR_CHAIN_SPACING_GENTLE'),
        ('MEDIUM 10%', 'XR_CHAIN_SPACING_MEDIUM'),
        ('STRONG 20%', 'XR_CHAIN_SPACING_STRONG'),
        ('PREVIEW CHAIN', _PREVIEW),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_CONFIRM] = (
        ('SPACE CHAIN', _COMMIT), ('KEEP PATH', _CANCEL), ('BACK', 'BACK'))
    menus.TITLES[_PAGE] = 'NATIVE EDGE CHAIN SPACING'
    menus.TITLES[_CONFIRM] = 'CONFIRM EDGE CHAIN SPACING'
    v065.TOOLTIPS.update({
        _ENTRY: ('Space Along Native Edge Chain',
                 'Follow selected open path rather than a world/local X/Y/Z axis'),
        _PREVIEW: ('Preview Along-Path Spacing',
                   'Keep endpoints fixed; cap each move relative to local path edges'),
        _COMMIT: ('Confirm Along-Path Spacing',
                  'Apply native BMesh vertex coordinates with XR mesh Undo/Redo'),
        _CANCEL: ('Keep Original Edge Path',
                  'Discard the preview; no geometry or UV change'),
    })
    for key, (_title, fraction) in _PRESETS.items():
        v065.TOOLTIPS[key] = (
            'Chain Spacing {}%'.format(int(fraction*100)),
            'Limit each moved vertex to {}% of its shortest selected edge'.format(
                int(fraction*100)))


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_edge_chain_spacing_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == mesh_even_spacing_v090._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controller gesture before Edge Chain Spacing')
            _source(context)
            self._xr_edge_chain_spacing_pending = None
            self._xr_edge_chain_spacing_preset = 'XR_CHAIN_SPACING_MEDIUM'
            self.menu.page = _PAGE
            self.status = 'EDGE CHAIN / 1 OPEN PATH / CHOOSE STRENGTH AND PREVIEW'
            return
        if page == _PAGE:
            if action == 'BACK':
                self._xr_edge_chain_spacing_pending = None
                self.menu.page = mesh_even_spacing_v090._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before Edge Chain preview')
            if action in _PRESETS:
                self._xr_edge_chain_spacing_preset = action
                self._xr_edge_chain_spacing_pending = None
                self.status = 'CHAIN SPACING / {} / PREVIEW NEXT'.format(
                    _PRESETS[action][0])
                return
            if action != _PREVIEW:
                raise ValueError('Choose Edge Chain strength or Preview')
            proposal = plan(context, getattr(
                self, '_xr_edge_chain_spacing_preset', 'XR_CHAIN_SPACING_MEDIUM'))
            self._xr_edge_chain_spacing_pending = proposal
            self.menu.page = _CONFIRM
            self.status = 'CHAIN PREVIEW / {} VERTS / MOVE {:.5g} / CONFIRM?'.format(
                len(proposal['changes']), proposal['max_world_move'])
            return
        if page == _CONFIRM:
            if action in {_CANCEL, 'BACK'}:
                self._xr_edge_chain_spacing_pending = None
                self.menu.page = _PAGE
                self.status = 'EDGE CHAIN SPACING CANCELLED / NO NATIVE EDIT'
                return
            if action != _COMMIT:
                raise ValueError('Confirm or cancel native Edge Chain Spacing')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before Edge Chain commit')
            proposal = getattr(self, '_xr_edge_chain_spacing_pending', None)
            if proposal is None:
                raise ValueError('Edge Chain approval expired; preview again')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('XR native mesh history required for Edge Chain Spacing')
            count = commit(context, proposal, history)
            self._xr_edge_chain_spacing_pending = None
            self._xr_precision_last_ray = None
            self.menu.page = _PAGE
            self.status = 'EDGE CHAIN / {} VERTICES / XR UNDO READY'.format(count)
            return
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_edge_chain_spacing_090_patched = True


CLASSES = (BXR_OT_edge_chain_spacing,)
