# SPDX-License-Identifier: GPL-3.0-or-later
"""Guarded native UV-island rotation and U/V alignment for Blender XR.

A single active selected face chooses its continuous UV island. All source
loops are read-only until a second explicit confirmation. Preserve native UV
density and winding by applying one rigid 2D rotation only to the active UV
layer. No Blender mesh geometry, seams, modifiers, or other UV maps change.
"""
import math

import bpy
from mathutils import Vector

from . import (input_ownership_v080, menus, mesh, mesh_axis_snap_v090,
               mesh_selection_tools_v086, mesh_weld_preview_v090,
               runtime, selection, uv_island_inspector_v090,
               uv_island_match_v090, v065)

_PAGE = 'XR_UV_ORIENT_090'
_CONFIRM_PAGE = 'XR_UV_ORIENT_CONFIRM_090'
_ENTRY = 'XR_UV_ORIENT_MENU'
_PREVIEW = 'XR_UV_ORIENT_PREVIEW'
_APPLY = 'XR_UV_ORIENT_APPLY'
_CANCEL = 'XR_UV_ORIENT_CANCEL'
_CHOICES = {
    'XR_UV_ORIENT_CW': 'CW',
    'XR_UV_ORIENT_CCW': 'CCW',
    'XR_UV_ORIENT_HALF': 'HALF',
    'XR_UV_ORIENT_ALIGN_U': 'ALIGN_U',
    'XR_UV_ORIENT_ALIGN_V': 'ALIGN_V',
    'XR_UV_ORIENT_FLIP_U': 'FLIP_U',
    'XR_UV_ORIENT_FLIP_V': 'FLIP_V',
}
_MAX_TARGET_FACES = 15000
_EPS = 1e-10


def _source(context):
    if selection.mode(context) != 'FACE':
        raise ValueError('Use Face Select Mode to choose a native UV island')
    obj, bm, layer, visible_faces = uv_island_inspector_v090._source(context)
    if (obj.library or obj.override_library or obj.data.library or
            obj.data.override_library or obj.data.users != 1 or
            obj.data.shape_keys is not None):
        raise ValueError('UV alignment needs a local single-user mesh without shape keys')
    chosen = [face for face in visible_faces if face.select]
    face = bm.faces.active
    if (len(chosen) != 1 or face is None or face is not chosen[0] or
            not face.is_valid or face.hide):
        raise ValueError('Select exactly one active visible face inside a UV island')
    islands = uv_island_inspector_v090.inspect(context)
    ids = islands['islands'][islands['by_face'][face.index]]
    if not 1 <= len(ids) <= _MAX_TARGET_FACES:
        raise ValueError('UV alignment supports islands of 1 to 15,000 faces')
    face_lookup = {item.index: item for item in visible_faces}
    uv_source = uv_island_match_v090._island_coords(ids, face_lookup, layer)
    if not uv_source or any(not all(math.isfinite(v) for v in pair)
                            for pair in uv_source):
        raise ValueError('Selected island has invalid native UV corners')
    return obj, bm, layer, face, ids, face_lookup, islands, uv_source


def _anchor_angle(face, layer, target):
    """Align the longest edge of the active face to the U or V axis.

    The closest axis-parallel orientation wins, so this will never rotate
    more than 90 degrees. The longest side and loop order break ties
    deterministically.
    """
    lengths = []
    for i, loop in enumerate(face.loops):
        a = loop[layer].uv
        b = loop.link_loop_next[layer].uv
        du, dv = float(b.x-a.x), float(b.y-a.y)
        if not math.isfinite(du) or not math.isfinite(dv):
            raise ValueError('Active face UV edge contains invalid coordinates')
        lengths.append((du*du+dv*dv, -i, du, dv))
    if not lengths:
        raise ValueError('Active face contains no UV edge to align')
    size, _order, du, dv = max(lengths)
    if size <= 1e-14:
        raise ValueError('Active face UV edges are collapsed')
    base = math.atan2(dv, du)
    desired = 0.0 if target == 'ALIGN_U' else math.pi/2
    angle = desired - base
    return (angle + math.pi/2) % math.pi - math.pi/2


def _angle(action, face, layer):
    if action == 'CW':
        return -math.pi/2
    if action == 'CCW':
        return math.pi/2
    if action == 'HALF':
        return math.pi
    if action in {'ALIGN_U', 'ALIGN_V'}:
        return _anchor_angle(face, layer, action)
    raise ValueError('Choose clockwise/counter-clockwise, 180 or Align U/V')


def _hidden_adjacency(bm, target_faces, layer):
    """An invisible continuation of a UV island must not be left behind."""
    selected = set(target_faces)
    for face in target_faces:
        for edge in face.edges:
            if edge.seam:
                continue
            for adjacent in edge.link_faces:
                if adjacent in selected or not adjacent.is_valid:
                    continue
                if adjacent.hide and uv_island_inspector_v090._continuous(
                        face, adjacent, edge, layer):
                    raise ValueError(
                        'A hidden face shares the UV island; reveal it before alignment')


def plan(context, action):
    if action not in _CHOICES.values():
        raise ValueError('Select a supported native UV rotation')
    obj, bm, layer, face, ids, lookup, islands, before = _source(context)
    moving_faces = tuple(lookup[i] for i in ids)
    _hidden_adjacency(bm, moving_faces, layer)
    mirrored = action in {'FLIP_U', 'FLIP_V'}
    angle = 0.0 if mirrored else _angle(action, face, layer)
    if not mirrored and (not math.isfinite(angle) or abs(angle) < 1e-8):
        raise ValueError('Selected UV edge is already aligned in this direction')
    midpoint = (sum(p[0] for p in before)/len(before),
                sum(p[1] for p in before)/len(before))
    if action == 'FLIP_U':
        after = tuple((2*midpoint[0] - u, v) for u, v in before)
    elif action == 'FLIP_V':
        after = tuple((u, 2*midpoint[1] - v) for u, v in before)
    else:
        cosine, sine = math.cos(angle), math.sin(angle)
        after = tuple(
            (midpoint[0] + (p[0]-midpoint[0])*cosine - (p[1]-midpoint[1])*sine,
             midpoint[1] + (p[0]-midpoint[0])*sine + (p[1]-midpoint[1])*cosine)
            for p in before
        )
    if any(not all(math.isfinite(v) for v in p) for p in after):
        raise ValueError('UV orientation produced invalid native coordinates')
    if mirrored and all(
            abs(a-b) <= 1e-10
            for before_uv, after_uv in zip(before, after)
            for a, b in zip(before_uv, after_uv)):
        raise ValueError('Selected UV island is degenerate on the requested mirror axis')
    old_box = uv_island_match_v090._box(before)
    new_box = uv_island_match_v090._box(after)
    # Reject newly introduced bounding-box overlap, including hidden faces.
    # Pre-existing intentionally stacked islands are left as they are.
    obstacle_groups = [
        uv_island_match_v090._island_coords(part, lookup, layer)
        for part in islands['islands'] if part != ids
    ]
    obstacle_groups.extend(
        tuple(tuple(float(c) for c in loop[layer].uv) for loop in f.loops)
        for f in bm.faces if f.is_valid and f.hide
    )
    for corners in obstacle_groups:
        if not corners:
            continue
        obstacle = uv_island_match_v090._box(corners)
        if (uv_island_match_v090._overlap(new_box, obstacle) and
                not uv_island_match_v090._overlap(old_box, obstacle)):
            raise ValueError('UV orientation could overlap another island; move it first')
    # Entire native edit-cage and active UV layer are guarded, not only the
    # island being edited. Any external Blender edit invalidates the preview.
    signature = (
        mesh_selection_tools_v086._topology(bm),
        mesh_weld_preview_v090._geometry_stamp(bm),
        mesh_axis_snap_v090._matrix_stamp(obj.matrix_world),
        tuple(layer_.name for layer_ in obj.data.uv_layers),
        layer.name, uv_island_match_v090._fingerprint(bm, layer),
        face.index, tuple(f.index for f in bm.faces if f.is_valid and f.select),
        ids,
    )
    return {
        'scene': context.scene.name, 'scene_ptr': context.scene.as_pointer(),
        'layer': context.view_layer.name, 'obj': obj.name,
        'obj_ptr': obj.as_pointer(), 'mesh': obj.data.name,
        'mesh_ptr': obj.data.as_pointer(), 'signature': signature,
        'action': action, 'angle': angle, 'pivot': midpoint,
        'uv_layer': layer.name, 'face_ids': ids,
        'before': before, 'after': after,
    }


def _verify(context, proposal):
    if plan(context, proposal['action']) != proposal:
        raise ValueError('Native UV island changed after preview; preview again')
    obj, bm, layer, _face, ids, lookup, _islands, _before = _source(context)
    return obj, bm, layer, ids, lookup


def _write(context, proposal):
    obj, bm, layer, ids, lookup = _verify(context, proposal)
    loops = tuple(loop for index in ids for loop in lookup[index].loops)
    if len(loops) != len(proposal['before']):
        raise ValueError('Native UV island loop count changed before rotation')
    if any(tuple(float(v) for v in loop[layer].uv) != before
           for loop, before in zip(loops, proposal['before'])):
        raise ValueError('Native UV coordinates changed before the rotation')
    for loop, value in zip(loops, proposal['after']):
        loop[layer].uv = Vector(value)
    return obj


def commit(context, proposal, history=None):
    obj, _bm, _layer, _ids, _lookup = _verify(context, proposal)
    if history is not None:
        mesh.snapshot_and_push(obj, lambda: _write(context, proposal), history)
    else:
        saved = mesh.snapshot(obj)
        try:
            _write(context, proposal)
            mesh.update(obj)
        except BaseException:
            try:
                mesh.restore(obj, saved)
            except Exception as exc:
                raise mesh.MeshRollbackFailure(
                    'Native UV rotation restore failed; inspect mesh') from exc
            raise
        finally:
            mesh._dispose_temporary_meshes(saved)
    return len(proposal['face_ids']), math.degrees(proposal['angle'])


class BXR_OT_uv_orient(bpy.types.Operator):
    bl_idname = 'blender_xr.uv_orient'
    bl_label = 'Preview Native UV Island Orientation'
    bl_description = 'Rotate or mirror the active UV island while preserving mesh geometry'
    bl_options = {'REGISTER', 'UNDO'}
    action: bpy.props.EnumProperty(
        name='Orientation',
        items=(
            ('CW', 'Clockwise 90°', 'Rotate UVs clockwise 90 degrees'),
            ('CCW', 'Counterclockwise 90°', 'Rotate UVs counter-clockwise 90 degrees'),
            ('HALF', 'Rotate 180°', 'Rotate the UV island 180 degrees'),
            ('ALIGN_U', 'Align Longest Edge to U', 'Orient active face longest UV edge horizontally'),
            ('ALIGN_V', 'Align Longest Edge to V', 'Orient active face longest UV edge vertically'),
            ('FLIP_U', 'Mirror UV Horizontally', 'Flip U around island pivot; reverses UV handedness'),
            ('FLIP_V', 'Mirror UV Vertically', 'Flip V around island pivot; reverses UV handedness'),
        ), default='ALIGN_U')
    _proposal = None

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and
                    context.mode == 'EDIT_MESH' and selection.mode(context) == 'FACE')

    def invoke(self, context, event):
        self._proposal = None
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR UV Align wrist menu during VR')
            return {'CANCELLED'}
        try:
            self._proposal = plan(context, self.action)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        p = self._proposal
        if p:
            self.layout.label(text='UV island faces: {}'.format(len(p['face_ids'])))
            if p['action'] in {'FLIP_U', 'FLIP_V'}:
                self.layout.label(text='Preview: Mirror ' + p['action'][-1])
                self.layout.label(text='UV handedness reverses: check textures/normal maps',
                                  icon='ERROR')
            else:
                self.layout.label(text='Preview rotation: {:.2f} degrees'.format(
                    math.degrees(p['angle'])))
        self.layout.label(text='Only the active Blender UV layer will change')
        self.layout.label(text='Existing stacked islands are preserved')

    def execute(self, context):
        if runtime.CURRENT is not None or self._proposal is None:
            self.report({'WARNING'}, 'Open a fresh UV alignment preview first')
            return {'CANCELLED'}
        try:
            if self.action != self._proposal['action']:
                raise ValueError('UV alignment choice changed; preview again')
            count, degrees = commit(context, self._proposal)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self._proposal = None
        if self.action in {'FLIP_U', 'FLIP_V'}:
            self.report({'INFO'}, '{} native UV faces mirrored on {}'.format(
                count, self.action[-1]))
        else:
            self.report({'INFO'}, '{} faces rotated {:.2f} degrees'.format(
                count, degrees))
        return {'FINISHED'}


def install_pages():
    parent = uv_island_inspector_v090._PAGE
    buttons = tuple(menus.PAGES[parent])
    if not buttons or buttons[-1][1] != 'BACK':
        raise ValueError('Native UV island menu unavailable')
    if not any(action == _ENTRY for label, action in buttons):
        buttons = buttons[:-1] + (('ALIGN ISLAND', _ENTRY), buttons[-1])
    if len(buttons) > 12:
        raise ValueError('Native UV island menu has no capacity for alignment')
    menus.PAGES[parent] = buttons
    menus.PAGES[_PAGE] = (
        ('CW 90', 'XR_UV_ORIENT_CW'),
        ('CCW 90', 'XR_UV_ORIENT_CCW'),
        ('ROTATE 180', 'XR_UV_ORIENT_HALF'),
        ('ALIGN U', 'XR_UV_ORIENT_ALIGN_U'),
        ('ALIGN V', 'XR_UV_ORIENT_ALIGN_V'),
        ('MIRROR U', 'XR_UV_ORIENT_FLIP_U'),
        ('MIRROR V', 'XR_UV_ORIENT_FLIP_V'),
        ('PREVIEW', _PREVIEW),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_CONFIRM_PAGE] = (
        ('APPLY ROTATION', _APPLY), ('KEEP UVS', _CANCEL), ('BACK', 'BACK'))
    menus.TITLES[_PAGE] = 'ALIGN NATIVE UV ISLAND'
    menus.TITLES[_CONFIRM_PAGE] = 'CONFIRM UV ISLAND EDIT'
    v065.TOOLTIPS.update({
        _ENTRY: ('Native UV Island Orientation',
                 'Select one active face to orient its entire UV-continuous island'),
        _PREVIEW: ('Preview UV Island Orientation',
                   'Review a fixed rotation before changing the active UV layer'),
        _APPLY: ('Confirm UV Island Orientation',
                 'Rotate or mirror active native UV coordinates with XR Undo'),
        _CANCEL: ('Keep UV Island',
                  'Cancel native UV orientation without changing mesh data'),
    })
    for action, value in _CHOICES.items():
        v065.TOOLTIPS[action] = (
            'UV Island ' + value.replace('_', ' ').title(),
            ('Mirror reverses native UV handedness; preview before editing'
             if value.startswith('FLIP_') else
             'Choose a native UV rotation; preview before editing'))


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_uv_orientation_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == uv_island_inspector_v090._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before native UV alignment')
            self._xr_uv_orient_pending = None
            self._xr_uv_orient_action = 'ALIGN_U'
            self.menu.page = _PAGE
            self.status = 'UV ALIGN / CHOOSE ORIENTATION AND PREVIEW'
            return
        if page == _PAGE:
            if action == 'BACK':
                self._xr_uv_orient_pending = None
                self.menu.page = uv_island_inspector_v090._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before UV orientation preview')
            if action in _CHOICES:
                self._xr_uv_orient_action = _CHOICES[action]
                self._xr_uv_orient_pending = None
                self.status = 'UV ALIGN / ' + self._xr_uv_orient_action
                return
            if action != _PREVIEW:
                raise ValueError('Select orientation or Preview UV island')
            proposal = plan(context, getattr(self, '_xr_uv_orient_action', 'ALIGN_U'))
            self._xr_uv_orient_pending = proposal
            self.menu.page = _CONFIRM_PAGE
            if proposal['action'] in {'FLIP_U', 'FLIP_V'}:
                self.status = 'UV PREVIEW / MIRROR {} / REVERSES UV WINDING / {} FACES'.format(
                    proposal['action'][-1], len(proposal['face_ids']))
            else:
                self.status = 'UV PREVIEW / {:.1f} DEG / {} FACES / CONFIRM'.format(
                    math.degrees(proposal['angle']), len(proposal['face_ids']))
            return
        if page == _CONFIRM_PAGE:
            if action in {_CANCEL, 'BACK'}:
                self._xr_uv_orient_pending = None
                self.menu.page = _PAGE
                self.status = 'UV ORIENTATION CANCELLED / NO NATIVE EDIT'
                return
            if action != _APPLY:
                raise ValueError('Confirm or cancel UV island orientation')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before UV rotation')
            proposal = getattr(self, '_xr_uv_orient_pending', None)
            if proposal is None:
                raise ValueError('UV orientation preview expired; preview again')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('Native XR mesh history required for UV alignment')
            count, degrees = commit(context, proposal, history)
            self._xr_uv_orient_pending = None
            self.menu.page = _PAGE
            self._xr_precision_last_ray = None
            if proposal['action'] in {'FLIP_U', 'FLIP_V'}:
                self.status = 'UV MIRRORED {} / {} FACES / XR UNDO'.format(
                    proposal['action'][-1], count)
            else:
                self.status = 'UV ROTATED / {:.1f} DEG / {} FACES / XR UNDO'.format(
                    degrees, count)
            return
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_uv_orientation_090_patched = True


CLASSES = (BXR_OT_uv_orient,)
