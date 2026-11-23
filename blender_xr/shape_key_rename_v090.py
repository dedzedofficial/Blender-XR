# SPDX-License-Identifier: GPL-3.0-or-later
"""Headset-native shape-key naming with exact-name XR Undo/Redo.

Reuses the established hierarchy keyboard's visible alphabet, but writes
only a native Blender KeyBlock.name. Does not alter Basis, mesh topology,
shape geometry, vertex groups, any FCurve, or the project's naming format.
"""
import bpy

from . import (hierarchy_rename_v086, input_ownership_v080, menus, mesh,
               shape_key_v090, v065)

_PAGE = 'XR_SHAPE_RENAME_090'
_BACK_PAGE = shape_key_v090._PAGE
_SYMBOLS = hierarchy_rename_v086._SYMBOLS
_KEYS_PER_PAGE = hierarchy_rename_v086._KEYS_PER_PAGE
_MAX_BYTES = 63
_TAG = 'XR_SHAPE_RENAME_090'


def _layout(keys, ignore_index):
    return tuple((i, b.name, b.as_pointer())
                 for i, b in enumerate(keys.key_blocks)
                 if i != ignore_index)


def _entry(context, obj, keys, index, before, after):
    block = keys.key_blocks[index]
    return (_TAG, context.scene.name, context.view_layer.name,
            obj.name, obj.as_pointer(), obj.data.name, obj.data.as_pointer(),
            keys.as_pointer(), index, block.as_pointer(), before, after,
            _layout(keys, index), len(obj.data.vertices))


def _guard(context, entry, backwards):
    (_kind, scene_name, layer_name, obj_name, obj_ptr, mesh_name,
     mesh_ptr, keys_ptr, index, block_ptr, before, after, others,
     vertex_count) = entry
    if (context.mode != 'OBJECT' or context.scene.name != scene_name or
            context.view_layer.name != layer_name):
        raise ValueError('Restore the original scene/view layer and Object Mode')
    obj = context.view_layer.objects.active
    if (obj is None or obj.name != obj_name or obj.as_pointer() != obj_ptr or
            obj.type != 'MESH' or obj.data.name != mesh_name or
            obj.data.as_pointer() != mesh_ptr or
            len(obj.data.vertices) != vertex_count):
        raise ValueError('Shape-key mesh was changed or replaced outside XR')
    obj, keys = shape_key_v090._object(context)
    if keys.as_pointer() != keys_ptr or len(keys.key_blocks) != len(others) + 1:
        raise ValueError('Original Blender shape-key data was replaced')
    if _layout(keys, index) != others:
        raise ValueError('Other shape keys changed outside XR rename history')
    if not 0 < index < len(keys.key_blocks):
        raise ValueError('A shape key was removed or reordered since rename')
    block = keys.key_blocks[index]
    expected = after if backwards else before
    target = before if backwards else after
    if block.as_pointer() != block_ptr or block.name != expected:
        raise ValueError('The renamed key changed outside XR history')
    if any(other != block and other.name == target
           for other in keys.key_blocks):
        raise ValueError('The desired shape key name is already occupied')
    return block, target


def _rename(context, session, new_name):
    obj, keys, index, block = shape_key_v090._target(context)
    if not new_name.strip() or len(new_name.encode('utf-8')) > _MAX_BYTES:
        raise ValueError('Enter a nonempty native shape-key name (max 63 bytes)')
    before = block.name
    if new_name == before:
        return before, False
    if any(other != block and other.name == new_name
           for other in keys.key_blocks):
        raise ValueError('Another shape key already has that exact name')
    history = getattr(session, 'history', None)
    if history is None:
        raise ValueError('XR history is required before renaming shape keys')
    entry = _entry(context, obj, keys, index, before, new_name)
    block.name = new_name
    if block.name != new_name:
        block.name = before
        raise ValueError('Blender rejected the requested shape-key name')
    try:
        history.push(entry)
    except Exception:
        if block.name == new_name:
            block.name = before
        raise
    return new_name, True


def _target(session, context):
    state = getattr(session, '_xr_shape_rename_state', None)
    if state is None:
        raise ValueError('No active shape-key rename')
    if (context.scene.name != state['scene'] or
            context.view_layer.name != state['layer']):
        raise ValueError('Scene/view layer changed; cancel the rename')
    obj, keys, index, block = shape_key_v090._target(context)
    if (obj.name != state['obj_name'] or
            obj.as_pointer() != state['obj_ptr'] or
            obj.data.as_pointer() != state['mesh_ptr'] or
            keys.as_pointer() != state['keys_ptr'] or
            index != state['index'] or
            block.as_pointer() != state['block_ptr'] or
            block.name != state['before'] or
            _layout(keys, index) != state['other_keys']):
        raise ValueError('Shape key changed while the headset keyboard was open')
    return state


def _keyboard(session):
    state = session._xr_shape_rename_state
    count = (len(_SYMBOLS) + _KEYS_PER_PAGE - 1) // _KEYS_PER_PAGE
    page = state['page'] % count
    state['page'] = page
    start = page * _KEYS_PER_PAGE
    options = []
    labels = {' ': 'SPACE', '_': 'UNDERSCORE', '-': 'DASH', '.': 'DOT'}
    for index in range(start, min(start + _KEYS_PER_PAGE, len(_SYMBOLS))):
        key = _SYMBOLS[index]
        shown = key.lower() if state['lower'] and key.isalpha() else key
        options.append((labels.get(shown, shown),
                        'XR_SHAPE_RENAME_CHAR_' + str(index)))
    options.extend((
        ('MORE KEYS', 'XR_SHAPE_RENAME_NEXT'),
        ('UPPERCASE' if state['lower'] else 'LOWERCASE', 'XR_SHAPE_RENAME_CASE'),
        ('DELETE', 'XR_SHAPE_RENAME_DELETE'),
        ('CLEAR', 'XR_SHAPE_RENAME_CLEAR'),
        ('SAVE', 'XR_SHAPE_RENAME_SAVE'),
        ('CANCEL', 'XR_SHAPE_RENAME_CANCEL'),
    ))
    if len(options) > 12:
        raise ValueError('Shape key keyboard exceeds XR menu capacity')
    menus.PAGES[_PAGE] = tuple(options)
    menus.TITLES[_PAGE] = 'SHAPE NAME / {} OF {}'.format(page + 1, count)
    session.menu.page = _PAGE
    session.status = ('SHAPE KEY NAME / ' + (state['text'][-38:] or '(EMPTY)'))


def _begin(session, context):
    obj, keys, index, block = shape_key_v090._target(context)
    if input_ownership_v080.is_editing(session):
        raise ValueError('Release controller gestures before shape-key naming')
    session._xr_shape_rename_state = {
        'scene': context.scene.name,
        'layer': context.view_layer.name,
        'obj_name': obj.name,
        'obj_ptr': obj.as_pointer(),
        'mesh_ptr': obj.data.as_pointer(),
        'keys_ptr': keys.as_pointer(),
        'index': index,
        'block_ptr': block.as_pointer(),
        'before': block.name,
        'other_keys': _layout(keys, index),
        'text': block.name,
        'lower': False,
        'page': 0,
    }
    _keyboard(session)


def _cancel(session):
    session._xr_shape_rename_state = None
    session.menu.page = _BACK_PAGE
    session.status = 'SHAPE KEY NAME / CANCELLED / NO DATA CHANGE'


def _history():
    if getattr(mesh.History, '_xr_shape_rename_090_patched', False):
        return
    previous_step, previous_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == _TAG:
            return
        return previous_release(entry)

    def step(self, backwards=True):
        src, dst = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not src or src[-1][0] != _TAG:
            return previous_step(self, backwards)
        block, name = _guard(bpy.context, src[-1], backwards)
        previous = block.name
        block.name = name
        if block.name != name:
            block.name = previous
            raise ValueError('Blender rejected the XR history shape-key name')
        dst.append(src.pop())
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_shape_rename_090_patched = True


def install_pages():
    original = tuple(menus.PAGES[_BACK_PAGE])
    if not original or original[-1][1] != 'BACK':
        raise ValueError('Shape Keys value page is unavailable')
    if not any(action == 'XR_SHAPE_RENAME_MENU' for _label, action in original):
        original = original[:-1] + (('RENAME', 'XR_SHAPE_RENAME_MENU'),
                                    original[-1])
    if len(original) > 12:
        raise ValueError('Native Shape Keys menu has no room for Rename')
    menus.PAGES[_BACK_PAGE] = original
    menus.PAGES[_PAGE] = (('CANCEL', 'XR_SHAPE_RENAME_CANCEL'),)
    menus.TITLES[_PAGE] = 'RENAME SHAPE KEY'
    v065.TOOLTIPS.update({
        'XR_SHAPE_RENAME_MENU': ('Rename Native Shape Key',
             'Enter an exact KeyBlock name with the headset keyboard and guarded XR Undo'),
        'XR_SHAPE_RENAME_SAVE': ('Commit Shape Key Name',
             'Change the actual Blender KeyBlock name and record one XR Undo step'),
        'XR_SHAPE_RENAME_CANCEL': ('Cancel Shape Key Rename',
             'Leave the Blender key name and all other native data unchanged'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_shape_rename_090_patched', False):
        return
    _history()
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous_command(self, context, action)
        if action == 'XR_SHAPE_RENAME_MENU' and menu.page == _BACK_PAGE:
            _begin(self, context)
            return
        if menu.page != _PAGE:
            return previous_command(self, context, action)
        if action in {'BACK', 'XR_SHAPE_RENAME_CANCEL'}:
            _cancel(self)
            return
        state = _target(self, context)
        if action.startswith('XR_SHAPE_RENAME_CHAR_'):
            try:
                index = int(action[len('XR_SHAPE_RENAME_CHAR_'):])
            except ValueError:
                raise ValueError('Invalid shape key character') from None
            if (index < 0 or index >= len(_SYMBOLS) or
                    index // _KEYS_PER_PAGE != state['page']):
                raise ValueError('Shape-key keyboard page expired')
            ch = _SYMBOLS[index]
            ch = ch.lower() if state['lower'] and ch.isalpha() else ch
            if len((state['text'] + ch).encode('utf-8')) <= _MAX_BYTES:
                state['text'] += ch
        elif action == 'XR_SHAPE_RENAME_NEXT':
            state['page'] += 1
        elif action == 'XR_SHAPE_RENAME_CASE':
            state['lower'] = not state['lower']
        elif action == 'XR_SHAPE_RENAME_DELETE':
            state['text'] = state['text'][:-1]
        elif action == 'XR_SHAPE_RENAME_CLEAR':
            state['text'] = ''
        elif action == 'XR_SHAPE_RENAME_SAVE':
            name, changed = _rename(context, self, state['text'])
            self._xr_shape_rename_state = None
            menu.page = _BACK_PAGE
            self.status = ('SHAPE NAME / ' + name[:40] +
                           (' / UNDO READY' if changed else ' / UNCHANGED'))
            return
        else:
            raise ValueError('Finish or cancel the Shape Key rename first')
        _keyboard(self)

    Runtime.command = command
    Runtime._xr_shape_rename_090_patched = True
