# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only native Blender UV seam and geometric split diagnostics.

UV discontinuities can exist without marked seams, and marked seams can
have continuous UV corners. Report these independently for the active
native UV layer. Selecting suspicious edges uses XR mesh-selection history;
no UVs, seams, edges or other datablocks are changed by inspection.
"""
import bpy

from . import (input_ownership_v080, menus, mesh_selection_tools_v086,
               runtime, selection, selection_quicksets_v090,
               uv_island_inspector_v090, v065)

_PAGE = 'XR_UV_BOUNDARY_AUDIT_090'
_ENTRY = 'XR_UV_BOUNDARY_MENU'
_REPORT = 'XR_UV_BOUNDARY_REPORT'
_SELECT = {
    'XR_UV_BOUNDARY_SPLITS': 'UNMARKED_SPLITS',
    'XR_UV_BOUNDARY_SEAMS': 'CONTINUOUS_SEAMS',
    'XR_UV_BOUNDARY_ALL': 'ALL',
}
_MAX_EDGES = 250000


def inspect(context):
    # The existing island source validates Blender's native edit mesh,
    # active UV layer, face indices and a bounded face count.
    obj, bm, layer, visible_faces = uv_island_inspector_v090._source(context)
    if len(bm.edges) > _MAX_EDGES:
        raise ValueError('UV boundary audit supports at most 250,000 mesh edges')
    face_set = set(visible_faces)
    unmarked = []
    continuous_seams = []
    real_boundaries = 0
    marked_seams = 0
    uv_splits = 0
    checked = 0
    for edge in bm.edges:
        if not edge.is_valid or edge.hide:
            continue
        linked = tuple(face for face in edge.link_faces if face in face_set)
        if len(linked) != 2 or not edge.is_manifold:
            real_boundaries += 1
            continue
        checked += 1
        continuous = uv_island_inspector_v090._continuous(
            linked[0], linked[1], edge, layer)
        if edge.seam:
            marked_seams += 1
            if continuous:
                # A marked seam that still has matching UVs may be an
                # intentional unwrap boundary. Report, never clear it.
                continuous_seams.append(edge.index)
        elif not continuous:
            unmarked.append(edge.index)
        if not continuous:
            uv_splits += 1
    return {
        'object': obj.name, 'uv_layer': layer.name, 'checked': checked,
        'visible_faces': len(visible_faces), 'nonmanifold_borders': real_boundaries,
        'marked_seams': marked_seams, 'uv_splits': uv_splits,
        'UNMARKED_SPLITS': tuple(sorted(unmarked)),
        'CONTINUOUS_SEAMS': tuple(sorted(continuous_seams)),
        'ALL': tuple(sorted(set(unmarked).union(continuous_seams))),
    }


def _report(session, context):
    r = inspect(context)
    session.status = (
        'UV BOUNDARY / SPLITS NO SEAM {} / SEAMS CONTINUOUS {} / '
        'OPEN EDGES {} / UV {}'
    ).format(len(r['UNMARKED_SPLITS']), len(r['CONTINUOUS_SEAMS']),
             r['nonmanifold_borders'], r['uv_layer'])
    return r


def _select(session, context, action):
    if selection.mode(context) != 'EDGE':
        raise ValueError('Switch to Edge Select Mode to highlight UV boundaries')
    if getattr(session, 'history', None) is None:
        raise ValueError('XR Undo history is required for native UV boundary selection')
    result = inspect(context)
    group = _SELECT[action]
    count, changed = selection_quicksets_v090.restore_indices(
        session, context, result[group], additive=False)
    session.status = 'UV BOUNDARY / {} / {} EDGES / {}'.format(
        group.replace('_', ' '), count,
        'XR UNDO READY' if changed else 'UNCHANGED')
    return changed


class BXR_OT_uv_boundary_report(bpy.types.Operator):
    bl_idname = 'blender_xr.uv_boundary_report'
    bl_label = 'Read-Only Native UV Boundary Report'
    bl_description = 'Compare existing UV splits and native mesh seam marks'
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
                    'UV {} / {} unmarked splits / {} continuous seams / {} borders'.format(
                        result['uv_layer'], len(result['UNMARKED_SPLITS']),
                        len(result['CONTINUOUS_SEAMS']),
                        result['nonmanifold_borders']))
        return {'FINISHED'}


class BXR_OT_uv_boundary_select(bpy.types.Operator):
    bl_idname = 'blender_xr.uv_boundary_select'
    bl_label = 'Select UV Boundary Problems'
    bl_description = 'Select native edge seams or unmarked UV discontinuities'
    bl_options = {'REGISTER', 'UNDO'}
    category: bpy.props.EnumProperty(
        items=(
            ('XR_UV_BOUNDARY_SPLITS', 'Unmarked UV Splits',
             'Select edges with UV-coordinate discontinuity but no seam'),
            ('XR_UV_BOUNDARY_SEAMS', 'Continuous Marked Seams',
             'Select native seams whose UV corners are still continuous'),
            ('XR_UV_BOUNDARY_ALL', 'All Boundary Warnings',
             'Select both categories of UV/seam mismatches'),
        ), default='XR_UV_BOUNDARY_ALL')

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and
                    context.mode == 'EDIT_MESH' and selection.mode(context) == 'EDGE')

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the headset UV Boundary wrist menu in VR')
            return {'CANCELLED'}
        try:
            report = inspect(context)
            desired = report[_SELECT[self.category]]
            obj = mesh_selection_tools_v086._editable(context)
            _bm, edges = mesh_selection_tools_v086._current(obj, 'EDGE')
            if mesh_selection_tools_v086._selected(edges) == desired:
                self.report({'INFO'}, 'UV boundary selection is unchanged')
                return {'CANCELLED'}
            mesh_selection_tools_v086._set_selection(obj, 'EDGE', desired)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, '{} native UV boundary edges selected'.format(
            len(desired)))
        return {'FINISHED'}


def install_pages():
    parent = uv_island_inspector_v090._PAGE
    buttons = tuple(menus.PAGES[parent])
    if not buttons or buttons[-1][1] != 'BACK':
        raise ValueError('UV Island menu is missing its Back action')
    if not any(action == _ENTRY for _label, action in buttons):
        buttons = buttons[:-1] + (('UV BOUNDARY', _ENTRY), buttons[-1])
    if len(buttons) > 12:
        raise ValueError('Native UV Island menu is full')
    menus.PAGES[parent] = buttons
    menus.PAGES[_PAGE] = (
        ('REPORT', _REPORT),
        ('SPLIT NO SEAM', 'XR_UV_BOUNDARY_SPLITS'),
        ('SEAM NO SPLIT', 'XR_UV_BOUNDARY_SEAMS'),
        ('ALL WARNINGS', 'XR_UV_BOUNDARY_ALL'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'NATIVE UV SEAM BOUNDARIES'
    v065.TOOLTIPS.update({
        _ENTRY: ('Inspect Native UV Seam Boundaries',
                 'Compare selected UV map discontinuities to marked mesh seams'),
        _REPORT: ('UV Seam and Split Report',
                  'Read count of unmarked UV splits and marked continuous seams'),
        'XR_UV_BOUNDARY_SPLITS': ('Select Unmarked UV Splits',
                  'Highlight native edges where UVs split without a seam mark'),
        'XR_UV_BOUNDARY_SEAMS': ('Select Continuous Marked Seams',
                  'Highlight seams that still have continuous UV corners'),
        'XR_UV_BOUNDARY_ALL': ('Select All UV Boundary Warnings',
                  'Highlight both UV/seam discrepancy categories'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_uv_boundary_audit_090_patched', False):
        return
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == uv_island_inspector_v090._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controller gesture before inspecting UV boundaries')
            uv_island_inspector_v090._source(context)
            self.menu.page = _PAGE
            self.status = 'UV BOUNDARY / REPORT OR SELECT NATIVE EDGE WARNINGS'
            return
        if page == _PAGE:
            if action == 'BACK':
                self.menu.page = uv_island_inspector_v090._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR controllers before UV boundary selection')
            if action == _REPORT:
                return _report(self, context)
            if action in _SELECT:
                return _select(self, context, action)
            raise ValueError('Choose a UV boundary report or edge warning')
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_uv_boundary_audit_090_patched = True


CLASSES = (BXR_OT_uv_boundary_report, BXR_OT_uv_boundary_select)
