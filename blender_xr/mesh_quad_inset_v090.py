# SPDX-License-Identifier: GPL-3.0-or-later
"""Preview-confirm a conservative native inset of one selected Blender quad.

One selected planar, convex four-sided face is inset at fixed local distances.
Blender interpolates new loop data. The original artist-authored object and
mesh remain native, while the established mesh snapshot owns XR Undo/Redo.
"""
import math

import bpy
import bmesh

from . import (input_ownership_v080, menus, mesh, mesh_axis_snap_v090,
               mesh_selection_tools_v086, mesh_select_similar_v090,
               mesh_weld_preview_v090, runtime, selection, v065)

_PAGE = 'XR_QUAD_INSET_090'
_CONFIRM_PAGE = 'XR_QUAD_INSET_CONFIRM_090'
_ENTRY = 'XR_QUAD_INSET_MENU'
_PREVIEW = 'XR_QUAD_INSET_PREVIEW'
_COMMIT = 'XR_QUAD_INSET_COMMIT'
_CANCEL = 'XR_QUAD_INSET_CANCEL'
_DISTANCES = {
    'XR_QUAD_INSET_TINY': 0.001,
    'XR_QUAD_INSET_SMALL': 0.01,
    'XR_QUAD_INSET_MEDIUM': 0.05,
}
_MAX_FACES = 150000


def _eligible(context):
    obj = mesh_selection_tools_v086._editable(context)
    if selection.mode(context) != 'FACE':
        raise ValueError('Select Face Mode and exactly one native quad')
    if (obj.library or obj.override_library or obj.data.library or
            obj.data.override_library or obj.data.users != 1 or
            obj.data.shape_keys is not None):
        raise ValueError('Native quad inset requires a local single-user mesh without shape keys')
    bm, faces = mesh_selection_tools_v086._current(obj, 'FACE')
    if len(bm.faces) > _MAX_FACES:
        raise ValueError('Quad inset supports up to 150,000 faces')
    selected = tuple(face for face in faces
                     if face.is_valid and face.select and not face.hide)
    if len(selected) != 1 or len(selected[0].verts) != 4:
        raise ValueError('Select exactly one visible native quad')
    return obj, bm, selected[0]


def _measure(face):
    points = [vertex.co.copy() for vertex in face.verts]
    if any(not all(math.isfinite(float(v)) for v in p) for p in points):
        raise ValueError('The selected quad contains invalid coordinates')
    lengths = [(points[(i + 1) % 4] - points[i]).length for i in range(4)]
    if min(lengths) <= 1e-8 or face.calc_area() <= 1e-12:
        raise ValueError('Cannot inset a degenerate quad')
    normal = (points[1] - points[0]).cross(points[2] - points[0])
    if normal.length_squared <= 1e-16:
        raise ValueError('Quad has an invalid reference plane')
    normal.normalize()
    if max(abs(float((p - points[0]).dot(normal))) for p in points) > max(
            1e-6, min(lengths) * 0.02):
        raise ValueError('Quad is not planar enough for a safe single inset')
    bends = []
    for i in range(4):
        incoming = points[i] - points[i-1]
        outgoing = points[(i+1) % 4] - points[i]
        signed = float(incoming.cross(outgoing).dot(normal))
        if abs(signed) <= 1e-10 * min(lengths) ** 2:
            raise ValueError('Selected quad has a collinear corner')
        bends.append(signed > 0)
    if len(set(bends)) != 1:
        raise ValueError('Inset would affect a concave or crossed quad')
    return min(lengths)


def _uv_stamp(obj, bm, face):
    stamps = []
    for layer in obj.data.uv_layers:
        bm_layer = bm.loops.layers.uv.get(layer.name)
        if bm_layer is None:
            raise ValueError('Native Blender UV map is inaccessible')
        coords = tuple(tuple(float(v) for v in loop[bm_layer].uv)
                       for loop in face.loops)
        if any(not all(math.isfinite(v) for v in pair) for pair in coords):
            raise ValueError('Selected native UV coordinates are invalid')
        stamps.append((layer.name, coords))
    return tuple(stamps)


def plan(context, distance):
    if not math.isfinite(distance) or distance <= 0:
        raise ValueError('Choose a positive native inset distance')
    obj, bm, face = _eligible(context)
    shortest = _measure(face)
    if distance > shortest * 0.20:
        raise ValueError('Inset exceeds 20% of the shortest quad edge')
    signature = (
        mesh_selection_tools_v086._topology(bm),
        mesh_weld_preview_v090._geometry_stamp(bm),
        mesh_axis_snap_v090._matrix_stamp(obj.matrix_world),
        face.index,
        tuple(vertex.index for vertex in face.verts),
        int(face.material_index), bool(face.smooth),
        _uv_stamp(obj, bm, face),
    )
    return {
        'scene': context.scene.name, 'scene_ptr': context.scene.as_pointer(),
        'layer': context.view_layer.name,
        'obj': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'signature': signature,
        'distance': distance, 'faces': len(bm.faces),
        'edges': len(bm.edges), 'verts': len(bm.verts),
        'uv_maps': len(obj.data.uv_layers),
    }


def _verify(context, proposal):
    fresh = plan(context, proposal['distance'])
    if fresh != proposal:
        raise ValueError('Selected native quad changed; preview the inset again')
    return _eligible(context)


def _mutate(context, proposal):
    obj, bm, face = _verify(context, proposal)
    old_verts = set(bm.verts)
    original_vertices = set(face.verts)
    original_edges = set(face.edges)
    original_normal = face.normal.copy()
    uv_layers = tuple(bm.loops.layers.uv.get(layer.name)
                      for layer in obj.data.uv_layers)
    if any(layer is None for layer in uv_layers):
        raise ValueError('Native UV layer became unavailable before inset')
    result = bmesh.ops.inset_individual(
        bm, faces=[face], thickness=proposal['distance'], depth=0.0,
        use_even_offset=True, use_interpolate=True, use_relative_offset=False)
    new_verts = set(bm.verts).difference(old_verts)
    if (len(bm.faces) != proposal['faces'] + 4 or
            len(bm.verts) != proposal['verts'] + 4 or
            len(bm.edges) != proposal['edges'] + 8 or
            len(new_verts) != 4):
        raise ValueError('Blender inset did not create the expected five-quad patch')
    patch = tuple(face for face in bm.faces
                  if face.is_valid and any(v in new_verts for v in face.verts))
    if len(patch) != 5:
        raise ValueError('Native inset patch did not produce five faces')
    if any(len(face.verts) != 4 or not math.isfinite(float(face.calc_area()))
           or face.calc_area() <= 1e-12 for face in patch):
        raise ValueError('Blender produced a triangle or degenerate inset face')
    if any(item not in bm.faces or not item.is_valid
           for item in result.get('faces', ())):
        raise ValueError('Blender inset returned an unavailable face')
    # A safe inset must retain the four source corners and perimeter edges.
    # Reject unexpected rewiring, duplicated centre faces, or inverted quads.
    if (any(not vertex.is_valid for vertex in original_vertices) or
            any(not edge.is_valid for edge in original_edges)):
        raise ValueError('Inset unexpectedly removed original boundary geometry')
    centres = [item for item in patch
               if all(vertex in new_verts for vertex in item.verts)]
    if len(centres) != 1:
        raise ValueError('Inset did not create exactly one inner quad')
    sides = [item for item in patch if item not in centres]
    if (len(sides) != 4 or
            any(len(set(item.verts) & original_vertices) != 2 or
                len(set(item.verts) & new_verts) != 2 for item in sides)):
        raise ValueError('Inset side faces do not match the original quad')
    if any(not any(edge in item.edges for item in sides)
           for edge in original_edges):
        raise ValueError('Inset lost an original perimeter edge')
    for item in patch:
        item.normal_update()
        if item.normal.dot(original_normal) <= 0:
            raise ValueError('Inset created a reversed or invalid quad normal')
        for loop in item.loops:
            for layer in uv_layers:
                if not all(math.isfinite(float(value))
                           for value in loop[layer].uv):
                    raise ValueError('Inset generated non-finite UV coordinates')
    return obj


def commit(context, proposal, history=None):
    obj, _bm, _face = _verify(context, proposal)
    if history is not None:
        mesh.snapshot_and_push(obj, lambda: _mutate(context, proposal), history)
    else:
        saved = mesh.snapshot(obj)
        try:
            _mutate(context, proposal)
            mesh.update(obj)
        except Exception:
            mesh.restore(obj, saved)
            raise
        finally:
            if saved.name in bpy.data.meshes:
                bpy.data.meshes.remove(saved)
    return proposal['faces'] + 4


class BXR_OT_quad_inset(bpy.types.Operator):
    bl_idname = 'blender_xr.quad_inset'
    bl_label = 'Preview and Confirm Native Quad Inset'
    bl_description = 'Inset one selected compatible Blender quad after preview'
    bl_options = {'REGISTER', 'UNDO'}
    distance: bpy.props.FloatProperty(
        name='Local Inset Distance', default=0.01,
        min=0.0001, max=0.1, precision=4)
    _proposal = None

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH')

    def invoke(self, context, event):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Quad Inset menu in the headset')
            return {'CANCELLED'}
        try:
            self._proposal = plan(context, self.distance)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        self.layout.label(text='One quad becomes a five-quad native patch')
        self.layout.label(text='Inset distance {:.4f} local units'.format(
            self._proposal['distance'] if self._proposal else 0))
        self.layout.label(text='Blender interpolates newly-created UV loops')

    def execute(self, context):
        if runtime.CURRENT is not None or self._proposal is None:
            self.report({'WARNING'}, 'Open a new inset preview before confirming')
            return {'CANCELLED'}
        try:
            if abs(self.distance - self._proposal['distance']) > 1e-9:
                raise ValueError('Inset distance changed; preview again')
            faces = commit(context, self._proposal)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Inset committed / {} native faces'.format(faces))
        return {'FINISHED'}


def install_pages():
    parent = mesh_select_similar_v090._DIAGNOSTICS
    current = tuple(menus.PAGES[parent])
    if not current or current[-1][1] != 'BACK':
        raise ValueError('Mesh Diagnostics menu unavailable')
    if not any(action == _ENTRY for _label, action in current):
        current = current[:-1] + (('QUAD INSET', _ENTRY), current[-1])
    if len(current) > 12:
        raise ValueError('Mesh Diagnostics has no capacity for native quad inset')
    menus.PAGES[parent] = current
    menus.PAGES[_PAGE] = (
        ('DIST .001', 'XR_QUAD_INSET_TINY'),
        ('DIST .01', 'XR_QUAD_INSET_SMALL'),
        ('DIST .05', 'XR_QUAD_INSET_MEDIUM'),
        ('PREVIEW', _PREVIEW),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_CONFIRM_PAGE] = (
        ('MAKE INSET', _COMMIT), ('KEEP QUAD', _CANCEL), ('BACK', 'BACK'))
    menus.TITLES[_PAGE] = 'SINGLE QUAD INSET'
    menus.TITLES[_CONFIRM_PAGE] = 'CONFIRM QUAD INSET'
    v065.TOOLTIPS.update({
        _ENTRY: ('Inset One Native Quad',
                 'Preview a bounded inset of one selected convex planar quad'),
        _PREVIEW: ('Preview Single Quad Inset',
                   'Check selected quad, UVs and native topology without editing'),
        _COMMIT: ('Confirm Native Quad Inset',
                  'Turn one quad into a five-quad patch with XR Undo'),
        _CANCEL: ('Keep Existing Quad',
                  'Cancel without changing native Blender geometry'),
    })
    for action, distance in _DISTANCES.items():
        v065.TOOLTIPS[action] = (
            'Inset {:.3f}'.format(distance),
            'Use a local Blender-unit inset distance before Preview')


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_single_quad_inset_090_patched', False):
        return
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        page = getattr(menu, 'page', None)
        if page == mesh_select_similar_v090._DIAGNOSTICS and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before Quad Inset')
            _eligible(context)
            self._xr_quad_inset_pending = None
            menu.page = _PAGE
            self.status = 'INSET QUAD / CHOOSE DISTANCE AND PREVIEW'
            return
        if page == _PAGE:
            if action == 'BACK':
                self._xr_quad_inset_pending = None
                menu.page = mesh_select_similar_v090._DIAGNOSTICS
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before Inset Preview')
            if action in _DISTANCES:
                self._xr_quad_inset_distance = _DISTANCES[action]
                self._xr_quad_inset_pending = None
                self.status = 'QUAD INSET / LOCAL {:.3f}'.format(
                    self._xr_quad_inset_distance)
                return
            if action == _PREVIEW:
                distance = float(getattr(self, '_xr_quad_inset_distance', 0.01))
                proposal = plan(context, distance)
                self._xr_quad_inset_pending = proposal
                menu.page = _CONFIRM_PAGE
                self.status = 'INSET PREVIEW / 1 QUAD → 5 QUADS / CONFIRM?'
                return
            raise ValueError('Choose inset distance, Preview or Back')
        if page == _CONFIRM_PAGE:
            if action in {_CANCEL, 'BACK'}:
                self._xr_quad_inset_pending = None
                menu.page = _PAGE
                self.status = 'QUAD INSET CANCELLED / NO CHANGE'
                return
            if action != _COMMIT:
                raise ValueError('Confirm or cancel native Quad Inset')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controllers before Quad Inset')
            proposal = getattr(self, '_xr_quad_inset_pending', None)
            if proposal is None:
                raise ValueError('Quad inset approval expired; preview again')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('XR Undo history required for Quad Inset')
            count = commit(context, proposal, history)
            self._xr_quad_inset_pending = None
            menu.page = _PAGE
            self._xr_precision_last_ray = None
            self.status = 'QUAD INSET / {} FACES / XR UNDO READY'.format(count)
            return
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_single_quad_inset_090_patched = True


CLASSES = (BXR_OT_quad_inset,)
