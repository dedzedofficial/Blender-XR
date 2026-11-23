# SPDX-License-Identifier: GPL-3.0-or-later
"""Preview and confirm one native Blender quad as a 2x2 quad grid.

Only a single planar convex quad whose four edges are unseamed, smooth and
true mesh boundaries is supported. This deliberately excludes shared
perimeter edges, because their subdivision could affect neighbouring faces.
BMesh subdivide_edges remains native and is guarded by one mesh XR snapshot.
"""
import math

import bpy
import bmesh

from . import (input_ownership_v080, menus, mesh, mesh_axis_snap_v090,
               mesh_quad_inset_v090, mesh_selection_tools_v086,
               mesh_select_similar_v090, mesh_weld_preview_v090,
               runtime, v065)

_PAGE = 'XR_QUAD_GRID_090'
_CONFIRM_PAGE = 'XR_QUAD_GRID_CONFIRM_090'
_ENTRY = 'XR_QUAD_GRID_MENU'
_PREVIEW = 'XR_QUAD_GRID_PREVIEW'
_COMMIT = 'XR_QUAD_GRID_COMMIT'
_CANCEL = 'XR_QUAD_GRID_CANCEL'
_MAX_FACES = 150000


def _source(context):
    obj, bm, face = mesh_quad_inset_v090._eligible(context)
    if len(bm.faces) > _MAX_FACES:
        raise ValueError('Native Quad Grid supports at most 150,000 mesh faces')
    mesh_quad_inset_v090._measure(face)
    edges = tuple(face.edges)
    if len(edges) != 4:
        raise ValueError('Quad Grid requires exactly four native perimeter edges')
    if any(not edge.is_valid or edge.hide or len(edge.link_faces) != 1 or
           edge.link_faces[0] is not face or edge.seam or not edge.smooth
           for edge in edges):
        raise ValueError('All four perimeter edges must be visible, smooth and unseamed boundaries')
    return obj, bm, face, edges


def plan(context):
    obj, bm, face, edges = _source(context)
    if not math.isfinite(float(face.calc_area())) or face.calc_area() <= 1e-12:
        raise ValueError('Selected native quad has invalid area')
    signature = (
        mesh_selection_tools_v086._topology(bm),
        mesh_weld_preview_v090._geometry_stamp(bm),
        mesh_axis_snap_v090._matrix_stamp(obj.matrix_world),
        face.index, tuple(vertex.index for vertex in face.verts),
        tuple((edge.index, tuple(v.index for v in edge.verts),
               bool(edge.seam), bool(edge.smooth))
              for edge in edges),
        int(face.material_index), bool(face.smooth),
        mesh_quad_inset_v090._uv_stamp(obj, bm, face),
        float(face.calc_area()),
    )
    return {
        'scene': context.scene.name, 'scene_ptr': context.scene.as_pointer(),
        'layer': context.view_layer.name,
        'obj': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'signature': signature,
        'faces': len(bm.faces), 'edges': len(bm.edges),
        'verts': len(bm.verts), 'uv_maps': len(obj.data.uv_layers),
        'material': int(face.material_index), 'smooth': bool(face.smooth),
    }


def _verify(context, proposal):
    fresh = plan(context)
    if fresh != proposal:
        raise ValueError('Quad perimeter or native mesh changed since grid preview')
    return _source(context)


def _mutate(context, proposal):
    obj, bm, face, edges = _verify(context, proposal)
    original_corners = set(face.verts)
    source_area = float(face.calc_area())
    old_verts = set(bm.verts)
    # Blender's native grid fill splits every boundary edge exactly once,
    # inserts one centre vertex and four quad faces; no arbitrary smoothing.
    bmesh.ops.subdivide_edges(
        bm, edges=list(edges), cuts=1, smooth=0.0, fractal=0.0,
        quad_corner_type='STRAIGHT_CUT',
        use_grid_fill=True, use_only_quads=True)
    new_verts = set(bm.verts).difference(old_verts)
    if (len(bm.faces) != proposal['faces'] + 3 or
            len(bm.verts) != proposal['verts'] + 5 or
            len(bm.edges) != proposal['edges'] + 8 or
            len(new_verts) != 5 or
            not all(vertex.is_valid for vertex in original_corners)):
        raise ValueError('Blender did not create the expected 2x2 quad grid')
    patch = tuple(face for face in bm.faces
                  if face.is_valid and any(vert in new_verts for vert in face.verts))
    if len(patch) != 4:
        raise ValueError('Blender subdivide generated unexpected adjacent faces')
    areas = []
    for quad in patch:
        area = float(quad.calc_area())
        if (len(quad.verts) != 4 or
                len(set(quad.verts).intersection(original_corners)) != 1 or
                not math.isfinite(area) or area <= 1e-12):
            raise ValueError('Native grid contains a triangle, degenerate or overlapping quad')
        quad.material_index = proposal['material']
        quad.smooth = proposal['smooth']
        areas.append(area)
    if abs(sum(areas) - source_area) > max(1e-8, source_area * 0.01):
        raise ValueError('Native quad grid changed the source surface area')
    for layer in obj.data.uv_layers:
        uv = bm.loops.layers.uv.get(layer.name)
        if uv is None:
            raise ValueError('Blender did not preserve the native UV layer')
        for quad in patch:
            for loop in quad.loops:
                if not all(math.isfinite(float(v)) for v in loop[uv].uv):
                    raise ValueError('New quad UV loops contain invalid coordinates')
    return obj


def commit(context, proposal, history=None):
    obj, _bm, _face, _edges = _verify(context, proposal)
    if history is not None:
        mesh.snapshot_and_push(obj, lambda: _mutate(context, proposal), history)
    else:
        old = mesh.snapshot(obj)
        try:
            _mutate(context, proposal)
            mesh.update(obj)
        except Exception:
            mesh.restore(obj, old)
            raise
        finally:
            if bpy.data.meshes.get(old.name) == old:
                bpy.data.meshes.remove(old)
    return proposal['faces'] + 3


class BXR_OT_quad_grid(bpy.types.Operator):
    bl_idname = 'blender_xr.quad_grid'
    bl_label = 'Preview and Confirm Native 2x2 Quad Grid'
    bl_description = 'Subdivide one isolated boundary quad into four native quads'
    bl_options = {'REGISTER', 'UNDO'}
    _proposal = None

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH')

    def invoke(self, context, event):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use XR Quad Grid wrist preview while in headset')
            return {'CANCELLED'}
        try:
            self._proposal = plan(context)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=390)

    def draw(self, context):
        p = self._proposal
        if p:
            self.layout.label(text='Selected single boundary quad -> four quads')
            self.layout.label(text='Native faces: {} -> {}'.format(
                p['faces'], p['faces'] + 3))
            if p['uv_maps']:
                self.layout.label(text='Inspect Blender-interpolated UV loops',
                                  icon='INFO')
        self.layout.label(text='No neighbouring perimeter faces are permitted')

    def execute(self, context):
        if runtime.CURRENT is not None or self._proposal is None:
            self.report({'WARNING'}, 'Preview a new isolated quad first')
            return {'CANCELLED'}
        try:
            total = commit(context, self._proposal)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Native quad grid created / {} faces total'.format(total))
        return {'FINISHED'}


def install_pages():
    parent = mesh_select_similar_v090._DIAGNOSTICS
    buttons = tuple(menus.PAGES[parent])
    if not buttons or buttons[-1][1] != 'BACK':
        raise ValueError('Quad Grid needs Mesh Diagnostics menu')
    if not any(action == _ENTRY for _label, action in buttons):
        buttons = buttons[:-1] + (('QUAD GRID', _ENTRY), buttons[-1])
    if len(buttons) > 12:
        raise ValueError('Mesh Diagnostics is full; cannot add Quad Grid')
    menus.PAGES[parent] = buttons
    menus.PAGES[_PAGE] = (('PREVIEW GRID', _PREVIEW), ('BACK', 'BACK'))
    menus.PAGES[_CONFIRM_PAGE] = (
        ('MAKE 4 QUADS', _COMMIT),
        ('KEEP QUAD', _CANCEL),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'SINGLE QUAD 2X2 GRID'
    menus.TITLES[_CONFIRM_PAGE] = 'CONFIRM FOUR QUADS'
    v065.TOOLTIPS.update({
        _ENTRY: ('Create Native Quad Grid',
                 'Subdivide one isolated boundary quad into four native quads'),
        _PREVIEW: ('Preview 2x2 Grid',
                   'Validate four native boundary edges and unchanged geometry'),
        _COMMIT: ('Confirm Four Native Quads',
                  'Make four equal-grid quads in one XR mesh Undo transaction'),
        _CANCEL: ('Keep Original Quad',
                  'Cancel without changing the native Blender mesh'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_quad_grid_090_patched', False):
        return
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == mesh_select_similar_v090._DIAGNOSTICS and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before Quad Grid preview')
            _source(context)
            self._xr_quad_grid_pending = None
            self.menu.page = _PAGE
            self.status = 'QUAD GRID / ONE ISOLATED QUAD / PREVIEW'
            return
        if page == _PAGE:
            if action == 'BACK':
                self._xr_quad_grid_pending = None
                self.menu.page = mesh_select_similar_v090._DIAGNOSTICS
                return
            if action != _PREVIEW:
                raise ValueError('Preview a single boundary quad before approval')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before Quad Grid preview')
            proposal = plan(context)
            self._xr_quad_grid_pending = proposal
            self.menu.page = _CONFIRM_PAGE
            self.status = 'GRID PREVIEW / 1 QUAD TO 4 / CONFIRM OR CANCEL'
            return
        if page == _CONFIRM_PAGE:
            if action in {_CANCEL, 'BACK'}:
                self._xr_quad_grid_pending = None
                self.menu.page = _PAGE
                self.status = 'QUAD GRID CANCELLED / NO DATA CHANGED'
                return
            if action != _COMMIT:
                raise ValueError('Confirm or cancel native quad grid')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before Quad Grid commit')
            proposal = getattr(self, '_xr_quad_grid_pending', None)
            if proposal is None:
                raise ValueError('Quad grid approval expired; preview again')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('XR history is required before making quads')
            count = commit(context, proposal, history)
            self._xr_quad_grid_pending = None
            self.menu.page = _PAGE
            self._xr_precision_last_ray = None
            self.status = '2X2 QUAD GRID / {} TOTAL FACES / XR UNDO READY'.format(count)
            return
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_quad_grid_090_patched = True


CLASSES = (BXR_OT_quad_grid,)
