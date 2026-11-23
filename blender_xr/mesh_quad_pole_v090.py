# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only native Blender quad vertex-fan topology diagnostics.

Separate ordinary mesh boundaries and quad corners from true interior 3/
5+-way poles, nonmanifold or mixed-face junctions. Selection is native
BMesh vertex selection via the existing XR_MESH_SELECTION_086 Undo history.
No geometry, UVs, materials, weights or mesh datablocks are authored.
"""
import math

import bpy

from . import (input_ownership_v080, menus, mesh_quad_quality_v090,
               mesh_selection_tools_v086, runtime, selection,
               selection_quicksets_v090, v065)

_PAGE = 'XR_QUAD_POLE_AUDIT_090'
_ENTRY = 'XR_QUAD_POLE_MENU'
_REPORT = 'XR_QUAD_POLE_REPORT'
_SELECT = {
    'XR_QUAD_POLE_3': 'THREE_WAY',
    'XR_QUAD_POLE_5': 'FIVE_PLUS',
    'XR_QUAD_POLE_BOUNDARY': 'BOUNDARY_COMPLEX',
    'XR_QUAD_POLE_NONQUAD': 'NONQUAD_NEIGHBOR',
    'XR_QUAD_POLE_NONMANIFOLD': 'NONMANIFOLD',
    'XR_QUAD_POLE_ALL': 'ALL',
}
_MAX_ELEMENTS = 250000


def inspect(context):
    obj = mesh_selection_tools_v086._editable(context)
    bm, _items = mesh_selection_tools_v086._current(
        obj, selection.mode(context))
    if max(len(bm.verts), len(bm.edges), len(bm.faces)) > _MAX_ELEMENTS:
        raise ValueError('Quad Pole Audit supports up to 250,000 elements per mesh domain')
    targets = {key: set() for key in _SELECT.values()}
    regular_interior = regular_boundary = occluded = 0
    visible = 0
    for vert in bm.verts:
        if not vert.is_valid or vert.hide:
            continue
        visible += 1
        if any(not math.isfinite(float(v)) for v in vert.co):
            raise ValueError('Quad Pole Audit found invalid native vertex coordinates')
        edges = tuple(vert.link_edges)
        faces = tuple(vert.link_faces)
        if (any(not e.is_valid or e.hide for e in edges) or
                any(not f.is_valid or f.hide for f in faces)):
            # Hidden neighbours can make a healthy quad fan appear to be a
            # boundary. Do not label it as a problem or permit selection.
            occluded += 1
            continue

        edge_faces = tuple(len(edge.link_faces) for edge in edges)
        if not edges or any(n not in (1, 2) for n in edge_faces):
            targets['NONMANIFOLD'].add(vert.index)
            continue
        boundary_count = sum(n == 1 for n in edge_faces)
        if boundary_count not in (0, 2):
            # More than two boundary edges meeting at one vertex means a
            # pinched/nonmanifold fan, not an intentional smooth boundary.
            targets['NONMANIFOLD'].add(vert.index)
            continue

        if any(len(face.verts) != 4 for face in faces):
            targets['NONQUAD_NEIGHBOR'].add(vert.index)
            continue

        valence = len(edges)
        if boundary_count == 2:
            if len(faces) != valence-1:
                targets['NONMANIFOLD'].add(vert.index)
            elif valence > 3:
                targets['BOUNDARY_COMPLEX'].add(vert.index)
            else:
                # One quad at a corner (valence 2) and two quads along an
                # ordinary boundary (valence 3) are not interior poles.
                regular_boundary += 1
            continue

        # Fully closed all-quad fans: a regular quad grid interior has four
        # incident edges and four incident faces, regardless of curvature.
        if len(faces) != valence:
            targets['NONMANIFOLD'].add(vert.index)
        elif valence == 4:
            regular_interior += 1
        elif valence == 3:
            targets['THREE_WAY'].add(vert.index)
        elif valence >= 5:
            targets['FIVE_PLUS'].add(vert.index)
        else:
            targets['NONMANIFOLD'].add(vert.index)

    all_warnings = set().union(*targets.values())
    targets['ALL'] = all_warnings
    result = {key: tuple(sorted(value)) for key, value in targets.items()}
    result.update({
        'object': obj.name,
        'visible': visible,
        'regular_interior': regular_interior,
        'regular_boundary': regular_boundary,
        'occluded': occluded,
        'warned': len(all_warnings),
        'regular_percent': (100 * (regular_interior+regular_boundary) / visible
                            if visible else 0.0),
    })
    return result


def _report(session, context):
    r = inspect(context)
    session.status = (
        'QUAD FLOW / REGULAR {:.1f}% / 3-POLES {} / 5+-POLES {} / '
        'BOUNDARY {} / NONMANIFOLD {}'
    ).format(
        r['regular_percent'], len(r['THREE_WAY']), len(r['FIVE_PLUS']),
        len(r['BOUNDARY_COMPLEX']), len(r['NONMANIFOLD']))
    return r


def _select(session, context, action):
    if selection.mode(context) != 'VERT':
        raise ValueError('Use Vertex Select Mode to highlight quad-flow poles')
    if getattr(session, 'history', None) is None:
        raise ValueError('Native XR selection history required for Quad Pole Audit')
    r = inspect(context)
    count, changed = selection_quicksets_v090.restore_indices(
        session, context, r[_SELECT[action]], additive=False)
    session.status = 'QUAD FLOW / {} VERTICES / {}'.format(
        count, 'XR UNDO READY' if changed else 'UNCHANGED')
    return changed


class BXR_OT_quad_pole_report(bpy.types.Operator):
    bl_idname = 'blender_xr.quad_pole_report'
    bl_label = 'Read-Only Native Quad Flow and Pole Audit'
    bl_description = 'Distinguish interior quad poles from ordinary boundaries'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH')

    def execute(self, context):
        try:
            r = inspect(context)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'},
                    '{} / regular {:.1f}% / 3-way {} / 5+-way {} / boundary {} / mixed {} / nonmanifold {}'.format(
                        r['object'], r['regular_percent'],
                        len(r['THREE_WAY']), len(r['FIVE_PLUS']),
                        len(r['BOUNDARY_COMPLEX']), len(r['NONQUAD_NEIGHBOR']),
                        len(r['NONMANIFOLD'])))
        return {'FINISHED'}


class BXR_OT_quad_pole_select(bpy.types.Operator):
    bl_idname = 'blender_xr.quad_pole_select'
    bl_label = 'Select Native Quad Flow Warnings'
    bl_description = 'Select irregular quad fan vertices for manual retopology'
    bl_options = {'REGISTER', 'UNDO'}

    category: bpy.props.EnumProperty(
        items=(
            ('XR_QUAD_POLE_3', 'Three-Way Poles',
             'Select interior valence-three all-quad vertices'),
            ('XR_QUAD_POLE_5', 'Five-or-More Poles',
             'Select interior vertices with valence five or more'),
            ('XR_QUAD_POLE_BOUNDARY', 'Complex Boundary Vertices',
             'Select boundary fans with more than three incident edges'),
            ('XR_QUAD_POLE_NONQUAD', 'Mixed Face Fans',
             'Select vertices adjacent to triangles or n-gons'),
            ('XR_QUAD_POLE_NONMANIFOLD', 'Nonmanifold Fans',
             'Select wires, singular or nonmanifold vertex fans'),
            ('XR_QUAD_POLE_ALL', 'All Quad Flow Warnings',
             'Select all flagged native quad-flow vertices'),
        ), default='XR_QUAD_POLE_ALL')

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH'
                    and selection.mode(context) == 'VERT')

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Quad Pole wrist menu in VR')
            return {'CANCELLED'}
        try:
            report = inspect(context)
            indices = report[_SELECT[self.category]]
            obj = mesh_selection_tools_v086._editable(context)
            _bm, verts = mesh_selection_tools_v086._current(obj, 'VERT')
            if mesh_selection_tools_v086._selected(verts) == indices:
                self.report({'INFO'}, 'Quad-flow warning selection is unchanged')
                return {'CANCELLED'}
            mesh_selection_tools_v086._set_selection(obj, 'VERT', indices)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, '{} quad-flow vertices selected'.format(
            len(indices)))
        return {'FINISHED'}


def install_pages():
    parent = mesh_quad_quality_v090._PAGE
    existing = tuple(menus.PAGES[parent])
    if not existing or existing[-1][1] != 'BACK':
        raise ValueError('Quad Quality menu unavailable for native pole inspection')
    if not any(action == _ENTRY for _label, action in existing):
        existing = existing[:-1] + (('QUAD POLES', _ENTRY), existing[-1])
    if len(existing) > 12:
        raise ValueError('Quad Quality menu has no capacity for Pole Audit')
    menus.PAGES[parent] = existing
    menus.PAGES[_PAGE] = (
        ('REPORT', _REPORT),
        ('3-WAY POLES', 'XR_QUAD_POLE_3'),
        ('5+ POLES', 'XR_QUAD_POLE_5'),
        ('BOUNDARIES', 'XR_QUAD_POLE_BOUNDARY'),
        ('MIXED FACES', 'XR_QUAD_POLE_NONQUAD'),
        ('NONMANIFOLD', 'XR_QUAD_POLE_NONMANIFOLD'),
        ('ALL WARNINGS', 'XR_QUAD_POLE_ALL'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'NATIVE QUAD FLOW POLES'
    v065.TOOLTIPS.update({
        _ENTRY: ('Inspect Native Quad Poles',
                 'Distinguish genuine interior quad poles from ordinary boundary corners'),
        _REPORT: ('Read Quad Pole Health',
                  'Inspect interior valence 3/5+, complex boundaries and invalid fans'),
    })
    for action, key in _SELECT.items():
        v065.TOOLTIPS[action] = (
            'Select Quad ' + key.replace('_', ' ').title(),
            'Highlight native quad-flow vertex warnings without changing geometry')


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_quad_pole_audit_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == mesh_quad_quality_v090._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release headset gesture before Quad Pole Audit')
            mesh_selection_tools_v086._editable(context)
            self.menu.page = _PAGE
            self.status = 'QUAD POLES / REPORT OR SELECT IRREGULAR FAN'
            return
        if page == _PAGE:
            if action == 'BACK':
                self.menu.page = mesh_quad_quality_v090._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR controllers before pole inspection')
            if action == _REPORT:
                return _report(self, context)
            if action in _SELECT:
                return _select(self, context, action)
            raise ValueError('Choose a quad pole report or vertex selection')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_quad_pole_audit_090_patched = True


CLASSES = (BXR_OT_quad_pole_report, BXR_OT_quad_pole_select)
