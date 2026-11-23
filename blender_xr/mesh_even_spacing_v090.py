# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only preview and confirmed even spacing of native edit-mesh vertices.

Distribute three or more distinctly positioned selected vertices along one
local/world coordinate axis, preserving the two extreme vertices. Only native
BMVert.co values are modified. The unchanged other axes, topology, UVs, face
attributes, weights and object transform remain Blender-editable.
"""
import math

import bpy
from bpy.props import EnumProperty
from mathutils import Vector

from . import (input_ownership_v080, menus, mesh, mesh_selection_tools_v086,
               mesh_snap_v086, precision_selection_v086, runtime, selection, v065)

_PAGE = 'XR_EVEN_SPACING_090'
_CONFIRM_PAGE = 'XR_EVEN_SPACING_CONFIRM_090'
_ENTRY = 'XR_SPACING_MENU'
_PREVIEW = 'XR_SPACING_PREVIEW'
_COMMIT = 'XR_SPACING_COMMIT'
_CANCEL = 'XR_SPACING_CANCEL'
_AXES = {'XR_SPACING_X': 'X', 'XR_SPACING_Y': 'Y',
         'XR_SPACING_Z': 'Z'}
_SPACES = {'XR_SPACING_LOCAL': 'LOCAL', 'XR_SPACING_WORLD': 'WORLD'}
_MAX_VERTICES = 4096
_MAX_AFFECTED_FACES = 20000


def _source(context):
    obj = mesh_snap_v086._eligible(context)
    mode = selection.mode(context)
    bm, _items = mesh_selection_tools_v086._current(obj, mode)
    selected = tuple(sorted(mesh.selected_transform_vertices(obj, mode),
                            key=lambda vertex: vertex.index))
    if not 3 <= len(selected) <= _MAX_VERTICES:
        raise ValueError('Even Spacing requires 3–4096 selected vertices')
    if any(not vertex.is_valid or vertex.hide for vertex in selected):
        raise ValueError('Selected geometry is hidden or invalid')
    neighbors = {face for vertex in selected for face in vertex.link_faces}
    if (len(neighbors) > _MAX_AFFECTED_FACES or
            any(not face.is_valid or face.hide or
                any(edge.hide or not edge.is_valid for edge in face.edges)
                for face in neighbors)):
        raise ValueError('Spacing would affect hidden or overly dense linked faces')
    return obj, bm, selected


def plan(context, axis='X', space='LOCAL'):
    """Capture a complete read-only proposal that can be rechecked on commit."""
    if axis not in 'XYZ' or space not in {'LOCAL', 'WORLD'}:
        raise ValueError('Choose one X/Y/Z axis and local/world space')
    obj, bm, selected = _source(context)
    matrix = obj.matrix_world.copy()
    determinant = float(matrix.determinant())
    if (not math.isfinite(determinant) or abs(determinant) <= 1e-10 or
            not all(math.isfinite(float(x)) for row in matrix for x in row)):
        raise ValueError('Spacing needs a finite, invertible object transform')
    inverse = matrix.inverted()
    dimension = 'XYZ'.index(axis)
    source = tuple(
        (vertex.index, vertex.co.copy(),
         (matrix @ vertex.co) if space == 'WORLD' else vertex.co.copy())
        for vertex in selected
    )
    if any(not all(math.isfinite(float(x)) for x in (*local, *working))
           for _index, local, working in source):
        raise ValueError('Selected native mesh has invalid coordinates')
    ordered = sorted(source, key=lambda item: (float(item[2][dimension]), item[0]))
    values = [float(item[2][dimension]) for item in ordered]
    span = values[-1] - values[0]
    if not math.isfinite(span) or span <= 1e-8 or span > 10000.0:
        raise ValueError('Spacing needs a distinct, bounded axis range')
    epsilon = max(1e-8, span * 1e-8)
    if any(b - a <= epsilon for a, b in zip(values, values[1:])):
        raise ValueError('Selected vertices share an axis position; select one chain')
    increment = span / float(len(ordered) - 1)
    changes = []
    for position, (index, original, working) in enumerate(ordered):
        # Never resample the two anchors, including on rotated or
        # non-uniformly scaled Blender objects.
        if position == 0 or position == len(ordered) - 1:
            destination = original.copy()
        else:
            target = working.copy()
            target[dimension] = values[0] + increment * position
            destination = (inverse @ target if space == 'WORLD' else target)
        if not all(math.isfinite(float(component)) for component in destination):
            raise ValueError('Even Spacing produced invalid native coordinates')
        changes.append((int(index), tuple(float(x) for x in original),
                        tuple(float(x) for x in destination)))
    changed = tuple(item for item in changes
                    if any(abs(a - b) > 1e-10 for a, b in zip(item[1], item[2])))
    if not changed:
        raise ValueError('Selected vertices are already evenly spaced')
    world_displacements = [
        ((matrix @ Vector(after)) - (matrix @ Vector(before))).length
        for _index, before, after in changed
    ]
    stamp = (
        mesh_snap_v086._native_selection_stamp(context, obj, 'LOCAL_CENTER'),
        precision_selection_v086._geometry_stamp(bm),
    )
    return {
        'scene': context.scene.name, 'scene_ptr': context.scene.as_pointer(),
        'layer': context.view_layer.name,
        'obj': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'axis': axis, 'space': space, 'stamp': stamp,
        'changes': changed, 'selected': len(source),
        'moving': len(changed), 'max_world_move': max(world_displacements),
        'span': span, 'step': increment,
    }


def _verify(context, proposal):
    if not isinstance(proposal, dict):
        raise ValueError('Even Spacing preview is missing')
    if plan(context, proposal['axis'], proposal['space']) != proposal:
        raise ValueError('Native mesh changed; preview Even Spacing again')
    return _source(context)


def _mutate(context, proposal):
    obj, bm, selected = _verify(context, proposal)
    affected = {face for vertex in selected for face in vertex.link_faces}
    before_faces = {}
    for face in affected:
        face.normal_update()
        area = float(face.calc_area())
        normal = face.normal.copy()
        if (not math.isfinite(area) or area <= 1e-12 or
                not all(math.isfinite(float(x)) for x in normal) or
                normal.length_squared <= 1e-12):
            raise ValueError('A connected face is degenerate before spacing')
        before_faces[face] = (area, normal)
    bm.verts.ensure_lookup_table()
    for index, old, new in proposal['changes']:
        vertex = bm.verts[index]
        if (not vertex.is_valid or vertex.hide or
                tuple(float(x) for x in vertex.co) != old):
            raise ValueError('An Even Spacing vertex changed during confirmation')
    for index, _old, new in proposal['changes']:
        bm.verts[index].co = Vector(new)
    for face, (previous_area, previous_normal) in before_faces.items():
        face.normal_update()
        area = float(face.calc_area())
        if (not math.isfinite(area) or area <= max(1e-12, previous_area * 0.20)
                or face.normal.dot(previous_normal) <= 0.5):
            raise ValueError('Spacing collapsed or reversed a connected face')
    return obj


def commit(context, proposal, history=None):
    obj, _bm, _selected = _verify(context, proposal)
    if history is not None:
        mesh.snapshot_and_push(obj, lambda: _mutate(context, proposal), history)
    else:
        # A desktop operator uses Blender's own Undo, with an additional
        # native edit-cage snapshot for failed multi-vertex updates.
        saved = mesh.snapshot(obj)
        try:
            _mutate(context, proposal)
            mesh.update(obj)
        except BaseException:
            try:
                mesh.restore(obj, saved)
            except Exception as exc:
                raise mesh.MeshRollbackFailure(
                    'Even Spacing restore failed; inspect native Blender mesh') from exc
            raise
        finally:
            mesh._dispose_temporary_meshes(saved)
    return proposal['moving']


class BXR_OT_even_spacing(bpy.types.Operator):
    bl_idname = 'blender_xr.even_mesh_spacing'
    bl_label = 'Preview and Confirm Native Even Vertex Spacing'
    bl_description = 'Space selected native vertices along X/Y/Z, keeping end anchors'
    bl_options = {'REGISTER', 'UNDO'}
    axis: EnumProperty(name='Axis',
                       items=[(a, a, 'Evenly space along ' + a) for a in 'XYZ'],
                       default='X')
    space: EnumProperty(name='Coordinates', items=(
        ('LOCAL', 'Local', 'Native mesh coordinate spacing'),
        ('WORLD', 'World', 'World-space spacing for transformed mesh objects'),
    ), default='LOCAL')
    _proposal = None

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH')

    def invoke(self, context, event):
        self._proposal = None
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Even Spacing wrist menu in headset')
            return {'CANCELLED'}
        try:
            self._proposal = plan(context, self.axis, self.space)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=390)

    def draw(self, context):
        if self._proposal is not None:
            self.layout.label(text='{} axis in {} space'.format(
                self._proposal['axis'], self._proposal['space']))
            self.layout.label(text='{} of {} selected vertices move'.format(
                self._proposal['moving'], self._proposal['selected']))
            self.layout.label(text='End anchors stay fixed; native Undo available')
            self.layout.label(text='Max world movement: {:.6g}'.format(
                self._proposal['max_world_move']))

    def execute(self, context):
        if (runtime.CURRENT is not None or self._proposal is None or
                self.axis != self._proposal['axis'] or
                self.space != self._proposal['space']):
            self.report({'WARNING'}, 'Preview the requested axis/space again')
            return {'CANCELLED'}
        try:
            count = commit(context, self._proposal)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self._proposal = None
        self.report({'INFO'}, 'Evenly spaced {} native Blender vertices'.format(count))
        return {'FINISHED'}


def install_pages():
    parent = mesh_snap_v086._PAGE
    entries = tuple(menus.PAGES[parent])
    if not entries or entries[-1][1] != 'BACK':
        raise ValueError('Snap Selected menu is unavailable')
    if not any(action == _ENTRY for _label, action in entries):
        entries = entries[:-1] + (('EVEN SPACING', _ENTRY), entries[-1])
    if len(entries) > 12:
        raise ValueError('Snap Selected menu cannot fit Even Spacing')
    menus.PAGES[parent] = entries
    menus.PAGES[_PAGE] = (
        ('SPACE X', 'XR_SPACING_X'),
        ('SPACE Y', 'XR_SPACING_Y'),
        ('SPACE Z', 'XR_SPACING_Z'),
        ('LOCAL', 'XR_SPACING_LOCAL'),
        ('WORLD', 'XR_SPACING_WORLD'),
        ('PREVIEW', _PREVIEW),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_CONFIRM_PAGE] = (
        ('SPACE VERTS', _COMMIT), ('KEEP MESH', _CANCEL), ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'NATIVE EVEN SPACING'
    menus.TITLES[_CONFIRM_PAGE] = 'CONFIRM EVEN SPACING'
    v065.TOOLTIPS.update({
        _ENTRY: ('Evenly Space Selected', 'Preview exact native vertex spacing with fixed endpoints'),
        _PREVIEW: ('Preview Even Spacing', 'Read-only movement and face distortion preflight'),
        _COMMIT: ('Confirm Even Spacing', 'Apply one guarded native edit-mesh Undo transaction'),
        _CANCEL: ('Keep Original Vertices', 'Discard the preview without changing mesh coordinates'),
        'XR_SPACING_LOCAL': ('Local Spacing', 'Space vertices in native mesh coordinates'),
        'XR_SPACING_WORLD': ('World Spacing', 'Space vertices in Blender world coordinates'),
    })
    for action, axis in _AXES.items():
        v065.TOOLTIPS[action] = ('Evenly Space ' + axis,
                                'Distribute distinct selected coordinates along ' + axis)


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_even_spacing_090_patched', False):
        return
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == mesh_snap_v086._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before Even Spacing')
            mesh_snap_v086._eligible(context)
            self._xr_even_spacing_pending = None
            self.menu.page = _PAGE
            self.status = 'EVEN SPACING / CHOOSE LOCAL OR WORLD AND AXIS'
            return
        if page == _PAGE:
            if action == 'BACK':
                self._xr_even_spacing_pending = None
                self.menu.page = mesh_snap_v086._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controller gesture before spacing preview')
            if action in _AXES:
                self._xr_even_spacing_axis = _AXES[action]
                self._xr_even_spacing_pending = None
                self.status = 'EVEN SPACING AXIS / ' + _AXES[action]
                return
            if action in _SPACES:
                self._xr_even_spacing_space = _SPACES[action]
                self._xr_even_spacing_pending = None
                self.status = 'EVEN SPACING SPACE / ' + _SPACES[action]
                return
            if action != _PREVIEW:
                raise ValueError('Choose an axis, space, Preview or Back')
            proposal = plan(context,
                            getattr(self, '_xr_even_spacing_axis', 'X'),
                            getattr(self, '_xr_even_spacing_space', 'LOCAL'))
            self._xr_even_spacing_pending = proposal
            self.menu.page = _CONFIRM_PAGE
            self.status = 'EVEN SPACING / {} VERTS / MAX {:.5g} / CONFIRM'.format(
                proposal['moving'], proposal['max_world_move'])
            return
        if page == _CONFIRM_PAGE:
            if action in {_CANCEL, 'BACK'}:
                self._xr_even_spacing_pending = None
                self.menu.page = _PAGE
                self.status = 'EVEN SPACING CANCELLED / NATIVE MESH UNCHANGED'
                return
            if action != _COMMIT:
                raise ValueError('Confirm or cancel native Even Spacing')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before applying spacing')
            pending = getattr(self, '_xr_even_spacing_pending', None)
            if pending is None:
                raise ValueError('Even Spacing approval expired; preview again')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('Native XR mesh history required for spacing')
            count = commit(context, pending, history)
            self._xr_even_spacing_pending = None
            self._xr_precision_last_ray = None
            self.menu.page = _PAGE
            self.status = 'EVEN SPACING / {} VERTS / XR UNDO READY'.format(count)
            return
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_even_spacing_090_patched = True


CLASSES = (BXR_OT_even_spacing,)
