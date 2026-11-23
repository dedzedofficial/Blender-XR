# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only Blender UV-island winding and collapsed-polygon diagnostics.

UV mirroring is legitimate. Flag UV faces with an opposite winding to the
area-weighted majority *within their own continuous UV island*, not all
globally negative UV triangles. If an island has equally signed positive and
negative areas, report it as ambiguous rather than guessing artist intent.
Native UV coordinates, seams, topology and shading are never modified.
"""
import math

import bpy

from . import (input_ownership_v080, menus, mesh_selection_tools_v086,
               runtime, selection, selection_quicksets_v090,
               uv_island_inspector_v090, v065)

_PAGE = 'XR_UV_WINDING_AUDIT_090'
_ENTRY = 'XR_UV_WINDING_MENU'
_REPORT = 'XR_UV_WINDING_REPORT'
_SELECT = {
    'XR_UV_WINDING_MIXED': 'DISAGREE',
    'XR_UV_WINDING_COLLAPSED': 'COLLAPSED',
    'XR_UV_WINDING_ALL': 'ALL',
}
_AREA_EPS = 1e-12


def _signed_area(face, layer):
    """Signed polygon UV area in Blender's stored loop order."""
    uv = [tuple(float(v) for v in loop[layer].uv) for loop in face.loops]
    if any(len(coords) != 2 or not all(math.isfinite(v) for v in coords)
           for coords in uv):
        raise ValueError('The active native UV layer contains nonfinite corners')
    if len(uv) < 3:
        return 0.0
    return 0.5 * math.fsum(
        uv[i][0]*uv[(i+1) % len(uv)][1] -
        uv[(i+1) % len(uv)][0]*uv[i][1]
        for i in range(len(uv)))


def inspect(context):
    groups = uv_island_inspector_v090.inspect(context)['islands']
    obj, bm, layer, faces = uv_island_inspector_v090._source(context)
    by_index = {face.index: face for face in faces}
    areas = {face.index: _signed_area(face, layer) for face in faces}
    collapsed = set()
    flipped = set()
    ambiguous = set()
    wholly_mirrored = 0
    mixed_islands = 0
    ambiguous_islands = 0

    for group in groups:
        positive = math.fsum(max(0.0, areas[i]) for i in group)
        negative = math.fsum(max(0.0, -areas[i]) for i in group)
        for i in group:
            if abs(areas[i]) <= _AREA_EPS:
                collapsed.add(i)
        if positive <= _AREA_EPS and negative > _AREA_EPS:
            # An entirely mirrored island is not an error by itself.
            wholly_mirrored += 1
        if positive > _AREA_EPS and negative > _AREA_EPS:
            mixed_islands += 1
            # Equal positive and negative signed area can be an overlapping
            # UV double surface. Do not invent a majority in this case.
            if abs(positive-negative) <= max(_AREA_EPS, (positive+negative)*0.001):
                ambiguous_islands += 1
                ambiguous.update(
                    i for i in group if abs(areas[i]) > _AREA_EPS)
            else:
                majority = 1 if positive > negative else -1
                flipped.update(
                    i for i in group if areas[i]*majority < -_AREA_EPS)

    # Winding disagreements are warnings, not proof of a bad texture layout.
    return {
        'object': obj.name, 'uv_layer': layer.name, 'faces': len(faces),
        'islands': len(groups), 'fully_mirrored_islands': wholly_mirrored,
        'mixed_islands': mixed_islands,
        'ambiguous_islands': ambiguous_islands,
        'DISAGREE': tuple(sorted(flipped | ambiguous)),
        'COLLAPSED': tuple(sorted(collapsed)),
        'ALL': tuple(sorted(flipped | ambiguous | collapsed)),
        'flipped_minorities': len(flipped),
        'ambiguous_faces': len(ambiguous),
    }


def _report(session, context):
    result = inspect(context)
    session.status = (
        'UV WINDING / MIXED {} / NEGATIVE WHOLE {} / COLLAPSED {} / '
        'WARN FACES {}'
    ).format(
        result['mixed_islands'], result['fully_mirrored_islands'],
        len(result['COLLAPSED']), len(result['ALL']))
    return result


def _select(session, context, action):
    if selection.mode(context) != 'FACE':
        raise ValueError('Switch to Face Select Mode to highlight UV winding warnings')
    if getattr(session, 'history', None) is None:
        raise ValueError('XR selection Undo history required for UV winding selection')
    result = inspect(context)
    indices = result[_SELECT[action]]
    count, changed = selection_quicksets_v090.restore_indices(
        session, context, indices, additive=False)
    session.status = 'UV WINDING / {} FACE WARNINGS / {}'.format(
        count, 'XR UNDO READY' if changed else 'UNCHANGED')
    return changed


class BXR_OT_uv_winding_report(bpy.types.Operator):
    bl_idname = 'blender_xr.uv_winding_report'
    bl_label = 'Read-Only Native UV Winding Audit'
    bl_description = 'Inspect mixed UV winding and degenerate UV polygons per island'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH')

    def execute(self, context):
        try:
            result = inspect(context)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'},
                    'UV {} / {} mixed islands / {} whole mirrored / {} collapsed / {} ambiguous'.format(
                        result['uv_layer'], result['mixed_islands'],
                        result['fully_mirrored_islands'],
                        len(result['COLLAPSED']),
                        result['ambiguous_islands']))
        return {'FINISHED'}


class BXR_OT_uv_winding_select(bpy.types.Operator):
    bl_idname = 'blender_xr.uv_winding_select'
    bl_label = 'Select UV Island Winding Warnings'
    bl_description = 'Select Blender faces with mixed or collapsed UV winding'
    bl_options = {'REGISTER', 'UNDO'}
    category: bpy.props.EnumProperty(
        items=(
            ('XR_UV_WINDING_MIXED', 'Mixed Winding',
             'Select faces opposite the island majority or on tied islands'),
            ('XR_UV_WINDING_COLLAPSED', 'Collapsed UVs',
             'Select UV polygons with nearly zero signed area'),
            ('XR_UV_WINDING_ALL', 'All UV Winding Warnings',
             'Select mixed winding and collapsed polygons'),
        ), default='XR_UV_WINDING_ALL')

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and
                    context.mode == 'EDIT_MESH' and selection.mode(context) == 'FACE')

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR UV Winding wrist menu while in VR')
            return {'CANCELLED'}
        try:
            result = inspect(context)
            selected = result[_SELECT[self.category]]
            obj = mesh_selection_tools_v086._editable(context)
            _bm, faces = mesh_selection_tools_v086._current(obj, 'FACE')
            if mesh_selection_tools_v086._selected(faces) == selected:
                self.report({'INFO'}, 'UV winding selection already matches')
                return {'CANCELLED'}
            mesh_selection_tools_v086._set_selection(obj, 'FACE', selected)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, '{} native UV winding warnings selected'.format(
            len(selected)))
        return {'FINISHED'}


def install_pages():
    parent = uv_island_inspector_v090._PAGE
    current = tuple(menus.PAGES[parent])
    if not current or current[-1][1] != 'BACK':
        raise ValueError('Native UV Island menu is unavailable for winding audit')
    if not any(action == _ENTRY for _label, action in current):
        current = current[:-1] + (('WINDING AUDIT', _ENTRY), current[-1])
    if len(current) > 12:
        raise ValueError('Native UV Island menu is full')
    menus.PAGES[parent] = current
    menus.PAGES[_PAGE] = (
        ('REPORT', _REPORT),
        ('MIXED WIND', 'XR_UV_WINDING_MIXED'),
        ('COLLAPSED', 'XR_UV_WINDING_COLLAPSED'),
        ('ALL WARNINGS', 'XR_UV_WINDING_ALL'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'UV ISLAND WINDING'
    v065.TOOLTIPS.update({
        _ENTRY: ('UV Island Winding Audit',
                 'Read mixed and collapsed UV polygons without authoring changes'),
        _REPORT: ('Report UV Winding',
                   'Compare existing native UV winding within each continuous island'),
        'XR_UV_WINDING_MIXED': ('Select Mixed UV Winding',
                   'Highlight minority or tied winding inside UV-continuous islands'),
        'XR_UV_WINDING_COLLAPSED': ('Select Collapsed UV Polygon',
                   'Highlight native face UV polygons with nearly zero area'),
        'XR_UV_WINDING_ALL': ('Select All UV Winding Warnings',
                   'Highlight mixed or ambiguous winding and collapsed UV polygons'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_uv_winding_audit_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == uv_island_inspector_v090._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before UV Winding inspection')
            uv_island_inspector_v090._source(context)
            self.menu.page = _PAGE
            self.status = 'UV WINDING / REPORT, MIXED OR COLLAPSED'
            return
        if page == _PAGE:
            if action == 'BACK':
                self.menu.page = uv_island_inspector_v090._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before UV Winding inspection')
            if action == _REPORT:
                return _report(self, context)
            if action in _SELECT:
                return _select(self, context, action)
            raise ValueError('Choose a UV Winding report or face-warning selection')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_uv_winding_audit_090_patched = True


CLASSES = (BXR_OT_uv_winding_report, BXR_OT_uv_winding_select)
