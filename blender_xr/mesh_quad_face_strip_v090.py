# SPDX-License-Identifier: GPL-3.0-or-later
"""Native quad face-strip selection guided by two adjacent selected faces.

Follow opposite edges across real manifold quads, stopping at existing UV
splits, Blender seams, sharp edges, hidden geometry, material/shading changes
or non-quad faces. Read-only traversal; selection edits reuse the established
XR_MESH_SELECTION_086 history. No topology, UV or mesh data is changed.
"""
import math

import bpy

from . import (input_ownership_v080, menus, mesh_select_similar_v090,
               mesh_selection_tools_v086, runtime, selection,
               selection_quicksets_v090, v065)

_PAGE = 'XR_QUAD_FACE_STRIP_090'
_ENTRY = 'XR_QUAD_FACE_STRIP_MENU'
_REPORT = 'XR_QUAD_FACE_STRIP_REPORT'
_TARGETS = {
    'XR_QUAD_FACE_STRIP_ALL': 'ALL',
    'XR_QUAD_FACE_STRIP_A': 'A',
    'XR_QUAD_FACE_STRIP_B': 'B',
}
_ADD = 'XR_QUAD_FACE_STRIP_ADD'
_MAX_FACES = 150000
_MAX_STRIP = 4096
_UV_EPS = 1e-6


def _source(context):
    obj = mesh_selection_tools_v086._editable(context)
    if selection.mode(context) != 'FACE':
        raise ValueError('Switch to Face Select Mode to follow a quad face strip')
    bm, faces = mesh_selection_tools_v086._current(obj, 'FACE')
    if len(faces) > _MAX_FACES:
        raise ValueError('Quad Face Strip supports up to 150,000 mesh faces')
    selected = tuple(sorted(
        (face for face in faces if face.is_valid and not face.hide
         and face.select), key=lambda face: face.index))
    if len(selected) != 2 or any(len(face.verts) != 4 for face in selected):
        raise ValueError('Select exactly two adjacent visible quads as the strip direction')
    first, second = selected
    shared = set(first.edges).intersection(second.edges)
    if len(shared) != 1:
        raise ValueError('Selected quad faces must share exactly one edge')
    edge = next(iter(shared))
    if edge.hide or not edge.is_valid or not edge.is_manifold:
        raise ValueError('Selected quads do not share a visible manifold edge')
    if edge.seam or not edge.smooth:
        raise ValueError('Selected quad strip starts across a marked seam or sharp edge')
    if first.material_index != second.material_index or first.smooth != second.smooth:
        raise ValueError('Select two quads with matching materials and shading')
    uv_layers = tuple(bm.loops.layers.uv.get(layer.name)
                      for layer in obj.data.uv_layers)
    if any(layer is None for layer in uv_layers):
        raise ValueError('One of the native mesh UV maps is inaccessible')
    if not _same_uvs(first, second, edge, uv_layers):
        raise ValueError('The selected quads are separated by a native UV split')
    return first, second, edge, uv_layers


def _corner(face, edge, layer):
    endpoints = set(edge.verts)
    coords = {}
    for loop in face.loops:
        if loop.vert in endpoints:
            pos = tuple(float(v) for v in loop[layer].uv)
            if not all(math.isfinite(v) for v in pos):
                raise ValueError('Native mesh UV map contains non-finite corners')
            coords[loop.vert] = pos
    if len(coords) != 2:
        raise ValueError('UV corner lookup failed on native quad edge')
    return coords


def _same_uvs(first, second, edge, layers):
    for layer in layers:
        left = _corner(first, edge, layer)
        right = _corner(second, edge, layer)
        if any(abs(left[v][axis] - right[v][axis]) > _UV_EPS
               for v in edge.verts for axis in (0, 1)):
            return False
    return True


def _opposite(face, incoming):
    if len(face.verts) != 4 or incoming not in face.edges:
        raise ValueError('Strip traversal encountered non-quad native geometry')
    candidates = tuple(edge for edge in face.edges
                       if edge is not incoming and
                       not any(v in incoming.verts for v in edge.verts))
    if len(candidates) != 1:
        raise ValueError('Native quad has no unambiguous opposite edge')
    return candidates[0]


def _advance(face, incoming, layers):
    far = _opposite(face, incoming)
    if (not far.is_valid or far.hide or not far.is_manifold or
            far.seam or not far.smooth):
        return None
    adjacent = [neighbor for neighbor in far.link_faces if neighbor is not face]
    if len(adjacent) != 1:
        return None
    neighbor = adjacent[0]
    if (not neighbor.is_valid or neighbor.hide or len(neighbor.verts) != 4 or
            neighbor.material_index != face.material_index or
            neighbor.smooth != face.smooth or
            not _same_uvs(face, neighbor, far, layers)):
        return None
    return neighbor, far


def _trace(seed, crossing, layers, visited):
    """Follow one side of a face strip without repeating the selected pair."""
    found = [seed.index]
    current, incoming = seed, crossing
    for _ in range(_MAX_STRIP):
        following = _advance(current, incoming, layers)
        if following is None:
            return tuple(found)
        face, edge = following
        if face in visited:
            # Closed loops are handled as one finite native face set.
            return tuple(found)
        found.append(face.index)
        visited.add(face)
        current, incoming = face, edge
    raise ValueError('Quad strip exceeds 4096 faces; select a smaller section')


def inspect(context):
    first, second, common, layers = _source(context)
    visited = {first, second}
    a = _trace(first, common, layers, visited)
    b = _trace(second, common, layers, visited)
    joined = tuple(sorted(set(a).union(b)))
    return {
        'A': a, 'B': b, 'ALL': joined,
        'a_seed': first.index, 'b_seed': second.index,
        'total': len(joined),
    }


class BXR_OT_quad_face_strip(bpy.types.Operator):
    bl_idname = 'blender_xr.quad_face_strip'
    bl_label = 'Select Native Quad Face Strip'
    bl_description = 'Follow two selected Blender quads in both directions'
    bl_options = {'REGISTER', 'UNDO'}

    side: bpy.props.EnumProperty(
        items=(
            ('ALL', 'Entire Strip', 'Select all matching faces on both sides'),
            ('A', 'First Seed Side', 'Select the side with the lower-index source face'),
            ('B', 'Second Seed Side', 'Select the side with the higher-index source face'),
        ), default='ALL')
    additive: bpy.props.BoolProperty(
        name='Add to Selection', default=False,
        description='Keep existing selected faces while adding this quad strip')

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and
                    context.mode == 'EDIT_MESH' and selection.mode(context) == 'FACE')

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Quad Face Strip wrist menu')
            return {'CANCELLED'}
        try:
            result = inspect(context)
            obj = mesh_selection_tools_v086._editable(context)
            bm, items = mesh_selection_tools_v086._current(obj, 'FACE')
            before = mesh_selection_tools_v086._selected(items)
            desired = (tuple(sorted(set(before).union(result[self.side])))
                       if self.additive else tuple(sorted(result[self.side])))
            if before == desired:
                self.report({'INFO'}, 'The selected quad face strip is unchanged')
                return {'CANCELLED'}
            mesh_selection_tools_v086._set_selection(obj, 'FACE', desired)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, '{} faces selected in native quad strip'.format(
            len(desired)))
        return {'FINISHED'}


def install_pages():
    parent = mesh_select_similar_v090._DIAGNOSTICS
    buttons = tuple(menus.PAGES[parent])
    if not buttons or buttons[-1][1] != 'BACK':
        raise ValueError('Quad face strip needs the existing Diagnostics menu')
    if not any(action == _ENTRY for _label, action in buttons):
        buttons = buttons[:-1] + (('QUAD STRIP', _ENTRY), buttons[-1])
    if len(buttons) > 12:
        raise ValueError('Mesh Diagnostics is full; quad face strip cannot be added')
    menus.PAGES[parent] = buttons
    menus.PAGES[_PAGE] = (
        ('INSPECT STRIP', _REPORT),
        ('BOTH SIDES', 'XR_QUAD_FACE_STRIP_ALL'),
        ('SIDE A', 'XR_QUAD_FACE_STRIP_A'),
        ('SIDE B', 'XR_QUAD_FACE_STRIP_B'),
        ('ADD/REPLACE', _ADD),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'QUAD FACE STRIPS'
    v065.TOOLTIPS.update({
        _ENTRY: ('Quad Face Strip Selection',
            'Select exactly two adjacent quads as direction, then follow their strip'),
        _REPORT: ('Inspect Quad Face Strip',
            'Count the full strip on either side without editing the Blender mesh'),
        _ADD: ('Add or Replace Face Strip',
            'Change face-selection recall mode before confirming a strip'),
        'XR_QUAD_FACE_STRIP_ALL': ('Select Both Strip Directions',
            'Follow opposite quad edges until an existing boundary or discontinuity'),
        'XR_QUAD_FACE_STRIP_A': ('Select Lower-Index Seed Side',
            'Select only the strip starting from the lower-index source face'),
        'XR_QUAD_FACE_STRIP_B': ('Select Higher-Index Seed Side',
            'Select only the strip starting from the higher-index source face'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_quad_face_strip_090_patched', False):
        return
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        page = getattr(menu, 'page', None)
        if page == mesh_select_similar_v090._DIAGNOSTICS and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before quad strip inspection')
            _source(context)
            menu.page = _PAGE
            self.status = 'QUAD STRIP / 2 ADJACENT QUADS / FOLLOW BOTH SIDES'
            return
        if page == _PAGE:
            if action == 'BACK':
                menu.page = mesh_select_similar_v090._DIAGNOSTICS
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR controllers before selecting a quad strip')
            if action == _ADD:
                self._xr_quad_strip_add = not bool(getattr(self, '_xr_quad_strip_add', False))
                self.status = ('QUAD STRIP / ' +
                               ('ADD TO SELECTION' if self._xr_quad_strip_add
                                else 'REPLACE SELECTION'))
                return
            if action == _REPORT:
                result = inspect(context)
                self.status = 'QUAD STRIP / {} FACES / A {} / B {}'.format(
                    result['total'], len(result['A']), len(result['B']))
                return
            if action in _TARGETS:
                if getattr(self, 'history', None) is None:
                    raise ValueError('XR selection history is required for quad strips')
                result = inspect(context)
                indices = result[_TARGETS[action]]
                count, changed = selection_quicksets_v090.restore_indices(
                    self, context, indices,
                    additive=bool(getattr(self, '_xr_quad_strip_add', False)))
                self.status = 'QUAD STRIP / {} FACES / {}'.format(
                    count, 'XR UNDO READY' if changed else 'UNCHANGED')
                return
            raise ValueError('Inspect or select a native quad face strip')
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_quad_face_strip_090_patched = True


CLASSES = (BXR_OT_quad_face_strip,)
