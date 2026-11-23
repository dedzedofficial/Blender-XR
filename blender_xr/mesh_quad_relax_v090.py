# SPDX-License-Identifier: GPL-3.0-or-later
"""Guarded native quad-patch interior relaxation for Blender XR.

Preview is read-only. Only fully enclosed, regular four-quad vertices move.
Patch boundaries, poles, seam/sharp edges, UV loops, weights and topology
remain untouched. Confirmation writes native BMesh coordinates through the
existing XR mesh-snapshot Undo/Redo transaction.
"""
import math

import bpy
from bpy.props import EnumProperty
from mathutils import Vector

from . import (input_ownership_v080, menus, mesh, mesh_axis_snap_v090,
               mesh_quad_quality_v090, mesh_selection_tools_v086,
               mesh_weld_preview_v090, runtime, v065)

_PAGE = 'XR_QUAD_RELAX_090'
_CONFIRM_PAGE = 'XR_QUAD_RELAX_CONFIRM_090'
_ENTRY = 'XR_QUAD_RELAX_MENU'
_PREVIEW = 'XR_QUAD_RELAX_PREVIEW'
_COMMIT = 'XR_QUAD_RELAX_COMMIT'
_CANCEL = 'XR_QUAD_RELAX_CANCEL'
_PRESETS = {'XR_QUAD_RELAX_GENTLE': (0.25, 0.05),
            'XR_QUAD_RELAX_MEDIUM': (0.50, 0.10),
            'XR_QUAD_RELAX_STRONG': (0.75, 0.15)}
_MAX_MESH_VERTICES = 150000
_MAX_SELECTED_FACES = 30000
_MAX_CANDIDATES = 10000
_EPS = 1e-12


def _source(context):
    obj = mesh_selection_tools_v086._editable(context)
    if (obj.library or obj.override_library or obj.data.library or
            obj.data.override_library or obj.data.users != 1 or
            obj.data.shape_keys is not None):
        raise ValueError('Quad relaxation requires a local single-user mesh without shape keys')
    if context.mode != 'EDIT_MESH' or not context.tool_settings.mesh_select_mode[2]:
        raise ValueError('Select the quad patch in Face Select Mode')
    bm, faces = mesh_selection_tools_v086._current(obj, 'FACE')
    if len(bm.verts) > _MAX_MESH_VERTICES:
        raise ValueError('Quad Relax supports meshes up to 150,000 vertices')
    selected = tuple(face for face in faces
                     if face.is_valid and face.select and not face.hide)
    if not 4 <= len(selected) <= _MAX_SELECTED_FACES:
        raise ValueError('Select between 4 and 30,000 visible quads')
    if any(len(face.verts) != 4 for face in selected):
        raise ValueError('Only existing native quads may enter a relax patch')
    if any(not math.isfinite(float(c)) for face in selected
           for vert in face.verts for c in vert.co):
        raise ValueError('Patch vertices contain non-finite coordinates')
    return obj, bm, selected


def _interior(selected, bm):
    selected_set = set(selected)
    verts = {vert for face in selected for vert in face.verts}
    candidates = []
    for vert in sorted(verts, key=lambda v: v.index):
        if not vert.is_valid or vert.hide:
            continue
        linked_faces = tuple(vert.link_faces)
        linked_edges = tuple(vert.link_edges)
        # Fully enclosed regular quad valence-4 fan. Exclude boundary,
        # poles, UV seams and sharp borders even when their faces were picked.
        if (len(linked_faces) != 4 or len(linked_edges) != 4 or
                any(face not in selected_set or face.hide or
                    len(face.verts) != 4 for face in linked_faces) or
                any(not edge.is_valid or edge.hide or edge.seam or
                    not edge.smooth or not edge.is_manifold for edge in linked_edges)):
            continue
        candidates.append(vert)
    if not candidates or len(candidates) > _MAX_CANDIDATES:
        raise ValueError('Select a patch with 1–10,000 fully enclosed regular quad vertices')
    return candidates


def _targets(selected, bm, preset):
    factor, max_ratio = _PRESETS[preset]
    candidates = _interior(selected, bm)
    moved = []
    for vert in candidates:
        edges = tuple(vert.link_edges)
        neighbor = tuple(edge.other_vert(vert) for edge in edges)
        shortest = min((other.co - vert.co).length for other in neighbor)
        if shortest <= 1e-9:
            raise ValueError('Selected patch has a degenerate interior edge')
        avg = sum((other.co for other in neighbor),
                  Vector((0.0, 0.0, 0.0))) / len(neighbor)
        delta = (avg - vert.co) * factor
        if not all(math.isfinite(float(v)) for v in delta):
            raise ValueError('Quad Relax would produce a non-finite coordinate')
        # Hard displacement bound relative to local edge size. Never move
        # any vertex more than 5/10/15 percent of its shortest linked edge.
        bound = shortest * max_ratio
        if delta.length > bound:
            delta = delta.normalized() * bound
        if delta.length <= max(1e-10, shortest * 1e-7):
            continue
        old = tuple(float(c) for c in vert.co)
        dest = tuple(float(c) for c in vert.co + delta)
        if not all(math.isfinite(v) for v in dest):
            raise ValueError('Quad Relax displacement is invalid')
        moved.append((vert.index, old, dest))
    if not moved:
        raise ValueError('Quad-patch interior is already relaxed at this precision')
    return tuple(moved), len(candidates)


def plan(context, preset='XR_QUAD_RELAX_GENTLE'):
    if preset not in _PRESETS:
        raise ValueError('Choose Gentle, Medium or Strong Quad Relax')
    obj, bm, faces = _source(context)
    changes, candidate_count = _targets(faces, bm, preset)
    relevant = {face for index, _old, _dest in changes
                for face in bm.verts[index].link_faces}
    if any(face.hide or not face.is_valid for face in relevant):
        raise ValueError('Moving this quad patch would affect hidden geometry')
    # The complete native mesh position/connectivity signatures disallow
    # stale previews after another Blender editor changed the geometry.
    stamp = (
        mesh_selection_tools_v086._topology(bm),
        mesh_weld_preview_v090._geometry_stamp(bm),
        mesh_axis_snap_v090._matrix_stamp(obj.matrix_world),
        tuple(face.index for face in faces),
        tuple(sorted((face.index, int(face.material_index), bool(face.smooth))
                     for face in relevant)),
    )
    return {
        'scene': context.scene.name, 'scene_ptr': context.scene.as_pointer(),
        'layer': context.view_layer.name,
        'obj': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'stamp': stamp, 'preset': preset, 'changes': changes,
        'candidates': candidate_count, 'moving': len(changes),
        'faces': len(faces),
        'max_move': max((Vector(after) - Vector(before)).length
                        for _index, before, after in changes),
    }


def _verify(context, proposal):
    if plan(context, proposal['preset']) != proposal:
        raise ValueError('Quad Relax source changed: open a new preview')
    obj, bm, _selected = _source(context)
    return obj, bm


def _mutate(context, proposal):
    obj, bm = _verify(context, proposal)
    affected = {face for index, _before, _after in proposal['changes']
                for face in bm.verts[index].link_faces}
    previous = {}
    for face in affected:
        face.normal_update()
        area = float(face.calc_area())
        if (not math.isfinite(area) or area <= _EPS or
                not all(math.isfinite(float(x)) for x in face.normal)):
            raise ValueError('Quad Relax has a degenerate affected face')
        previous[face] = (area, face.normal.copy())
    for index, before, after in proposal['changes']:
        vert = bm.verts[index]
        if tuple(float(v) for v in vert.co) != before:
            raise ValueError('Quad Relax source vertex changed after preview')
        vert.co = Vector(after)
    for face, (area, normal) in previous.items():
        face.normal_update()
        current_area = float(face.calc_area())
        if (not math.isfinite(current_area) or current_area < area * 0.5 or
                face.normal.dot(normal) < 0.70):
            raise ValueError('Quad Relax would invert or collapse an adjacent face')
        for vert in face.verts:
            if not all(math.isfinite(float(v)) for v in vert.co):
                raise ValueError('Quad Relax created invalid native coordinates')
    return obj


def commit(context, proposal, history=None):
    obj, _bm = _verify(context, proposal)
    if history is not None:
        mesh.snapshot_and_push(obj, lambda: _mutate(context, proposal), history)
    else:
        saved = mesh.snapshot(obj)
        try:
            _mutate(context, proposal)
            mesh.update(obj)
        except BaseException:
            try:
                mesh.restore(obj, saved)
            except Exception as exc:
                raise mesh.MeshRollbackFailure(
                    'Native Quad Relax restore failed; inspect the mesh') from exc
            raise
        finally:
            mesh._dispose_temporary_meshes(saved)
    return proposal['moving']


class BXR_OT_quad_relax(bpy.types.Operator):
    bl_idname = 'blender_xr.quad_relax'
    bl_label = 'Preview and Confirm Native Interior Quad Relax'
    bl_description = 'Smooth fully enclosed quad interior vertices without moving the patch boundary'
    bl_options = {'REGISTER', 'UNDO'}
    preset: EnumProperty(
        name='Relax Strength',
        items=(('XR_QUAD_RELAX_GENTLE', 'Gentle', '25% Laplacian, 5% edge cap'),
               ('XR_QUAD_RELAX_MEDIUM', 'Medium', '50% Laplacian, 10% edge cap'),
               ('XR_QUAD_RELAX_STRONG', 'Strong', '75% Laplacian, 15% edge cap')),
        default='XR_QUAD_RELAX_GENTLE')
    _proposal = None

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and context.mode == 'EDIT_MESH'
                    and context.tool_settings.mesh_select_mode[2])

    def invoke(self, context, event):
        self._proposal = None
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Quad Relax wrist confirmation')
            return {'CANCELLED'}
        try:
            self._proposal = plan(context, self.preset)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=390)

    def draw(self, context):
        if self._proposal:
            p = self._proposal
            self.layout.label(text='Selected quads: {}'.format(p['faces']))
            self.layout.label(text='Interior vertices moved: {}'.format(p['moving']))
            self.layout.label(text='Maximum local displacement: {:.6g}'.format(p['max_move']))
        self.layout.label(text='Patch boundary, poles, seams and hard edges stay fixed')

    def execute(self, context):
        if (runtime.CURRENT is not None or self._proposal is None or
                self.preset != self._proposal['preset']):
            self.report({'WARNING'}, 'Preview the chosen Quad Relax strength first')
            return {'CANCELLED'}
        try:
            changed = commit(context, self._proposal)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self._proposal = None
        self.report({'INFO'}, 'Relaxed {} interior native quad vertices'.format(changed))
        return {'FINISHED'}


def install_pages():
    parent = mesh_quad_quality_v090._PAGE
    buttons = tuple(menus.PAGES[parent])
    if not buttons or buttons[-1][1] != 'BACK':
        raise ValueError('Quad Quality wrist page unavailable')
    if not any(action == _ENTRY for _label, action in buttons):
        buttons = buttons[:-1] + (('RELAX QUADS', _ENTRY), buttons[-1])
    if len(buttons) > 12:
        raise ValueError('Quad Quality wrist page has no capacity for Relax')
    menus.PAGES[parent] = buttons
    menus.PAGES[_PAGE] = (
        ('GENTLE 5%', 'XR_QUAD_RELAX_GENTLE'),
        ('MEDIUM 10%', 'XR_QUAD_RELAX_MEDIUM'),
        ('STRONG 15%', 'XR_QUAD_RELAX_STRONG'),
        ('PREVIEW', _PREVIEW),
        ('BACK', 'BACK'))
    menus.PAGES[_CONFIRM_PAGE] = (
        ('APPLY RELAX', _COMMIT), ('KEEP MESH', _CANCEL), ('BACK', 'BACK'))
    menus.TITLES[_PAGE] = 'NATIVE QUAD RELAX'
    menus.TITLES[_CONFIRM_PAGE] = 'CONFIRM QUAD RELAX'
    v065.TOOLTIPS.update({
        _ENTRY: ('Relax Quad Patch', 'Smooth interior quad flow without moving open edges'),
        _PREVIEW: ('Preview Native Quad Relax', 'Check patch, affected vertices and displacement'),
        _COMMIT: ('Confirm Quad Relax', 'Move bounded interior vertices in one native XR Undo edit'),
        _CANCEL: ('Keep Mesh Unchanged', 'Discard this quad-surface correction'),
    })
    for action, (factor, cap) in _PRESETS.items():
        v065.TOOLTIPS[action] = (
            'Quad Relax ' + action.replace('XR_QUAD_RELAX_', '').title(),
            'Jacobi smoothing {:.0f}% with {:.0f}% maximum edge displacement'.format(
                factor * 100, cap * 100))


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_quad_interior_relax_090_patched', False):
        return
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == mesh_quad_quality_v090._PAGE and action == _ENTRY:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR controllers before Quad Relax')
            _source(context)
            self._xr_quad_relax_pending = None
            self.menu.page = _PAGE
            self.status = 'QUAD RELAX / CHOOSE STRENGTH AND PREVIEW'
            return
        if page == _PAGE:
            if action == 'BACK':
                self._xr_quad_relax_pending = None
                self.menu.page = mesh_quad_quality_v090._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR editing gesture before relax preview')
            if action in _PRESETS:
                self._xr_quad_relax_preset = action
                self._xr_quad_relax_pending = None
                self.status = 'QUAD RELAX STRENGTH / ' + action.replace(
                    'XR_QUAD_RELAX_', '')
                return
            if action != _PREVIEW:
                raise ValueError('Choose relax strength, Preview or Back')
            preset = getattr(self, '_xr_quad_relax_preset', 'XR_QUAD_RELAX_GENTLE')
            proposal = plan(context, preset)
            self._xr_quad_relax_pending = proposal
            self.menu.page = _CONFIRM_PAGE
            self.status = 'RELAX PREVIEW / {} INTERIOR VERTS / MAX {:.5g} / CONFIRM'.format(
                proposal['moving'], proposal['max_move'])
            return
        if page == _CONFIRM_PAGE:
            if action in {_CANCEL, 'BACK'}:
                self._xr_quad_relax_pending = None
                self.menu.page = _PAGE
                self.status = 'QUAD RELAX CANCELLED / NO DATA CHANGED'
                return
            if action != _COMMIT:
                raise ValueError('Confirm or cancel native Quad Relax')
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before native relax commit')
            proposal = getattr(self, '_xr_quad_relax_pending', None)
            if proposal is None:
                raise ValueError('Quad Relax approval expired; preview again')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('XR native mesh history required for Quad Relax')
            changed = commit(context, proposal, history)
            self._xr_quad_relax_pending = None
            self.menu.page = _PAGE
            self._xr_precision_last_ray = None
            self.status = 'QUAD RELAX / {} VERTICES / XR UNDO READY'.format(changed)
            return
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_quad_interior_relax_090_patched = True


CLASSES = (BXR_OT_quad_relax,)
