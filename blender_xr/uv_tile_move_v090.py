# SPDX-License-Identifier: GPL-3.0-or-later
"""Move one complete native Blender UV island by exact integer UDIM tiles.

This is a controlled 2D translation of an existing UV island, not an unwrap,
pack, atlas modification, or creation of new image tiles. It preserves island
geometry, scale, tangent orientation and all non-active UV maps. Preview is
read-only; a separate confirmation owns one native XR mesh snapshot/Undo.
"""
import math

import bpy
from mathutils import Vector

from . import (input_ownership_v080, menus, mesh, mesh_axis_snap_v090,
               mesh_selection_tools_v086, mesh_weld_preview_v090,
               runtime, uv_island_inspector_v090, uv_island_match_v090,
               uv_island_orient_v090, v065)

_PAGE = 'XR_UV_TILE_MOVE_090'
_CONFIRM_PAGE = 'XR_UV_TILE_CONFIRM_090'
_ENTRY = 'XR_UV_TILE_MOVE_MENU'
_PREVIEW = 'XR_UV_TILE_PREVIEW'
_APPLY = 'XR_UV_TILE_APPLY'
_CANCEL = 'XR_UV_TILE_CANCEL'
_OFFSETS = {
    'XR_UV_TILE_LEFT': (-1, 0),
    'XR_UV_TILE_RIGHT': (1, 0),
    'XR_UV_TILE_UP': (0, 1),
    'XR_UV_TILE_DOWN': (0, -1),
    'XR_UV_TILE_UL': (-1, 1),
    'XR_UV_TILE_UR': (1, 1),
    'XR_UV_TILE_DL': (-1, -1),
    'XR_UV_TILE_DR': (1, -1),
}
_MAX_ROW = 99
_EPS = 1e-7


def _tile(bounds):
    """Return the integer UDIM column/row only for one fully enclosed tile.

    UV coordinates may lie precisely on a tile border. The island may touch
    its upper tile edges, but must never span more than one tile or start
    outside a supported 1001+10*v+u region.
    """
    low_u, low_v, high_u, high_v = bounds
    if not all(math.isfinite(v) for v in bounds):
        raise ValueError('Native UV island bounds contain invalid values')
    col, row = math.floor(low_u + _EPS), math.floor(low_v + _EPS)
    if not (0 <= col <= 9 and 0 <= row <= _MAX_ROW):
        raise ValueError('Source UV island is outside the supported UDIM tile columns/rows')
    if (low_u < col - _EPS or low_v < row - _EPS or
            high_u > col + 1 + _EPS or high_v > row + 1 + _EPS):
        raise ValueError('Source UV island spans multiple tiles; isolate it first')
    return col, row


def _number(col, row):
    return 1001 + col + row * 10


def plan(context, action):
    if action not in _OFFSETS:
        raise ValueError('Select a supported neighbouring UV tile direction')
    obj, bm, layer, active, ids, lookup, islands, before = (
        uv_island_orient_v090._source(context))
    faces = tuple(lookup[index] for index in ids)
    uv_island_orient_v090._hidden_adjacency(bm, faces, layer)
    source_bounds = uv_island_match_v090._box(before)
    source_col, source_row = _tile(source_bounds)
    du, dv = _OFFSETS[action]
    destination_col, destination_row = source_col + du, source_row + dv
    if not (0 <= destination_col <= 9 and
            0 <= destination_row <= _MAX_ROW):
        raise ValueError('Destination is outside the supported UDIM tile grid')
    after = tuple((u + du, v + dv) for u, v in before)
    if any(not all(math.isfinite(v) for v in point) for point in after):
        raise ValueError('Native UV tile move would create invalid coordinates')
    destination_box = uv_island_match_v090._box(after)
    # Unchanged hidden UV faces are obstacles too, and we never move other
    # islands automatically to make room. Deliberate stacked UV islands are
    # permitted at their OLD positions, but never introduced by this move.
    obstacles = [
        uv_island_match_v090._island_coords(group, lookup, layer)
        for group in islands['islands'] if group != ids
    ]
    obstacles.extend(
        tuple(tuple(float(v) for v in loop[layer].uv) for loop in face.loops)
        for face in bm.faces if face.is_valid and face.hide
    )
    for corners in obstacles:
        if corners and uv_island_match_v090._overlap(
                destination_box, uv_island_match_v090._box(corners)):
            raise ValueError('Target UV tile already overlaps another island or hidden face')
    signature = (
        mesh_selection_tools_v086._topology(bm),
        mesh_weld_preview_v090._geometry_stamp(bm),
        mesh_axis_snap_v090._matrix_stamp(obj.matrix_world),
        tuple(item.name for item in obj.data.uv_layers),
        layer.name, uv_island_match_v090._fingerprint(bm, layer),
        active.index, tuple(face.index for face in bm.faces
                            if face.is_valid and face.select),
        ids, action, source_col, source_row, destination_col, destination_row,
    )
    return {
        'scene': context.scene.name, 'scene_ptr': context.scene.as_pointer(),
        'layer': context.view_layer.name, 'obj': obj.name,
        'obj_ptr': obj.as_pointer(), 'mesh': obj.data.name,
        'mesh_ptr': obj.data.as_pointer(), 'signature': signature,
        'action': action, 'offset': (du, dv),
        'source_tile': _number(source_col, source_row),
        'destination_tile': _number(destination_col, destination_row),
        'uv_layer': layer.name, 'face_ids': ids,
        'before': before, 'after': after,
    }


def _verify(context, proposal):
    if plan(context, proposal['action']) != proposal:
        raise ValueError('UV tile source, destination or scene changed; preview again')
    obj, bm, layer, _active, ids, lookup, _islands, _before = (
        uv_island_orient_v090._source(context))
    return obj, bm, layer, ids, lookup


def _write(context, proposal):
    obj, bm, layer, ids, lookup = _verify(context, proposal)
    loops = tuple(loop for index in ids for loop in lookup[index].loops)
    if len(loops) != len(proposal['before']):
        raise ValueError('Selected UV island changed since preview')
    if any(tuple(float(v) for v in loop[layer].uv) != point
           for loop, point in zip(loops, proposal['before'])):
        raise ValueError('Native UV coordinates changed before tile shift')
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
                    'Native UV tile shift restore failed; inspect Blender mesh') from exc
            raise
        finally:
            mesh._dispose_temporary_meshes(saved)
    return len(proposal['face_ids']), proposal['destination_tile']


class BXR_OT_uv_tile_move(bpy.types.Operator):
    bl_idname = 'blender_xr.uv_tile_move'
    bl_label = 'Preview Native UV Island UDIM Tile Move'
    bl_description = 'Move the active UV island to an adjacent integer UV tile'
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(
        items=tuple(
            (key, key.replace('XR_UV_TILE_', '').title(),
             'Move this UV island by ({}, {}) whole UV tiles'.format(*offset))
            for key, offset in _OFFSETS.items()),
        default='XR_UV_TILE_RIGHT')
    _proposal = None

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and
                    context.mode == 'EDIT_MESH' and
                    context.tool_settings.mesh_select_mode[2])

    def invoke(self, context, event):
        self._proposal = None
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the headset UV Tile Move menu in XR')
            return {'CANCELLED'}
        try:
            self._proposal = plan(context, self.action)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=390)

    def draw(self, context):
        p = self._proposal
        if p:
            self.layout.label(text='Move {} to UV tile {}'.format(
                p['source_tile'], p['destination_tile']))
            self.layout.label(text='Preserve {} island faces'.format(
                len(p['face_ids'])))
        self.layout.label(text='Moves existing UVs, does not create UDIM image tiles')
        self.layout.label(text='All other UV islands and mesh data remain unchanged')

    def execute(self, context):
        if runtime.CURRENT is not None or self._proposal is None:
            self.report({'WARNING'}, 'Preview a specific UV tile move first')
            return {'CANCELLED'}
        try:
            if self.action != self._proposal['action']:
                raise ValueError('UV tile direction changed; preview again')
            count, number = commit(context, self._proposal)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self._proposal = None
        self.report({'INFO'}, '{} UV faces moved to tile {}'.format(count, number))
        return {'FINISHED'}


def install_pages():
    parent = uv_island_inspector_v090._PAGE
    original = tuple(menus.PAGES[parent])
    if not original or original[-1][1] != 'BACK':
        raise ValueError('Native UV island page unavailable for tile movement')
    if not any(action == _ENTRY for _label, action in original):
        original = original[:-1] + (('MOVE UV TILE', _ENTRY), original[-1])
    if len(original) > 12:
        raise ValueError('Native UV Island page has no capacity for tile movement')
    menus.PAGES[parent] = original
    menus.PAGES[_PAGE] = (
        ('LEFT', 'XR_UV_TILE_LEFT'),
        ('RIGHT', 'XR_UV_TILE_RIGHT'),
        ('UP', 'XR_UV_TILE_UP'),
        ('DOWN', 'XR_UV_TILE_DOWN'),
        ('UP-LEFT', 'XR_UV_TILE_UL'),
        ('UP-RIGHT', 'XR_UV_TILE_UR'),
        ('DOWN-LEFT', 'XR_UV_TILE_DL'),
        ('DOWN-RIGHT', 'XR_UV_TILE_DR'),
        ('PREVIEW', _PREVIEW),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_CONFIRM_PAGE] = (
        ('MOVE UVS', _APPLY), ('KEEP TILE', _CANCEL), ('BACK', 'BACK'))
    menus.TITLES[_PAGE] = 'NATIVE UV TILE MOVE'
    menus.TITLES[_CONFIRM_PAGE] = 'CONFIRM UV TILE MOVE'
    v065.TOOLTIPS.update({
        _ENTRY: ('Move a Native UV Island to Another Tile',
                 'Select one active face to move an entire UV island to a neighbouring tile'),
        _PREVIEW: ('Preview Integer UV Tile Shift',
                   'Validate the destination UDIM grid tile without editing Blender data'),
        _APPLY: ('Confirm UV Tile Shift',
                 'Move the active-layer UV island with native mesh history Undo'),
        _CANCEL: ('Keep UV Island in Current Tile',
                  'Cancel without modifying Blender UV loops'),
    })
    for action, (u, v) in _OFFSETS.items():
        v065.TOOLTIPS[action] = (
            'UV Tile Offset ({}, {})'.format(u, v),
            'Choose integer UV-tile direction, then Preview and Confirm')


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_uv_tile_move_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == uv_island_inspector_v090._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before UV Tile Move')
            self._xr_uv_tile_pending = None
            self._xr_uv_tile_action = 'XR_UV_TILE_RIGHT'
            self.menu.page = _PAGE
            self.status = 'UV TILE / CHOOSE DIRECTION AND PREVIEW'
            return
        if page == _PAGE:
            if action == 'BACK':
                self._xr_uv_tile_pending = None
                self.menu.page = uv_island_inspector_v090._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before UV tile preview')
            if action in _OFFSETS:
                self._xr_uv_tile_action = action
                self._xr_uv_tile_pending = None
                self.status = 'UV TILE / {} / PREVIEW NEXT'.format(
                    action.replace('XR_UV_TILE_', ''))
                return
            if action != _PREVIEW:
                raise ValueError('Choose UV tile direction or Preview')
            proposal = plan(context, getattr(
                self, '_xr_uv_tile_action', 'XR_UV_TILE_RIGHT'))
            self._xr_uv_tile_pending = proposal
            self.menu.page = _CONFIRM_PAGE
            self.status = 'UV PREVIEW / {} TO {} / CONFIRM?'.format(
                proposal['source_tile'], proposal['destination_tile'])
            return
        if page == _CONFIRM_PAGE:
            if action in {_CANCEL, 'BACK'}:
                self._xr_uv_tile_pending = None
                self.menu.page = _PAGE
                self.status = 'UV TILE CANCELLED / NO UV CHANGE'
                return
            if action != _APPLY:
                raise ValueError('Confirm or cancel native UV tile movement')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before UV tile editing')
            proposal = getattr(self, '_xr_uv_tile_pending', None)
            if proposal is None:
                raise ValueError('UV Tile Move approval expired; preview again')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('Native XR mesh history required for UV Tile Move')
            count, number = commit(context, proposal, history)
            self._xr_uv_tile_pending = None
            self.menu.page = _PAGE
            self._xr_precision_last_ray = None
            self.status = 'UV TILE MOVED / {} FACES / TILE {} / XR UNDO'.format(
                count, number)
            return
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_uv_tile_move_090_patched = True


CLASSES = (BXR_OT_uv_tile_move,)
