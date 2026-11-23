# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistent native Blender mesh-attribute selection sets for VR authoring.

Unlike session-only XR Quick Sets, A/B/C slots are saved into the actual
mesh as Blender integer attributes on the selected POINT/EDGE/FACE domain.
They survive .blend reload and native edit operations. No duplicate mesh
or proprietary serialized selection object is created.
"""
import bmesh
import bpy

from . import (input_ownership_v080, menus, mesh, mesh_selection_tools_v086,
               selection_quicksets_v090, v065)

_PAGE = 'XR_PERSISTENT_SELECTION_090'
_PARENT = selection_quicksets_v090._PAGE
_TAG = 'XR_PERSISTENT_SELECTION_ATTR_090'
_GROUPS = {'VERT': ('verts', 'POINT'),
           'EDGE': ('edges', 'EDGE'),
           'FACE': ('faces', 'FACE')}
_SLOTS = 'ABC'
_SAVE = {'XR_PERSIST_SAVE_' + slot: slot for slot in _SLOTS}
_LOAD = {'XR_PERSIST_LOAD_' + slot: slot for slot in _SLOTS}
_CLEAR = {'XR_PERSIST_CLEAR_' + slot: slot for slot in _SLOTS}
_MAX_ELEMENTS = 120000


def _name(slot, mode):
    if slot not in _SLOTS or mode not in _GROUPS:
        raise ValueError('Unknown persistent native selection slot or domain')
    return 'BXR_Select_{}_{}_v090'.format(slot, mode)


def _context(context):
    obj, mode, bm, items, topology = selection_quicksets_v090._current(context)
    if obj.data.users != 1 or obj.data.library or obj.data.override_library:
        raise ValueError('Persistent selections require a local single-user mesh')
    if len(items) > _MAX_ELEMENTS:
        raise ValueError('Persistent selection sets support 120,000 elements per domain')
    return obj, mode, bm, items, topology


def _layers(bm, mode):
    return getattr(getattr(bm, _GROUPS[mode][0]).layers, 'int')


def _read(obj, bm, items, mode, name):
    """Read the edit BMesh values, validating any native attribute collision."""
    native = obj.data.attributes.get(name)
    if native is not None and (
            native.domain != _GROUPS[mode][1] or native.data_type != 'INT'):
        raise ValueError('A Blender attribute with this name has another type/domain')
    layer = _layers(bm, mode).get(name)
    if layer is None:
        if native is not None:
            raise ValueError('Saved mesh attribute is unavailable in Edit Mode')
        return None
    values = tuple(int(item[layer]) for item in items)
    if any(value not in (0, 1) for value in values):
        raise ValueError('Selection attribute was edited to an invalid value')
    return values


def _set_layer(obj, bm, items, mode, name, values):
    layer_store = _layers(bm, mode)
    layer = layer_store.get(name)
    if values is None:
        if layer is not None:
            layer_store.remove(layer)
    else:
        if len(values) != len(items) or any(v not in (0, 1) for v in values):
            raise ValueError('Selection set length or native values are invalid')
        if layer is None:
            layer = layer_store.new(name)
        for item, value in zip(items, values):
            item[layer] = value
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)


def _write(obj, bm, items, mode, name, expected, target):
    if _read(obj, bm, items, mode, name) != expected:
        raise ValueError('Persistent selection attribute changed outside XR history')
    try:
        _set_layer(obj, bm, items, mode, name, target)
    except Exception:
        # Keep an atomic edit even if CustomData allocation/update fails.
        # This synchronous best-effort rollback modifies only our own layer.
        try:
            _set_layer(obj, bm, items, mode, name, expected)
        except Exception:
            pass
        raise


def _identity(context, obj, mode, topo, name, before, after):
    return (_TAG, context.scene.name, context.view_layer.name,
            obj.name, obj.as_pointer(), obj.data.name, obj.data.as_pointer(),
            mode, topo, name, before, after)


def _guard(context, entry):
    (_tag, scene, layer, object_name, obj_ptr, mesh_name, data_ptr,
     mode, topology, name, _before, _after) = entry
    obj, current_mode, bm, items, current_topology = _context(context)
    if (context.scene.name != scene or context.view_layer.name != layer or
            obj.name != object_name or obj.as_pointer() != obj_ptr or
            obj.data.name != mesh_name or obj.data.as_pointer() != data_ptr or
            current_mode != mode or topology != current_topology or
            name not in {_name(c, mode) for c in _SLOTS}):
        raise ValueError('Persistent set mesh, topology or select mode changed outside XR')
    return obj, bm, items


def _apply_entry(context, entry, backwards):
    obj, bm, items = _guard(context, entry)
    expected, desired = ((entry[11], entry[10]) if backwards
                         else (entry[10], entry[11]))
    _write(obj, bm, items, entry[7], entry[9], expected, desired)


def _edit(session, context, slot, clear):
    if input_ownership_v080.is_editing(session):
        raise ValueError('Release XR gestures before editing mesh selection sets')
    if getattr(session, 'history', None) is None:
        raise ValueError('XR history required for persistent native selection sets')
    obj, mode, bm, items, topo = _context(context)
    name = _name(slot, mode)
    before = _read(obj, bm, items, mode, name)
    if clear:
        if before is None:
            session.status = 'PERSIST {} / ALREADY EMPTY'.format(slot)
            return False
        after = None
    else:
        after = tuple(int(bool(item.select and not item.hide)) for item in items)
    if before == after:
        session.status = 'PERSIST {} / SELECTION UNCHANGED'.format(slot)
        return False
    entry = _identity(context, obj, mode, topo, name, before, after)
    _apply_entry(context, entry, backwards=False)
    try:
        session.history.push(entry)
    except Exception:
        # A failed Undo push must not leave a silent persistent mesh mutation.
        _apply_entry(context, entry, backwards=True)
        raise
    session.status = 'PERSIST {} / {} / {} {}'.format(
        slot, 'CLEARED' if clear else 'SAVED',
        0 if after is None else sum(after), mode)
    return True


def _load(session, context, slot):
    if input_ownership_v080.is_editing(session):
        raise ValueError('Release XR gestures before recalling persistent sets')
    obj, mode, bm, items, _topo = _context(context)
    name = _name(slot, mode)
    saved = _read(obj, bm, items, mode, name)
    if saved is None:
        raise ValueError('No persistent {} set exists for {} mode'.format(slot, mode))
    # Hide/reveal operations do not destroy saved mesh data. Never select
    # hidden elements when recalling a persisted native selection.
    indices = tuple(item.index for item, value in zip(items, saved)
                    if value and item.is_valid and not item.hide)
    additive = bool(getattr(session, '_xr_persistent_selection_add', False))
    count, changed = selection_quicksets_v090.restore_indices(
        session, context, indices, additive=additive)
    session.status = 'PERSIST {} / {} / {} {} {}'.format(
        slot, 'ADDED' if additive else 'RECALLED',
        count, mode, 'UNDO READY' if changed else 'UNCHANGED')
    return changed


def _history():
    if getattr(mesh.History, '_xr_persistent_selection_090_patched', False):
        return
    prior_step, prior_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == _TAG:
            return
        return prior_release(entry)

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] != _TAG:
            return prior_step(self, backwards)
        entry = source[-1]
        dest.append(entry)
        try:
            _apply_entry(bpy.context, entry, backwards=backwards)
        except Exception:
            dest.pop()
            raise
        source.pop()
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_persistent_selection_090_patched = True


def install_pages():
    parent = tuple(menus.PAGES[_PARENT])
    if not parent or parent[-1][1] != 'BACK':
        raise ValueError('Native Quick Sets page is unavailable')
    if not any(action == 'XR_PERSIST_MENU' for _label, action in parent):
        parent = parent[:-1] + (('PERSISTENT', 'XR_PERSIST_MENU'), parent[-1])
    if len(parent) > 12:
        raise ValueError('Quick Sets cannot hold persistent selection category')
    menus.PAGES[_PARENT] = parent
    buttons = []
    for slot in _SLOTS:
        buttons.extend((
            ('SAVE ' + slot, 'XR_PERSIST_SAVE_' + slot),
            ('LOAD ' + slot, 'XR_PERSIST_LOAD_' + slot),
            ('CLEAR ' + slot, 'XR_PERSIST_CLEAR_' + slot),
        ))
    buttons.extend((
        ('ADD / REPLACE', 'XR_PERSIST_MODE'),
        ('BACK', 'BACK'),
    ))
    menus.PAGES[_PAGE] = tuple(buttons)
    menus.TITLES[_PAGE] = 'PERSISTENT SELECT SETS'
    v065.TOOLTIPS.update({
        'XR_PERSIST_MENU': ('Native Persistent Selections',
            'Save A/B/C selections as real Blender mesh attributes in the .blend file'),
        'XR_PERSIST_MODE': ('Add or Replace Selection Recall',
            'Toggle whether loading a set adds to or replaces the current selection'),
    })
    for slot in _SLOTS:
        v065.TOOLTIPS['XR_PERSIST_SAVE_' + slot] = (
            'Save Persistent Selection ' + slot,
            'Write the current native edit selection to a mesh attribute')
        v065.TOOLTIPS['XR_PERSIST_LOAD_' + slot] = (
            'Load Persistent Selection ' + slot,
            'Recall a saved Blender attribute through XR selection history')
        v065.TOOLTIPS['XR_PERSIST_CLEAR_' + slot] = (
            'Delete Persistent Selection ' + slot,
            'Remove only this Blender selection attribute with XR Undo')


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_persistent_selection_090_patched', False):
        return
    _history()
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if action == 'XR_PERSIST_MENU' and page == _PARENT:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gestures before Persistent Selection')
            _context(context)
            self.menu.page = _PAGE
            self.status = 'PERSIST / SELECT A B C / SAVED IN BLENDER MESH'
            return
        if page == _PAGE:
            if action == 'BACK':
                self.menu.page = _PARENT
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR editing gesture before selection tools')
            if action == 'XR_PERSIST_MODE':
                self._xr_persistent_selection_add = not bool(getattr(
                    self, '_xr_persistent_selection_add', False))
                self.status = ('PERSIST RECALL / ' +
                               ('ADD' if self._xr_persistent_selection_add
                                else 'REPLACE'))
                return
            if action in _SAVE:
                return _edit(self, context, _SAVE[action], clear=False)
            if action in _CLEAR:
                return _edit(self, context, _CLEAR[action], clear=True)
            if action in _LOAD:
                return _load(self, context, _LOAD[action])
            raise ValueError('Unknown native persistent selection command')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_persistent_selection_090_patched = True
