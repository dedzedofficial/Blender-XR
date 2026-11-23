# SPDX-License-Identifier: GPL-3.0-or-later
"""Preview-confirm an existing UV island onto a real texture texel grid.

Move only the active native UV map's loop coordinates. The operation is a
small uniform U/V translation, not a UV unwrap, pack, scale, geometry snap,
image edit, or texture node change. Entire-island matching preserves scale,
internal continuity, UV winding and normal-map handedness.
"""
import math

import bpy
from mathutils import Vector

from . import (input_ownership_v080, menus, mesh, mesh_axis_snap_v090,
               mesh_selection_tools_v086, mesh_weld_preview_v090,
               runtime, selection, uv_island_inspector_v090,
               uv_island_match_v090, uv_island_orient_v090,
               uv_tile_move_v090, v065)

_PAGE = 'XR_UV_TEXEL_SNAP_090'
_CONFIRM = 'XR_UV_TEXEL_CONFIRM_090'
_ENTRY = 'XR_UV_TEXEL_MENU'
_PREVIEW = 'XR_UV_TEXEL_PREVIEW'
_APPLY = 'XR_UV_TEXEL_APPLY'
_CANCEL = 'XR_UV_TEXEL_CANCEL'
_RESOLUTIONS = {
    'XR_UV_TEXEL_512': 512,
    'XR_UV_TEXEL_1024': 1024,
    'XR_UV_TEXEL_2048': 2048,
}
_MODES = {
    'XR_UV_TEXEL_EDGE': 'EDGE',
    'XR_UV_TEXEL_CENTER': 'CENTER',
}
_TOLERANCE = 1e-9


def _nearest(value, resolution, mode):
    scaled = value * resolution
    if not math.isfinite(scaled):
        raise ValueError('UV grid coordinate is invalid')
    if mode == 'EDGE':
        # Deterministic half-up rounding, not Python banker's rounding.
        return math.floor(scaled + 0.5) / resolution
    if mode == 'CENTER':
        # Nearest centre is in the texel containing the selected minimum
        # when the value lies on a positive whole-pixel boundary.
        return (math.floor(scaled) + 0.5) / resolution
    raise ValueError('Choose nearest Texel Edge or Texel Centre')


def plan(context, resolution=1024, mode='EDGE'):
    if type(resolution) is not int or resolution not in _RESOLUTIONS.values():
        raise ValueError('Choose an existing 512, 1024 or 2048 texel grid')
    if mode not in _MODES.values():
        raise ValueError('Choose Texel Edge or Texel Centre')

    obj, bm, layer, active, faces, lookup, islands, before = (
        uv_island_orient_v090._source(context))
    source_faces = tuple(lookup[index] for index in faces)
    uv_island_orient_v090._hidden_adjacency(bm, source_faces, layer)
    bounds = uv_island_match_v090._box(before)
    col, row = uv_tile_move_v090._tile(bounds)

    # The bounding box minimum identifies a deterministic anchor, making
    # this practical for pixel-perfect sprites/low-poly texture islands.
    shift = (
        _nearest(bounds[0], resolution, mode) - bounds[0],
        _nearest(bounds[1], resolution, mode) - bounds[1],
    )
    if not all(math.isfinite(v) for v in shift):
        raise ValueError('Native UV texel correction was not finite')
    if max(abs(v) for v in shift) <= _TOLERANCE:
        raise ValueError('UV island is already aligned at this resolution')
    if any(abs(v) > (0.50001 / resolution) for v in shift):
        raise ValueError('UV translation exceeds half a texture texel')

    after = tuple((u + shift[0], v + shift[1]) for u, v in before)
    if any(not all(math.isfinite(v) for v in coords) for coords in after):
        raise ValueError('UV Texel Snap produced invalid native UV values')
    new_bounds = uv_island_match_v090._box(after)
    if (new_bounds[0] < col - 1e-7 or new_bounds[1] < row - 1e-7 or
            new_bounds[2] > col+1+1e-7 or new_bounds[3] > row+1+1e-7):
        raise ValueError('Texel snap would move the UV island across a tile boundary')

    # Reject a NEW possible overlap, but preserve pre-existing intentional
    # UV stacks. Invisible face UVs are inspected as separate obstacles.
    other_groups = [
        uv_island_match_v090._island_coords(group, lookup, layer)
        for group in islands['islands'] if group != faces
    ]
    other_groups.extend(
        tuple(tuple(float(v) for v in loop[layer].uv) for loop in face.loops)
        for face in bm.faces if face.is_valid and face.hide
    )
    for corners in other_groups:
        if not corners:
            continue
        obstacle = uv_island_match_v090._box(corners)
        if (uv_island_match_v090._overlap(new_bounds, obstacle) and
                not uv_island_match_v090._overlap(bounds, obstacle)):
            raise ValueError(
                'Texel snap could introduce UV overlap; move other islands first')

    signature = (
        mesh_selection_tools_v086._topology(bm),
        mesh_weld_preview_v090._geometry_stamp(bm),
        mesh_axis_snap_v090._matrix_stamp(obj.matrix_world),
        tuple(uv.name for uv in obj.data.uv_layers),
        layer.name, uv_island_match_v090._fingerprint(bm, layer),
        active.index,
        tuple(face.index for face in bm.faces if face.is_valid and face.select),
        faces, resolution, mode, col, row,
    )
    return {
        'scene': context.scene.name, 'scene_ptr': context.scene.as_pointer(),
        'view_layer': context.view_layer.name,
        'obj': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'signature': signature, 'resolution': resolution, 'mode': mode,
        'uv_layer': layer.name, 'face_ids': faces,
        'tile': uv_tile_move_v090._number(col, row),
        'shift': shift, 'before': before, 'after': after,
    }


def _verify(context, proposal):
    fresh = plan(context, proposal['resolution'], proposal['mode'])
    if fresh != proposal:
        raise ValueError('UV Texel Snap preview expired; inspect the native mesh again')
    obj, bm, layer, _active, faces, lookup, _islands, _before = (
        uv_island_orient_v090._source(context))
    return obj, bm, layer, faces, lookup


def _write(context, proposal):
    obj, bm, layer, faces, lookup = _verify(context, proposal)
    loops = tuple(loop for index in faces for loop in lookup[index].loops)
    if len(loops) != len(proposal['before']):
        raise ValueError('Native UV island loop count changed after preview')
    for loop, expected in zip(loops, proposal['before']):
        if tuple(float(v) for v in loop[layer].uv) != expected:
            raise ValueError('UV coordinates changed before texel snapping')
    for loop, destination in zip(loops, proposal['after']):
        loop[layer].uv = Vector(destination)
    return obj


def commit(context, proposal, history=None):
    obj, _bm, _layer, _faces, _lookup = _verify(context, proposal)
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
                    'Native UV Texel Snap restore failed; inspect mesh') from exc
            raise
        finally:
            mesh._dispose_temporary_meshes(saved)
    return len(proposal['face_ids'])


class BXR_OT_uv_texel_snap(bpy.types.Operator):
    bl_idname = 'blender_xr.uv_texel_snap'
    bl_label = 'Preview and Snap Native UV Island to Texel Grid'
    bl_description = 'Move one native UV island by at most half a texel'
    bl_options = {'REGISTER', 'UNDO'}

    resolution: bpy.props.EnumProperty(
        name='Texture Resolution',
        items=(
            ('512', '512 px', 'Use a 512 by 512 texel grid'),
            ('1024', '1024 px', 'Use a 1024 by 1024 texel grid'),
            ('2048', '2048 px', 'Use a 2048 by 2048 texel grid'),
        ), default='1024')
    mode: bpy.props.EnumProperty(
        name='Anchor',
        items=(
            ('EDGE', 'Pixel Boundary', 'Align lower-left UV bound to texel grid lines'),
            ('CENTER', 'Pixel Centre', 'Align lower-left UV bound to a texel centre'),
        ), default='EDGE')
    _proposal = None

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH'
                    and selection.mode(context) == 'FACE')

    def invoke(self, context, event):
        self._proposal = None
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR UV Texel Snap wrist menu')
            return {'CANCELLED'}
        try:
            self._proposal = plan(context, int(self.resolution), self.mode)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        p = self._proposal
        if p:
            self.layout.label(text='UV island: {} faces / tile {}'.format(
                len(p['face_ids']), p['tile']))
            self.layout.label(text='Snap: {} px / {}'.format(
                p['resolution'], p['mode'].title()))
            self.layout.label(text='Shift U {:.4f}, V {:.4f} texels'.format(
                p['shift'][0] * p['resolution'],
                p['shift'][1] * p['resolution']))
        self.layout.label(text='No UV scaling, unwrap, or mesh geometry changes')

    def execute(self, context):
        if runtime.CURRENT is not None or self._proposal is None:
            self.report({'WARNING'}, 'A fresh native UV preview is required')
            return {'CANCELLED'}
        if (int(self.resolution), self.mode) != (
                self._proposal['resolution'], self._proposal['mode']):
            self.report({'WARNING'}, 'Texel snap settings changed; preview again')
            return {'CANCELLED'}
        try:
            count = commit(context, self._proposal)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self._proposal = None
        self.report({'INFO'}, 'Snapped {} island faces to {}-px grid'.format(
            count, self.resolution))
        return {'FINISHED'}


def install_pages():
    parent = uv_island_inspector_v090._PAGE
    current = tuple(menus.PAGES[parent])
    if not current or current[-1][1] != 'BACK':
        raise ValueError('Native UV Island wrist menu is unavailable')
    if not any(action == _ENTRY for _label, action in current):
        current = current[:-1] + (('TEXEL SNAP', _ENTRY), current[-1])
    if len(current) > 12:
        raise ValueError('UV island menu lacks capacity for Texel Snap')
    menus.PAGES[parent] = current
    menus.PAGES[_PAGE] = (
        ('512 PX', 'XR_UV_TEXEL_512'),
        ('1024 PX', 'XR_UV_TEXEL_1024'),
        ('2048 PX', 'XR_UV_TEXEL_2048'),
        ('PIXEL EDGE', 'XR_UV_TEXEL_EDGE'),
        ('PIXEL CENTER', 'XR_UV_TEXEL_CENTER'),
        ('PREVIEW', _PREVIEW),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_CONFIRM] = (
        ('SNAP UVS', _APPLY),
        ('KEEP UVS', _CANCEL),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'NATIVE UV TEXEL SNAP'
    menus.TITLES[_CONFIRM] = 'CONFIRM UV TEXEL SNAP'
    v065.TOOLTIPS.update({
        _ENTRY: ('Snap UV Island to Texel Grid',
                 'Preview native UV pivot translation at 512, 1024 or 2048 pixels'),
        _PREVIEW: ('Preview UV Texel Snap',
                   'Read native UV bounds and verify destination before changing data'),
        _APPLY: ('Confirm Native UV Texel Snap',
                 'Move only the active UV layer in one XR mesh Undo transaction'),
        _CANCEL: ('Keep Existing UV Island',
                  'Cancel with no native UV loop changes'),
    })
    for key, resolution in _RESOLUTIONS.items():
        v065.TOOLTIPS[key] = (
            'Texel Grid {} px'.format(resolution),
            'Choose a {} by {} texture coordinate grid'.format(
                resolution, resolution))
    for key, mode in _MODES.items():
        v065.TOOLTIPS[key] = (
            'Texel ' + mode.title(),
            'Snap the island minimum UV coordinate to the nearest pixel ' +
            ('edge' if mode == 'EDGE' else 'centre'))


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_uv_texel_snap_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == uv_island_inspector_v090._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release gesture before native UV Texel Snap')
            self._xr_uv_texel_pending = None
            self._xr_uv_texel_resolution = 1024
            self._xr_uv_texel_mode = 'EDGE'
            self.menu.page = _PAGE
            self.status = 'UV TEXEL / SELECT GRID AND PREVIEW'
            return
        if page == _PAGE:
            if action == 'BACK':
                self._xr_uv_texel_pending = None
                self.menu.page = uv_island_inspector_v090._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before native texel snap')
            if action in _RESOLUTIONS or action in _MODES:
                if action in _RESOLUTIONS:
                    self._xr_uv_texel_resolution = _RESOLUTIONS[action]
                else:
                    self._xr_uv_texel_mode = _MODES[action]
                self._xr_uv_texel_pending = None
                self.status = 'UV TEXEL / {} PX / {}'.format(
                    self._xr_uv_texel_resolution, self._xr_uv_texel_mode)
                return
            if action != _PREVIEW:
                raise ValueError('Choose resolution, pixel anchor or Preview')
            proposal = plan(context, getattr(
                self, '_xr_uv_texel_resolution', 1024), getattr(
                self, '_xr_uv_texel_mode', 'EDGE'))
            self._xr_uv_texel_pending = proposal
            self.menu.page = _CONFIRM
            self.status = 'UV TEXEL PREVIEW / {} PX / U {:.3f} V {:.3f} TEXELS'.format(
                proposal['resolution'],
                proposal['shift'][0] * proposal['resolution'],
                proposal['shift'][1] * proposal['resolution'])
            return
        if page == _CONFIRM:
            if action in {_CANCEL, 'BACK'}:
                self._xr_uv_texel_pending = None
                self.menu.page = _PAGE
                self.status = 'UV TEXEL SNAP CANCELLED / NO UV CHANGE'
                return
            if action != _APPLY:
                raise ValueError('Confirm or cancel Texel Snap')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before Texel Snap commit')
            proposal = getattr(self, '_xr_uv_texel_pending', None)
            if proposal is None:
                raise ValueError('UV Texel Snap preview expired; preview again')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('Native mesh history required to Snap UV island')
            count = commit(context, proposal, history)
            self._xr_uv_texel_pending = None
            self.menu.page = _PAGE
            self._xr_precision_last_ray = None
            self.status = 'UV TEXEL / {} FACES / {} PX / XR UNDO READY'.format(
                count, proposal['resolution'])
            return
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_uv_texel_snap_090_patched = True


CLASSES = (BXR_OT_uv_texel_snap,)
