# SPDX-License-Identifier: GPL-3.0-or-later
"""Create native Blender Basis / relative shape keys from the XR wrist menu.

Structural edits can invalidate older pointer-addressed XR history, so XR
requires an explicit confirmation to discard existing local Undo/Redo first.
The created KeyBlock and its native coordinates remain in Blender's actual
Mesh.shape_keys; no duplicate geometry objects or custom serialization.
"""
import hashlib
import math
import struct
import traceback

import bpy

from . import (input_ownership_v080, menus, mesh, shape_key_v090,
               shape_key_rename_v090, runtime, v065)

_PAGE = 'XR_SHAPE_MANAGE_090'
_CONFIRM = 'XR_SHAPE_CREATE_CONFIRM_090'
_TAG = 'XR_SHAPE_CREATE_090'
_ACTIONS = {
    'XR_SHAPE_CREATE_BASIS': 'BASIS',
    'XR_SHAPE_CREATE_KEY': 'NEW',
    'XR_SHAPE_DUPLICATE': 'DUPLICATE',
}
_MAX_VERTICES = 120000


def _editable_mesh(context):
    obj = context.view_layer.objects.active
    if (obj is None or obj.type != 'MESH' or obj.mode != 'OBJECT' or
            context.mode != 'OBJECT' or
            context.view_layer.objects.get(obj.name) != obj):
        raise ValueError('Select a native mesh in Object Mode to create shape keys')
    if (obj.library or obj.override_library or obj.data.library or
            obj.data.override_library or obj.data.users != 1 or
            obj.hide_select or obj.hide_get() or not obj.visible_get()):
        raise ValueError('Use an unlocked, visible, local, single-user mesh')
    if len(obj.data.vertices) == 0 or len(obj.data.vertices) > _MAX_VERTICES:
        raise ValueError('Shape key authoring requires 1–120,000 mesh vertices')
    keys = obj.data.shape_keys
    if keys is not None:
        if not keys.use_relative:
            raise ValueError('Only native relative shape keys are supported in XR')
        animation = keys.animation_data
        if animation is not None and (animation.action or animation.drivers):
            raise ValueError('Animated/driven shape keys require desktop Blender editing')
    return obj, keys


def _layout(keys):
    if keys is None:
        return ()
    return tuple((key.name, key.as_pointer()) for key in keys.key_blocks)


def _mesh_digest(obj):
    """Protect the same-count topology/coordinate edits before redo or undo.

    The Blender mesh retains the complete native geometry. This digest is
    a session-only preflight and is never written into the .blend file.
    """
    h = hashlib.blake2b(digest_size=16)
    data = obj.data
    h.update(struct.pack('<III', len(data.vertices), len(data.edges),
                         len(data.polygons)))
    for vert in data.vertices:
        h.update(struct.pack('<ddd', *(float(value) for value in vert.co)))
    for edge in data.edges:
        h.update(struct.pack('<II', *(int(index) for index in edge.vertices)))
    for poly in data.polygons:
        h.update(struct.pack('<I', len(poly.vertices)))
        for index in poly.vertices:
            h.update(struct.pack('<I', int(index)))
    return h.digest()


def _block_digest(block):
    h = hashlib.blake2b(digest_size=16)
    for point in block.data:
        values = tuple(float(value) for value in point.co)
        if not all(math.isfinite(value) for value in values):
            raise ValueError('Shape key contains non-finite vertex coordinates')
        h.update(struct.pack('<ddd', *values))
    return h.digest()


def _next_name(keys):
    taken = set(name for name, _pointer in _layout(keys))
    for num in range(1, 10000):
        label = 'XR Key {:03d}'.format(num)
        if label not in taken:
            return label
    raise ValueError('Shape Key name range exhausted')


def _plan(context, action):
    obj, keys = _editable_mesh(context)
    if action not in _ACTIONS:
        raise ValueError('Unknown structural shape-key operation')
    kind = _ACTIONS[action]
    count = len(keys.key_blocks) if keys else 0
    if kind == 'BASIS' and count:
        raise ValueError('Basis already exists; choose Add Shape Key instead')
    if kind in {'NEW', 'DUPLICATE'} and not count:
        raise ValueError('Create the Basis first, then add relative shape keys')
    if kind == 'DUPLICATE' and (obj.active_shape_key_index < 1 or
                                 obj.active_shape_key_index >= count):
        raise ValueError('Select a non-Basis key to duplicate')
    if count >= 64:
        raise ValueError('XR shape-key menu is limited to 64 keys per mesh')

    source_index = obj.active_shape_key_index if kind == 'DUPLICATE' else 0
    source = keys.key_blocks[source_index] if kind == 'DUPLICATE' else None
    coords = None
    metadata = None
    if source is not None:
        coords = tuple(tuple(float(v) for v in item.co) for item in source.data)
        if len(coords) != len(obj.data.vertices):
            raise ValueError('Source shape key does not match the native mesh')
        if not all(math.isfinite(v) for point in coords for v in point):
            raise ValueError('Source key has invalid coordinates')
        metadata = (float(source.slider_min), float(source.slider_max),
                    source.interpolation, source.vertex_group, source.mute,
                    source.relative_key.name if source.relative_key else None)
    return {
        'action': kind, 'name': ('Basis' if kind == 'BASIS' else _next_name(keys)),
        'obj_name': obj.name, 'obj_ptr': obj.as_pointer(),
        'mesh_name': obj.data.name, 'mesh_ptr': obj.data.as_pointer(),
        'scene': context.scene.name, 'layer': context.view_layer.name,
        'vertex_count': len(obj.data.vertices), 'mesh_digest': _mesh_digest(obj),
        'before_layout': _layout(keys),
        'keys_before_ptr': keys.as_pointer() if keys else 0,
        'active_before': int(obj.active_shape_key_index),
        'source_coords': coords, 'source_metadata': metadata,
    }


def _same_plan(old, now):
    return all(old[key] == now[key] for key in (
        'action', 'name', 'obj_name', 'obj_ptr', 'mesh_name', 'mesh_ptr',
        'scene', 'layer', 'vertex_count', 'mesh_digest', 'before_layout',
        'keys_before_ptr', 'active_before', 'source_coords',
        'source_metadata'))


def _check_owner(context, saved):
    obj, keys = _editable_mesh(context)
    if (obj.name != saved['obj_name'] or obj.as_pointer() != saved['obj_ptr']
            or obj.data.name != saved['mesh_name'] or
            obj.data.as_pointer() != saved['mesh_ptr'] or
            context.scene.name != saved['scene'] or
            context.view_layer.name != saved['layer'] or
            len(obj.data.vertices) != saved['vertex_count'] or
            _mesh_digest(obj) != saved['mesh_digest']):
        raise ValueError('Mesh identity, topology or geometry changed since shape creation')
    return obj, keys


def _before(context, saved):
    obj, keys = _check_owner(context, saved)
    if _layout(keys) != saved['before_layout']:
        raise ValueError('Shape-key layout changed since the structure edit')
    if (keys.as_pointer() if keys else 0) != saved['keys_before_ptr']:
        raise ValueError('Native Blender Keys datablock was replaced')
    return obj, keys


def _after(context, saved):
    obj, keys = _check_owner(context, saved)
    if (keys is None or keys.as_pointer() != saved['keys_after_ptr'] or
            len(keys.key_blocks) != len(saved['before_layout']) + 1 or
            _layout(keys) != saved['before_layout'] + (
                (saved['name'], saved['created_ptr']),)):
        raise ValueError('Created native shape key changed or was replaced')
    block = keys.key_blocks[-1]
    if (_block_digest(block) != saved['created_digest'] or
            bool(block.mute) != saved['mute'] or
            abs(float(block.value) - saved['value']) > 1e-6 or
            abs(float(block.slider_min) - saved['slider_min']) > 1e-6 or
            abs(float(block.slider_max) - saved['slider_max']) > 1e-6 or
            block.interpolation != saved['interpolation'] or
            block.vertex_group != saved['vertex_group'] or
            (block.relative_key.name if block.relative_key else None)
            != saved['relative_name']):
        raise ValueError('Created shape key was edited outside XR history')
    return obj, keys, block


def _create_native(context, plan):
    obj, keys = _before(context, plan)
    if plan['action'] == 'BASIS':
        new = obj.shape_key_add(name='Basis', from_mix=False)
    else:
        new = obj.shape_key_add(name=plan['name'], from_mix=False)
    try:
        if new.name != plan['name']:
            raise ValueError('Blender could not create the requested exact key name')
        metadata = plan['source_metadata']
        if metadata is not None:
            for vertex, coords in zip(new.data, plan['source_coords']):
                vertex.co = coords
            new.slider_min, new.slider_max = metadata[:2]
            new.interpolation = metadata[2]
            new.vertex_group = metadata[3]
            new.mute = metadata[4]
            if metadata[5]:
                relative = obj.data.shape_keys.key_blocks.get(metadata[5])
                if relative is None:
                    raise ValueError('Duplicated key relative source was removed')
                new.relative_key = relative
        # Snapshot the exact original native KeyBlock state for redo.
        result = dict(plan)
        result.update(
            keys_after_ptr=obj.data.shape_keys.as_pointer(),
            created_ptr=new.as_pointer(),
            created_coords=tuple(tuple(float(v) for v in pt.co) for pt in new.data),
            created_digest=_block_digest(new),
            slider_min=float(new.slider_min), slider_max=float(new.slider_max),
            interpolation=new.interpolation, vertex_group=new.vertex_group,
            mute=bool(new.mute), value=float(new.value),
            relative_name=new.relative_key.name if new.relative_key else None,
        )
        obj.active_shape_key_index = len(obj.data.shape_keys.key_blocks) - 1
        context.view_layer.update()
        return result
    except Exception:
        # Creation is one Blender-native mutation; no half-created key should
        # remain if metadata copying or the dependency-graph update fails.
        try:
            obj.shape_key_remove(new)
            obj.active_shape_key_index = plan['active_before']
            context.view_layer.update()
        except Exception:
            traceback.print_exc()
        raise


def _remove_created(context, state):
    obj, _keys, block = _after(context, state)
    obj.shape_key_remove(block)
    obj.active_shape_key_index = min(
        state['active_before'],
        max(0, len(obj.data.shape_keys.key_blocks) - 1)
        if obj.data.shape_keys else 0)
    context.view_layer.update()


def _recreate(context, state):
    obj, _keys = _before(context, state)
    new = obj.shape_key_add(name=state['name'], from_mix=False)
    try:
        if new.name != state['name']:
            raise ValueError('Shape key name taken since XR Undo')
        if len(new.data) != len(state['created_coords']):
            raise ValueError('Created shape key vertex count changed')
        for vertex, coords in zip(new.data, state['created_coords']):
            vertex.co = coords
        new.slider_min = state['slider_min']
        new.slider_max = state['slider_max']
        new.interpolation = state['interpolation']
        new.vertex_group = state['vertex_group']
        new.mute = state['mute']
        new.value = state['value']
        if state['relative_name']:
            relative = obj.data.shape_keys.key_blocks.get(state['relative_name'])
            if relative is None:
                raise ValueError('Native relative shape key was removed')
            # Blender creates the Basis with a self reference. Preserve that
            # native relationship without assigning the KeyBlock to itself.
            if relative != new:
                new.relative_key = relative
        if _block_digest(new) != state['created_digest']:
            raise ValueError('Shape key restoration produced different vertex positions')
        state['keys_after_ptr'] = obj.data.shape_keys.as_pointer()
        state['created_ptr'] = new.as_pointer()
        obj.active_shape_key_index = len(obj.data.shape_keys.key_blocks) - 1
        context.view_layer.update()
        return
    except Exception:
        try:
            obj.shape_key_remove(new)
            obj.active_shape_key_index = state['active_before']
            context.view_layer.update()
        except Exception:
            traceback.print_exc()
        raise


def _history():
    if getattr(mesh.History, '_xr_shape_structure_090_patched', False):
        return
    prior_step, prior_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == _TAG:
            return
        return prior_release(entry)

    def step(self, backwards=True):
        src, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not src or src[-1][0] != _TAG:
            return prior_step(self, backwards)
        state = src[-1][1]
        # Reserve room in the destination *before* touching native Blender
        # datablocks; a failed Python append must not make the edit un-undoable.
        entry = src[-1]
        dest.append(entry)
        try:
            if backwards:
                _remove_created(bpy.context, state)
            else:
                _recreate(bpy.context, state)
        except Exception:
            dest.pop()
            raise
        src.pop()
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_shape_structure_090_patched = True


def _commit(session, context, plan, reset_history):
    history = getattr(session, 'history', None)
    if history is None:
        raise ValueError('XR history is required before creating shape keys')
    current = _plan(context, next(key for key, kind in _ACTIONS.items()
                                  if kind == plan['action']))
    if not _same_plan(plan, current):
        raise ValueError('Shape-key target changed while awaiting confirmation')
    if (history.undo or history.redo) and not reset_history:
        raise ValueError('Confirm clearing older XR Undo/Redo before adding a key')
    previous_undo, previous_redo = history.undo, history.redo
    # Stage an isolated new history. On failed creation/push restore the old
    # stacks and their owned snapshots instead of silently losing them.
    if reset_history:
        history.undo, history.redo = [], []
    try:
        state = _create_native(context, current)
        try:
            history.push((_TAG, state))
        except Exception:
            _remove_created(context, state)
            raise
    except Exception:
        if reset_history:
            history.undo, history.redo = previous_undo, previous_redo
        raise
    if reset_history:
        for entry in previous_undo + previous_redo:
            try:
                history.release(entry)
            except Exception:
                traceback.print_exc()
    session._xr_shape_create_pending = None
    session.menu.page = shape_key_v090._PAGE
    session.status = 'CREATED SHAPE KEY / ' + state['name'][:40] + ' / UNDO READY'


class BXR_OT_shape_key_create(bpy.types.Operator):
    bl_idname = 'blender_xr.shape_key_create'
    bl_label = 'Create Native Blender Shape Key'
    bl_description = 'Create native Basis, add relative shape key, or duplicate a selected key'
    bl_options = {'REGISTER', 'UNDO'}
    action: bpy.props.EnumProperty(items=(
        ('XR_SHAPE_CREATE_BASIS', 'Create Basis', 'Add initial Blender Basis'),
        ('XR_SHAPE_CREATE_KEY', 'Add Key', 'Add a relative key from the Basis'),
        ('XR_SHAPE_DUPLICATE', 'Duplicate Key', 'Copy selected native key coordinates'),
    ), default='XR_SHAPE_CREATE_KEY')

    @classmethod
    def poll(cls, context):
        return (context.mode == 'OBJECT' and
                context.view_layer.objects.active is not None and
                context.view_layer.objects.active.type == 'MESH')

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Shape Manage wrist menu during VR')
            return {'CANCELLED'}
        try:
            plan = _plan(context, self.action)
            state = _create_native(context, plan)
        except (ValueError, RuntimeError, ReferenceError, TypeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Created native Shape Key ' + state['name'])
        return {'FINISHED'}


def install_pages():
    prior = tuple(menus.PAGES[shape_key_v090._PAGE])
    if not prior or prior[-1][1] != 'BACK':
        raise ValueError('Shape Key value menu must exist before Shape Manage')
    if sum(action == 'XR_SHAPE_RENAME_MENU' for _label, action in prior) != 1:
        raise ValueError('Shape Rename menu changed; cannot add Shape Manage')
    updated = tuple(('MANAGE', 'XR_SHAPE_MANAGE_MENU')
                    if action == 'XR_SHAPE_RENAME_MENU' else (label, action)
                    for label, action in prior)
    if len(updated) > 12:
        raise ValueError('Shape Manage overflows Shape Key value page')
    menus.PAGES[shape_key_v090._PAGE] = updated
    menus.PAGES[_PAGE] = (
        ('NEW BASIS', 'XR_SHAPE_CREATE_BASIS'),
        ('ADD KEY', 'XR_SHAPE_CREATE_KEY'),
        ('DUPLICATE', 'XR_SHAPE_DUPLICATE'),
        ('RENAME', 'XR_SHAPE_RENAME_MENU'),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_CONFIRM] = (
        ('RESET UNDO + ADD', 'XR_SHAPE_CREATE_CONFIRM'),
        ('KEEP HISTORY', 'XR_SHAPE_CREATE_CANCEL'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'SHAPE KEY MANAGE'
    menus.TITLES[_CONFIRM] = 'RESET XR UNDO?'
    # Renaming the selected KeyBlock lives under Manage; its existing
    # keyboard still owns typing, cancel, precise names and history.
    shape_key_rename_v090._BACK_PAGE = _PAGE
    v065.TOOLTIPS.update({
        'XR_SHAPE_MANAGE_MENU': ('Native Shape Key Manager',
            'Create a Basis or relative shape key, duplicate, or rename existing keys'),
        'XR_SHAPE_CREATE_BASIS': ('Create Basis',
            'Create native Blender Basis when the mesh has no shape keys'),
        'XR_SHAPE_CREATE_KEY': ('Create Relative Shape Key',
            'Add a native relative key initialized from the Basis'),
        'XR_SHAPE_DUPLICATE': ('Duplicate Shape Key',
            'Copy the active non-Basis KeyBlock coordinates without new mesh objects'),
        'XR_SHAPE_CREATE_CONFIRM': ('Clear XR History and Create Key',
            'Discard older XR-only Undo/Redo entries that reference an outdated key layout'),
        'XR_SHAPE_CREATE_CANCEL': ('Keep Existing XR History',
            'Cancel structural key creation without changing Blender data'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_shape_structure_090_patched', False):
        return
    _history()
    install_pages()
    prior_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return prior_command(self, context, action)
        if action == 'XR_SHAPE_MENU':
            # The older Shape Value menu required an existing non-Basis key;
            # entering Manage must also work on a mesh with *no* Basis.
            _editable_mesh(context)
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gestures before opening Shape Keys')
            menu.page = shape_key_v090._PAGE
            self.status = 'SHAPE KEYS / MANAGE OR EDIT NATIVE KEYS'
            return
        if action == 'XR_SHAPE_MANAGE_MENU' and menu.page == shape_key_v090._PAGE:
            _editable_mesh(context)
            menu.page = _PAGE
            self.status = 'SHAPE MANAGE / BASIS, ADD, DUPLICATE OR RENAME'
            return
        if menu.page == _CONFIRM:
            if action in {'BACK', 'XR_SHAPE_CREATE_CANCEL'}:
                self._xr_shape_create_pending = None
                menu.page = _PAGE
                self.status = 'SHAPE CREATE CANCELLED / HISTORY PRESERVED'
                return
            if action == 'XR_SHAPE_CREATE_CONFIRM':
                pending = getattr(self, '_xr_shape_create_pending', None)
                if pending is None:
                    raise ValueError('No pending shape key creation')
                _commit(self, context, pending, reset_history=True)
                return
            raise ValueError('Confirm or cancel the pending structure edit')
        if menu.page == _PAGE:
            if action == 'BACK':
                menu.page = shape_key_v090._PAGE
                return
            if action in _ACTIONS:
                if input_ownership_v080.is_editing(self):
                    raise ValueError('Release XR gestures before creating shape keys')
                plan = _plan(context, action)
                history = getattr(self, 'history', None)
                if history is None:
                    raise ValueError('XR history unavailable for creating keys')
                if history.undo or history.redo:
                    self._xr_shape_create_pending = plan
                    menu.page = _CONFIRM
                    self.status = 'CREATING KEY REQUIRES XR HISTORY RESET / CONFIRM'
                    return
                _commit(self, context, plan, reset_history=False)
                return
            if action != 'XR_SHAPE_RENAME_MENU':
                raise ValueError('Choose Basis, Add, Duplicate or Rename')
        return prior_command(self, context, action)

    Runtime.command = command
    Runtime._xr_shape_structure_090_patched = True


CLASSES = (BXR_OT_shape_key_create,)
