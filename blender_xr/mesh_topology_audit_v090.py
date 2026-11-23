# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only quad/topology audit and guarded selection of mesh repair targets.

Reports native BMesh face composition and vertex connectivity. Selecting
problem geometry changes only the current edit-mode selection through the
existing XR_MESH_SELECTION_086 undo path. No automatic retopology, delete,
dissolve, normals operation or geometry mutation is performed.
"""
import math

import bpy

from . import (input_ownership_v080, menus, mesh_selection_tools_v086,
               mesh_select_similar_v090, runtime, selection,
               selection_quicksets_v090, v065)

_PAGE = 'XR_TOPO_AUDIT_090'
_ENTRY = 'XR_TOPO_AUDIT_MENU'
_REPORT = 'XR_TOPO_REPORT'
_ACTIONS = {
    'XR_TOPO_SELECT_NONQUADS': ('FACE', 'NONQUADS'),
    'XR_TOPO_SELECT_TRIANGLES': ('FACE', 'TRIANGLES'),
    'XR_TOPO_SELECT_NGONS': ('FACE', 'NGONS'),
    'XR_TOPO_SELECT_ZERO_AREA': ('FACE', 'DEGENERATE'),
    'XR_TOPO_SELECT_POLES': ('VERT', 'POLES'),
    'XR_TOPO_SELECT_LOOSE': ('VERT', 'LOOSE'),
}
_MAX_ELEMENTS = 250000
_ZERO_AREA = 1e-12


def _mesh(context):
    obj = mesh_selection_tools_v086._editable(context)
    bm, _items = mesh_selection_tools_v086._current(
        obj, selection.mode(context))
    if max(len(bm.verts), len(bm.edges), len(bm.faces)) > _MAX_ELEMENTS:
        raise ValueError('Topology audit supports 250,000 elements per mesh domain')
    return obj, bm


def _is_pole(vert):
    edges = tuple(edge for edge in vert.link_edges if edge.is_valid
                  and not edge.hide)
    if not edges or any(not edge.is_manifold for edge in edges):
        return False
    # Only interior, manifold vertices count as quad-flow poles; a
    # three-edge vertex on a mesh boundary is not by itself a pole.
    return len(edges) != 4


def _report(context):
    obj, bm = _mesh(context)
    faces = tuple(face for face in bm.faces if face.is_valid and not face.hide)
    triangles = quads = ngons = degenerate = 0
    for face in faces:
        sides = len(face.verts)
        triangles += sides == 3
        quads += sides == 4
        ngons += sides > 4
        area = float(face.calc_area())
        if not math.isfinite(area) or area <= _ZERO_AREA:
            degenerate += 1
    nonmanifold = sum(1 for edge in bm.edges
                      if edge.is_valid and not edge.hide and not edge.is_manifold)
    poles = sum(1 for vert in bm.verts if vert.is_valid and not vert.hide
                and _is_pole(vert))
    loose = sum(1 for vert in bm.verts if vert.is_valid and not vert.hide
                and len(vert.link_edges) == 0)
    percent = 100.0 * quads / len(faces) if faces else 0.0
    return {
        'obj': obj.name, 'faces': len(faces), 'quads': quads,
        'quad_percent': percent, 'triangles': triangles, 'ngons': ngons,
        'degenerate': degenerate, 'nonmanifold': nonmanifold,
        'poles': poles, 'loose': loose,
    }


def _targets(context, action):
    if action not in _ACTIONS:
        raise ValueError('Unknown topology target selection')
    obj, bm = _mesh(context)
    required, kind = _ACTIONS[action]
    if selection.mode(context) != required:
        raise ValueError('Switch to {} Select Mode for {} audit'.format(
            required, kind))
    _bm, items = mesh_selection_tools_v086._current(obj, required)
    visible = (item for item in items if item.is_valid and not item.hide)
    if kind == 'NONQUADS':
        return tuple(face.index for face in visible
                     if len(face.verts) != 4)
    if kind == 'TRIANGLES':
        return tuple(face.index for face in visible
                     if len(face.verts) == 3)
    if kind == 'NGONS':
        return tuple(face.index for face in visible
                     if len(face.verts) > 4)
    if kind == 'DEGENERATE':
        return tuple(face.index for face in visible
                     if not math.isfinite(float(face.calc_area())) or
                     float(face.calc_area()) <= _ZERO_AREA)
    if kind == 'POLES':
        return tuple(vert.index for vert in visible if _is_pole(vert))
    if kind == 'LOOSE':
        return tuple(vert.index for vert in visible
                     if len(vert.link_edges) == 0)
    raise ValueError('Unsupported native topology target')


def _selection(session, context, action):
    if input_ownership_v080.is_editing(session):
        raise ValueError('Release XR controllers before auditing topology')
    if getattr(session, 'history', None) is None:
        raise ValueError('XR Undo history is required for topology selection')
    indices = _targets(context, action)
    count, changed = selection_quicksets_v090.restore_indices(
        session, context, indices, additive=False)
    session.status = 'TOPOLOGY / {} / {} TARGETS / {}'.format(
        _ACTIONS[action][1], count,
        'XR UNDO READY' if changed else 'UNCHANGED')
    return changed


class BXR_OT_topology_audit(bpy.types.Operator):
    bl_idname = 'blender_xr.topology_audit'
    bl_label = 'Read-Only Native Quad Topology Audit'
    bl_description = 'Count native quads, triangles, ngons and mesh connectivity problems'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and context.mode == 'EDIT_MESH' and obj.type == 'MESH')

    def execute(self, context):
        try:
            data = _report(context)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        result = ('{} / QUADS {:.1f}% ({}) / TRI {} / NGON {} / '
                  'ZERO {} / NONMANIFOLD {} / POLES {} / LOOSE {}').format(
            data['obj'], data['quad_percent'], data['quads'],
            data['triangles'], data['ngons'], data['degenerate'],
            data['nonmanifold'], data['poles'], data['loose'])
        self.report({'INFO'}, result)
        return {'FINISHED'}


class BXR_OT_topology_select(bpy.types.Operator):
    bl_idname = 'blender_xr.topology_select'
    bl_label = 'Select Native Topology Audit Problems'
    bl_description = 'Select native edit mesh problem elements without changing geometry'
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(
        items=[(action, label.title().replace('_', ' '),
                'Select corresponding native mesh elements')
               for action, (_mode, label) in _ACTIONS.items()],
        default='XR_TOPO_SELECT_NONQUADS')

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and context.mode == 'EDIT_MESH' and obj.type == 'MESH')

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Topology wrist menu during VR')
            return {'CANCELLED'}
        try:
            indices = _targets(context, self.action)
            obj = mesh_selection_tools_v086._editable(context)
            mode = selection.mode(context)
            _bm, items = mesh_selection_tools_v086._current(obj, mode)
            before = mesh_selection_tools_v086._selected(items)
            if tuple(sorted(indices)) == before:
                self.report({'INFO'}, 'Target topology selection already matches')
                return {'CANCELLED'}
            mesh_selection_tools_v086._set_selection(obj, mode, indices)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, '{} {} audit elements selected'.format(
            len(indices), _ACTIONS[self.action][1]))
        return {'FINISHED'}


def install_pages():
    parent = mesh_select_similar_v090._DIAGNOSTICS
    existing = tuple(menus.PAGES[parent])
    if not existing or existing[-1][1] != 'BACK':
        raise ValueError('Native Mesh Diagnostics page is unavailable')
    if not any(action == _ENTRY for _label, action in existing):
        existing = existing[:-1] + (('TOPOLOGY', _ENTRY), existing[-1])
    if len(existing) > 12:
        raise ValueError('Mesh Diagnostics cannot hold the quad audit')
    menus.PAGES[parent] = existing
    menus.PAGES[_PAGE] = (
        ('QUAD REPORT', _REPORT),
        ('NON-QUADS', 'XR_TOPO_SELECT_NONQUADS'),
        ('TRIANGLES', 'XR_TOPO_SELECT_TRIANGLES'),
        ('NGONS', 'XR_TOPO_SELECT_NGONS'),
        ('ZERO AREA', 'XR_TOPO_SELECT_ZERO_AREA'),
        ('VERT POLES', 'XR_TOPO_SELECT_POLES'),
        ('LOOSE VERTS', 'XR_TOPO_SELECT_LOOSE'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'QUAD TOPOLOGY AUDIT'
    v065.TOOLTIPS.update({
        _ENTRY: ('Read-Only Topology Audit',
                 'Inspect quad percentage, non-manifold and degenerate geometry'),
        _REPORT: ('Report Quad and Mesh Health',
                  'Read native triangle/quad/ngon counts, poles and non-manifold edges'),
    })
    for action, (_mode, name) in _ACTIONS.items():
        v065.TOOLTIPS[action] = (
            'Select ' + name.title(),
            'Highlight native Blender topology targets; preserve all mesh coordinates')


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_topology_audit_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        page = getattr(menu, 'page', None)
        if action == _ENTRY and page == mesh_select_similar_v090._DIAGNOSTICS:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR controllers before topology inspection')
            _mesh(context)
            menu.page = _PAGE
            self.status = 'TOPOLOGY / REPORT QUADS OR SELECT PROBLEMS'
            return
        if page == _PAGE:
            if action == 'BACK':
                menu.page = mesh_select_similar_v090._DIAGNOSTICS
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controller gesture before topology report')
            if action == _REPORT:
                data = _report(context)
                self.status = (
                    'QUADS {:.1f}% / TRI {} / NGON {} / ZERO {} / '
                    'NONMANIFOLD {} / POLES {} / LOOSE {}').format(
                    data['quad_percent'], data['triangles'],
                    data['ngons'], data['degenerate'],
                    data['nonmanifold'], data['poles'], data['loose'])
                return
            if action in _ACTIONS:
                return _selection(self, context, action)
            raise ValueError('Choose Quad Report or a native mesh problem')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_topology_audit_090_patched = True


CLASSES = (BXR_OT_topology_audit, BXR_OT_topology_select)
