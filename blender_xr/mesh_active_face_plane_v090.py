# SPDX-License-Identifier: GPL-3.0-or-later
"""Previewed, guarded native vertex projection onto an active edit face plane.

A selected active face defines the plane. The connected selected vertex patch
may be flattened in local or world coordinates, under a finite displacement
limit. Only BMVert.co is changed; no topology, UVs, materials, weights, or
object transforms are replaced.
"""
import math

import bmesh
import bpy
from bpy.props import EnumProperty
from mathutils import Vector

from . import (input_ownership_v080, menus, mesh, mesh_plane_align_v086,
               mesh_selection_tools_v086, mesh_snap_v086,
               precision_selection_v086, runtime, selection, v065)

_PAGE = 'XR_ACTIVE_FACE_PLANE_090'
_CONFIRM_PAGE = 'XR_ACTIVE_FACE_PLANE_CONFIRM_090'
_ENTRY = 'XR_FACE_PLANE_MENU'
_PREVIEW = 'XR_FACE_PLANE_PREVIEW'
_COMMIT = 'XR_FACE_PLANE_COMMIT'
_CANCEL = 'XR_FACE_PLANE_CANCEL'
_SPACES = {'XR_FACE_PLANE_LOCAL': 'LOCAL',
           'XR_FACE_PLANE_WORLD': 'WORLD'}
_LIMITS = {'XR_FACE_PLANE_FINE': 0.10,
           'XR_FACE_PLANE_WIDE': 0.50}
_MAX_SELECTED = 4096
_MAX_NEIGHBOURS = 12000


def _source(context):
    obj = mesh_snap_v086._eligible(context)
    if selection.mode(context) != 'FACE':
        raise ValueError('Select faces in native Mesh Face Edit Mode')
    bm, faces = mesh_selection_tools_v086._current(obj, 'FACE')
    active = bm.faces.active
    if (active is None or not active.is_valid or active.hide or not active.select
            or any(v.hide or not v.is_valid for v in active.verts)
            or any(e.hide or not e.is_valid for e in active.edges)):
        raise ValueError('Choose a visible selected active native face')
    vertices = tuple(sorted(mesh.selected_transform_vertices(obj, 'FACE'),
                            key=lambda vertex: vertex.index))
    if not 3 <= len(vertices) <= _MAX_SELECTED:
        raise ValueError('Select 3–4096 vertices belonging to selected faces')
    selected = set(vertices)
    if any(not v.is_valid or v.hide for v in vertices):
        raise ValueError('Selected vertices became hidden or invalid')
    # A single active face must not silently project several disconnected
    # mesh islands or accidentally alter geometry hidden behind the model.
    visited = set(active.verts) & selected
    frontier = list(visited)
    while frontier:
        vertex = frontier.pop()
        for edge in vertex.link_edges:
            if not edge.is_valid or edge.hide:
                continue
            other = edge.other_vert(vertex)
            if other in selected and other not in visited:
                visited.add(other)
                frontier.append(other)
    if len(visited) != len(selected):
        raise ValueError('Select one connected face patch containing the active face')
    neighbours = {face for vert in vertices for face in vert.link_faces}
    if (len(neighbours) > _MAX_NEIGHBOURS or
            any(not face.is_valid or face.hide or
                any(not edge.is_valid or edge.hide for edge in face.edges)
                for face in neighbours)):
        raise ValueError('Plane alignment touches hidden or excessively dense faces')
    return obj, bm, active, vertices, neighbours


def _plane(obj, face, space):
    matrix = obj.matrix_world.copy()
    if (not all(math.isfinite(float(x)) for row in matrix for x in row) or
            not math.isfinite(float(matrix.determinant())) or
            abs(float(matrix.determinant())) <= 1e-10):
        raise ValueError('Active mesh requires an invertible world transform')
    inverse = matrix.inverted()
    face.normal_update()
    normal = face.normal.copy()
    center = face.calc_center_median()
    if (normal.length_squared <= 1e-14 or
            not all(math.isfinite(float(x)) for x in (*normal, *center))):
        raise ValueError('Active face has an invalid plane')
    if space == 'WORLD':
        normal = inverse.transposed().to_3x3() @ normal
        center = matrix @ center
    if (normal.length_squared <= 1e-14 or
            not all(math.isfinite(float(x)) for x in (*normal, *center))):
        raise ValueError('Transformed active face plane is invalid')
    normal.normalize()
    return matrix, inverse, center, normal


def plan(context, space='LOCAL', limit='XR_FACE_PLANE_FINE'):
    if space not in {'LOCAL', 'WORLD'} or limit not in _LIMITS:
        raise ValueError('Choose valid plane space and movement limit')
    obj, bm, face, vertices, neighbours = _source(context)
    matrix, inverse, center, normal = _plane(obj, face, space)
    face_edges = tuple(edge for edge in face.edges if edge.is_valid)
    lengths = tuple(
        ((matrix @ edge.verts[0].co - matrix @ edge.verts[1].co).length
         if space == 'WORLD' else (edge.verts[0].co-edge.verts[1].co).length)
        for edge in face_edges
    )
    if not lengths or min(lengths) <= 1e-9:
        raise ValueError('Active face contains degenerate edges')
    limit_distance = _LIMITS[limit] * min(lengths)
    changes = []
    max_move = 0.0
    for vertex in vertices:
        original = vertex.co.copy()
        working = matrix @ original if space == 'WORLD' else original.copy()
        if not all(math.isfinite(float(x)) for x in working):
            raise ValueError('Selected mesh contains non-finite coordinates')
        offset = float((working - center).dot(normal))
        target = working - normal * offset
        local = inverse @ target if space == 'WORLD' else target
        if not all(math.isfinite(float(x)) for x in local):
            raise ValueError('Plane projection produced non-finite mesh geometry')
        max_move = max(max_move, abs(offset))
        if (local - original).length_squared > 1e-20:
            changes.append((int(vertex.index),
                            tuple(float(v) for v in original),
                            tuple(float(v) for v in local)))
    if not changes:
        raise ValueError('Selected vertices already lie on the active face plane')
    if max_move > limit_distance + 1e-10:
        raise ValueError('Plane movement exceeds the selected safety limit')
    # The native stamp captures current selected face/vertex IDs, source mesh
    # and its transforms. The streaming geometry hash additionally rejects
    # an edit to unrelated vertices between read-only Preview and Confirm.
    stamp = (
        mesh_snap_v086._native_selection_stamp(context, obj, 'LOCAL_CENTER'),
        precision_selection_v086._geometry_stamp(bm),
        int(face.index), tuple(int(v.index) for v in face.verts),
        int(face.material_index), bool(face.smooth),
    )
    return {
        'scene': context.scene.name, 'scene_ptr': context.scene.as_pointer(),
        'layer': context.view_layer.name,
        'obj': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'space': space, 'limit': limit, 'stamp': stamp,
        'changes': tuple(changes), 'selected': len(vertices),
        'moving': len(changes), 'neighbours': len(neighbours),
        'max_move': max_move,
    }


def _verify(context, proposal):
    if not isinstance(proposal, dict):
        raise ValueError('Active Face Plane preview is missing')
    if plan(context, proposal['space'], proposal['limit']) != proposal:
        raise ValueError('Native face plane or mesh changed; preview again')
    return _source(context)


def _mutate(context, proposal):
    obj, bm, _face, _vertices, neighbours = _verify(context, proposal)
    before = {}
    for face in neighbours:
        face.normal_update()
        area = float(face.calc_area())
        if (not math.isfinite(area) or area <= 1e-12 or
                not all(math.isfinite(float(x)) for x in face.normal) or
                face.normal.length_squared <= 1e-12):
            raise ValueError('A connected native face is already degenerate')
        before[face] = (area, face.normal.copy())
    bm.verts.ensure_lookup_table()
    for index, previous, _after in proposal['changes']:
        vertex = bm.verts[index]
        if (not vertex.is_valid or vertex.hide or
                tuple(float(v) for v in vertex.co) != previous):
            raise ValueError('Native face plane target changed since preview')
    for index, _previous, after in proposal['changes']:
        bm.verts[index].co = Vector(after)
    for face, (old_area, old_normal) in before.items():
        face.normal_update()
        area = float(face.calc_area())
        if (not math.isfinite(area) or area <= max(1e-12, old_area * 0.25)
                or face.normal.dot(old_normal) <= 0.45):
            raise ValueError('Face plane projection collapsed or inverted connected geometry')
    return obj


def commit(context, proposal, history=None):
    obj, _bm, _face, _verts, _neighbours = _verify(context, proposal)
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
                    'Active face plane rollback failed; review native mesh') from exc
            raise
        finally:
            mesh._dispose_temporary_meshes(saved)
    return proposal['moving']


class BXR_OT_active_face_plane(bpy.types.Operator):
    bl_idname = 'blender_xr.active_face_plane'
    bl_label = 'Preview and Confirm Native Active Face Plane'
    bl_description = 'Flatten a selected connected native patch to the active face plane'
    bl_options = {'REGISTER', 'UNDO'}
    space: EnumProperty(name='Coordinates', items=(
        ('LOCAL', 'Local', 'Project in native local mesh coordinates'),
        ('WORLD', 'World', 'Project in scene world coordinates'),
    ), default='LOCAL')
    limit: EnumProperty(name='Maximum Move', items=(
        ('XR_FACE_PLANE_FINE', '10% of edge', 'Conservative face plane projection'),
        ('XR_FACE_PLANE_WIDE', '50% of edge', 'Explicitly approved wider projection'),
    ), default='XR_FACE_PLANE_FINE')
    _proposal = None

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH'
                    and selection.mode(context) == 'FACE')

    def invoke(self, context, event):
        self._proposal = None
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the headset Active Face Plane menu')
            return {'CANCELLED'}
        try:
            self._proposal = plan(context, self.space, self.limit)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        if self._proposal is not None:
            self.layout.label(text='Active face plane in ' + self._proposal['space'])
            self.layout.label(text='Moves {} of {} selected vertices'.format(
                self._proposal['moving'], self._proposal['selected']))
            self.layout.label(text='Max plane movement: {:.6g}'.format(
                self._proposal['max_move']))
            self.layout.label(text='Connected faces checked; Blender Undo available')

    def execute(self, context):
        if (runtime.CURRENT is not None or self._proposal is None or
                self.space != self._proposal['space'] or
                self.limit != self._proposal['limit']):
            self.report({'WARNING'}, 'Preview the chosen face plane again')
            return {'CANCELLED'}
        try:
            count = commit(context, self._proposal)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self._proposal = None
        self.report({'INFO'}, 'Aligned {} vertices to the active face plane'.format(count))
        return {'FINISHED'}


def install_pages():
    parent = mesh_plane_align_v086._PAGE
    old = tuple(menus.PAGES[parent])
    if not old or old[-1][1] != 'BACK':
        raise ValueError('Native Flatten wrist page is unavailable')
    if not any(action == _ENTRY for _label, action in old):
        old = old[:-1] + (('FACE PLANE', _ENTRY), old[-1])
    if len(old) > 12:
        raise ValueError('Flatten wrist page cannot fit Active Face Plane')
    menus.PAGES[parent] = old
    menus.PAGES[_PAGE] = (
        ('LOCAL PLANE', 'XR_FACE_PLANE_LOCAL'),
        ('WORLD PLANE', 'XR_FACE_PLANE_WORLD'),
        ('10% EDGE', 'XR_FACE_PLANE_FINE'),
        ('50% EDGE', 'XR_FACE_PLANE_WIDE'),
        ('PREVIEW', _PREVIEW),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_CONFIRM_PAGE] = (
        ('ALIGN PATCH', _COMMIT), ('KEEP MESH', _CANCEL), ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'ACTIVE FACE PLANE'
    menus.TITLES[_CONFIRM_PAGE] = 'CONFIRM FACE PLANE'
    v065.TOOLTIPS.update({
        _ENTRY: ('Active Face Plane', 'Project a connected selected patch onto the selected active face'),
        _PREVIEW: ('Preview Active Face Plane', 'Check native vertex movements before changing mesh'),
        _COMMIT: ('Confirm Face Plane', 'Project the patch with guarded native XR Undo'),
        _CANCEL: ('Keep Original Mesh', 'Discard the read-only active face plane preview'),
        'XR_FACE_PLANE_LOCAL': ('Local Face Plane', 'Use native mesh coordinates for projection'),
        'XR_FACE_PLANE_WORLD': ('World Face Plane', 'Use true world coordinates, even on transformed objects'),
        'XR_FACE_PLANE_FINE': ('10% Edge Limit', 'Refuse large movement relative to the active face edge'),
        'XR_FACE_PLANE_WIDE': ('50% Edge Limit', 'Permit bounded, explicitly approved face plane movement'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_active_face_plane_090_patched', False):
        return
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == mesh_plane_align_v086._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before active face projection')
            _source(context)
            self._xr_face_plane_pending = None
            self.menu.page = _PAGE
            self.status = 'FACE PLANE / SET SPACE AND LIMIT / PREVIEW'
            return
        if page == _PAGE:
            if action == 'BACK':
                self._xr_face_plane_pending = None
                self.menu.page = mesh_plane_align_v086._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controller gesture before face plane preview')
            if action in _SPACES:
                self._xr_face_plane_space = _SPACES[action]
                self._xr_face_plane_pending = None
                self.status = 'ACTIVE PLANE SPACE / ' + _SPACES[action]
                return
            if action in _LIMITS:
                self._xr_face_plane_limit = action
                self._xr_face_plane_pending = None
                self.status = 'ACTIVE PLANE LIMIT / ' + action
                return
            if action != _PREVIEW:
                raise ValueError('Choose space, limit, Preview or Back')
            proposal = plan(context,
                            getattr(self, '_xr_face_plane_space', 'LOCAL'),
                            getattr(self, '_xr_face_plane_limit', 'XR_FACE_PLANE_FINE'))
            self._xr_face_plane_pending = proposal
            self.menu.page = _CONFIRM_PAGE
            self.status = 'FACE PLANE PREVIEW / {} VERTICES / MAX {:.5g}'.format(
                proposal['moving'], proposal['max_move'])
            return
        if page == _CONFIRM_PAGE:
            if action in {_CANCEL, 'BACK'}:
                self._xr_face_plane_pending = None
                self.menu.page = _PAGE
                self.status = 'FACE PLANE CANCELLED / NO MESH CHANGE'
                return
            if action != _COMMIT:
                raise ValueError('Confirm or cancel Active Face Plane')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before face plane confirmation')
            pending = getattr(self, '_xr_face_plane_pending', None)
            if pending is None:
                raise ValueError('Face Plane confirmation expired; preview again')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('Native XR mesh history unavailable')
            moved = commit(context, pending, history)
            self._xr_face_plane_pending = None
            self._xr_precision_last_ray = None
            self.menu.page = _PAGE
            self.status = 'ACTIVE FACE PLANE / {} VERTICES / XR UNDO'.format(moved)
            return
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_active_face_plane_090_patched = True


CLASSES = (BXR_OT_active_face_plane,)
