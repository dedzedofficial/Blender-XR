# SPDX-License-Identifier: GPL-3.0-or-later
"""Guarded native edit-mesh straightening for a single open vertex/edge chain.

Only positions of interior BMVerts are written. Native edges, face topology,
UVs, material assignments, vertex groups, modifiers and object transforms
stay intact. No derived/evaluated mesh is substituted for Blender's edit cage.
"""
import math

import bpy
from bpy.props import EnumProperty
from mathutils import Vector

from . import (input_ownership_v080, menus, mesh, mesh_selection_tools_v086,
               mesh_snap_v086, precision_selection_v086, runtime, selection,
               v065)

_PAGE = 'XR_STRAIGHT_CHAIN_090'
_CONFIRM_PAGE = 'XR_STRAIGHT_CHAIN_CONFIRM_090'
_ENTRY = 'XR_STRAIGHT_CHAIN_MENU'
_PREVIEW = 'XR_STRAIGHT_CHAIN_PREVIEW'
_COMMIT = 'XR_STRAIGHT_CHAIN_COMMIT'
_CANCEL = 'XR_STRAIGHT_CHAIN_CANCEL'
_METHODS = {'XR_STRAIGHT_PROJECT': 'PROJECT',
            'XR_STRAIGHT_EVEN': 'EVEN'}
_SPACES = {'XR_STRAIGHT_LOCAL': 'LOCAL', 'XR_STRAIGHT_WORLD': 'WORLD'}
_LIMITS = {'XR_STRAIGHT_FINE': 0.25, 'XR_STRAIGHT_WIDE': 2.0}
_MAX_VERTICES = 4096
_MAX_NEIGHBOURS = 12000


def _finite(vector):
    return all(math.isfinite(float(value)) for value in vector)


def _source(context):
    """Find exactly one unbranched native open path; never guess a loop cut."""
    obj = mesh_snap_v086._eligible(context)
    mode = selection.mode(context)
    if mode not in {'VERT', 'EDGE'}:
        raise ValueError('Use native Vertex or Edge selection for Straighten')
    bm, items = mesh_selection_tools_v086._current(obj, mode)
    if mode == 'VERT':
        vertices = tuple(v for v in bm.verts
                         if v.is_valid and v.select and not v.hide)
        selected = set(vertices)
        edges = tuple(
            edge for edge in bm.edges
            if edge.is_valid and all(v in selected for v in edge.verts))
    else:
        edges = tuple(e for e in bm.edges if e.is_valid and e.select and not e.hide)
        vertices = tuple({v for edge in edges for v in edge.verts})
        selected = set(vertices)
    if not 3 <= len(vertices) <= _MAX_VERTICES:
        raise ValueError('Select 3–4096 vertices in one open edge chain')
    if any(not vertex.is_valid or vertex.hide for vertex in vertices):
        raise ValueError('Straighten requires visible valid native vertices')
    if any(edge.hide or not edge.is_valid for edge in edges):
        raise ValueError('Selected chain contains hidden or deleted edges')
    if len(edges) != len(vertices) - 1:
        raise ValueError('Straighten requires a single non-branching open chain')
    neighbors = {vertex: [] for vertex in vertices}
    for edge in edges:
        a, b = edge.verts
        if a == b or a not in selected or b not in selected:
            raise ValueError('Native edge chain is inconsistent')
        neighbors[a].append(b)
        neighbors[b].append(a)
    endpoints = sorted((vertex for vertex in vertices
                        if len(neighbors[vertex]) == 1), key=lambda v: v.index)
    if (len(endpoints) != 2 or
            any(len(neighbors[v]) not in {1, 2} for v in vertices)):
        raise ValueError('Straighten rejects closed rings, forks and junctions')
    order = [endpoints[0]]
    seen = {order[0]}
    previous = None
    current = endpoints[0]
    while current != endpoints[1]:
        options = [v for v in neighbors[current] if v != previous]
        if len(options) != 1 or options[0] in seen:
            raise ValueError('Straighten cannot resolve the selected chain')
        previous, current = current, options[0]
        order.append(current)
        seen.add(current)
    if len(order) != len(vertices):
        raise ValueError('Straighten rejects disconnected selected geometry')
    affected = {face for vert in vertices for face in vert.link_faces}
    if (len(affected) > _MAX_NEIGHBOURS or
            any(not face.is_valid or face.hide or
                any(not edge.is_valid or edge.hide for edge in face.edges)
                for face in affected)):
        raise ValueError('Straightening would disturb hidden or excessive adjacent faces')
    return obj, bm, tuple(order), affected


def plan(context, method='PROJECT', space='LOCAL',
         limit='XR_STRAIGHT_FINE'):
    if (method not in {'PROJECT', 'EVEN'} or
            space not in {'LOCAL', 'WORLD'} or limit not in _LIMITS):
        raise ValueError('Choose Project/Even, Local/World and a safety limit')
    obj, bm, chain, faces = _source(context)
    matrix = obj.matrix_world.copy()
    determinant = float(matrix.determinant())
    if (not math.isfinite(determinant) or abs(determinant) <= 1e-10 or
            not all(_finite(row) for row in matrix)):
        raise ValueError('Straighten requires an invertible native object transform')
    inverse = matrix.inverted()
    original = tuple(vertex.co.copy() for vertex in chain)
    working = tuple(
        (matrix @ point if space == 'WORLD' else point.copy())
        for point in original
    )
    if any(not _finite(point) for point in (*original, *working)):
        raise ValueError('Selected chain has non-finite vertex coordinates')
    lengths = tuple((b-a).length for a, b in zip(working, working[1:]))
    if (not lengths or min(lengths) <= 1e-9 or
            any(not math.isfinite(value) for value in lengths)):
        raise ValueError('Straighten refuses collapsed adjacent edges')
    line = working[-1] - working[0]
    line_length = float(line.length)
    if not math.isfinite(line_length) or line_length <= 1e-9:
        raise ValueError('Straighten requires two distinct fixed endpoints')
    path_length = sum(lengths)
    distances = [0.0]
    for segment in lengths:
        distances.append(distances[-1] + segment)
    projected_t = [
        float((point - working[0]).dot(line) / line.length_squared)
        for point in working
    ]
    if method == 'PROJECT':
        # Projection is safe only when the original chain walks forwards
        # along the selected endpoint line. Backtracking is ambiguous and
        # can turn a face inside-out or collapse multiple native vertices.
        if (any(not (0.0 < t < 1.0) for t in projected_t[1:-1]) or
                any(b-a <= 1e-6 for a, b in
                    zip(projected_t, projected_t[1:]))):
            raise ValueError('Projection backtracks or overlaps; choose Even Path')
        fractions = projected_t
    else:
        fractions = [distance / path_length for distance in distances]
    changes = []
    maximum = 0.0
    maximum_world = 0.0
    for i, (vertex, old, point) in enumerate(zip(chain, original, working)):
        if i in (0, len(chain)-1):
            destination = old.copy()
            shift = 0.0
        else:
            projected = working[0] + line * fractions[i]
            destination = (inverse @ projected if space == 'WORLD'
                           else projected)
            shift = (projected-point).length
        if not _finite(destination):
            raise ValueError('Straightening produced non-finite mesh positions')
        world_shift = (matrix @ destination - matrix @ old).length
        maximum = max(maximum, shift)
        maximum_world = max(maximum_world, world_shift)
        if (destination-old).length_squared > 1e-20:
            changes.append((int(vertex.index),
                            tuple(float(v) for v in old),
                            tuple(float(v) for v in destination)))
    if not changes:
        raise ValueError('Selected edge chain is already straight')
    if maximum > _LIMITS[limit] * min(lengths) + 1e-10:
        raise ValueError('Straightening exceeds selected edge movement limit')
    fingerprint = (
        mesh_snap_v086._native_selection_stamp(context, obj, 'LOCAL_CENTER'),
        precision_selection_v086._geometry_stamp(bm),
        tuple(int(v.index) for v in chain),
    )
    return {
        'scene': context.scene.name, 'scene_ptr': context.scene.as_pointer(),
        'layer': context.view_layer.name,
        'obj': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'stamp': fingerprint, 'method': method, 'space': space,
        'limit': limit, 'changes': tuple(changes),
        'selected': len(chain), 'moving': len(changes),
        'faces': len(faces), 'maximum': maximum,
        'world_move': maximum_world,
    }


def _verify(context, proposal):
    if not isinstance(proposal, dict):
        raise ValueError('Straighten preview is missing')
    current = plan(context, proposal['method'], proposal['space'],
                   proposal['limit'])
    if current != proposal:
        raise ValueError('Native chain changed; preview Straighten again')
    return _source(context)


def _mutate(context, proposal):
    obj, bm, chain, affected = _verify(context, proposal)
    previous = {}
    for face in affected:
        face.normal_update()
        area = float(face.calc_area())
        normal = face.normal.copy()
        if (not math.isfinite(area) or area <= 1e-12 or
                not _finite(normal) or normal.length_squared <= 1e-12):
            raise ValueError('A connected face is degenerate before Straighten')
        previous[face] = (area, normal)
    bm.verts.ensure_lookup_table()
    for index, source, _target in proposal['changes']:
        vertex = bm.verts[index]
        if (not vertex.is_valid or vertex.hide or
                tuple(float(x) for x in vertex.co) != source):
            raise ValueError('Straighten vertex changed after Preview')
    for index, _source_coord, target in proposal['changes']:
        bm.verts[index].co = Vector(target)
    for face, (old_area, old_normal) in previous.items():
        face.normal_update()
        area = float(face.calc_area())
        if (not math.isfinite(area) or area <= max(1e-12, old_area * 0.25)
                or face.normal.dot(old_normal) <= 0.50):
            raise ValueError('Straighten would collapse or invert adjacent faces')
    return obj


def commit(context, proposal, history=None):
    obj, _bm, _chain, _faces = _verify(context, proposal)
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
                    'Straighten rollback failed; review native mesh') from exc
            raise
        finally:
            mesh._dispose_temporary_meshes(saved)
    return proposal['moving']


class BXR_OT_straighten_chain(bpy.types.Operator):
    bl_idname = 'blender_xr.straighten_mesh_chain'
    bl_label = 'Preview and Confirm Native Edge Chain Straightening'
    bl_description = 'Straighten one open native edge chain, keeping endpoints fixed'
    bl_options = {'REGISTER', 'UNDO'}
    method: EnumProperty(name='Distribution', items=(
        ('PROJECT', 'Project', 'Orthogonally project interior vertices onto the endpoint line'),
        ('EVEN', 'Even Path', 'Distribute interiors by cumulative original edge length'),
    ), default='PROJECT')
    space: EnumProperty(name='Space', items=(
        ('LOCAL', 'Local', 'Straighten native edit-mesh coordinates'),
        ('WORLD', 'World', 'Straighten in Blender world-space coordinates'),
    ), default='LOCAL')
    limit: EnumProperty(name='Movement Limit', items=(
        ('XR_STRAIGHT_FINE', '25% of shortest edge', 'Conservative local correction'),
        ('XR_STRAIGHT_WIDE', '200% of shortest edge', 'Explicitly approved larger correction'),
    ), default='XR_STRAIGHT_FINE')
    _proposal = None

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH'
                    and selection.mode(context) in {'VERT', 'EDGE'})

    def invoke(self, context, event):
        self._proposal = None
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Straighten Chain wrist menu')
            return {'CANCELLED'}
        try:
            self._proposal = plan(context, self.method, self.space, self.limit)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        if self._proposal:
            self.layout.label(text='{} / {}'.format(
                self._proposal['method'], self._proposal['space']))
            self.layout.label(text='{} of {} native chain vertices move'.format(
                self._proposal['moving'], self._proposal['selected']))
            self.layout.label(text='Two endpoint anchors stay fixed')
            self.layout.label(text='Maximum world movement {:.6g}'.format(
                self._proposal['world_move']))

    def execute(self, context):
        if (runtime.CURRENT is not None or self._proposal is None or
                self.method != self._proposal['method'] or
                self.space != self._proposal['space'] or
                self.limit != self._proposal['limit']):
            self.report({'WARNING'}, 'Preview the selected straighten settings again')
            return {'CANCELLED'}
        try:
            count = commit(context, self._proposal)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self._proposal = None
        self.report({'INFO'}, 'Straightened {} native chain vertices'.format(count))
        return {'FINISHED'}


def install_pages():
    parent = mesh_snap_v086._PAGE
    entries = tuple(menus.PAGES[parent])
    if not entries or entries[-1][1] != 'BACK':
        raise ValueError('Snap Selected wrist page is unavailable')
    if not any(action == _ENTRY for _label, action in entries):
        entries = entries[:-1] + (('STRAIGHTEN', _ENTRY), entries[-1])
    if len(entries) > 12:
        raise ValueError('Snap Selected page cannot fit Straighten Chain')
    menus.PAGES[parent] = entries
    menus.PAGES[_PAGE] = (
        ('PROJECT', 'XR_STRAIGHT_PROJECT'),
        ('EVEN PATH', 'XR_STRAIGHT_EVEN'),
        ('LOCAL', 'XR_STRAIGHT_LOCAL'),
        ('WORLD', 'XR_STRAIGHT_WORLD'),
        ('25% EDGE', 'XR_STRAIGHT_FINE'),
        ('200% EDGE', 'XR_STRAIGHT_WIDE'),
        ('PREVIEW', _PREVIEW), ('BACK', 'BACK'),
    )
    menus.PAGES[_CONFIRM_PAGE] = (
        ('STRAIGHTEN', _COMMIT), ('KEEP MESH', _CANCEL), ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'NATIVE STRAIGHTEN CHAIN'
    menus.TITLES[_CONFIRM_PAGE] = 'CONFIRM STRAIGHTEN'
    v065.TOOLTIPS.update({
        _ENTRY: ('Straighten Edge Chain',
                 'Straighten one selected open native edge path with fixed endpoints'),
        _PREVIEW: ('Preview Straightening',
                   'Inspect maximum displacement before native Blender mesh editing'),
        _COMMIT: ('Confirm Straightening',
                  'Straighten native vertices using one guarded XR Undo transaction'),
        _CANCEL: ('Keep Original Chain', 'Discard preview without editing native mesh'),
        'XR_STRAIGHT_PROJECT': ('Nearest Line Projection',
                                'Preserve original along-line position of each vertex'),
        'XR_STRAIGHT_EVEN': ('Even Path Distribution',
                             'Space vertices by original cumulative edge lengths'),
        'XR_STRAIGHT_LOCAL': ('Mesh Local Space',
                              'Calculate a straight line in native mesh coordinates'),
        'XR_STRAIGHT_WORLD': ('Blender World Space',
                              'Calculate a straight line in scene world coordinates'),
        'XR_STRAIGHT_FINE': ('25% Safety Limit',
                             'Permit movement up to a quarter of shortest edge length'),
        'XR_STRAIGHT_WIDE': ('200% Safety Limit',
                             'Permit larger explicitly approved straightening'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_straight_chain_090_patched', False):
        return
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == mesh_snap_v086._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before Straighten Chain')
            _source(context)
            self._xr_straight_chain_pending = None
            self.menu.page = _PAGE
            self.status = 'STRAIGHTEN / CHOOSE METHOD SPACE LIMIT'
            return
        if page == _PAGE:
            if action == 'BACK':
                self._xr_straight_chain_pending = None
                self.menu.page = mesh_snap_v086._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controller gesture before Straighten Preview')
            if action in _METHODS:
                self._xr_straight_chain_method = _METHODS[action]
                self._xr_straight_chain_pending = None
                self.status = 'STRAIGHTEN METHOD / ' + _METHODS[action]
                return
            if action in _SPACES:
                self._xr_straight_chain_space = _SPACES[action]
                self._xr_straight_chain_pending = None
                self.status = 'STRAIGHTEN SPACE / ' + _SPACES[action]
                return
            if action in _LIMITS:
                self._xr_straight_chain_limit = action
                self._xr_straight_chain_pending = None
                self.status = 'STRAIGHTEN LIMIT / ' + action
                return
            if action != _PREVIEW:
                raise ValueError('Choose method, space, safety limit or Preview')
            proposal = plan(
                context,
                getattr(self, '_xr_straight_chain_method', 'PROJECT'),
                getattr(self, '_xr_straight_chain_space', 'LOCAL'),
                getattr(self, '_xr_straight_chain_limit', 'XR_STRAIGHT_FINE'))
            self._xr_straight_chain_pending = proposal
            self.menu.page = _CONFIRM_PAGE
            self.status = 'STRAIGHTEN PREVIEW / {} MOVING / MAX {:.5g}'.format(
                proposal['moving'], proposal['world_move'])
            return
        if page == _CONFIRM_PAGE:
            if action in {_CANCEL, 'BACK'}:
                self._xr_straight_chain_pending = None
                self.menu.page = _PAGE
                self.status = 'STRAIGHTEN CANCELLED / MESH UNCHANGED'
                return
            if action != _COMMIT:
                raise ValueError('Confirm or cancel Straighten')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before Straighten approval')
            pending = getattr(self, '_xr_straight_chain_pending', None)
            if pending is None:
                raise ValueError('Straighten approval expired; preview again')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('XR mesh history required to straighten')
            count = commit(context, pending, history)
            self._xr_straight_chain_pending = None
            self._xr_precision_last_ray = None
            self.menu.page = _PAGE
            self.status = 'STRAIGHTEN / {} VERTICES / XR UNDO READY'.format(count)
            return
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_straight_chain_090_patched = True


CLASSES = (BXR_OT_straighten_chain,)
