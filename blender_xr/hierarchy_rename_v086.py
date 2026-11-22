# SPDX-License-Identifier: GPL-3.0-or-later
"""Headset keyboard and guarded native Object.name editing for Mesh XR.

Name changes happen only on explicit Save. An existing XR undo/redo stack
contains name-addressed history entries, so clearing that stack requires a
second confirmation; no history is silently discarded. The accepted rename
itself remains undoable within the current XR session.
"""
import bpy

from . import mesh, menus, scene_hierarchy_v080 as hierarchy, v065

_PAGE = 'XR_HIER_RENAME_086'
_CONFIRM = 'XR_HIER_RENAME_CONFIRM_086'
_SYMBOLS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-.'
_KEYS_PER_PAGE = 6
_LIMIT = 63


def _editable(context, obj):
    hierarchy._require_object_mode(context)
    if obj.mode != 'OBJECT' or context.view_layer.objects.get(obj.name) != obj:
        raise ValueError('Rename requires an object in the active view layer')
    if obj.library or obj.override_library:
        raise ValueError('Linked or library-overridden objects cannot be renamed')
    if obj.hide_select or not obj.visible_get(view_layer=context.view_layer):
        raise ValueError('Unlock and show the object before renaming')
    return obj


def _state_object(session, context):
    state = getattr(session, '_xr_hierarchy_rename_state', None)
    if not state:
        raise ValueError('No active object rename')
    if (context.scene.name, context.view_layer.name) != (state['scene'], state['layer']):
        raise ValueError('Scene/view layer changed; cancel and reopen rename')
    obj = bpy.data.objects.get(state['original'])
    if obj is None or obj.as_pointer() != state['pointer']:
        raise ValueError('Object was renamed or replaced outside XR')
    return state, _editable(context, obj)


def _keyboard(session):
    state = session._xr_hierarchy_rename_state
    # The symbol set is independent of the allowed name length.
    pages = (len(_SYMBOLS) + _KEYS_PER_PAGE - 1) // _KEYS_PER_PAGE
    state['page'] %= pages
    start = state['page'] * _KEYS_PER_PAGE
    symbols = _SYMBOLS[start:start + _KEYS_PER_PAGE]
    labels = {' ': 'SPACE', '_': 'UNDERSCORE', '-': 'DASH', '.': 'DOT'}
    buttons = []
    for index, char in enumerate(symbols, start):
        shown = char.lower() if state['lower'] and char.isalpha() else char
        buttons.append((labels.get(shown, shown), 'HIER_RENAME_KEY_' + str(index)))
    buttons.extend((
        ('MORE KEYS', 'HIER_RENAME_NEXT'),
        ('UPPERCASE' if state['lower'] else 'LOWERCASE', 'HIER_RENAME_CASE'),
        ('DELETE', 'HIER_RENAME_DELETE'),
        ('CLEAR', 'HIER_RENAME_CLEAR'),
        ('SAVE', 'HIER_RENAME_SAVE'),
        ('CANCEL', 'HIER_RENAME_CANCEL'),
    ))
    menus.PAGES[_PAGE] = tuple(buttons)
    menus.TITLES[_PAGE] = 'RENAME / {} OF {}'.format(state['page'] + 1, pages)
    session.menu.page = _PAGE
    session.status = 'NEW OBJECT NAME / ' + (state['text'][-42:] or '(EMPTY)')


def _begin(session, context):
    obj = _editable(context, hierarchy._active_item(session, context))
    session._xr_hierarchy_rename_state = {
        'scene': context.scene.name,
        'layer': context.view_layer.name,
        'original': obj.name,
        'pointer': obj.as_pointer(),
        'text': obj.name,
        'page': 0,
        'lower': False,
    }
    _keyboard(session)


def _cancel(session, context):
    session._xr_hierarchy_rename_state = None
    try:
        hierarchy._render_item(session, context)
    except ValueError:
        # A removed or externally renamed object must not strand the headset
        # on a keyboard with no editable object.
        session._xr_hierarchy_path = []
        session._xr_hierarchy_query = ''
        session._xr_hierarchy_page = 0
        hierarchy._render_list(session, context)


def _commit(session, context):
    state, obj = _state_object(session, context)
    new_name = state['text']
    if not new_name.strip():
        raise ValueError('Object name cannot be blank')
    if len(new_name.encode('utf-8')) > _LIMIT:
        raise ValueError('Object name exceeds the 63-byte limit')
    old_name = obj.name
    if new_name == old_name:
        _cancel(session, context)
        session.status = 'OBJECT NAME UNCHANGED'
        return
    occupied = bpy.data.objects.get(new_name)
    if occupied is not None and occupied != obj:
        raise ValueError('Another Blender object already has that name')
    # Complete preflight BEFORE invalidating old name-addressed history.
    obj.name = new_name
    if obj.name != new_name:
        obj.name = old_name
        raise ValueError('Blender could not assign that exact object name')
    session.history.clear()
    session.history.push(('XR_HIER_RENAME_086', state['scene'], state['layer'],
                          state['pointer'], old_name, new_name))
    session._xr_hierarchy_object = new_name
    session._xr_hierarchy_object_ptr = obj.as_pointer()
    session._xr_hierarchy_query = ''
    session._xr_hierarchy_rename_state = None
    hierarchy._render_item(session, context)
    session.status = 'OBJECT RENAMED / ' + new_name[:42]


def _save(session, context):
    state, obj = _state_object(session, context)
    name = state['text']
    if not name.strip():
        raise ValueError('Object name cannot be blank')
    if len(name.encode('utf-8')) > _LIMIT:
        raise ValueError('Object name exceeds the 63-byte limit')
    if bpy.data.objects.get(name) not in (None, obj):
        raise ValueError('Another Blender object already has that name')
    if name != obj.name and (session.history.undo or session.history.redo):
        menus.PAGES[_CONFIRM] = (
            ('RENAME + RESET UNDO', 'HIER_RENAME_CONFIRM'),
            ('KEEP MY HISTORY', 'HIER_RENAME_CANCEL'),
            ('EDIT NAME', 'HIER_RENAME_EDIT'),
        )
        session.menu.page = _CONFIRM
        session.status = 'RENAME REQUIRES DISCARDING OLD XR UNDO/REDO / CONFIRM'
    else:
        _commit(session, context)


def _patch_history():
    if getattr(mesh.History, '_xr_hierarchy_rename_086_history', False):
        return
    original_step, original_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == 'XR_HIER_RENAME_086':
            return
        return original_release(entry)

    def step(self, backwards=True):
        src, dst = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not src or src[-1][0] != 'XR_HIER_RENAME_086':
            return original_step(self, backwards)
        _, scene, layer, pointer, before, after = src[-1]
        ctx = bpy.context
        if (ctx.mode != 'OBJECT' or ctx.scene.name != scene or
                ctx.view_layer.name != layer):
            raise ValueError('Return to the original scene and Object Mode for rename undo')
        current = after if backwards else before
        target = before if backwards else after
        obj = bpy.data.objects.get(current)
        if obj is None or obj.as_pointer() != pointer:
            raise ValueError('Renamed object changed outside XR history')
        _editable(ctx, obj)
        if bpy.data.objects.get(target) not in (None, obj):
            raise ValueError('Undo name is already in use by another object')
        obj.name = target
        if obj.name != target:
            raise ValueError('Blender rejected the XR history name')
        dst.append(src.pop())
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_hierarchy_rename_086_history = True


def install_pages():
    menus.PAGES[_PAGE] = (('CANCEL', 'HIER_RENAME_CANCEL'),)
    menus.PAGES[_CONFIRM] = (('EDIT NAME', 'HIER_RENAME_EDIT'),)
    menus.TITLES[_PAGE] = 'RENAME OBJECT'
    menus.TITLES[_CONFIRM] = 'RESET XR HISTORY?'
    v065.TOOLTIPS.update({
        'HIER_RENAME_SAVE': ('Save Object Name', 'Commit the exact name; no automatic Blender .001 suffix'),
        'HIER_RENAME_CONFIRM': ('Confirm Rename and Reset History',
                                'Existing name-addressed XR undo entries are discarded'),
        'HIER_RENAME_CANCEL': ('Cancel Rename', 'Discard the typed name without changing Blender'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_hierarchy_rename_086_patched', False):
        return
    _patch_history()
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous_command(self, context, action)
        if action == 'HIER_RENAME' and menu.page == hierarchy._ITEM:
            _begin(self, context)
            return
        if menu.page not in {_PAGE, _CONFIRM}:
            return previous_command(self, context, action)
        if action in {'HIER_RENAME_CANCEL', 'HIER_BACK', 'BACK'}:
            _cancel(self, context)
            return
        if menu.page == _CONFIRM:
            if action == 'HIER_RENAME_EDIT':
                _state_object(self, context)
                _keyboard(self)
                return
            if action == 'HIER_RENAME_CONFIRM':
                _commit(self, context)
                return
            raise ValueError('Confirm or cancel the pending rename')
        state, _obj = _state_object(self, context)
        if action.startswith('HIER_RENAME_KEY_'):
            try:
                index = int(action[len('HIER_RENAME_KEY_'):])
            except ValueError:
                raise ValueError('Invalid keyboard key') from None
            if not (0 <= index < len(_SYMBOLS) and
                    index // _KEYS_PER_PAGE == state['page']):
                raise ValueError('Rename key expired; choose from current keyboard page')
            char = _SYMBOLS[index]
            if state['lower'] and char.isalpha():
                char = char.lower()
            if len((state['text'] + char).encode('utf-8')) <= _LIMIT:
                state['text'] += char
        elif action == 'HIER_RENAME_NEXT':
            state['page'] += 1
        elif action == 'HIER_RENAME_CASE':
            state['lower'] = not state['lower']
        elif action == 'HIER_RENAME_DELETE':
            state['text'] = state['text'][:-1]
        elif action == 'HIER_RENAME_CLEAR':
            state['text'] = ''
        elif action == 'HIER_RENAME_SAVE':
            _save(self, context)
            return
        else:
            raise ValueError('Finish or cancel the object rename first')
        _keyboard(self)

    Runtime.command = command
    Runtime._xr_hierarchy_rename_086_patched = True
