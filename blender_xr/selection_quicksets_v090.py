# SPDX-License-Identifier: GPL-3.0-or-later
"""Three guarded, session-local quick sets for native Blender edit selections.

Stores only vertex/edge/face index tuples and the active edit BMesh topology.
No additional mesh attributes, vertices, objects, or persisted project data.
Recall uses the existing XR selection-history implementation and its Undo/Redo.
"""
from . import (input_ownership_v080, menus, mesh_selection_tools_v086,
               selection, v065)

_PAGE = 'XR_SELECTION_SLOTS_090'
_SELECTION_PAGE = mesh_selection_tools_v086._PAGE
_FLOWS_PAGE = mesh_selection_tools_v086._FLOWS_PAGE
_SLOTS = 'ABC'
_SAVE = {'XR_SLOT_SAVE_' + c: c for c in _SLOTS}
_RECALL = {'XR_SLOT_LOAD_' + c: c for c in _SLOTS}
_CLEAR = {'XR_SLOT_CLEAR_' + c: c for c in _SLOTS}


def _current(context):
    obj = mesh_selection_tools_v086._editable(context)
    mode = selection.mode(context)
    bm, items = mesh_selection_tools_v086._current(obj, mode)
    topo = mesh_selection_tools_v086._topology(bm)
    return obj, mode, bm, items, topo


def _identity(context, obj, mode, topo):
    return (context.scene.name, context.view_layer.name,
            obj.name, obj.as_pointer(), obj.data.name,
            obj.data.as_pointer(), mode, topo)


def _check_owner(session):
    if input_ownership_v080.is_editing(session):
        raise ValueError('Release controller gestures before using Quick Sets')
    if getattr(session, 'history', None) is None:
        raise ValueError('XR Undo history is required for recalling selections')


def _set_status(session, action, label, mode, count=None):
    suffix = ' / {} {}'.format(count, mode) if count is not None else ' / ' + mode
    session.status = ('QUICK SET ' + label + ' / ' + action + suffix).upper()


def _store(session, context, label):
    obj, mode, _bm, items, topo = _current(context)
    selected = mesh_selection_tools_v086._selected(items)
    saved = getattr(session, '_xr_selection_quicksets', None)
    if saved is None:
        saved = {}
        session._xr_selection_quicksets = saved
    # Selection is read only. The same slot name is safe across meshes only
    # because recall verifies the complete identity before it touches BMesh.
    saved[label] = (_identity(context, obj, mode, topo), selected)
    _set_status(session, 'SAVED', label, mode, len(selected))
    return True


def restore_indices(session, context, indices, additive=False):
    """One native guarded selection-recall path for Quick and persistent sets."""
    _check_owner(session)
    obj, mode, _bm, items, topo = _current(context)
    before = mesh_selection_tools_v086._selected(items)
    validated = []
    for index in indices:
        if (not isinstance(index, int) or index < 0 or index >= len(items) or
                not items[index].is_valid or items[index].hide):
            raise ValueError('Selection set contains a hidden or invalid element')
        validated.append(index)
    after = (tuple(sorted(set(before).union(validated))) if additive
             else tuple(sorted(set(validated))))
    if before == after:
        return len(before), False
    # Reuse the established XR_MESH_SELECTION_086 history format.
    mesh_selection_tools_v086._set_selection(obj, mode, after)
    applied_bm, applied_items = mesh_selection_tools_v086._current(obj, mode)
    if mesh_selection_tools_v086._topology(applied_bm) != topo:
        raise ValueError('Mesh topology changed during selection recall')
    applied = mesh_selection_tools_v086._selected(applied_items)
    if applied == before:
        return len(applied), False
    entry = (mesh_selection_tools_v086._TAG, context.scene.name,
             context.view_layer.name, obj.name, obj.as_pointer(),
             obj.data.name, obj.data.as_pointer(), mode, topo, before, applied)
    try:
        session.history.push(entry)
    except Exception:
        # Roll back only when the same Blender mesh and post-flush selection
        # are still present; never overwrite another editor's selection.
        check_obj, check_mode, check_bm, check_items, check_topo = _current(context)
        if (check_obj == obj and check_mode == mode and check_topo == topo and
                mesh_selection_tools_v086._selected(check_items) == applied):
            mesh_selection_tools_v086._set_selection(obj, mode, before)
        raise
    session._xr_precision_last_ray = None
    return len(applied), True


def _recall(session, context, label):
    saved = getattr(session, '_xr_selection_quicksets', None) or {}
    if label not in saved:
        raise ValueError('Quick Set ' + label + ' is empty; save a selection')
    obj, mode, _bm, _items, topo = _current(context)
    identity, indices = saved[label]
    if identity != _identity(context, obj, mode, topo):
        raise ValueError('Quick Set ' + label + ' is stale; save it again')
    additive = bool(getattr(session, '_xr_selection_slots_add', False))
    count, changed = restore_indices(session, context, indices, additive)
    _set_status(session, 'ADDED' if additive else
                'RESTORED' if changed else 'UNCHANGED', label, mode, count)
    return changed


def install_pages():
    main = tuple(menus.PAGES[_SELECTION_PAGE])
    flow = tuple(menus.PAGES[_FLOWS_PAGE])
    if (not main or main[-1][1] != 'BACK' or
            not flow or flow[-1][1] != 'BACK'):
        raise ValueError('Selection Tools menu layout changed')
    # Preserve all existing tools while making Slots directly reachable.
    # Move MESH BOUNDARY into the related Edge Flows submenu to free a
    # single button on the twelve-button main Selection page.
    replaced = False
    updated = []
    for label, action in main:
        if action == 'XR_SEL_BOUNDARY':
            updated.append(('QUICK SETS', 'XR_SLOT_MENU'))
            replaced = True
        else:
            updated.append((label, action))
    if not replaced:
        raise ValueError('Selection boundary slot already changed')
    if len(updated) > 12 or any(a == 'XR_SLOT_MENU' for _l, a in main):
        raise ValueError('No wrist menu capacity for Quick Sets')
    menus.PAGES[_SELECTION_PAGE] = tuple(updated)
    if not any(action == 'XR_SEL_BOUNDARY' for _label, action in flow):
        menus.PAGES[_FLOWS_PAGE] = (('BOUNDARY', 'XR_SEL_BOUNDARY'),
                                   *flow[:-1], flow[-1])
    if len(menus.PAGES[_FLOWS_PAGE]) > 12:
        raise ValueError('Edge Flows submenu has no room for Boundary')

    # Three named session slots: each can be saved, restored or cleared.
    # Add/Replace chooses what recall does, without affecting Select mode.
    menus.PAGES[_PAGE] = (
        ('SAVE A', 'XR_SLOT_SAVE_A'), ('LOAD A', 'XR_SLOT_LOAD_A'),
        ('CLEAR A', 'XR_SLOT_CLEAR_A'),
        ('SAVE B', 'XR_SLOT_SAVE_B'), ('LOAD B', 'XR_SLOT_LOAD_B'),
        ('CLEAR B', 'XR_SLOT_CLEAR_B'),
        ('SAVE C', 'XR_SLOT_SAVE_C'), ('LOAD C', 'XR_SLOT_LOAD_C'),
        ('CLEAR C', 'XR_SLOT_CLEAR_C'),
        ('ADD / REPLACE', 'XR_SLOT_MODE'), ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'SELECTION QUICK SETS'
    v065.TOOLTIPS.update({
        'XR_SLOT_MENU': ('Selection Quick Sets',
                         'Store three session-only native BMesh selections'),
        'XR_SLOT_MODE': ('Add or Replace Recall',
                         'Toggle additive and replace recall without modifying geometry'),
    })
    for label in _SLOTS:
        v065.TOOLTIPS['XR_SLOT_SAVE_' + label] = (
            'Save Selection ' + label, 'Record current native edit-mesh '
            'selection in a session-only slot')
        v065.TOOLTIPS['XR_SLOT_LOAD_' + label] = (
            'Recall Selection ' + label, 'Restore selected vertices, edges or '
            'faces using existing guarded XR history')
        v065.TOOLTIPS['XR_SLOT_CLEAR_' + label] = (
            'Clear Slot ' + label, 'Forget the session-only selection slot '
            'without changing Blender data')


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_quicksets_090_patched', False):
        return
    install_pages()
    original_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return original_command(self, context, action)
        if action == 'XR_SLOT_MENU':
            _check_owner(self)
            _current(context)
            menu.page = _PAGE
            self.status = 'QUICK SETS / SAVE / RECALL / CLEAR A, B, C'
            return
        if menu.page == _PAGE:
            if action == 'BACK':
                menu.page = _SELECTION_PAGE
                return
            _check_owner(self)
            if action == 'XR_SLOT_MODE':
                self._xr_selection_slots_add = not bool(getattr(
                    self, '_xr_selection_slots_add', False))
                self.status = ('QUICK SET RECALL / ' +
                               ('ADD' if self._xr_selection_slots_add else
                                'REPLACE'))
                return
            if action in _SAVE:
                return _store(self, context, _SAVE[action])
            if action in _RECALL:
                return _recall(self, context, _RECALL[action])
            if action in _CLEAR:
                saved = getattr(self, '_xr_selection_quicksets', None)
                if saved is not None:
                    saved.pop(_CLEAR[action], None)
                self.status = 'QUICK SET ' + _CLEAR[action] + ' / CLEARED'
                return
            raise ValueError('Quick Sets command not available')
        # Boundary moved into Edge Flows, whose original handler expects
        # edge-only flow actions. Call its existing _apply instead of
        # bypassing the guarded selection snapshot implementation.
        if menu.page == _FLOWS_PAGE and action == 'XR_SEL_BOUNDARY':
            _check_owner(self)
            return mesh_selection_tools_v086._apply(self, context, action)
        return original_command(self, context, action)

    Runtime.command = command
    Runtime._xr_quicksets_090_patched = True
