# SPDX-License-Identifier: GPL-3.0-or-later
"""Non-destructive native Blender relative shape-key reset and X reflection.

Edits only existing KeyBlock.data[i].co. The reference and Basis shape keys,
mesh topology, UV maps, vertex groups and all other shape keys stay intact.
Native XR history records exact changed coordinates, refuses conflicting
external edits, and preflights every vertex before touching the datablock.
"""
import hashlib
import math
import struct

import bpy
from bpy.props import EnumProperty, FloatProperty
from mathutils import Vector
from mathutils.kdtree import KDTree

from . import (input_ownership_v080, menus, mesh, runtime, shape_key_v090,
               shape_key_structure_v090, v065)

_PAGE = 'XR_SHAPE_DEFORM_090'
_TAG = 'XR_SHAPE_DEFORM_090'
_MIRROR = {
    'XR_SHAPE_MIRROR_NEG_POS': -1,
    'XR_SHAPE_MIRROR_POS_NEG': 1,
}
_TOLERANCES = {
    'XR_SHAPE_TOL_1MM': 0.001,
    'XR_SHAPE_TOL_5MM': 0.005,
    'XR_SHAPE_TOL_2CM': 0.02,
}
_RESET = 'XR_SHAPE_RESET'
_MAX_VERTS = 120000


def _point(block, index):
    return tuple(float(v) for v in block.data[index].co)


def _identical(left, right):
    return all(abs(a - b) <= 1e-6 for a, b in zip(left, right))


def _reference(context):
    obj, keys, index, block = shape_key_v090._target(context)
    if len(obj.data.vertices) > _MAX_VERTS:
        raise ValueError('Shape deformation is limited to 120,000 vertices')
    if any(len(item.data) != len(obj.data.vertices) for item in
           (block, keys.key_blocks[0])):
        raise ValueError('Shape Key vertex layout differs from the mesh')
    relative = block.relative_key if block.relative_key else keys.key_blocks[0]
    if relative == block or len(relative.data) != len(obj.data.vertices):
        raise ValueError('Shape Key relative basis is invalid')
    return obj, keys, index, block, relative


def _unchanged_digest(block, touched):
    h = hashlib.blake2b(digest_size=16)
    for index, vertex in enumerate(block.data):
        if index in touched:
            continue
        h.update(struct.pack('<I', index))
        h.update(struct.pack('<ddd', *_point(block, index)))
    return h.digest()


def _plan(context, operation, tolerance):
    obj, keys, index, block, relative = _reference(context)
    if operation not in {-1, 1, 'RESET'}:
        raise ValueError('Choose Reset or a local-X mirror direction')
    tolerance = float(tolerance)
    if not math.isfinite(tolerance) or not 0.0001 <= tolerance <= 0.1:
        raise ValueError('Shape mirror tolerance must be 0.0001–0.1 local units')
    candidates = []
    if operation == 'RESET':
        for i in range(len(obj.data.vertices)):
            before, after = _point(block, i), _point(relative, i)
            if not _identical(before, after):
                candidates.append((i, before, after))
    else:
        basis = keys.key_blocks[0]
        seam = min(tolerance * 0.5, .001)
        sources = []
        dest = []
        for i in range(len(obj.data.vertices)):
            co = _point(basis, i)
            if not all(math.isfinite(v) for v in co):
                raise ValueError('Basis contains an invalid vertex coordinate')
            if co[0] * operation > seam:
                sources.append((i, co))
            elif co[0] * operation < -seam:
                dest.append((i, co))
        if not sources or not dest:
            raise ValueError('Mirror requires both X hemispheres on the Basis')
        tree = KDTree(len(sources))
        for i, co in sources:
            tree.insert(co, i)
        tree.balance()
        for i, co in dest:
            hit = tree.find((-co[0], co[1], co[2]))
            if hit is None or hit[2] > tolerance:
                continue
            source = hit[1]
            source_co = Vector(_point(block, source))
            reference_co = Vector(_point(relative, source))
            delta = source_co - reference_co
            reflected = (-delta.x, delta.y, delta.z)
            target = Vector(_point(relative, i)) + Vector(reflected)
            after = tuple(float(v) for v in target)
            if not all(math.isfinite(v) for v in after):
                raise ValueError('Shape mirror produces invalid coordinates')
            before = _point(block, i)
            if not _identical(before, after):
                candidates.append((i, before, after))
    if not candidates:
        return None
    layout = tuple((item.name, item.as_pointer()) for item in keys.key_blocks)
    affected = frozenset(row[0] for row in candidates)
    return (_TAG, context.scene.name, context.view_layer.name,
            obj.name, obj.as_pointer(), obj.data.name, obj.data.as_pointer(),
            keys.as_pointer(), layout, index, block.as_pointer(),
            relative.as_pointer(), shape_key_structure_v090._mesh_digest(obj),
            shape_key_structure_v090._block_digest(keys.key_blocks[0]),
            shape_key_structure_v090._block_digest(relative),
            _unchanged_digest(block, affected), tuple(candidates),
            str(operation), tolerance)


def _guard(context, entry):
    (_tag, scene, layer, name, obj_ptr, mesh_name, mesh_ptr, key_ptr,
     layout, index, block_ptr, relative_ptr, geometry, basis_digest,
     relative_digest, untampered, changes, _mode, _tolerance) = entry
    if context.scene.name != scene or context.view_layer.name != layer:
        raise ValueError('Return to the original shape-key scene and view layer')
    obj, keys, selected_index, _active = shape_key_v090._target(context)
    if (obj.name != name or obj.as_pointer() != obj_ptr or
            obj.data.name != mesh_name or obj.data.as_pointer() != mesh_ptr or
            keys.as_pointer() != key_ptr or
            tuple((item.name, item.as_pointer()) for item in keys.key_blocks)
            != layout):
        raise ValueError('Shape key identity or layout changed outside XR')
    if not 0 < index < len(keys.key_blocks):
        raise ValueError('Shape key target index is no longer valid')
    block = keys.key_blocks[index]
    relative = block.relative_key
    if (block.as_pointer() != block_ptr or
            relative is None or relative.as_pointer() != relative_ptr):
        raise ValueError('Shape key or its reference block was replaced')
    if (shape_key_structure_v090._mesh_digest(obj) != geometry or
            shape_key_structure_v090._block_digest(keys.key_blocks[0])
            != basis_digest or
            shape_key_structure_v090._block_digest(relative) != relative_digest):
        raise ValueError('Basis or referenced geometry changed outside XR')
    affected = frozenset(row[0] for row in changes)
    if _unchanged_digest(block, affected) != untampered:
        raise ValueError('Other shape key coordinates changed outside XR')
    return obj, block


def _write(context, entry, backwards):
    obj, block = _guard(context, entry)
    changes = entry[16]
    expected_index = 2 if backwards else 1
    desired_index = 1 if backwards else 2
    for index, before, after in changes:
        expected = (index, before, after)[expected_index]
        if not _identical(_point(block, index), expected):
            raise ValueError('A target shape vertex was edited outside XR')
    applied = []
    try:
        for row in changes:
            index, before, after = row
            previous = _point(block, index)
            block.data[index].co = row[desired_index]
            applied.append((index, previous, row[desired_index]))
        context.view_layer.update()
    except Exception:
        for index, previous, desired in reversed(applied):
            if _identical(_point(block, index), desired):
                block.data[index].co = previous
        context.view_layer.update()
        raise


def _apply(context, action, tolerance, history=None):
    operation = 'RESET' if action == _RESET else _MIRROR.get(action)
    if operation is None:
        raise ValueError('Unsupported native shape deformation')
    entry = _plan(context, operation, tolerance)
    if entry is None:
        return 0, False
    # Entry[16] contains complete planned writes; read-only planning happens
    # before any native KeyBlock coordinate is modified.
    _write(context, entry, backwards=False)
    try:
        if history is not None:
            history.push(entry)
    except Exception:
        _write(context, entry, backwards=True)
        raise
    return len(entry[16]), True


def _history():
    if getattr(mesh.History, '_xr_shape_deformation_090_patched', False):
        return
    previous_step, previous_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == _TAG:
            return
        return previous_release(entry)

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] != _TAG:
            return previous_step(self, backwards)
        entry = source[-1]
        dest.append(entry)
        try:
            _write(bpy.context, entry, backwards)
        except Exception:
            dest.pop()
            raise
        source.pop()
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_shape_deformation_090_patched = True


class BXR_OT_shape_deform(bpy.types.Operator):
    bl_idname = 'blender_xr.shape_deform'
    bl_label = 'Reset or Reflect Native Blender Shape-Key Deformation'
    bl_description = 'Reset relative deltas or mirror them across local mesh X'
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(items=(
        (_RESET, 'Reset to Relative', 'Set selected key coordinates to their relative reference'),
        ('XR_SHAPE_MIRROR_NEG_POS', '-X to +X', 'Copy local -X deltas to +X'),
        ('XR_SHAPE_MIRROR_POS_NEG', '+X to -X', 'Copy local +X deltas to -X'),
    ), default=_RESET)
    tolerance: FloatProperty(name='Local X Tolerance', default=0.005,
                             min=0.0001, max=0.1, precision=4)

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and obj.mode == 'OBJECT'
                    and obj.data.shape_keys and
                    len(obj.data.shape_keys.key_blocks) > 1)

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the headset Shape Deform menu during XR')
            return {'CANCELLED'}
        try:
            count, changed = _apply(context, self.action, self.tolerance)
        except (RuntimeError, ReferenceError, ValueError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, '{} shape-key vertices changed'.format(count))
        return {'FINISHED'} if changed else {'CANCELLED'}


def install_pages():
    parent = tuple(menus.PAGES[shape_key_structure_v090._PAGE])
    if not parent or parent[-1][1] != 'BACK':
        raise ValueError('Shape Manage menu changed; cannot add Deform')
    if not any(action == 'XR_SHAPE_DEFORM_MENU' for _label, action in parent):
        parent = parent[:-1] + (('DEFORM', 'XR_SHAPE_DEFORM_MENU'), parent[-1])
    if len(parent) > 12:
        raise ValueError('Shape Manage menu has insufficient capacity')
    menus.PAGES[shape_key_structure_v090._PAGE] = parent
    menus.PAGES[_PAGE] = (
        ('RESET KEY', _RESET),
        ('-X TO +X', 'XR_SHAPE_MIRROR_NEG_POS'),
        ('+X TO -X', 'XR_SHAPE_MIRROR_POS_NEG'),
        ('TOL 1MM', 'XR_SHAPE_TOL_1MM'),
        ('TOL 5MM', 'XR_SHAPE_TOL_5MM'),
        ('TOL 2CM', 'XR_SHAPE_TOL_2CM'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'SHAPE DEFORMATION'
    v065.TOOLTIPS.update({
        'XR_SHAPE_DEFORM_MENU': ('Native Shape Deformation',
            'Reset key deltas or reflect them across object-local X'),
        _RESET: ('Reset to Relative Shape', 'Clear only the selected shape key deformation'),
        'XR_SHAPE_MIRROR_NEG_POS': ('Mirror -X to +X', 'Copy the left-hand local-X shape deformation'),
        'XR_SHAPE_MIRROR_POS_NEG': ('Mirror +X to -X', 'Copy the right-hand local-X shape deformation'),
        'XR_SHAPE_TOL_1MM': ('1 mm tolerance', 'Find mirrored Basis pairs within 0.001 local mesh units'),
        'XR_SHAPE_TOL_5MM': ('5 mm tolerance', 'Find mirrored Basis pairs within 0.005 local mesh units'),
        'XR_SHAPE_TOL_2CM': ('2 cm tolerance', 'Find mirrored Basis pairs within 0.02 local mesh units'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_shape_deformation_090_patched', False):
        return
    _history()
    install_pages()
    prior_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if (action == 'XR_SHAPE_DEFORM_MENU' and
                page == shape_key_structure_v090._PAGE):
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before editing shape deformation')
            _reference(context)
            self.menu.page = _PAGE
            self.status = 'SHAPE DEFORM / RESET OR LOCAL X MIRROR'
            return
        if page == _PAGE:
            if action == 'BACK':
                self.menu.page = shape_key_structure_v090._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Finish controller gesture before editing Shape Keys')
            if action in _TOLERANCES:
                _reference(context)
                self._xr_shape_deform_tolerance = _TOLERANCES[action]
                self.status = 'SHAPE MIRROR / LOCAL TOLERANCE {:.3f}'.format(
                    self._xr_shape_deform_tolerance)
                return
            if action == _RESET or action in _MIRROR:
                history = getattr(self, 'history', None)
                if history is None:
                    raise ValueError('XR history required before altering shape geometry')
                count, changed = _apply(
                    context, action, getattr(self, '_xr_shape_deform_tolerance', 0.005),
                    history=history)
                self.status = 'SHAPE DEFORM / {} VERTICES / {}'.format(
                    count, 'XR UNDO READY' if changed else 'NO CHANGE')
                return
            raise ValueError('Choose Reset, Mirror or a local tolerance')
        return prior_command(self, context, action)

    Runtime.command = command
    Runtime._xr_shape_deformation_090_patched = True


CLASSES = (BXR_OT_shape_deform,)
