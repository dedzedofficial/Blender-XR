# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Blender scene hierarchy in the existing hand-mounted XR menu.

No scene duplicates, persistent custom layers, or extra editor windows.
The list is a snapshot during a menu interaction; an out-of-band rename or
deletion invalidates the selected row instead of targeting another object.
"""
from . import menus, v065

_LIST = 'SCENE_HIERARCHY'
_ITEM = 'SCENE_HIERARCHY_ITEM'
_PAGE_SIZE = 7


def _collection(context, path):
    collection = context.scene.collection
    for name in path:
        collection = collection.children.get(name)
        if collection is None:
            raise ValueError('Collection changed; reopen the hierarchy')
    return collection


def _items(context, path):
    collection = _collection(context, path)
    rows = [('COLLECTION', child.name) for child in collection.children]
    rows += [('OBJECT', obj.name) for obj in collection.objects
             if context.view_layer.objects.get(obj.name) == obj]
    return tuple(sorted(rows, key=lambda item: (item[0] != 'COLLECTION',
                                                item[1].casefold(), item[1])))


def _object(context, name):
    obj = context.view_layer.objects.get(name) if name else None
    if obj is None:
        raise ValueError('Object is no longer in the active view layer')
    return obj


def _require_object_mode(context):
    if context.mode != 'OBJECT':
        raise ValueError('Scene hierarchy editing needs Object Mode')


def _render_list(session, context):
    path = getattr(session, '_xr_hierarchy_path', [])
    entries = _items(context, path)
    page = max(0, int(getattr(session, '_xr_hierarchy_page', 0)))
    page = min(page, (len(entries) - 1) // _PAGE_SIZE if entries else 0)
    session._xr_hierarchy_page = page
    start = page * _PAGE_SIZE
    session._xr_hierarchy_rows = entries[start:start + _PAGE_SIZE]
    buttons = [
        (('C: ' if kind == 'COLLECTION' else 'O: ') + name[:17],
         'HIER_ROW_' + str(index))
        for index, (kind, name) in enumerate(session._xr_hierarchy_rows)
    ]
    if page:
        buttons.append(('PREVIOUS', 'HIER_PREV'))
    if start + _PAGE_SIZE < len(entries):
        buttons.append(('NEXT', 'HIER_NEXT'))
    if path:
        buttons.append(('UP LEVEL', 'HIER_UP'))
    buttons.extend((('REFRESH', 'HIER_REFRESH'), ('BACK', 'HIER_BACK')))
    menus.PAGES[_LIST] = tuple(buttons)
    menus.TITLES[_LIST] = ('SCENE / ' + _collection(context, path).name)[:21]
    session.menu.page = _LIST
    session.status = 'HIERARCHY / PAGE {} / {} ENTRIES'.format(page + 1, len(entries))


def _render_item(session, context):
    obj = _object(context, getattr(session, '_xr_hierarchy_object', None))
    hidden = obj.hide_get(view_layer=context.view_layer)
    locked = obj.hide_select
    menus.PAGES[_ITEM] = (
        ('SELECT', 'HIER_SELECT'),
        ('ADD/REMOVE', 'HIER_MULTI'),
        ('SHOW' if hidden else 'HIDE', 'HIER_VISIBILITY'),
        ('UNLOCK' if locked else 'LOCK', 'HIER_LOCK'),
        ('BACK', 'HIER_BACK'),
    )
    menus.TITLES[_ITEM] = ('OBJECT / ' + obj.name)[:21]
    session.menu.page = _ITEM
    session.status = ('HIDDEN / ' if hidden else 'VISIBLE / ') + (
        'LOCKED' if locked else 'UNLOCKED')


def _select(context, obj, additive=False):
    _require_object_mode(context)
    if obj.hide_select or not obj.visible_get(view_layer=context.view_layer):
        raise ValueError('Object is hidden or selection-locked')
    if not additive:
        for selected in tuple(context.selected_objects):
            if selected != obj:
                selected.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
    else:
        select = not obj.select_get(view_layer=context.view_layer)
        obj.select_set(select, view_layer=context.view_layer)
        if select:
            context.view_layer.objects.active = obj
        elif context.view_layer.objects.active == obj:
            context.view_layer.objects.active = None


def _toggle(session, context, obj, action):
    _require_object_mode(context)
    if obj.library or obj.override_library:
        raise ValueError('Linked/overridden objects cannot change hierarchy locks')
    if action == 'HIER_VISIBILITY':
        old = bool(obj.hide_get(view_layer=context.view_layer))
        new = not old
        if new and obj.select_get(view_layer=context.view_layer):
            obj.select_set(False, view_layer=context.view_layer)
        if new and context.view_layer.objects.active == obj:
            context.view_layer.objects.active = None
        obj.hide_set(new, view_layer=context.view_layer)
        kind = 'SCENE_VISIBILITY'
    else:
        old = bool(obj.hide_select)
        new = not old
        if new and obj.select_get(view_layer=context.view_layer):
            obj.select_set(False, view_layer=context.view_layer)
        if new and context.view_layer.objects.active == obj:
            context.view_layer.objects.active = None
        obj.hide_select = new
        kind = 'SCENE_SELECT_LOCK'
    session.history.push((kind, obj.name,
                          (context.scene.name, context.view_layer.name), old, new))
    _render_item(session, context)


def install_pages():
    menus.PAGES[_LIST] = (('BACK', 'HIER_BACK'),)
    menus.PAGES[_ITEM] = (('BACK', 'HIER_BACK'),)
    menus.TITLES[_LIST] = 'SCENE HIERARCHY'
    menus.TITLES[_ITEM] = 'OBJECT SETTINGS'
    v065.TOOLTIPS.update({
        'SCENE_MENU': ('Scene Hierarchy', 'Browse collections and select, hide or lock loaded objects on your offhand'),
        'HIER_SELECT': ('Select Object', 'Select this visible unlocked object exclusively'),
        'HIER_MULTI': ('Add/Remove Selection', 'Toggle this object within the current multi-selection'),
        'HIER_VISIBILITY': ('Toggle Object Visibility', 'Change view-layer visibility, preserving render visibility'),
        'HIER_LOCK': ('Toggle Selection Lock', 'Prevent selecting and editing this object'),
        'HIER_REFRESH': ('Refresh Hierarchy', 'Rebuild the object list after a scene change'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_hierarchy_patched', False):
        return
    install_pages()
    original_command = Runtime.command

    def command(self, context, action):
        if action == 'SCENE_MENU':
            _require_object_mode(context)
            self._xr_hierarchy_path = []
            self._xr_hierarchy_page = 0
            self._xr_hierarchy_object = None
            self._creator_parent_page = None
            _render_list(self, context)
            return
        if action == 'HIER_REFRESH' and self.menu.page == _LIST:
            _render_list(self, context)
            return
        if action in {'HIER_NEXT', 'HIER_PREV'} and self.menu.page == _LIST:
            self._xr_hierarchy_page += 1 if action == 'HIER_NEXT' else -1
            _render_list(self, context)
            return
        if action == 'HIER_UP' and self.menu.page == _LIST:
            if self._xr_hierarchy_path:
                self._xr_hierarchy_path.pop()
                self._xr_hierarchy_page = 0
            _render_list(self, context)
            return
        if action == 'HIER_BACK':
            if self.menu.page == _ITEM:
                _render_list(self, context)
            elif self.menu.page == _LIST:
                if getattr(self, '_xr_hierarchy_path', []):
                    self._xr_hierarchy_path.pop()
                    self._xr_hierarchy_page = 0
                    _render_list(self, context)
                else:
                    self.menu.page = 'CREATOR'
                    self.status = 'CREATOR HUB'
            else:
                return original_command(self, context, action)
            return
        if action.startswith('HIER_ROW_') and self.menu.page == _LIST:
            rows = tuple(getattr(self, '_xr_hierarchy_rows', ()))
            try:
                index = int(action[len('HIER_ROW_'):])
                kind, name = rows[index]
            except (ValueError, IndexError):
                raise ValueError('Hierarchy selection expired; refresh') from None
            # A row must never silently point to a different object after an
            # out-of-band rename, unlink or collection reordering.
            entries = _items(context, self._xr_hierarchy_path)
            start = self._xr_hierarchy_page * _PAGE_SIZE
            if rows != entries[start:start + _PAGE_SIZE]:
                _render_list(self, context)
                raise ValueError('Scene changed; choose an object again')
            if kind == 'COLLECTION':
                self._xr_hierarchy_path.append(name)
                self._xr_hierarchy_page = 0
                _render_list(self, context)
            else:
                self._xr_hierarchy_object = name
                _render_item(self, context)
            return
        if action in {'HIER_SELECT', 'HIER_MULTI',
                      'HIER_VISIBILITY', 'HIER_LOCK'} and self.menu.page == _ITEM:
            obj = _object(context, getattr(self, '_xr_hierarchy_object', None))
            if action in {'HIER_SELECT', 'HIER_MULTI'}:
                _select(context, obj, additive=(action == 'HIER_MULTI'))
                _render_item(self, context)
            else:
                _toggle(self, context, obj, action)
            return
        return original_command(self, context, action)

    Runtime.command = command
    Runtime._xr_hierarchy_patched = True
