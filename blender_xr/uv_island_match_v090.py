# SPDX-License-Identifier: GPL-3.0-or-later
"""Preview-and-confirm UV-island density matching on native Blender loop UVs.

One active selected face chooses a UV island. Match that whole island to the
median density of all OTHER nondegenerate visible UV islands. The uniform
positive scale preserves island-local UV continuity and relative face sizes;
the operation does not try to repair poor density *within* an island.
"""
import hashlib
import math
import statistics
import struct

import bpy
from mathutils import Vector

from . import (input_ownership_v080, menus, mesh, mesh_axis_snap_v090,
               mesh_selection_tools_v086, runtime, selection,
               uv_density_audit_v090, uv_island_inspector_v090, v065)

_PAGE = 'XR_UV_MATCH_DENSITY_090'
_CONFIRM = 'XR_UV_MATCH_CONFIRM_090'
_ENTRY = 'XR_UV_MATCH_MENU'
_PREVIEW = 'XR_UV_MATCH_PREVIEW'
_APPLY = 'XR_UV_MATCH_APPLY'
_CANCEL = 'XR_UV_MATCH_CANCEL'
_MAX_FACES = 150000
_MAX_ISLAND_FACES = 15000
_MIN_SCALE = 0.67
_MAX_SCALE = 1.5
_EPS = 1e-12


def _fingerprint(bm, layer):
    """Read every loop UV, including hidden geometry, to guard stale previews."""
    digest = hashlib.blake2b(digest_size=20)
    for face in bm.faces:
        digest.update(struct.pack('<II', face.index, len(face.loops)))
        for loop in face.loops:
            uv = tuple(float(v) for v in loop[layer].uv)
            if not all(math.isfinite(v) for v in uv):
                raise ValueError('UV map contains invalid coordinates')
            digest.update(struct.pack('<dd', *uv))
    return digest.digest()


def _box(coords):
    return (min(u for u, v in coords), min(v for u, v in coords),
            max(u for u, v in coords), max(v for u, v in coords))


def _overlap(a, b):
    # Conservative box test: a candidate that might overlap another UV
    # island is refused, rather than changing the artist's texture atlas.
    return (min(a[2], b[2]) - max(a[0], b[0]) > 1e-7 and
            min(a[3], b[3]) - max(a[1], b[1]) > 1e-7)


def _island_coords(indices, by_index, layer):
    return tuple(tuple(float(v) for v in loop[layer].uv)
                 for index in indices for loop in by_index[index].loops)


def _density(indices, by_index, layer, world):
    values = []
    for index in indices:
        face = by_index[index]
        world_area = uv_density_audit_v090._area_world(face, world)
        uv_area = uv_density_audit_v090._area_uv(face, layer)
        if (world_area <= _EPS or uv_area <= _EPS or
                not math.isfinite(world_area) or not math.isfinite(uv_area)):
            raise ValueError('UV density correction requires non-collapsed reference islands')
        density = math.sqrt(uv_area / world_area)
        if density <= _EPS or not math.isfinite(density):
            raise ValueError('A UV island contains invalid texel density')
        values.append(density)
    return statistics.median(values)


def plan(context):
    if selection.mode(context) != 'FACE':
        raise ValueError('Choose Face Select Mode and one active face on an existing UV island')
    obj, bm, layer, visible = uv_island_inspector_v090._source(context)
    mesh.editable(obj)
    if (obj.override_library or obj.data.override_library or
            obj.data.users != 1 or obj.data.shape_keys is not None):
        raise ValueError('UV density matching requires a local, single-user mesh without shape keys')
    if len(bm.faces) > _MAX_FACES:
        raise ValueError('UV matching supports up to 150,000 mesh faces')
    selected = [face for face in visible if face.select]
    active = bm.faces.active
    if (len(selected) != 1 or active is None or active is not selected[0] or
            not active.is_valid or active.hide):
        raise ValueError('Select exactly one active visible face to choose the UV island')
    islands = uv_island_inspector_v090.inspect(context)
    if len(islands['islands']) < 2:
        raise ValueError('UV density matching needs at least two existing visible UV islands')
    choice = islands['by_face'][active.index]
    target_indices = islands['islands'][choice]
    if len(target_indices) > _MAX_ISLAND_FACES:
        raise ValueError('Selected UV island is over the 15,000-face edit limit')
    by_index = {face.index: face for face in visible}
    origin = _island_coords(target_indices, by_index, layer)
    if not origin:
        raise ValueError('Selected UV island is empty')
    source_density = _density(target_indices, by_index, layer, obj.matrix_world)
    # Other islands provide the target, not the island being edited.
    reference_densities = []
    other_boxes = []
    for i, indices in enumerate(islands['islands']):
        if i == choice:
            continue
        coords = _island_coords(indices, by_index, layer)
        other_boxes.append(_box(coords))
        # A collapsed reference is not meaningful for median matching;
        # never auto-correct another island as a side effect.
        try:
            reference_densities.append(_density(
                indices, by_index, layer, obj.matrix_world))
        except ValueError:
            continue
    if not reference_densities:
        raise ValueError('No valid separate UV island density to match')
    goal = statistics.median(reference_densities)
    scale = goal / source_density
    if not math.isfinite(scale) or not _MIN_SCALE <= scale <= _MAX_SCALE:
        raise ValueError('Matching requires scale outside 0.67x to 1.50x; adjust UV manually')
    if abs(scale-1.0) < 0.005:
        raise ValueError('Selected island already matches the other island median')
    pivot = (sum(u for u, v in origin) / len(origin),
             sum(v for u, v in origin) / len(origin))
    destination = tuple((pivot[0] + (u-pivot[0])*scale,
                         pivot[1] + (v-pivot[1])*scale)
                        for u, v in origin)
    if any(not all(math.isfinite(v) for v in uv) for uv in destination):
        raise ValueError('UV scaling would create invalid coordinates')
    bounds = _box(destination)
    if any(_overlap(bounds, box) for box in other_boxes):
        raise ValueError('Scaled UV island could overlap another island; rearrange UV atlas first')
    # Store the full active layer state, including hidden faces, plus the
    # exact active layer and other UV-layer identities. This protects
    # against stale edits and UV-map changes between preview and confirm.
    stamp = (
        mesh_selection_tools_v086._topology(bm),
        uv_density_audit_v090.uv_island_inspector_v090._source(context)[2].name,
        _fingerprint(bm, layer),
        mesh_axis_snap_v090._matrix_stamp(obj.matrix_world),
        tuple(uv.name for uv in obj.data.uv_layers),
        active.index, tuple(face.index for face in selected),
        target_indices,
    )
    return {
        'scene': context.scene.name, 'scene_ptr': context.scene.as_pointer(),
        'layer': context.view_layer.name, 'obj': obj.name,
        'obj_ptr': obj.as_pointer(), 'mesh': obj.data.name,
        'mesh_ptr': obj.data.as_pointer(), 'stamp': stamp,
        'scale': scale, 'from': source_density, 'to': goal,
        'pivot': pivot, 'uv_layer': layer.name,
        'target_faces': target_indices, 'before': origin, 'after': destination,
    }


def _verify(context, proposal):
    fresh = plan(context)
    if fresh != proposal:
        raise ValueError('UV island, reference atlas or source mesh changed: preview again')
    obj, bm, layer, faces = uv_island_inspector_v090._source(context)
    return obj, bm, layer, {face.index: face for face in faces}


def _write(context, proposal):
    obj, bm, layer, faces = _verify(context, proposal)
    loops = [loop for index in proposal['target_faces']
             for loop in faces[index].loops]
    if len(loops) != len(proposal['before']):
        raise ValueError('Native island loop count changed before UV correction')
    for loop, before in zip(loops, proposal['before']):
        if tuple(float(v) for v in loop[layer].uv) != before:
            raise ValueError('Native UV corner changed before applying preview')
    for loop, coords in zip(loops, proposal['after']):
        loop[layer].uv = Vector(coords)
    # Preserve native BMesh geometry, seam/sharp flags, other UV maps and
    # texture source links; only the active layer's loop coordinates move.
    return obj


def commit(context, proposal, history=None):
    obj, _bm, _layer, _faces = _verify(context, proposal)
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
                    'UV island density rollback failed; inspect Blender mesh') from exc
            raise
        finally:
            mesh._dispose_temporary_meshes(saved)
    return len(proposal['target_faces']), proposal['scale']


class BXR_OT_uv_match_density(bpy.types.Operator):
    bl_idname = 'blender_xr.uv_match_density'
    bl_label = 'Preview and Match Selected Native UV Island Density'
    bl_description = 'Uniformly scale the active UV island to the median density of other islands'
    bl_options = {'REGISTER', 'UNDO'}
    _proposal = None

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH'
                    and selection.mode(context) == 'FACE')

    def invoke(self, context, event):
        self._proposal = None
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use headset UV Match Density preview while in VR')
            return {'CANCELLED'}
        try:
            self._proposal = plan(context)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        if self._proposal:
            p = self._proposal
            self.layout.label(text='Island faces: {}'.format(len(p['target_faces'])))
            self.layout.label(text='UV density scale: {:.3f}x'.format(p['scale']))
            self.layout.label(text='Reference: other visible UV islands')
        self.layout.label(text='Other islands and mesh geometry remain untouched')

    def execute(self, context):
        if runtime.CURRENT is not None or self._proposal is None:
            self.report({'WARNING'}, 'Open a new UV density preview first')
            return {'CANCELLED'}
        try:
            count, scale = commit(context, self._proposal)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self._proposal = None
        self.report({'INFO'}, '{} island faces scaled {:.3f}x'.format(count, scale))
        return {'FINISHED'}


def install_pages():
    parent = uv_density_audit_v090._PAGE
    current = tuple(menus.PAGES[parent])
    if not current or current[-1][1] != 'BACK':
        raise ValueError('UV Density Audit page is unavailable')
    if not any(action == _ENTRY for _label, action in current):
        current = current[:-1] + (('MATCH ISLAND', _ENTRY), current[-1])
    if len(current) > 12:
        raise ValueError('UV density page cannot hold island correction')
    menus.PAGES[parent] = current
    menus.PAGES[_PAGE] = (('PREVIEW', _PREVIEW), ('BACK', 'BACK'))
    menus.PAGES[_CONFIRM] = (
        ('SCALE UV ISLAND', _APPLY),
        ('KEEP UVS', _CANCEL), ('BACK', 'BACK'))
    menus.TITLES[_PAGE] = 'MATCH UV ISLAND DENSITY'
    menus.TITLES[_CONFIRM] = 'CONFIRM NATIVE UV SCALE'
    v065.TOOLTIPS.update({
        _ENTRY: ('Match UV Island Density',
                 'Choose one selected active face on an existing UV island'),
        _PREVIEW: ('Preview UV Density Match',
                   'Read a bounded scale against the median density of other UV islands'),
        _APPLY: ('Confirm UV Island Scaling',
                 'Scale only active UV loops after exact preview and XR Undo preflight'),
        _CANCEL: ('Keep Native UV Atlas',
                  'Discard the preview without changing UV coordinates'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_uv_match_density_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == uv_density_audit_v090._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before UV density correction')
            self._xr_uv_match_pending = None
            self.menu.page = _PAGE
            self.status = 'UV MATCH / SELECT 1 ACTIVE FACE / PREVIEW'
            return
        if page == _PAGE:
            if action == 'BACK':
                self._xr_uv_match_pending = None
                self.menu.page = uv_density_audit_v090._PAGE
                return
            if action != _PREVIEW:
                raise ValueError('Preview UV island scale before approval')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controller gesture before UV Preview')
            proposal = plan(context)
            self._xr_uv_match_pending = proposal
            self.menu.page = _CONFIRM
            self.status = 'UV PREVIEW / SCALE {:.3f}X / {} FACES / CONFIRM?'.format(
                proposal['scale'], len(proposal['target_faces']))
            return
        if page == _CONFIRM:
            if action in {_CANCEL, 'BACK'}:
                self._xr_uv_match_pending = None
                self.menu.page = _PAGE
                self.status = 'UV MATCH CANCELLED / NO UV CHANGE'
                return
            if action != _APPLY:
                raise ValueError('Confirm or cancel native UV scaling')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before UV Match apply')
            proposal = getattr(self, '_xr_uv_match_pending', None)
            if proposal is None:
                raise ValueError('UV density approval expired; preview again')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('XR native mesh history is required for UV correction')
            count, scale = commit(context, proposal, history)
            self._xr_uv_match_pending = None
            self.menu.page = _PAGE
            self._xr_precision_last_ray = None
            self.status = 'UV MATCH / {} FACES / {:.3f}X / XR UNDO READY'.format(
                count, scale)
            return
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_uv_match_density_090_patched = True


CLASSES = (BXR_OT_uv_match_density,)
