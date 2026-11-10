# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Mirror/Array editing through the existing Mesh XR modifier menu.

Controls target an already-existing Blender modifier by name, unless the user
explicitly presses NEW. Every confirmed button action records an XR-local undo
entry; no modal previews, evaluated meshes or hidden duplicate modifiers.
"""
import bpy

from . import menus, mesh, v065, v071

_MIRROR_PAGE = 'XR_MIRROR_EDIT'
_ARRAY_PAGE = 'XR_ARRAY_EDIT'
_ARRAY_MODE_PAGE = 'XR_ARRAY_MODES'
_MODIFIER_KINDS = frozenset(('MIRROR', 'ARRAY'))


def _editable(context):
    if context.mode != 'OBJECT':
        raise ValueError('Use Object Mode to edit modifiers')
    obj = context.view_layer.objects.active
    if obj is None or obj.type != 'MESH' or obj.mode != 'OBJECT':
        raise ValueError('Select a mesh object in Object Mode')
    if (obj.library or obj.override_library or
            (obj.data and obj.data.library)):
        raise ValueError('Linked or overridden mesh objects cannot be edited')
    if obj.hide_select or not obj.visible_get(view_layer=context.view_layer):
        raise ValueError('Unlock and show the mesh before editing modifiers')
    return obj


def _reference(name):
    if name is None:
        return None
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError('Modifier reference object changed or was deleted')
    return obj


def _state(mod):
    """Snapshot only supported native RNA fields; no modifier stack rebuild."""
    if mod.type == 'MIRROR':
        return (
            tuple(bool(x) for x in mod.use_axis),
            bool(mod.use_clip),
            bool(mod.use_mirror_merge),
            float(mod.merge_threshold),
            mod.mirror_object.name if mod.mirror_object else None,
            bool(mod.show_viewport),
        )
    if mod.type == 'ARRAY':
        return (
            int(mod.count),
            bool(mod.use_relative_offset),
            tuple(float(x) for x in mod.relative_offset_displace),
            bool(mod.use_constant_offset),
            tuple(float(x) for x in mod.constant_offset_displace),
            bool(mod.use_object_offset),
            mod.offset_object.name if mod.offset_object else None,
            bool(mod.show_viewport),
        )
    raise ValueError('Only native Mirror and Array modifiers are supported')


def _same(a, b):
    if isinstance(a, (float, int)) and isinstance(b, (float, int)):
        return abs(a - b) <= 1e-7
    if isinstance(a, tuple) and isinstance(b, tuple):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def _restore(mod, state):
    if mod.type == 'MIRROR':
        axes, clip, merge, threshold, target, visible = state
        reference = _reference(target)
        mod.use_axis = axes
        mod.use_clip = clip
        mod.use_mirror_merge = merge
        mod.merge_threshold = threshold
        mod.mirror_object = reference
        mod.show_viewport = visible
    elif mod.type == 'ARRAY':
        count, relative, rel_values, constant, const_values, object_mode, target, visible = state
        reference = _reference(target)
        mod.count = count
        mod.use_relative_offset = relative
        mod.relative_offset_displace = rel_values
        mod.use_constant_offset = constant
        mod.constant_offset_displace = const_values
        mod.use_object_offset = object_mode
        mod.offset_object = reference
        mod.show_viewport = visible
    else:
        raise ValueError('Unsupported modifier for XR undo')


def _target(context):
    obj = _editable(context)
    selected = [other for other in context.selected_objects if other != obj]
    if len(selected) != 1 or selected[0] == obj:
        raise ValueError('Select exactly one other object as the modifier reference')
    other = selected[0]
    if context.view_layer.objects.get(other.name) != other:
        raise ValueError('Reference must belong to the active view layer')
    return other


def _chosen(session, context, kind):
    obj = _editable(context)
    selection = getattr(session, '_xr_native_modifier', None)
    if not selection or selection[:3] != (obj.name, obj.as_pointer(), kind):
        raise ValueError('Selected modifier changed; reopen the modifier page')
    name = selection[3]
    mod = obj.modifiers.get(name) if name else None
    if mod is None or mod.type != kind:
        raise ValueError('Modifier was removed; reopen the modifier page')
    return obj, mod


def _page(session, kind):
    session.menu.page = _MIRROR_PAGE if kind == 'MIRROR' else _ARRAY_PAGE
    session.status = '{} / {}'.format(kind, session._xr_native_modifier[3] or 'PRESS NEW')


def _open(session, context, kind):
    obj = _editable(context)
    mods = [mod for mod in obj.modifiers if mod.type == kind]
    session._xr_native_modifier = (obj.name, obj.as_pointer(), kind,
                                   mods[0].name if mods else None)
    _page(session, kind)


def _next(session, context, kind):
    obj = _editable(context)
    previous = getattr(session, '_xr_native_modifier', None)
    if not previous or previous[:3] != (obj.name, obj.as_pointer(), kind):
        raise ValueError('Reopen the modifier page')
    names = [mod.name for mod in obj.modifiers if mod.type == kind]
    if not names:
        raise ValueError('No {} modifiers available'.format(kind))
    old = previous[3]
    name = names[(names.index(old) + 1) % len(names)] if old in names else names[0]
    session._xr_native_modifier = (obj.name, obj.as_pointer(), kind, name)
    _page(session, kind)


def _history_entry(obj, mod, old, new, created=False, index=None):
    if old is not None and _same(old, new):
        return None
    return ('XR_NATIVE_MODIFIER', obj.name, obj.data.name, obj,
            mod.name, mod.type, old, new, bool(created),
            len(obj.modifiers) - 1 if index is None else int(index))


def _edit(session, context, kind, action):
    obj, mod = _chosen(session, context, kind)
    before = _state(mod)
    try:
        if kind == 'MIRROR':
            if action in {'XR_MIRROR_X', 'XR_MIRROR_Y', 'XR_MIRROR_Z'}:
                axis = 'XYZ'.index(action[-1])
                axes = list(mod.use_axis)
                axes[axis] = not axes[axis]
                mod.use_axis = axes
            elif action == 'XR_MIRROR_CLIP':
                mod.use_clip = not mod.use_clip
            elif action == 'XR_MIRROR_MERGE':
                mod.use_mirror_merge = not mod.use_mirror_merge
            elif action in {'XR_MIRROR_THRESHOLD_DOWN', 'XR_MIRROR_THRESHOLD_UP'}:
                delta = -.0005 if action.endswith('DOWN') else .0005
                mod.merge_threshold = max(0.0, min(.1, mod.merge_threshold + delta))
            elif action == 'XR_MIRROR_TARGET':
                mod.mirror_object = _target(context)
            elif action == 'XR_MIRROR_TARGET_CLEAR':
                mod.mirror_object = None
            else:
                raise ValueError('Unknown Mirror action')
        else:
            if action in {'XR_ARRAY_COUNT_DOWN', 'XR_ARRAY_COUNT_UP'}:
                delta = -1 if action.endswith('DOWN') else 1
                mod.count = max(1, min(10000, mod.count + delta))
            elif action in {'XR_ARRAY_X_DOWN', 'XR_ARRAY_X_UP',
                            'XR_ARRAY_Y_DOWN', 'XR_ARRAY_Y_UP',
                            'XR_ARRAY_Z_DOWN', 'XR_ARRAY_Z_UP'}:
                axis = 'XYZ'.index(action[9])
                delta = -.1 if action.endswith('DOWN') else .1
                if mod.use_object_offset and not (mod.use_relative_offset or mod.use_constant_offset):
                    raise ValueError('Choose Relative or Constant spacing before dragging')
                attr = ('relative_offset_displace' if mod.use_relative_offset else
                        'constant_offset_displace')
                values = list(getattr(mod, attr))
                values[axis] = max(-1000.0, min(1000.0, values[axis] + delta))
                setattr(mod, attr, values)
            elif action == 'XR_ARRAY_MODE_RELATIVE':
                mod.use_relative_offset = True
                mod.use_constant_offset = False
                mod.use_object_offset = False
            elif action == 'XR_ARRAY_MODE_CONSTANT':
                mod.use_relative_offset = False
                mod.use_constant_offset = True
                mod.use_object_offset = False
            elif action == 'XR_ARRAY_MODE_OBJECT':
                target = _target(context)
                mod.offset_object = target
                mod.use_relative_offset = False
                mod.use_constant_offset = False
                mod.use_object_offset = True
            elif action == 'XR_ARRAY_TARGET_CLEAR':
                mod.offset_object = None
                mod.use_object_offset = False
                if not mod.use_constant_offset:
                    mod.use_relative_offset = True
            else:
                raise ValueError('Unknown Array action')
    except Exception:
        _restore(mod, before)
        raise
    entry = _history_entry(obj, mod, before, _state(mod))
    if entry:
        session.history.push(entry)
    session.status = '{} / {}'.format(kind, action.replace('_', ' '))
    return entry


def _create(session, context, kind):
    obj = _editable(context)
    mod = obj.modifiers.new(name='Mesh XR ' + kind.title(), type=kind)
    if kind == 'MIRROR':
        mod.use_axis = (True, False, False)
        mod.use_clip = True
    else:
        mod.count = 2
    session._xr_native_modifier = (obj.name, obj.as_pointer(), kind, mod.name)
    session.history.push(_history_entry(obj, mod, None, _state(mod), created=True))
    _page(session, kind)


def _history_patch():
    if getattr(mesh.History, '_xr_native_modifiers_patched', False):
        return
    old_step = mesh.History.step
    old_release = mesh.History.release

    def release(entry):
        if entry[0] == 'XR_NATIVE_MODIFIER':
            return
        return old_release(entry)

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] != 'XR_NATIVE_MODIFIER':
            return old_step(self, backwards)
        entry = source[-1]
        (_tag, obj_name, data_name, identity, mod_name, kind,
         before, after, created, index) = entry
        obj = bpy.data.objects.get(obj_name)
        if (bpy.context.mode != 'OBJECT' or obj is None or obj != identity
                or obj.data.name != data_name or obj.library or
                obj.override_library or obj.hide_select):
            raise ValueError('The modifier object changed outside XR history')
        existing = obj.modifiers.get(mod_name)
        if created and not backwards:
            if existing is not None:
                raise ValueError('Modifier name is occupied; undo history is stale')
            mod = obj.modifiers.new(mod_name, kind)
            try:
                _restore(mod, after)
                obj.modifiers.move(len(obj.modifiers) - 1, min(index, len(obj.modifiers) - 1))
            except Exception:
                obj.modifiers.remove(mod)
                raise
        else:
            if existing is None or existing.type != kind or (
                    list(obj.modifiers).index(existing) != index):
                raise ValueError('Modifier stack changed outside XR history')
            expected = after if backwards else before
            if not _same(_state(existing), expected):
                raise ValueError('Modifier values changed outside XR history')
            if created:
                obj.modifiers.remove(existing)
            else:
                _restore(existing, before if backwards else after)
        dest.append(source.pop())
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_native_modifiers_patched = True


def install_pages():
    # Retain Solidify, managed visibility and thickness/count shortcuts.
    # Mirror axes and Array creation live in the dedicated context pages.
    menus.PAGES['MODIFIER_MENU'] = (
        ('MIRROR EDIT', 'MOD_MIRROR_EDIT_MENU'),
        ('ARRAY EDIT', 'MOD_ARRAY_EDIT_MENU'),
        ('SOLIDIFY', 'MOD_SOLIDIFY'), ('COUNT +', 'MOD_COUNT_UP'),
        ('COUNT -', 'MOD_COUNT_DOWN'),
        ('THICK +', 'MOD_THICK_UP'), ('THICK -', 'MOD_THICK_DOWN'),
        ('SHOW/HIDE', 'MOD_TOGGLE'), ('REMOVE', 'MOD_REMOVE'),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_MIRROR_PAGE] = (
        ('NEW', 'XR_MIRROR_NEW'), ('NEXT', 'XR_MIRROR_NEXT'),
        ('X', 'XR_MIRROR_X'), ('Y', 'XR_MIRROR_Y'),
        ('Z', 'XR_MIRROR_Z'), ('CLIPPING', 'XR_MIRROR_CLIP'),
        ('MERGE', 'XR_MIRROR_MERGE'),
        ('MERGE -', 'XR_MIRROR_THRESHOLD_DOWN'),
        ('MERGE +', 'XR_MIRROR_THRESHOLD_UP'),
        ('REF TARGET', 'XR_MIRROR_TARGET'),
        ('CLEAR REF', 'XR_MIRROR_TARGET_CLEAR'), ('BACK', 'BACK'),
    )
    menus.PAGES[_ARRAY_PAGE] = (
        ('NEW', 'XR_ARRAY_NEW'), ('NEXT', 'XR_ARRAY_NEXT'),
        ('COUNT -', 'XR_ARRAY_COUNT_DOWN'), ('COUNT +', 'XR_ARRAY_COUNT_UP'),
        ('X -', 'XR_ARRAY_X_DOWN'), ('X +', 'XR_ARRAY_X_UP'),
        ('Y -', 'XR_ARRAY_Y_DOWN'), ('Y +', 'XR_ARRAY_Y_UP'),
        ('Z -', 'XR_ARRAY_Z_DOWN'), ('Z +', 'XR_ARRAY_Z_UP'),
        ('SPACING', 'XR_ARRAY_MODES_MENU'), ('BACK', 'BACK'),
    )
    menus.PAGES[_ARRAY_MODE_PAGE] = (
        ('RELATIVE', 'XR_ARRAY_MODE_RELATIVE'),
        ('CONSTANT', 'XR_ARRAY_MODE_CONSTANT'),
        ('OBJECT REF', 'XR_ARRAY_MODE_OBJECT'),
        ('CLEAR REF', 'XR_ARRAY_TARGET_CLEAR'), ('BACK', 'BACK'),
    )
    menus.TITLES.update({_MIRROR_PAGE: 'EDIT MIRROR', _ARRAY_PAGE: 'EDIT ARRAY',
                         _ARRAY_MODE_PAGE: 'ARRAY SPACING'})
    v065.TOOLTIPS.update({
        'MOD_MIRROR_EDIT_MENU': ('Edit Mirror', 'Edit any existing native Mirror or explicitly add one'),
        'MOD_ARRAY_EDIT_MENU': ('Edit Array', 'Edit any existing native Array or explicitly add one'),
        'XR_MIRROR_TARGET': ('Mirror Reference', 'Select exactly one other object along with the mesh'),
        'XR_ARRAY_MODE_OBJECT': ('Object Offset', 'Select exactly one other object along with the mesh'),
        'XR_ARRAY_MODES_MENU': ('Array Spacing', 'Choose Relative, Constant or Object offset'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_native_modifiers_patched', False):
        return
    _history_patch()
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        if action == 'MODIFIER_MENU':
            v071._idle(self)
            _editable(context)
            if getattr(self.menu, 'page', None) == 'CREATOR':
                self._creator_parent_page = 'MODIFIER_MENU'
            self.menu.page = 'MODIFIER_MENU'
            self.status = 'MODIFIERS / SELECT MIRROR OR ARRAY'
            return
        if action in {'MOD_MIRROR_EDIT_MENU', 'MOD_ARRAY_EDIT_MENU'}:
            v071._idle(self)
            _open(self, context, 'MIRROR' if action == 'MOD_MIRROR_EDIT_MENU' else 'ARRAY')
            return
        page = getattr(self.menu, 'page', None)
        if action == 'BACK' and page in {_MIRROR_PAGE, _ARRAY_PAGE, _ARRAY_MODE_PAGE}:
            if page == _ARRAY_MODE_PAGE:
                self.menu.page = _ARRAY_PAGE
            else:
                self.menu.page = 'MODIFIER_MENU'
            self.status = 'MODIFIERS'
            return
        if action == 'XR_ARRAY_MODES_MENU' and page == _ARRAY_PAGE:
            _chosen(self, context, 'ARRAY')
            self.menu.page = _ARRAY_MODE_PAGE
            self.status = 'ARRAY SPACING / SELECT MODE'
            return
        kind = ('MIRROR' if page == _MIRROR_PAGE else
                'ARRAY' if page in {_ARRAY_PAGE, _ARRAY_MODE_PAGE} else None)
        if kind and action.startswith('XR_'):
            v071._idle(self)
            if action == 'XR_' + kind + '_NEW':
                _create(self, context, kind)
            elif action == 'XR_' + kind + '_NEXT':
                _next(self, context, kind)
            else:
                _edit(self, context, kind, action)
            return
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_native_modifiers_patched = True
