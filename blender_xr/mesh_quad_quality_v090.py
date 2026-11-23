# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only BMesh quad shape audit: lengths, corner angles and warpage.

The score is a geometric heuristic, not an automatic retopology pass.
Selecting poor faces delegates to existing native XR selection history;
mesh topology, UVs, shading, and face positions are never authored here.
"""
import math

import bpy

from . import (input_ownership_v080, menus, mesh_selection_tools_v086,
               mesh_select_similar_v090, runtime, selection,
               selection_quicksets_v090, v065)

_PAGE = 'XR_QUAD_QUALITY_090'
_ENTRY = 'XR_QUAD_QUALITY_MENU'
_REPORT = 'XR_QUAD_QUALITY_REPORT'
_CHOICES = {
    'XR_QUAD_QUALITY_STRETCHED': 'STRETCHED',
    'XR_QUAD_QUALITY_CORNERS': 'CORNERS',
    'XR_QUAD_QUALITY_WARPED': 'WARPED',
    'XR_QUAD_QUALITY_ALL': 'ALL',
}
_THRESHOLDS = {
    # (max edge ratio, maximum deviation from right angles, relative warpage)
    'XR_QUAD_QUALITY_STRICT': (2.0, 20.0, 0.01),
    'XR_QUAD_QUALITY_NORMAL': (3.0, 35.0, 0.03),
    'XR_QUAD_QUALITY_LENIENT': (5.0, 55.0, 0.08),
}
_MAX_FACES = 150000
_EPS = 1e-12


def _mesh(context):
    obj = mesh_selection_tools_v086._editable(context)
    bm, _items = mesh_selection_tools_v086._current(obj, selection.mode(context))
    if len(bm.faces) > _MAX_FACES:
        raise ValueError('Quad quality inspector supports up to 150,000 faces')
    faces = tuple(face for face in bm.faces
                  if face.is_valid and not face.hide and len(face.verts) == 4)
    return obj, faces


def _features(face):
    """Return (edge aspect, angle error, relative warpage) for one quad.

    Invalid/concave geometry returns inf for at least one metric so the face
    is always considered poor. Values are measured in local Blender units
    and therefore do not depend on scene display unit settings.
    """
    points = [vert.co.copy() for vert in face.verts]
    if any(not all(math.isfinite(float(v)) for v in p) for p in points):
        return float('inf'), float('inf'), float('inf')
    lengths = [(points[(i+1) % 4] - points[i]).length for i in range(4)]
    if min(lengths) <= _EPS:
        return float('inf'), float('inf'), float('inf')
    mean = sum(lengths) / 4
    aspect = max(lengths) / min(lengths)
    angles = []
    for i in range(4):
        before = (points[i-1] - points[i]).normalized()
        after = (points[(i+1) % 4] - points[i]).normalized()
        dot = max(-1.0, min(1.0, float(before.dot(after))))
        angles.append(math.degrees(math.acos(dot)))
    angle_error = max(abs(value - 90.0) for value in angles)
    reference = (points[1] - points[0]).cross(points[2] - points[0])
    if reference.length_squared <= _EPS * _EPS:
        return aspect, float('inf'), float('inf')
    reference.normalize()
    bend = []
    for i in range(4):
        incoming = points[i] - points[i-1]
        outgoing = points[(i+1) % 4] - points[i]
        value = float(incoming.cross(outgoing).dot(reference))
        if abs(value) <= _EPS * max(mean * mean, 1.0):
            return aspect, float('inf'), float('inf')
        bend.append(value > 0)
    # A concave or crossed four-sided face needs manual re-topology, not
    # an automatic "quad fix" that guesses where the artist wanted edges.
    if len(set(bend)) != 1:
        angle_error = float('inf')
    warpage = abs(float((points[3] - points[0]).dot(reference))) / mean
    if not all(math.isfinite(v) for v in (aspect, angle_error, warpage)):
        return float('inf'), float('inf'), float('inf')
    return aspect, angle_error, warpage


def inspect(context, preset='XR_QUAD_QUALITY_NORMAL'):
    if preset not in _THRESHOLDS:
        raise ValueError('Select a supported quad-quality threshold')
    obj, faces = _mesh(context)
    ratio_limit, corner_limit, warp_limit = _THRESHOLDS[preset]
    issues = {'STRETCHED': [], 'CORNERS': [], 'WARPED': [], 'ALL': []}
    for face in faces:
        aspect, angle_error, warpage = _features(face)
        problems = (
            aspect > ratio_limit,
            angle_error > corner_limit,
            warpage > warp_limit,
        )
        if any(problems):
            issues['ALL'].append(face.index)
        for key, problem in zip(('STRETCHED', 'CORNERS', 'WARPED'), problems):
            if problem:
                issues[key].append(face.index)
    result = {key: tuple(indices) for key, indices in issues.items()}
    total = len(faces)
    result.update({
        'object': obj.name, 'total': total, 'good': total-len(issues['ALL']),
        'percent': 100.0 * (total-len(issues['ALL'])) / total if total else 0.0,
        'preset': preset,
    })
    return result


def _preset(session):
    return getattr(session, '_xr_quad_quality_preset', 'XR_QUAD_QUALITY_NORMAL')


def _report(session, context):
    r = inspect(context, _preset(session))
    session.status = (
        'QUAD QUALITY {:.1f}% / GOOD {} / STRETCH {} / CORNERS {} / WARP {}'
    ).format(r['percent'], r['good'],
             len(r['STRETCHED']), len(r['CORNERS']), len(r['WARPED']))
    return r


def _select(session, context, action):
    if selection.mode(context) != 'FACE':
        raise ValueError('Choose Face Select Mode to highlight poor quads')
    if getattr(session, 'history', None) is None:
        raise ValueError('XR Undo history required before selecting quad problems')
    category = _CHOICES[action]
    r = inspect(context, _preset(session))
    count, changed = selection_quicksets_v090.restore_indices(
        session, context, r[category], additive=False)
    session.status = 'QUAD QUALITY / {} FACES {} / {}'.format(
        count, category, 'XR UNDO READY' if changed else 'UNCHANGED')
    return changed


class BXR_OT_quad_quality_report(bpy.types.Operator):
    bl_idname = 'blender_xr.quad_quality_report'
    bl_label = 'Read-Only Native Quad Quality Report'
    bl_description = 'Report warped, stretched or irregular native quads'
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
        self.report({'INFO'}, ('{} / {:.1f}% acceptable quads / {} stretched / '
                               '{} corners / {} warped').format(
            r['object'], r['percent'], len(r['STRETCHED']),
            len(r['CORNERS']), len(r['WARPED'])))
        return {'FINISHED'}


class BXR_OT_quad_quality_select(bpy.types.Operator):
    bl_idname = 'blender_xr.quad_quality_select'
    bl_label = 'Select Low-Quality Native Quads'
    bl_description = 'Select existing native Blender quad faces by geometric quality'
    bl_options = {'REGISTER', 'UNDO'}
    category: bpy.props.EnumProperty(
        items=[(name, label.title(), 'Select the corresponding quad issue')
               for name, label in _CHOICES.items()],
        default='XR_QUAD_QUALITY_ALL')
    preset: bpy.props.EnumProperty(
        items=[(key, key.replace('XR_QUAD_QUALITY_', '').title(),
                'Choose geometric quad-quality tolerances')
               for key in _THRESHOLDS],
        default='XR_QUAD_QUALITY_NORMAL')

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH'
                    and selection.mode(context) == 'FACE')

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Quad Quality wrist menu in VR')
            return {'CANCELLED'}
        try:
            r = inspect(context, self.preset)
            obj = mesh_selection_tools_v086._editable(context)
            mesh_selection_tools_v086._set_selection(
                obj, 'FACE', r[_CHOICES[self.category]])
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, '{} poor quads selected'.format(
            len(r[_CHOICES[self.category]])))
        return {'FINISHED'}


def install_pages():
    parent = mesh_select_similar_v090._DIAGNOSTICS
    original = tuple(menus.PAGES[parent])
    if not original or original[-1][1] != 'BACK':
        raise ValueError('Mesh Diagnostics page is unavailable')
    if not any(action == _ENTRY for _label, action in original):
        original = original[:-1] + (('QUAD QUALITY', _ENTRY), original[-1])
    if len(original) > 12:
        raise ValueError('Mesh Diagnostics menu has no capacity for quad quality')
    menus.PAGES[parent] = original
    menus.PAGES[_PAGE] = (
        ('REPORT', _REPORT),
        ('STRETCHED', 'XR_QUAD_QUALITY_STRETCHED'),
        ('CORNERS', 'XR_QUAD_QUALITY_CORNERS'),
        ('WARPED', 'XR_QUAD_QUALITY_WARPED'),
        ('ALL POOR', 'XR_QUAD_QUALITY_ALL'),
        ('STRICT', 'XR_QUAD_QUALITY_STRICT'),
        ('STANDARD', 'XR_QUAD_QUALITY_NORMAL'),
        ('LENIENT', 'XR_QUAD_QUALITY_LENIENT'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'QUAD SHAPE QUALITY'
    v065.TOOLTIPS.update({
        _ENTRY: ('Native Quad Shape Quality',
                 'Inspect bad corner angles, stretched edges and nonplanarity'),
        _REPORT: ('Read Quad Shape Quality',
                  'Report geometric quality heuristics without changing Blender mesh'),
    })
    for action, key in _CHOICES.items():
        v065.TOOLTIPS[action] = (
            'Select ' + key.title() + ' Quads',
            'Highlight poor native quad faces without changing their topology')
    for key, (ratio, angle, warp) in _THRESHOLDS.items():
        v065.TOOLTIPS[key] = (
            'Quad Quality ' + key.replace('XR_QUAD_QUALITY_', '').title(),
            'Edge ratio {:.1f}; corner deviation {:.0f} degrees; warpage {:.0f}%'.format(
                ratio, angle, warp*100))


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_quad_quality_090_patched', False):
        return
    install_pages()
    prior_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        page = getattr(menu, 'page', None)
        if page == mesh_select_similar_v090._DIAGNOSTICS and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controller gesture before quad inspection')
            _mesh(context)
            menu.page = _PAGE
            self.status = 'QUAD QUALITY / REPORT, SELECT OR CHOOSE THRESHOLD'
            return
        if page == _PAGE:
            if action == 'BACK':
                menu.page = mesh_select_similar_v090._DIAGNOSTICS
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR editing gesture before quad selection')
            if action in _THRESHOLDS:
                self._xr_quad_quality_preset = action
                self.status = 'QUAD QUALITY / ' + action.replace(
                    'XR_QUAD_QUALITY_', '')
                return
            if action == _REPORT:
                return _report(self, context)
            if action in _CHOICES:
                return _select(self, context, action)
            raise ValueError('Choose a native quad issue or quality threshold')
        return prior_command(self, context, action)

    Runtime.command = command
    Runtime._xr_quad_quality_090_patched = True


CLASSES = (BXR_OT_quad_quality_report, BXR_OT_quad_quality_select)
