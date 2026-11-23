# SPDX-License-Identifier: GPL-3.0-or-later
"""Preview and explicitly join exactly two compatible native mesh triangles.

The preview is read-only. Confirmation rechecks the original BMesh, UV
continuity, triangle winding, face material, normals, and quad convexity
before one Blender join_triangles operation in the existing XR mesh
snapshot transaction. Never run global beautify or automatic retopology.
"""
import math

import bpy
import bmesh
from mathutils import Vector

from . import (input_ownership_v080, menus, mesh, mesh_selection_tools_v086,
               mesh_topology_audit_v090, mesh_weld_preview_v090, runtime,
               selection, v065)

_PAGE = 'XR_QUAD_PAIR_090'
_CONFIRM_PAGE = 'XR_QUAD_PAIR_CONFIRM_090'
_ENTRY = 'XR_QUAD_PAIR_MENU'
_PREVIEW = 'XR_QUAD_PAIR_PREVIEW'
_COMMIT = 'XR_QUAD_PAIR_COMMIT'
_CANCEL = 'XR_QUAD_PAIR_CANCEL'
_MAX_FACES = 150000
_NORMAL_LIMIT = math.cos(math.radians(12.0))
_UV_EPS = 1e-6


def _eligible(context):
    obj = mesh_selection_tools_v086._editable(context)
    if selection.mode(context) != 'FACE':
        raise ValueError('Select Face Mode and exactly two adjacent triangles')
    if obj.data.users != 1 or obj.data.shape_keys is not None:
        raise ValueError('Quad construction needs a local single-user mesh without shape keys')
    bm, faces = mesh_selection_tools_v086._current(obj, 'FACE')
    if len(faces) > _MAX_FACES:
        raise ValueError('Quad preview supports up to 150,000 mesh faces')
    picked = tuple(face for face in faces if face.is_valid and face.select
                   and not face.hide)
    if len(picked) != 2 or any(len(face.verts) != 3 for face in picked):
        raise ValueError('Select exactly two visible triangular faces')
    return obj, bm, faces, picked


def _outer_cycle(first, second, shared):
    """Build the four-edge boundary ring without changing native BMesh."""
    outer = [edge for face in (first, second) for edge in face.edges
             if edge is not shared]
    if len(outer) != 4 or len(set(outer)) != 4:
        raise ValueError('Triangles do not form a single four-edge boundary')
    links = {}
    for edge in outer:
        a, b = edge.verts
        links.setdefault(a, []).append(b)
        links.setdefault(b, []).append(a)
    if len(links) != 4 or any(len(nexts) != 2 for nexts in links.values()):
        raise ValueError('Triangle pair does not create an unambiguous quad loop')
    begin = min(links, key=lambda v: v.index)
    order = [begin, min(links[begin], key=lambda v: v.index)]
    while len(order) < 4:
        nexts = [v for v in links[order[-1]] if v is not order[-2]]
        if len(nexts) != 1 or nexts[0] in order:
            raise ValueError('Triangle perimeter is self-intersecting')
        order.append(nexts[0])
    if begin not in links[order[-1]]:
        raise ValueError('Triangle perimeter does not close')
    return tuple(order)


def _quad_geometry(first, second, cycle):
    if first.calc_area() <= 1e-12 or second.calc_area() <= 1e-12:
        raise ValueError('Zero-area triangles cannot form a safe quad')
    normal_a = first.normal.normalized()
    normal_b = second.normal.normalized()
    if not all(math.isfinite(float(v)) for v in (*normal_a, *normal_b)):
        raise ValueError('Triangle normals are invalid')
    if normal_a.dot(normal_b) < _NORMAL_LIMIT:
        raise ValueError('Triangle pair exceeds the 12-degree normal threshold')
    points = [v.co.copy() for v in cycle]
    lengths = [(points[(i+1)%4]-points[i]).length for i in range(4)]
    size = sum(lengths) / 4
    if size < 1e-8:
        raise ValueError('Quad perimeter is degenerate')
    plane = points[0]
    if max(abs((point-plane).dot(normal_a)) for point in points) > max(1e-6, size*0.02):
        raise ValueError('Resulting quad would be too nonplanar')
    corner_signs = []
    for i in range(4):
        incoming = points[i] - points[i-1]
        outgoing = points[(i+1)%4] - points[i]
        bend = incoming.cross(outgoing).dot(normal_a)
        if abs(bend) < 1e-9 * max(size * size, 1e-12):
            raise ValueError('Resulting quad has a degenerate or collinear corner')
        corner_signs.append(bend > 0)
    if len(set(corner_signs)) != 1:
        raise ValueError('Resulting quad is concave or self-intersecting')


def _uv_compatible(obj, bm, first, second, shared):
    for uv_layer in obj.data.uv_layers:
        layer = bm.loops.layers.uv.get(uv_layer.name)
        if layer is None:
            raise ValueError('UV map is not accessible from the Edit BMesh')
        corners = []
        for face in (first, second):
            values = {}
            for loop in face.loops:
                if loop.vert in shared.verts:
                    value = tuple(float(c) for c in loop[layer].uv)
                    if not all(math.isfinite(c) for c in value):
                        raise ValueError('Native UV map contains invalid coordinates')
                    values[loop.vert] = value
            if len(values) != 2:
                raise ValueError('Shared-edge UV coordinates are missing')
            corners.append(values)
        for endpoint in shared.verts:
            if any(abs(a-b) > _UV_EPS for a,b in
                   zip(corners[0][endpoint], corners[1][endpoint])):
                raise ValueError('Shared triangle edge crosses a UV split')


def plan(context):
    obj, bm, faces, selected = _eligible(context)
    first, second = selected
    common = set(first.edges).intersection(second.edges)
    if len(common) != 1:
        raise ValueError('Selected triangles must share exactly one edge')
    shared = next(iter(common))
    # Reject reversed/native inconsistent triangle winding at the shared
    # edge; Blender's join operator otherwise may silently flip a new quad.
    def directed_edge(face, edge):
        for loop in face.loops:
            if loop.edge is edge:
                return loop.vert, loop.link_loop_next.vert
        raise ValueError('Triangle does not own the expected shared edge')
    a0, a1 = directed_edge(first, shared)
    b0, b1 = directed_edge(second, shared)
    if not (a0 is b1 and a1 is b0):
        raise ValueError('Triangle pair has inconsistent shared-edge winding')
    if (len(shared.link_faces) != 2 or shared.seam or not shared.smooth or
            shared.hide or not shared.is_manifold):
        raise ValueError('Shared edge is a boundary, seam, non-manifold or sharp')
    if first.material_index != second.material_index or first.smooth != second.smooth:
        raise ValueError('Triangle materials or shading differ')
    cycle = _outer_cycle(first, second, shared)
    _quad_geometry(first, second, cycle)
    _uv_compatible(obj, bm, first, second, shared)
    for face in bm.faces:
        if (face not in selected and len(face.verts) == 4 and
                set(face.verts) == set(cycle)):
            raise ValueError('A quad already covers these four vertices')
    # Capture all existing UV maps on both proposed triangles, including
    # unselected/nonactive maps. A late UV edit invalidates the preview.
    uv_stamp = tuple(
        (layer.name, tuple(tuple(float(v) for v in loop[
            bm.loops.layers.uv.get(layer.name)].uv) for face in selected
            for loop in face.loops))
        for layer in obj.data.uv_layers
    )
    signature = (
        mesh_selection_tools_v086._topology(bm),
        mesh_weld_preview_v090._geometry_stamp(bm),
        tuple(face.index for face in selected),
        shared.index,
        tuple(v.index for v in cycle),
        tuple((face.material_index, bool(face.smooth)) for face in selected),
        uv_stamp,
    )
    return {
        'scene': context.scene.name,
        'scene_ptr': context.scene.as_pointer(),
        'view_layer': context.view_layer.name,
        'obj': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'signature': signature,
        'before_faces': len(bm.faces),
        'before_quads': sum(1 for face in bm.faces if len(face.verts) == 4),
    }


def _verify(context, proposal):
    current = plan(context)
    if (context.scene.name != proposal['scene'] or
            context.scene.as_pointer() != proposal['scene_ptr'] or
            context.view_layer.name != proposal['view_layer'] or
            current['obj'] != proposal['obj'] or
            current['obj_ptr'] != proposal['obj_ptr'] or
            current['mesh'] != proposal['mesh'] or
            current['mesh_ptr'] != proposal['mesh_ptr'] or
            current['signature'] != proposal['signature']):
        raise ValueError('Native triangle geometry changed since Quad Preview')
    obj, bm, faces, selected = _eligible(context)
    return obj, bm, selected


def _mutate(context, proposal):
    obj, bm, selected = _verify(context, proposal)
    before = len(bm.faces)
    result = bmesh.ops.join_triangles(
        bm, faces=list(selected), cmp_seam=True, cmp_sharp=True,
        cmp_uvs=True, cmp_vcols=True, cmp_materials=True,
        angle_face_threshold=math.radians(12),
        angle_shape_threshold=math.radians(30))
    made = tuple(face for face in result.get('faces', ())
                 if face.is_valid and len(face.verts) == 4)
    if len(made) != 1 or len(bm.faces) != before - 1:
        raise ValueError('Blender did not join exactly two triangles into one quad')
    return obj


def _commit(context, proposal, history=None):
    obj, _bm, _selected = _verify(context, proposal)
    if history is not None:
        mesh.snapshot_and_push(obj, lambda: _mutate(context, proposal), history)
    else:
        # Blender's native operator Undo owns desktop changes; recover from
        # a partial BMesh operation using an independent temporary snapshot.
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
    return proposal['before_faces'] - 1, proposal['before_quads'] + 1


class BXR_OT_quad_pair(bpy.types.Operator):
    bl_idname = 'blender_xr.quad_pair'
    bl_label = 'Preview and Confirm Two Triangles into One Quad'
    bl_description = 'Join exactly two compatible native triangles after review'
    bl_options = {'REGISTER', 'UNDO'}
    _preview = None

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and
                    context.mode == 'EDIT_MESH')

    def invoke(self, context, event):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Quad Pair wrist confirmation')
            return {'CANCELLED'}
        try:
            self._preview = plan(context)
        except (ValueError, ReferenceError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        if self._preview:
            p = self._preview
            layout.label(text='Faces: {} to {}'.format(
                p['before_faces'], p['before_faces'] - 1))
            layout.label(text='Quads: {} to {}'.format(
                p['before_quads'], p['before_quads'] + 1))
        layout.label(text='Only one compatible selected triangle pair is affected')
        layout.label(text='UV, seam, sharp, material and convexity guards active')

    def execute(self, context):
        if runtime.CURRENT is not None or self._preview is None:
            self.report({'WARNING'}, 'Preview and approve a new quad pair first')
            return {'CANCELLED'}
        try:
            faces, quads = _commit(context, self._preview)
        except (ValueError, ReferenceError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Native quad created / {} faces / {} quads'.format(
            faces, quads))
        return {'FINISHED'}


def install_pages():
    parent = mesh_topology_audit_v090._PAGE
    current = tuple(menus.PAGES[parent])
    if not current or current[-1][1] != 'BACK':
        raise ValueError('Mesh topology audit menu is unavailable')
    if not any(action == _ENTRY for _label, action in current):
        current = current[:-1] + (('QUAD PAIR', _ENTRY), current[-1])
    if len(current) > 12:
        raise ValueError('Topology audit menu has insufficient room for quad preview')
    menus.PAGES[parent] = current
    menus.PAGES[_PAGE] = (
        ('PREVIEW PAIR', _PREVIEW),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_CONFIRM_PAGE] = (
        ('JOIN TO QUAD', _COMMIT),
        ('KEEP TRIANGLES', _CANCEL),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'QUAD CONSTRUCTION'
    menus.TITLES[_CONFIRM_PAGE] = 'CONFIRM ONE NATIVE QUAD'
    v065.TOOLTIPS.update({
        _ENTRY: ('Conservative Native Quad Pair',
            'Inspect exactly two selected triangles before joining a quad'),
        _PREVIEW: ('Preview Compatible Triangle Pair',
            'Validate convexity, UV continuity, shared edge, material and normals'),
        _COMMIT: ('Confirm Native Quad',
            'Replace the two selected triangles with one quad, with XR mesh Undo'),
        _CANCEL: ('Keep Existing Triangles',
            'Leave Blender mesh unchanged and return to quad preview'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_native_quad_pair_090_patched', False):
        return
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        page = getattr(menu, 'page', None)
        if page == mesh_topology_audit_v090._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before Quad Pair preview')
            _eligible(context)
            self._xr_quad_pair_pending = None
            menu.page = _PAGE
            self.status = 'QUAD PAIR / SELECT 2 TRIANGLES / PREVIEW'
            return
        if page == _PAGE:
            if action == 'BACK':
                self._xr_quad_pair_pending = None
                menu.page = mesh_topology_audit_v090._PAGE
                return
            if action != _PREVIEW:
                raise ValueError('Preview one triangle pair before committing')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before quad preview')
            proposal = plan(context)
            self._xr_quad_pair_pending = proposal
            menu.page = _CONFIRM_PAGE
            self.status = ('QUAD PREVIEW / 2 TRIANGLES → 1 QUAD / '
                           'CHECK UVS AND MATERIAL / CONFIRM?')
            return
        if page == _CONFIRM_PAGE:
            if action in {_CANCEL, 'BACK'}:
                self._xr_quad_pair_pending = None
                menu.page = _PAGE
                self.status = 'QUAD PAIR CANCELLED / NO GEOMETRY CHANGE'
                return
            if action != _COMMIT:
                raise ValueError('Confirm Join or Keep Triangles')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before joining triangles')
            if self._xr_quad_pair_pending is None:
                raise ValueError('Previous quad preview expired; preview again')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('XR mesh history is required for quad construction')
            faces, quads = _commit(context, self._xr_quad_pair_pending, history)
            self._xr_quad_pair_pending = None
            menu.page = _PAGE
            self._xr_precision_last_ray = None
            self.status = 'QUAD CREATED / {} FACES / {} QUADS / XR UNDO'.format(
                faces, quads)
            return
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_native_quad_pair_090_patched = True


CLASSES = (BXR_OT_quad_pair,)
