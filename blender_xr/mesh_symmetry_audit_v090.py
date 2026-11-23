# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only native BMesh symmetry/valence audit for headset avatar modelling.

Find missing local X/Y/Z mirror partners and differences in local vertex
connectivity using a bounded KDTree. No mesh is modified by the audit.
Problem selection uses the same native XR_MESH_SELECTION_086 history as the
existing topology and Select Similar tools.
"""
import math

import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

from . import (input_ownership_v080, menus, mesh_selection_tools_v086,
               mesh_topology_audit_v090, runtime, selection,
               selection_quicksets_v090, v065)

_PAGE = 'XR_SYMMETRY_AUDIT_090'
_ENTRY = 'XR_SYMMETRY_AUDIT_MENU'
_REPORT = 'XR_SYMMETRY_REPORT'
_SELECT_MISSING = 'XR_SYMMETRY_SELECT_MISSING'
_SELECT_VALENCE = 'XR_SYMMETRY_SELECT_VALENCE'
_MAX_VERTICES = 150000
_TOLERANCE = {
    'XR_SYMMETRY_TOL_FINE': 0.0001,
    'XR_SYMMETRY_TOL_MEDIUM': 0.001,
    'XR_SYMMETRY_TOL_BROAD': 0.01,
}
_AXIS = {'XR_SYMMETRY_AXIS_X': 0, 'XR_SYMMETRY_AXIS_Y': 1,
         'XR_SYMMETRY_AXIS_Z': 2}


def _verts(context):
    obj = mesh_selection_tools_v086._editable(context)
    mode = selection.mode(context)
    bm, _items = mesh_selection_tools_v086._current(obj, mode)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    if len(bm.verts) > _MAX_VERTICES:
        raise ValueError('Native mesh symmetry audit supports up to 150,000 vertices')
    visible = tuple(vertex for vertex in bm.verts
                    if vertex.is_valid and not vertex.hide)
    if not visible:
        raise ValueError('No visible native mesh vertices to inspect')
    coords = {}
    valence = {}
    for vertex in visible:
        co = tuple(float(v) for v in vertex.co)
        if not all(math.isfinite(v) for v in co):
            raise ValueError('Mesh contains invalid vertex coordinates')
        coords[vertex.index] = co
        valence[vertex.index] = sum(1 for edge in vertex.link_edges
                                   if edge.is_valid and not edge.hide)
    return obj, coords, valence


def _report(context, axis, tolerance):
    if axis not in (0, 1, 2) or not math.isfinite(tolerance) or not 1e-5 <= tolerance <= 0.1:
        raise ValueError('Select a valid local axis and symmetry tolerance')
    obj, coords, valence = _verts(context)
    ids = tuple(sorted(coords))
    tree = KDTree(len(ids))
    for index in ids:
        tree.insert(coords[index], index)
    tree.balance()
    missing, unequal = [], []
    mirror_pairs = set()
    for index in ids:
        co = list(coords[index])
        co[axis] = -co[axis]
        reflected = Vector(co)
        result = tree.find(reflected)
        if result is None or result[2] > tolerance:
            missing.append(index)
            continue
        partner = result[1]
        # Symmetry in a dense mesh can have ambiguous near-duplicate verts.
        # Only mutual nearest pairs are accepted, otherwise mark both sides
        # for an artist's inspection, rather than guessing geometry mapping.
        inverse = list(coords[partner])
        inverse[axis] = -inverse[axis]
        back = tree.find(Vector(inverse))
        if back is None or back[2] > tolerance or back[1] != index:
            missing.append(index)
            continue
        if valence[index] != valence[partner]:
            unequal.append(index)
        mirror_pairs.add(tuple(sorted((index, partner))))
    matched = len(ids) - len(missing)
    return {
        'object': obj.name, 'total': len(ids),
        'paired': matched, 'missing': tuple(missing),
        'valence': tuple(unequal), 'pairs': len(mirror_pairs),
        'axis': axis, 'tolerance': tolerance,
        'percent': 100.0 * matched / len(ids),
    }


def _settings(session):
    axis = int(getattr(session, '_xr_symmetry_axis', 0))
    tol = float(getattr(session, '_xr_symmetry_tolerance', 0.001))
    return axis, tol


def _inspect(session, context):
    axis, tolerance = _settings(session)
    result = _report(context, axis, tolerance)
    session.status = (
        'SYMMETRY {} / {:.1f}% PAIRED / MISSING {} / VALENCE {} / TOL {:.4f}'
    ).format(
        'XYZ'[axis], result['percent'], len(result['missing']),
        len(result['valence']), tolerance)
    return result


def _select(session, context, action):
    if selection.mode(context) != 'VERT':
        raise ValueError('Switch to Vertex Select Mode to highlight symmetry problems')
    history = getattr(session, 'history', None)
    if history is None:
        raise ValueError('XR history required for selecting native mesh problems')
    report = _inspect(session, context)
    indices = (report['missing'] if action == _SELECT_MISSING
               else report['valence'])
    count, changed = selection_quicksets_v090.restore_indices(
        session, context, indices, additive=False)
    session.status = ('SYMMETRY {} / {} VERTS / {}').format(
        'MISSING' if action == _SELECT_MISSING else 'VALENCE',
        count, 'XR UNDO READY' if changed else 'UNCHANGED')
    return changed


class BXR_OT_mesh_symmetry_audit(bpy.types.Operator):
    bl_idname = 'blender_xr.mesh_symmetry_audit'
    bl_label = 'Read-only Native Mesh Symmetry Audit'
    bl_description = 'Inspect paired positions and vertex valence across a local mirror axis'
    bl_options = {'INTERNAL'}

    axis: bpy.props.EnumProperty(items=(
        ('X', 'Local X', 'Mirror around local X = 0'),
        ('Y', 'Local Y', 'Mirror around local Y = 0'),
        ('Z', 'Local Z', 'Mirror around local Z = 0'),
    ), default='X')
    tolerance: bpy.props.FloatProperty(
        name='Local Tolerance', default=0.001, min=0.00001, max=0.1, precision=5)

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH')

    def execute(self, context):
        try:
            audit = _report(context, 'XYZ'.index(self.axis), self.tolerance)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, '{} / {} {:.1f}% paired / {} missing / {} valence mismatches'.format(
            audit['object'], self.axis, audit['percent'],
            len(audit['missing']), len(audit['valence'])))
        return {'FINISHED'}


def install_pages():
    parent = mesh_topology_audit_v090._PAGE
    existing = tuple(menus.PAGES[parent])
    if not existing or existing[-1][1] != 'BACK':
        raise ValueError('Quad Topology Audit menu is unavailable')
    if not any(action == _ENTRY for _label, action in existing):
        existing = existing[:-1] + (('SYMMETRY', _ENTRY), existing[-1])
    if len(existing) > 12:
        raise ValueError('Quad Topology Audit has no wrist capacity for Symmetry')
    menus.PAGES[parent] = existing
    menus.PAGES[_PAGE] = (
        ('LOCAL X', 'XR_SYMMETRY_AXIS_X'),
        ('LOCAL Y', 'XR_SYMMETRY_AXIS_Y'),
        ('LOCAL Z', 'XR_SYMMETRY_AXIS_Z'),
        ('TOL .0001', 'XR_SYMMETRY_TOL_FINE'),
        ('TOL .001', 'XR_SYMMETRY_TOL_MEDIUM'),
        ('TOL .01', 'XR_SYMMETRY_TOL_BROAD'),
        ('REPORT', _REPORT),
        ('SELECT MISSING', _SELECT_MISSING),
        ('SELECT VALENCE', _SELECT_VALENCE),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'NATIVE MESH SYMMETRY'
    v065.TOOLTIPS.update({
        _ENTRY: ('Local Mesh Symmetry Audit',
            'Inspect native mesh vertex mirror matching without modifying geometry'),
        _REPORT: ('Read Mirrored Vertex Count',
            'Report matched positions, missing partners and edge connectivity mismatches'),
        _SELECT_MISSING: ('Select Missing Mirror Vertices',
            'Select vertices with no unambiguous partner across the local mirror axis'),
        _SELECT_VALENCE: ('Select Mirrored Topology Differences',
            'Select vertices whose mirror partner has a different native edge count'),
    })
    for key, axis in _AXIS.items():
        v065.TOOLTIPS[key] = ('Local Mirror ' + 'XYZ'[axis],
                             'Check mirror symmetry around local coordinate zero')
    for key, tolerance in _TOLERANCE.items():
        v065.TOOLTIPS[key] = (
            'Mirror Tolerance {:.4f}'.format(tolerance),
            'Compare native mesh vertex coordinates within this local distance')


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_native_symmetry_audit_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        page = getattr(menu, 'page', None)
        if page == mesh_topology_audit_v090._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before mesh symmetry audit')
            _verts(context)
            menu.page = _PAGE
            self.status = 'SYMMETRY / CHOOSE LOCAL AXIS AND TOLERANCE'
            return
        if page == _PAGE:
            if action == 'BACK':
                menu.page = mesh_topology_audit_v090._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR controller edits before symmetry inspection')
            if action in _AXIS:
                self._xr_symmetry_axis = _AXIS[action]
                self.status = 'SYMMETRY / LOCAL ' + 'XYZ'[self._xr_symmetry_axis]
                return
            if action in _TOLERANCE:
                self._xr_symmetry_tolerance = _TOLERANCE[action]
                self.status = 'SYMMETRY TOLERANCE / {:.4f}'.format(
                    self._xr_symmetry_tolerance)
                return
            if action == _REPORT:
                return _inspect(self, context)
            if action in {_SELECT_MISSING, _SELECT_VALENCE}:
                return _select(self, context, action)
            raise ValueError('Choose Mirror Report or problem selection')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_native_symmetry_audit_090_patched = True


CLASSES = (BXR_OT_mesh_symmetry_audit,)
