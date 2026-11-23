# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only native edit BMesh UV island analysis with guarded selection.

An island connects faces only across a manifold, unseamed edge for which
both native UV corner coordinates agree. This detects actual UV splits even
when the artist has not marked a seam. Never create UV layers, unwrap,
repack, overwrite custom normals or edit Blender polygon topology.
"""
import math

import bpy

from . import (input_ownership_v080, menus, mesh_selection_tools_v086,
               runtime, selection, selection_quicksets_v090, v065)

_PAGE = 'XR_UV_ISLAND_INSPECT_090'
_ENTRY = 'XR_UV_ISLAND_MENU'
_REPORT = 'XR_UV_ISLAND_REPORT'
_SELECT_ACTIVE = 'XR_UV_ISLAND_SELECT_ACTIVE'
_SELECT_LARGEST = 'XR_UV_ISLAND_SELECT_LARGEST'
_SELECT_SMALLEST = 'XR_UV_ISLAND_SELECT_SMALLEST'
_MAX_FACES = 150000
_UV_TOLERANCE = 1e-6


def _source(context):
    obj = mesh_selection_tools_v086._editable(context)
    bm, _items = mesh_selection_tools_v086._current(obj, selection.mode(context))
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    if len(bm.faces) > _MAX_FACES:
        raise ValueError('Native UV island inspector supports up to 150,000 faces')
    uv_layer = bm.loops.layers.uv.active
    if uv_layer is None:
        raise ValueError('Create a native Blender UV map before inspecting islands')
    faces = tuple(face for face in bm.faces if face.is_valid and not face.hide)
    if not faces:
        raise ValueError('There are no visible native faces to inspect')
    return obj, bm, uv_layer, faces


def _corners(face, edge, uv_layer):
    endpoints = set(edge.verts)
    coords = {}
    for loop in face.loops:
        if loop.vert in endpoints:
            point = tuple(float(component) for component in loop[uv_layer].uv)
            if len(point) != 2 or not all(math.isfinite(c) for c in point):
                raise ValueError('Native UV map contains invalid corner values')
            coords[loop.vert] = point
    if len(coords) != 2:
        raise ValueError('UV edge endpoints do not match the native mesh face')
    return coords


def _continuous(left, right, edge, uv_layer):
    a = _corners(left, edge, uv_layer)
    b = _corners(right, edge, uv_layer)
    return all(
        abs(a[vert][dim] - b[vert][dim]) <= _UV_TOLERANCE
        for vert in edge.verts for dim in (0, 1)
    )


def inspect(context):
    obj, bm, uv, faces = _source(context)
    ids = {face.index for face in faces}
    neighbors = {face.index: set() for face in faces}
    seams = uv_splits = borders = 0
    for edge in bm.edges:
        if not edge.is_valid or edge.hide:
            continue
        linked = tuple(face for face in edge.link_faces
                       if face.is_valid and face.index in ids)
        if len(linked) != 2:
            borders += 1
            continue
        if edge.seam:
            seams += 1
            continue
        if not _continuous(linked[0], linked[1], edge, uv):
            uv_splits += 1
            continue
        a, b = linked
        neighbors[a.index].add(b.index)
        neighbors[b.index].add(a.index)

    remaining = set(ids)
    islands = []
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        members = {seed}
        stack = [seed]
        while stack:
            face_index = stack.pop()
            for neighbor in neighbors[face_index]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    members.add(neighbor)
                    stack.append(neighbor)
        islands.append(tuple(sorted(members)))
    islands.sort(key=lambda island: (-len(island), island[0]))
    lookup = {face_index: number for number, members in enumerate(islands)
              for face_index in members}
    return {
        'obj': obj.name,
        'islands': tuple(islands),
        'by_face': lookup,
        'faces': len(faces),
        'seams': seams,
        'uv_splits': uv_splits,
        'borders': borders,
        'largest': len(islands[0]) if islands else 0,
    }


def _selected_faces(context, result, action):
    if selection.mode(context) != 'FACE':
        raise ValueError('Switch to Face Select Mode to recall a native UV island')
    islands = result['islands']
    if action == _SELECT_LARGEST:
        return islands[0]
    if action == _SELECT_SMALLEST:
        return sorted(islands, key=lambda group: (len(group), group[0]))[0]
    if action == _SELECT_ACTIVE:
        _obj, bm, _layer, _faces = _source(context)
        active = bm.faces.active
        if (active is None or not active.is_valid or active.hide or
                active.index not in result['by_face']):
            raise ValueError('Select a visible active native face first')
        return islands[result['by_face'][active.index]]
    raise ValueError('Unknown UV island selection command')


def _report(session, context):
    info = inspect(context)
    session.status = (
        'NATIVE UV / ISLANDS {} / FACES {} / SEAMS {} / UV SPLITS {} / BORDER {}'
    ).format(len(info['islands']), info['faces'], info['seams'],
             info['uv_splits'], info['borders'])
    return info


def _select(session, context, action):
    if getattr(session, 'history', None) is None:
        raise ValueError('XR history required for native UV island selection')
    info = inspect(context)
    indices = _selected_faces(context, info, action)
    count, changed = selection_quicksets_v090.restore_indices(
        session, context, indices, additive=False)
    session.status = 'UV ISLAND / {} FACES / {}'.format(
        count, 'XR UNDO READY' if changed else 'UNCHANGED')
    return changed


class BXR_OT_uv_island_inspect(bpy.types.Operator):
    bl_idname = 'blender_xr.uv_island_inspect'
    bl_label = 'Inspect Native UV Islands'
    bl_description = 'Read UV islands, seams and splits without changing native Blender UVs'
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
        self.report({'INFO'}, 'UV ISLANDS {} / FACES {} / SEAMS {} / SPLITS {}'.format(
            len(result['islands']), result['faces'],
            result['seams'], result['uv_splits']))
        return {'FINISHED'}


class BXR_OT_uv_island_select(bpy.types.Operator):
    bl_idname = 'blender_xr.uv_island_select'
    bl_label = 'Select Native UV Island'
    bl_description = 'Select a real Blender UV island by its face set'
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(items=(
        (_SELECT_ACTIVE, 'Active Island', 'Select the island containing the active face'),
        (_SELECT_LARGEST, 'Largest Island', 'Select the island with the most visible faces'),
        (_SELECT_SMALLEST, 'Smallest Island', 'Select the smallest visible island'),
    ), default=_SELECT_ACTIVE)

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and context.mode == 'EDIT_MESH' and obj.type == 'MESH'
                    and selection.mode(context) == 'FACE')

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR UV Island wrist menu while in VR')
            return {'CANCELLED'}
        try:
            info = inspect(context)
            indices = _selected_faces(context, info, self.action)
            obj = mesh_selection_tools_v086._editable(context)
            mesh_selection_tools_v086._set_selection(obj, 'FACE', indices)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, '{} faces selected in native UV island'.format(len(indices)))
        return {'FINISHED'}


def install_pages():
    original = tuple(menus.PAGES['UV'])
    if not original or original[-1][1] != 'BACK':
        raise ValueError('Native Blender UV tools menu is unavailable')
    if not any(action == _ENTRY for _label, action in original):
        original = original[:-1] + (
            ('UV ISLANDS', _ENTRY), original[-1])
    if len(original) > 12:
        raise ValueError('UV menu has no capacity for native UV island inspection')
    menus.PAGES['UV'] = original
    menus.PAGES[_PAGE] = (
        ('REPORT', _REPORT),
        ('ACTIVE ISLAND', _SELECT_ACTIVE),
        ('LARGEST', _SELECT_LARGEST),
        ('SMALLEST', _SELECT_SMALLEST),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'NATIVE UV ISLANDS'
    v065.TOOLTIPS.update({
        _ENTRY: ('UV Island Inspector',
                 'Inspect actual native UV coordinate continuity and seam flags'),
        _REPORT: ('UV Island Report',
                  'Read existing UV island count, seams, splits and mesh borders'),
        _SELECT_ACTIVE: ('Select Active Face UV Island',
                  'Select the continuous UV region containing the active native face'),
        _SELECT_LARGEST: ('Select Largest UV Island',
                  'Select the island with the greatest native visible face count'),
        _SELECT_SMALLEST: ('Select Smallest UV Island',
                  'Select the island with the fewest native visible faces'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_uv_island_inspection_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        page = getattr(menu, 'page', None)
        if page == 'UV' and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before inspecting UV islands')
            _source(context)
            menu.page = _PAGE
            self.status = 'UV ISLANDS / REPORT OR SELECT NATIVE REGION'
            return
        if page == _PAGE:
            if action == 'BACK':
                menu.page = 'UV'
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR controllers before reading the UV layout')
            if action == _REPORT:
                return _report(self, context)
            if action in {_SELECT_ACTIVE, _SELECT_LARGEST, _SELECT_SMALLEST}:
                return _select(self, context, action)
            raise ValueError('Choose UV Report or an existing UV Island')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_uv_island_inspection_090_patched = True


CLASSES = (BXR_OT_uv_island_inspect, BXR_OT_uv_island_select)
