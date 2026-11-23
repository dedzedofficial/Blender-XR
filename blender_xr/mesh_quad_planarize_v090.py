# SPDX-License-Identifier: GPL-3.0-or-later
"""Flatten one warped native Blender quad without changing its topology.

Preview computes the plane and vertex positions but never applies an edit.
Confirmation rechecks the complete mesh and uses the existing guarded XR
mesh snapshot transaction, including rollback and normal/area validation.
UVs, loops, weights, materials, object transforms and vertex indices remain.
"""
import math

import bpy
from bpy.props import EnumProperty
from mathutils import Vector

from . import (input_ownership_v080, menus, mesh, mesh_axis_snap_v090,
               mesh_quad_inset_v090, mesh_quad_quality_v090,
               mesh_selection_tools_v086, mesh_weld_preview_v090,
               runtime, v065)

_PAGE = 'XR_QUAD_PLANARIZE_090'
_CONFIRM_PAGE = 'XR_QUAD_PLANARIZE_CONFIRM_090'
_ENTRY = 'XR_QUAD_PLANARIZE_MENU'
_PREVIEW = 'XR_QUAD_PLANARIZE_PREVIEW'
_COMMIT = 'XR_QUAD_PLANARIZE_COMMIT'
_CANCEL = 'XR_QUAD_PLANARIZE_CANCEL'
_LIMITS = {'XR_QUAD_FLAT_FINE': 0.05, 'XR_QUAD_FLAT_WIDE': 0.20}
_MAX_LINKED_FACES = 1000


def _eligible(context):
    obj, bm, face = mesh_quad_inset_v090._eligible(context)
    if any(vertex.hide or not vertex.is_valid for vertex in face.verts):
        raise ValueError('Planarise requires four visible, valid quad corners')
    # A shared vertex also moves adjacent faces. Never silently modify
    # hidden neighbours or an extraordinarily dense local fan.
    neighbours = {linked for vertex in face.verts for linked in vertex.link_faces}
    if (len(neighbours) > _MAX_LINKED_FACES or
            any(linked.hide or not linked.is_valid for linked in neighbours) or
            any(edge.hide for vertex in face.verts for edge in vertex.link_edges)):
        raise ValueError('Quad has hidden or overly dense connected geometry')
    return obj, bm, face


def _projection(face, limit):
    """Return projected local coordinates and maximum move, or refuse."""
    if limit not in _LIMITS:
        raise ValueError('Choose a supported quad planarisation limit')
    points = tuple(vertex.co.copy() for vertex in face.verts)
    if any(not all(math.isfinite(float(v)) for v in point) for point in points):
        raise ValueError('Quad has non-finite coordinates')
    edges = tuple((points[(i + 1) % 4] - points[i]).length for i in range(4))
    shortest = min(edges)
    if shortest <= 1e-9 or face.calc_area() <= 1e-12:
        raise ValueError('Cannot planarise a degenerate quad')
    centre = sum(points, Vector((0.0, 0.0, 0.0))) / 4.0
    offsets = tuple(point - centre for point in points)
    normal = sum((offsets[i].cross(offsets[(i + 1) % 4])
                  for i in range(4)), Vector((0.0, 0.0, 0.0)))
    if normal.length_squared <= (shortest * shortest * 1e-8) ** 2:
        raise ValueError('Quad is crossed, collapsed or has an ambiguous plane')
    normal.normalize()
    if normal.dot(face.normal) <= 0:
        raise ValueError('Quad orientation is inconsistent with its plane')
    movements = tuple(float(offset.dot(normal)) for offset in offsets)
    maximum = max(abs(distance) for distance in movements)
    if maximum <= max(1e-9, shortest * 1e-6):
        raise ValueError('Quad is already planar at modelling precision')
    if maximum > shortest * _LIMITS[limit]:
        raise ValueError('Warp exceeds the chosen 5% or 20% edge safety limit')
    projected = tuple(point - normal * distance
                      for point, distance in zip(points, movements))
    signs = []
    for i in range(4):
        incoming = projected[i] - projected[i - 1]
        outgoing = projected[(i + 1) % 4] - projected[i]
        signed = float(incoming.cross(outgoing).dot(normal))
        if signed <= shortest * shortest * 1e-8:
            raise ValueError('Projection would collapse or reverse a quad corner')
        signs.append(signed)
    return tuple(tuple(float(v) for v in point) for point in projected), maximum


def plan(context, limit='XR_QUAD_FLAT_FINE'):
    obj, bm, face = _eligible(context)
    coordinates, maximum = _projection(face, limit)
    signature = (
        mesh_selection_tools_v086._topology(bm),
        mesh_weld_preview_v090._geometry_stamp(bm),
        mesh_axis_snap_v090._matrix_stamp(obj.matrix_world),
        face.index,
        tuple(vertex.index for vertex in face.verts),
        int(face.material_index), bool(face.smooth),
        mesh_quad_inset_v090._uv_stamp(obj, bm, face),
    )
    return {
        'scene': context.scene.name, 'scene_ptr': context.scene.as_pointer(),
        'layer': context.view_layer.name,
        'obj': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'signature': signature, 'limit': limit,
        'target': coordinates, 'max_move': maximum,
    }


def _verify(context, proposal):
    current = plan(context, proposal['limit'])
    if current != proposal:
        raise ValueError('Quad or connected geometry changed; preview again')
    return _eligible(context)


def _mutate(context, proposal):
    obj, bm, face = _verify(context, proposal)
    neighbours = {linked for vertex in face.verts for linked in vertex.link_faces}
    before = {}
    for linked in neighbours:
        linked.normal_update()
        area = float(linked.calc_area())
        if not math.isfinite(area) or area <= 1e-12:
            raise ValueError('A connected face is already degenerate')
        before[linked] = (area, linked.normal.copy())
        if linked.normal.length_squared <= 1e-12:
            raise ValueError('A connected face has invalid orientation')
    for vertex, coordinates in zip(face.verts, proposal['target']):
        vertex.co = Vector(coordinates)
    # Shared-corner moves can alter adjacent faces; refuse any collapsed
    # neighbour or flipped normal before committing the history record.
    for linked, (area, normal) in before.items():
        linked.normal_update()
        after = float(linked.calc_area())
        if (not math.isfinite(after) or after <= max(1e-12, area * 0.25) or
                linked.normal.dot(normal) <= 0.5):
            raise ValueError('Planarisation distorted or inverted a connected face')
    projected, maximum = _projection_after(face)
    if maximum > 1e-6:
        raise ValueError('Planarised quad remains warped beyond tolerance')
    return obj


def _projection_after(face):
    """Read-only residual warpage relative to the final quad plane."""
    points = tuple(vertex.co.copy() for vertex in face.verts)
    centre = sum(points, Vector((0.0, 0.0, 0.0))) / 4.0
    normal = sum(((points[i] - centre).cross(points[(i + 1) % 4] - centre)
                  for i in range(4)), Vector((0.0, 0.0, 0.0)))
    if normal.length_squared <= 1e-24:
        raise ValueError('Planarised quad has no valid normal')
    normal.normalize()
    residual = max(abs(float((point - centre).dot(normal))) for point in points)
    return normal, residual


def commit(context, proposal, history=None):
    obj, _bm, _face = _verify(context, proposal)
    if history is not None:
        mesh.snapshot_and_push(obj, lambda: _mutate(context, proposal), history)
    else:
        backup = mesh.snapshot(obj)
        try:
            _mutate(context, proposal)
            mesh.update(obj)
        except BaseException:
            try:
                mesh.restore(obj, backup)
            except Exception as exc:
                raise mesh.MeshRollbackFailure(
                    'Quad planarisation rollback failed; review native mesh') from exc
            raise
        finally:
            mesh._dispose_temporary_meshes(backup)
    return proposal['max_move']


class BXR_OT_quad_planarize(bpy.types.Operator):
    bl_idname = 'blender_xr.quad_planarize'
    bl_label = 'Preview and Confirm Native Quad Planarisation'
    bl_description = 'Project one warped quad to its best-fit plane with guarded Undo'
    bl_options = {'REGISTER', 'UNDO'}
    limit: EnumProperty(
        name='Maximum Warp',
        items=(
            ('XR_QUAD_FLAT_FINE', '5% of shortest edge', 'Subtle quad correction'),
            ('XR_QUAD_FLAT_WIDE', '20% of shortest edge', 'Larger, explicitly approved correction'),
        ),
        default='XR_QUAD_FLAT_FINE')
    _proposal = None

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH')

    def invoke(self, context, event):
        self._proposal = None
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Quad Planarise menu in headset')
            return {'CANCELLED'}
        try:
            self._proposal = plan(context, self.limit)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=390)

    def draw(self, context):
        if self._proposal:
            self.layout.label(text='Maximum local corner move {:.6g}'.format(
                self._proposal['max_move']))
            self.layout.label(text='Only four existing vertex coordinates change')
            self.layout.label(text='Adjacent connected faces are also affected')

    def execute(self, context):
        if (runtime.CURRENT is not None or self._proposal is None or
                self.limit != self._proposal['limit']):
            self.report({'WARNING'}, 'Preview the chosen correction again')
            return {'CANCELLED'}
        try:
            moved = commit(context, self._proposal)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self._proposal = None
        self.report({'INFO'}, 'Planarised native quad (max move {:.6g})'.format(moved))
        return {'FINISHED'}


def install_pages():
    parent = mesh_quad_quality_v090._PAGE
    old = tuple(menus.PAGES[parent])
    if not old or old[-1][1] != 'BACK':
        raise ValueError('Quad Quality menu is unavailable')
    if not any(action == _ENTRY for _label, action in old):
        old = old[:-1] + (('PLANARISE', _ENTRY), old[-1])
    if len(old) > 12:
        raise ValueError('Quad Quality menu has no capacity for Planarise')
    menus.PAGES[parent] = old
    menus.PAGES[_PAGE] = (
        ('WARP ≤ 5%', 'XR_QUAD_FLAT_FINE'),
        ('WARP ≤ 20%', 'XR_QUAD_FLAT_WIDE'),
        ('PREVIEW', _PREVIEW), ('BACK', 'BACK'),
    )
    menus.PAGES[_CONFIRM_PAGE] = (
        ('FLATTEN QUAD', _COMMIT), ('KEEP QUAD', _CANCEL), ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'NATIVE QUAD PLANARISE'
    menus.TITLES[_CONFIRM_PAGE] = 'CONFIRM FLATTEN QUAD'
    v065.TOOLTIPS.update({
        _ENTRY: ('Planarise One Warped Quad',
                 'Preview a best-fit-plane correction of four native vertices'),
        _PREVIEW: ('Preview Native Quad Planarisation',
                   'Inspect max movement before changing shared corners'),
        _COMMIT: ('Confirm Native Quad Planarisation',
                  'Move quad corners with guarded native XR mesh Undo'),
        _CANCEL: ('Keep Original Quad', 'Discard preview without changing mesh'),
        'XR_QUAD_FLAT_FINE': ('5% Limit', 'Conservative local quad correction'),
        'XR_QUAD_FLAT_WIDE': ('20% Limit', 'Allow a larger local quad correction'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_quad_planarize_090_patched', False):
        return
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        page = getattr(menu, 'page', None)
        if page == mesh_quad_quality_v090._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before Quad Planarise')
            _eligible(context)
            self._xr_quad_flat_pending = None
            menu.page = _PAGE
            self.status = 'QUAD PLANARISE / CHOOSE LIMIT AND PREVIEW'
            return
        if page == _PAGE:
            if action == 'BACK':
                self._xr_quad_flat_pending = None
                menu.page = mesh_quad_quality_v090._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before Planarise Preview')
            if action in _LIMITS:
                self._xr_quad_flat_limit = action
                self._xr_quad_flat_pending = None
                self.status = 'PLANARISE LIMIT / ' + action.replace('XR_QUAD_FLAT_', '')
                return
            if action == _PREVIEW:
                limit = getattr(self, '_xr_quad_flat_limit', 'XR_QUAD_FLAT_FINE')
                self._xr_quad_flat_pending = plan(context, limit)
                menu.page = _CONFIRM_PAGE
                self.status = 'QUAD PREVIEW / MAX MOVE {:.5g} / CONFIRM?'.format(
                    self._xr_quad_flat_pending['max_move'])
                return
            raise ValueError('Choose planarisation limit, Preview or Back')
        if page == _CONFIRM_PAGE:
            if action in {_CANCEL, 'BACK'}:
                self._xr_quad_flat_pending = None
                menu.page = _PAGE
                self.status = 'QUAD PLANARISE CANCELLED / NO CHANGE'
                return
            if action != _COMMIT:
                raise ValueError('Confirm or cancel native Quad Planarise')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before Quad Planarise')
            pending = getattr(self, '_xr_quad_flat_pending', None)
            if pending is None:
                raise ValueError('Planarise approval expired; preview again')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('XR Undo history required for Quad Planarise')
            moved = commit(context, pending, history)
            self._xr_quad_flat_pending = None
            menu.page = _PAGE
            self._xr_precision_last_ray = None
            self.status = 'QUAD PLANARISED / MOVE {:.5g} / XR UNDO READY'.format(moved)
            return
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_quad_planarize_090_patched = True


CLASSES = (BXR_OT_quad_planarize,)
