# SPDX-License-Identifier: GPL-3.0-or-later
"""Preview and explicitly confirm native Blender selected-vertex welding.

Preview is read-only: bmesh.ops.find_doubles returns a targetmap but does not
mutate the mesh. A separate confirmation validates the exact same selected
mesh, geometry and targetmap and commits Blender's weld_verts operator in one
existing XR MESH snapshot transaction. No automatic cleanup or mesh copies.
"""
import hashlib
import math
import struct

import bpy
import bmesh
from bpy.props import FloatProperty

from . import (input_ownership_v080, menus, mesh, mesh_selection_tools_v086,
               mesh_select_similar_v090, runtime, selection, v065)

_PAGE = 'XR_WELD_PREVIEW_090'
_CONFIRM = 'XR_WELD_CONFIRM_090'
_ENTRY = 'XR_WELD_MENU'
_OPEN = 'XR_WELD_PREVIEW'
_APPROVE = 'XR_WELD_APPROVE'
_CANCEL = 'XR_WELD_CANCEL'
_TOLERANCES = {
    'XR_WELD_TINY': 0.0001,
    'XR_WELD_SMALL': 0.001,
    'XR_WELD_MEDIUM': 0.005,
}
_MAX_SELECTED = 20000
_MAX_TOTAL = 150000


def _editable(context):
    obj = mesh_selection_tools_v086._editable(context)
    if obj.data.users != 1 or obj.data.shape_keys is not None:
        raise ValueError('Welding requires a local, single-user mesh without shape keys')
    return obj


def _geometry_stamp(bm):
    """Bounded all-vertex coordinate fingerprint, not just element counts."""
    digest = hashlib.blake2b(digest_size=16)
    if len(bm.verts) > _MAX_TOTAL:
        raise ValueError('Weld preview supports meshes up to 150,000 vertices')
    for vert in bm.verts:
        if any(not math.isfinite(float(x)) for x in vert.co):
            raise ValueError('Mesh contains non-finite vertex coordinates')
        digest.update(struct.pack('<ddd', *(float(x) for x in vert.co)))
    return digest.digest()


def _selection(context, obj):
    mode = selection.mode(context)
    bm, items = mesh_selection_tools_v086._current(obj, mode)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    verts = tuple(sorted(mesh.selected_transform_vertices(obj, mode),
                         key=lambda v: v.index))
    if (len(verts) < 2 or len(verts) > _MAX_SELECTED or
            any(not v.is_valid or v.hide for v in verts)):
        raise ValueError('Select between 2 and 20,000 visible vertices')
    return bm, items, mode, verts


def _find_map(bm, verts, distance):
    """Native Blender read-only weld projection; safe for a preview screen."""
    result = bmesh.ops.find_doubles(bm, verts=list(verts), dist=distance)
    pairs = tuple(sorted(
        (source.index, target.index)
        for source, target in result['targetmap'].items()
        if source.is_valid and target.is_valid and source != target
    ))
    selected_indices = frozenset(v.index for v in verts)
    if any(src not in selected_indices or dst not in selected_indices
           for src, dst in pairs):
        raise ValueError('Native weld proposal referenced an unselected vertex')
    sources = {source for source, target in pairs}
    if len(sources) != len(pairs) or any(target in sources for _src, target in pairs):
        raise ValueError('Ambiguous chained Blender weld target mapping')
    return pairs


def _degenerate_faces(bm, pairs):
    """Refuse any weld that would lower an existing face's vertex count.

    In particular, a selected quad must never silently turn into a triangle,
    and an existing triangle must never collapse to a line.
    """
    targets = dict(pairs)
    for face in bm.faces:
        if any(vert.index in targets for vert in face.verts):
            if len({targets.get(v.index, v.index) for v in face.verts}) < len(face.verts):
                return True
    return False


def _plan(context, distance):
    if not math.isfinite(distance) or not 0.00001 <= distance <= 0.05:
        raise ValueError('Use a Blender-local weld distance between 0.00001 and 0.05')
    obj = _editable(context)
    bm, items, mode, vertices = _selection(context, obj)
    topology = mesh_selection_tools_v086._topology(bm)
    stamp = _geometry_stamp(bm)
    indices = tuple(v.index for v in vertices)
    pairs = _find_map(bm, vertices, distance)
    if not pairs:
        raise ValueError('No selected duplicate vertices within this distance')
    if _degenerate_faces(bm, pairs):
        raise ValueError('Weld would reduce face sides; inspect geometry in Blender first')
    return {
        'scene': context.scene.name, 'layer': context.view_layer.name,
        'obj': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'mode': mode, 'selected': indices,
        'topology': topology, 'coords': stamp, 'distance': distance,
        'pairs': pairs, 'candidates': len(pairs),
    }


def _verify(context, plan):
    obj = _editable(context)
    if (context.scene.name != plan['scene'] or
            context.view_layer.name != plan['layer'] or
            obj.name != plan['obj'] or obj.as_pointer() != plan['obj_ptr'] or
            obj.data.name != plan['mesh'] or
            obj.data.as_pointer() != plan['mesh_ptr'] or
            selection.mode(context) != plan['mode']):
        raise ValueError('Weld target, scene or selection mode changed since preview')
    bm, items, mode, vertices = _selection(context, obj)
    if (mesh_selection_tools_v086._topology(bm) != plan['topology'] or
            _geometry_stamp(bm) != plan['coords'] or
            tuple(v.index for v in vertices) != plan['selected']):
        raise ValueError('Native mesh geometry or selection changed since preview')
    pairs = _find_map(bm, vertices, plan['distance'])
    if pairs != plan['pairs'] or _degenerate_faces(bm, pairs):
        raise ValueError('Native weld proposal changed since preview')
    return obj, bm, pairs


def _mutate(context, plan):
    obj, bm, pairs = _verify(context, plan)
    bm.verts.ensure_lookup_table()
    targetmap = {bm.verts[src]: bm.verts[dst] for src, dst in pairs}
    bmesh.ops.weld_verts(bm, targetmap=targetmap)
    return obj


def _commit(session, context, plan):
    history = getattr(session, 'history', None)
    if history is None:
        raise ValueError('XR Undo history required before welding geometry')
    if input_ownership_v080.is_editing(session):
        raise ValueError('Release controller gesture before committing weld')
    obj, bm, pairs = _verify(context, plan)
    mesh.snapshot_and_push(obj, lambda: _mutate(context, plan), history)
    session._xr_weld_pending = None
    session.menu.page = mesh_select_similar_v090._DIAGNOSTICS
    session._xr_precision_last_ray = None
    session.status = 'WELD COMMITTED / {} VERTEX CANDIDATES / XR UNDO READY'.format(
        plan['candidates'])


class BXR_OT_preview_weld(bpy.types.Operator):
    bl_idname = 'blender_xr.preview_weld'
    bl_label = 'Preview and Confirm Native Vertex Weld'
    bl_description = 'Preview nearby selected vertices before confirming one native Blender weld'
    bl_options = {'REGISTER', 'UNDO'}

    distance: FloatProperty(name='Local Weld Distance', default=0.001,
                            min=0.00001, max=0.05, precision=5)
    _preview = None

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH')

    def invoke(self, context, event):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use XR Diagnostics → Weld Preview while in VR')
            return {'CANCELLED'}
        try:
            self._preview = _plan(context, self.distance)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=375)

    def draw(self, context):
        layout = self.layout
        plan = self._preview
        layout.label(text='Selected duplicate candidates: {}'.format(
            plan['candidates'] if plan else 'not previewed'), icon='INFO')
        layout.label(text='Welding may change UV seams and vertex attributes.')
        layout.label(text='Confirm only after inspecting the selected geometry.')

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR wrist Weld confirmation instead')
            return {'CANCELLED'}
        try:
            plan = self._preview
            if plan is None:
                raise ValueError('Open the Weld Preview dialog before committing')
            if abs(self.distance - plan['distance']) > 1e-12:
                raise ValueError('Weld distance changed; open a fresh preview')
            obj, _bm, _pairs = _verify(context, plan)
            # Desktop Blender's REGISTER/UNDO owns this edit. Retain an
            # explicit native pre-edit snapshot until the mesh update succeeds
            # to restore the original selection/topology on a failed update.
            before = mesh.snapshot(obj)
            try:
                _mutate(context, plan)
                mesh.update(obj)
            except Exception:
                mesh.restore(obj, before)
                raise
            finally:
                if before.name in bpy.data.meshes:
                    bpy.data.meshes.remove(before)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Welded {} selected duplicate candidates'.format(
            plan['candidates']))
        return {'FINISHED'}


def install_pages():
    parent = mesh_select_similar_v090._DIAGNOSTICS
    previous = tuple(menus.PAGES[parent])
    if not previous or previous[-1][1] != 'BACK':
        raise ValueError('Existing Mesh Diagnostics page is unavailable')
    if not any(action == _ENTRY for _label, action in previous):
        previous = previous[:-1] + (('WELD PREVIEW', _ENTRY),
                                    previous[-1])
    if len(previous) > 12:
        raise ValueError('Mesh Diagnostics has no room for Weld Preview')
    menus.PAGES[parent] = previous
    menus.PAGES[_PAGE] = (
        ('DIST 0.0001', 'XR_WELD_TINY'),
        ('DIST 0.001', 'XR_WELD_SMALL'),
        ('DIST 0.005', 'XR_WELD_MEDIUM'),
        ('PREVIEW', _OPEN),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_CONFIRM] = (
        ('CONFIRM WELD', _APPROVE),
        ('CANCEL', _CANCEL),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'NATIVE WELD PREVIEW'
    menus.TITLES[_CONFIRM] = 'WELD VERTICES?'
    v065.TOOLTIPS.update({
        _ENTRY: ('Preview Mesh Vertex Weld',
                 'Review close selected vertices without modifying the mesh'),
        _OPEN: ('Preview Weld Candidates',
                'Find Blender native duplicate vertices without touching geometry'),
        _APPROVE: ('Confirm Native Weld',
                   'Explicitly merge the previewed selected vertices with XR Undo'),
        _CANCEL: ('Keep Original Geometry',
                  'Cancel without changing the Blender mesh'),
    })
    for action, distance in _TOLERANCES.items():
        v065.TOOLTIPS[action] = (
            'Weld distance {:.4f}'.format(distance),
            'Set a distance in mesh-local Blender units, then select Preview')


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_native_weld_preview_090_patched', False):
        return
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        page = getattr(menu, 'page', None)
        if action == _ENTRY and page == mesh_select_similar_v090._DIAGNOSTICS:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gestures before mesh repair')
            _editable(context)
            menu.page = _PAGE
            self.status = 'WELD PREVIEW / DISTANCE AND PREVIEW FIRST'
            return
        if page == _PAGE:
            if action == 'BACK':
                self._xr_weld_pending = None
                menu.page = mesh_select_similar_v090._DIAGNOSTICS
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gestures before inspecting mesh repair')
            if action in _TOLERANCES:
                self._xr_weld_distance = _TOLERANCES[action]
                self._xr_weld_pending = None
                self.status = 'WELD DISTANCE / LOCAL {:.4f}'.format(
                    self._xr_weld_distance)
                return
            if action == _OPEN:
                distance = float(getattr(self, '_xr_weld_distance', 0.001))
                plan = _plan(context, distance)
                self._xr_weld_pending = plan
                menu.page = _CONFIRM
                self.status = ('WELD PREVIEW / {} CANDIDATES / MAY AFFECT UVS / '
                               'CONFIRM OR CANCEL').format(plan['candidates'])
                return
            raise ValueError('Choose weld distance, Preview or Back')
        if page == _CONFIRM:
            if action in {_CANCEL, 'BACK'}:
                self._xr_weld_pending = None
                menu.page = _PAGE
                self.status = 'WELD CANCELLED / NO BLENDER DATA CHANGED'
                return
            if action != _APPROVE:
                raise ValueError('Confirm or cancel the reviewed vertex weld')
            plan = getattr(self, '_xr_weld_pending', None)
            if plan is None:
                raise ValueError('Weld preview expired; preview again')
            return _commit(self, context, plan)
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_native_weld_preview_090_patched = True


CLASSES = (BXR_OT_preview_weld,)
