# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only native UV density/area audit for existing Blender UV islands.

Compare each visible face's 2D UV surface area with its world-space triangle
area. Each existing UV island gets its own median density: this detects
unexpected scaling and collapsed UV polygons without requiring a texture
resolution. Selection uses the established guarded XR native-mesh history;
UV loops, topology, materials and meshes are not modified.
"""
import math
import statistics

import bpy
from mathutils import Vector

from . import (input_ownership_v080, menus, mesh_selection_tools_v086,
               runtime, selection, selection_quicksets_v090,
               uv_island_inspector_v090, v065)

_PAGE = 'XR_UV_DENSITY_AUDIT_090'
_ENTRY = 'XR_UV_DENSITY_MENU'
_REPORT = 'XR_UV_DENSITY_REPORT'
_PRESETS = {
    'XR_UV_DENSITY_FINE': 1.5,
    'XR_UV_DENSITY_NORMAL': 2.0,
    'XR_UV_DENSITY_BROAD': 3.0,
}
_SELECT = {
    'XR_UV_DENSITY_COLLAPSED': 'COLLAPSED',
    'XR_UV_DENSITY_UNEVEN': 'UNEVEN',
    'XR_UV_DENSITY_ALL': 'ALL',
}
_EPS = 1e-12


def _area_uv(face, layer):
    """Absolute shoelace area of the native polygon's existing UV corners."""
    loops = tuple(face.loops)
    points = [tuple(float(x) for x in loop[layer].uv) for loop in loops]
    if any(len(p) != 2 or not all(math.isfinite(v) for v in p)
           for p in points):
        raise ValueError('Native UV polygon has non-finite coordinates')
    if len(points) < 3:
        return 0.0
    area = 0.5 * abs(sum(
        points[i][0] * points[(i+1) % len(points)][1] -
        points[(i+1) % len(points)][0] * points[i][1]
        for i in range(len(points))))
    return area


def _area_world(face, matrix):
    """World-space triangle-fan area, handling non-uniform object scaling."""
    points = [matrix @ vert.co for vert in face.verts]
    if any(not all(math.isfinite(float(c)) for c in p) for p in points):
        raise ValueError('Mesh world-space positions contain invalid numbers')
    if len(points) < 3:
        return 0.0
    reference = points[0]
    area = 0.0
    for i in range(1, len(points)-1):
        area += (points[i] - reference).cross(
            points[i+1] - reference).length * 0.5
    return area


def inspect(context, preset='XR_UV_DENSITY_NORMAL'):
    if preset not in _PRESETS:
        raise ValueError('Choose a supported UV density threshold')
    # Reuse native island detection that treats unmarked UV-coordinate
    # discontinuities as boundaries, rather than trusting seam flags only.
    islands = uv_island_inspector_v090.inspect(context)
    obj, bm, layer, faces = uv_island_inspector_v090._source(context)
    limit = _PRESETS[preset]
    density = {}
    collapsed = set()
    for face in faces:
        area_3d = _area_world(face, obj.matrix_world)
        area_2d = _area_uv(face, layer)
        if (not math.isfinite(area_3d) or not math.isfinite(area_2d) or
                area_3d <= _EPS or area_2d <= _EPS):
            collapsed.add(face.index)
            continue
        value = math.sqrt(area_2d / area_3d)
        if not math.isfinite(value) or value <= _EPS:
            collapsed.add(face.index)
            continue
        density[face.index] = value

    uneven = set()
    checked_islands = 0
    for island in islands['islands']:
        values = [density[index] for index in island if index in density]
        if len(values) < 2:
            continue
        median = statistics.median(values)
        if median <= _EPS:
            continue
        checked_islands += 1
        for index in island:
            value = density.get(index)
            if value is not None and (value > median*limit or
                                      value*limit < median):
                uneven.add(index)
    # Selection/results are deterministic by native face index.
    result = {
        'object': obj.name,
        'layer': layer.name,
        'faces': len(faces), 'islands': len(islands['islands']),
        'islands_compared': checked_islands,
        'COLLAPSED': tuple(sorted(collapsed)),
        'UNEVEN': tuple(sorted(uneven)),
        'ALL': tuple(sorted(collapsed | uneven)),
        'threshold': limit,
        'preset': preset,
    }
    return result


def _preset(session):
    return getattr(session, '_xr_uv_density_preset', 'XR_UV_DENSITY_NORMAL')


def _report(session, context):
    r = inspect(context, _preset(session))
    session.status = (
        'UV DENSITY / {} ISLANDS / COLLAPSED {} / UNEVEN {} / {}x'
    ).format(r['islands'], len(r['COLLAPSED']),
             len(r['UNEVEN']), r['threshold'])
    return r


def _select(session, context, action):
    if selection.mode(context) != 'FACE':
        raise ValueError('Use Face Select Mode to highlight UV density issues')
    if getattr(session, 'history', None) is None:
        raise ValueError('XR native selection history required for UV density inspection')
    r = inspect(context, _preset(session))
    count, changed = selection_quicksets_v090.restore_indices(
        session, context, r[_SELECT[action]], additive=False)
    session.status = 'UV DENSITY / {} FACES SELECTED / {}'.format(
        count, 'XR UNDO READY' if changed else 'UNCHANGED')
    return changed


class BXR_OT_uv_density_report(bpy.types.Operator):
    bl_idname = 'blender_xr.uv_density_report'
    bl_label = 'Read-Only Native UV Density Audit'
    bl_description = 'Report collapsed UV polygons and within-island scale inconsistencies'
    bl_options = {'INTERNAL'}

    preset: bpy.props.EnumProperty(
        items=[(key, '{} ({}x)'.format(key.replace('XR_UV_DENSITY_', '').title(), ratio),
                'Density deviation from existing island median')
               for key, ratio in _PRESETS.items()],
        default='XR_UV_DENSITY_NORMAL')

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH')

    def execute(self, context):
        try:
            r = inspect(context, self.preset)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'},
                    '{} / UV {} / ISLANDS {} / COLLAPSED {} / UNEVEN {} / {}x'.format(
                        r['object'], r['layer'], r['islands'],
                        len(r['COLLAPSED']), len(r['UNEVEN']), r['threshold']))
        return {'FINISHED'}


class BXR_OT_uv_density_select(bpy.types.Operator):
    bl_idname = 'blender_xr.uv_density_select'
    bl_label = 'Select Native UV Density Problems'
    bl_description = 'Select collapsed or inconsistently scaled UV faces'
    bl_options = {'REGISTER', 'UNDO'}

    category: bpy.props.EnumProperty(
        items=[(action, group.title(), 'Select matching native face UV issue')
               for action, group in _SELECT.items()],
        default='XR_UV_DENSITY_ALL')
    preset: bpy.props.EnumProperty(
        items=[(key, key.replace('XR_UV_DENSITY_', '').title(),
                'Allowed native UV scaling variation per island')
               for key in _PRESETS],
        default='XR_UV_DENSITY_NORMAL')

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and
                    context.mode == 'EDIT_MESH' and
                    selection.mode(context) == 'FACE')

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR UV Density wrist menu in headset')
            return {'CANCELLED'}
        try:
            r = inspect(context, self.preset)
            obj = mesh_selection_tools_v086._editable(context)
            bm, items = mesh_selection_tools_v086._current(obj, 'FACE')
            before = mesh_selection_tools_v086._selected(items)
            desired = r[_SELECT[self.category]]
            if before == desired:
                self.report({'INFO'}, 'UV problem selection already matches')
                return {'CANCELLED'}
            mesh_selection_tools_v086._set_selection(obj, 'FACE', desired)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, '{} native UV problem faces selected'.format(
            len(desired)))
        return {'FINISHED'}


def install_pages():
    parent = uv_island_inspector_v090._PAGE
    old = tuple(menus.PAGES[parent])
    if not old or old[-1][1] != 'BACK':
        raise ValueError('Native UV Island menu is unavailable')
    if not any(action == _ENTRY for _label, action in old):
        old = old[:-1] + (('UV DENSITY', _ENTRY), old[-1])
    if len(old) > 12:
        raise ValueError('Native UV Island menu is full')
    menus.PAGES[parent] = old
    menus.PAGES[_PAGE] = (
        ('REPORT', _REPORT),
        ('COLLAPSED', 'XR_UV_DENSITY_COLLAPSED'),
        ('UNEVEN', 'XR_UV_DENSITY_UNEVEN'),
        ('ALL ISSUES', 'XR_UV_DENSITY_ALL'),
        ('FINE 1.5X', 'XR_UV_DENSITY_FINE'),
        ('NORMAL 2X', 'XR_UV_DENSITY_NORMAL'),
        ('BROAD 3X', 'XR_UV_DENSITY_BROAD'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'UV ISLAND DENSITY'
    v065.TOOLTIPS.update({
        _ENTRY: ('Inspect UV Island Density',
                 'Read real UV area and world-space face area without editing native data'),
        _REPORT: ('UV Density Report',
                  'Count collapsed UV polygons and face scale differences per existing island'),
    })
    for action, group in _SELECT.items():
        v065.TOOLTIPS[action] = (
            'Select UV ' + group.title(),
            'Highlight existing Blender faces with a UV density issue')
    for action, value in _PRESETS.items():
        v065.TOOLTIPS[action] = (
            'UV Density Threshold {}x'.format(value),
            'Flag per-face UV densities outside this multiple of island median')


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_uv_density_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == uv_island_inspector_v090._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controller gesture before inspecting UV density')
            uv_island_inspector_v090._source(context)
            self.menu.page = _PAGE
            self.status = 'UV DENSITY / REPORT OR SELECT PROBLEMS'
            return
        if page == _PAGE:
            if action == 'BACK':
                self.menu.page = uv_island_inspector_v090._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before UV inspection')
            if action in _PRESETS:
                self._xr_uv_density_preset = action
                self.status = 'UV DENSITY / THRESHOLD {}X'.format(_PRESETS[action])
                return
            if action == _REPORT:
                return _report(self, context)
            if action in _SELECT:
                return _select(self, context, action)
            raise ValueError('Choose a UV density report, issue or threshold')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_uv_density_090_patched = True


CLASSES = (BXR_OT_uv_density_report, BXR_OT_uv_density_select)
