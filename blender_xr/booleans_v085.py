# SPDX-License-Identifier: GPL-3.0-or-later
"""Mesh XR v0.8.5 native Boolean Shape Builder.

Object Mode Boolean Difference/Union/Intersect on an explicit active mesh and
one cutter. Existing user modifiers are never replaced. Applying is explicit,
guarded and uses full native Mesh snapshots for XR undo/redo.
"""
import bpy

from . import menus, mesh, v065

_PAGE = 'XR_BOOLEAN_085'
_MANAGED = 'Mesh XR Boolean'


def _valid(context, obj):
    if context.mode != 'OBJECT' or obj is None or obj.type != 'MESH' or obj.mode != 'OBJECT':
        raise ValueError('Select a mesh in Object Mode')
    if context.view_layer.objects.get(obj.name) != obj:
        raise ValueError('Object is not in this view layer')
    if obj.library or obj.override_library or obj.data.library or obj.data.users != 1:
        raise ValueError('Use a local single-user mesh')
    if obj.hide_select or not obj.visible_get(view_layer=context.view_layer):
        raise ValueError('Unlock and show the mesh first')
    if obj.constraints or obj.parent_type != 'OBJECT':
        raise ValueError('Constrained or bone-parented objects cannot be Boolean edited in XR')
    return obj


def _pair(context):
    selection = tuple(context.selected_objects)
    target = _valid(context, context.view_layer.objects.active)
    if len(selection) != 2 or target not in selection:
        raise ValueError('Select exactly two mesh objects; active is target')
    cutter = next(obj for obj in selection if obj != target)
    _valid(context, cutter)
    if target == cutter:
        raise ValueError('Target and cutter must be different')
    return target, cutter


def _mod(target, cutter):
    return next((m for m in target.modifiers
                 if m.type == 'BOOLEAN' and m.name.startswith(_MANAGED)
                 and m.object == cutter), None)


def _state(mod):
    return (mod.operation, mod.solver, mod.object.name if mod.object else None,
            bool(mod.show_viewport))


def _restore_mod(mod, state):
    operation, solver, cutter_name, visible = state
    cutter = bpy.data.objects.get(cutter_name)
    if cutter is None or cutter.type != 'MESH':
        raise ValueError('Boolean cutter was removed')
    mod.operation = operation
    mod.solver = solver
    mod.object = cutter
    mod.show_viewport = visible


def _visual(obj):
    return (str(obj.display_type), bool(obj.hide_render))


def _set_visual(obj, state):
    obj.display_type, obj.hide_render = state


def _same(a, b):
    return a == b


def _choose(session, context):
    target, cutter = _pair(context)
    session._xr_boolean_pair = (target.name, target.as_pointer(),
                                cutter.name, cutter.as_pointer())
    session.menu.page = _PAGE
    session.status = 'BOOLEAN / TARGET {} / CUTTER {}'.format(target.name[:16], cutter.name[:16])


def _selected_pair(session, context):
    target, cutter = _pair(context)
    expected = getattr(session, '_xr_boolean_pair', None)
    if expected != (target.name, target.as_pointer(), cutter.name, cutter.as_pointer()):
        raise ValueError('Boolean selection changed; reopen the Boolean menu')
    return target, cutter


def _edit(session, context, action):
    target, cutter = _selected_pair(session, context)
    existing = _mod(target, cutter)
    before = _state(existing) if existing else None
    cutter_before = _visual(cutter)
    index = list(target.modifiers).index(existing) if existing else len(target.modifiers)
    if action in {'XR_BOOL_DIFFERENCE', 'XR_BOOL_UNION', 'XR_BOOL_INTERSECT'}:
        if existing is None:
            existing = target.modifiers.new(_MANAGED, 'BOOLEAN')
        existing.object = cutter
        existing.operation = action.removeprefix('XR_BOOL_')
        existing.solver = 'EXACT'
        existing.show_viewport = True
        if not any(other.type == 'BOOLEAN' and other.object == cutter
                   for mesh_obj in context.scene.objects if mesh_obj.type == 'MESH'
                   for other in mesh_obj.modifiers if mesh_obj != target):
            cutter.display_type = 'WIRE'
            cutter.hide_render = True
    elif action == 'XR_BOOL_TOGGLE':
        if existing is None:
            raise ValueError('Create a Boolean modifier first')
        existing.show_viewport = not existing.show_viewport
    elif action == 'XR_BOOL_REMOVE':
        if existing is None:
            raise ValueError('No Mesh XR Boolean modifier for this pair')
        target.modifiers.remove(existing)
    else:
        raise ValueError('Unknown Boolean action')
    after_mod = _mod(target, cutter)
    after = _state(after_mod) if after_mod else None
    cutter_after = _visual(cutter)
    if before == after and cutter_before == cutter_after:
        session.status = 'BOOLEAN UNCHANGED'
        return
    # Removing a Boolean cannot reconstruct the creator's prior cutter visual
    # without a stable saved value: do not silently alter it.
    session.history.push(('XR_BOOL_EDIT', target, cutter, target.name, cutter.name,
                          before, after, index, cutter_before, cutter_after))
    session.status = 'BOOLEAN / ' + action.removeprefix('XR_BOOL_')


def _safe_apply(session, context):
    target, cutter = _selected_pair(session, context)
    mod = _mod(target, cutter)
    if mod is None:
        raise ValueError('Create a Boolean before applying it')
    if target.data.shape_keys or target.vertex_groups:
        raise ValueError('Applying Bool to shape keys/weighted rigs requires desktop review')
    if target.parent is not None or target.animation_data or target.data.animation_data:
        raise ValueError('Animated/parented mesh needs desktop Boolean Apply')
    if len(target.modifiers) != 1:
        raise ValueError('Apply Boolean in XR only when it is the sole modifier')
    if abs(target.matrix_world.determinant()) < 1e-8:
        raise ValueError('Object has invalid transform')
    before = target.data.copy()
    before.name = '.Mesh XR Boolean Before'
    old = _state(mod)
    position = list(target.modifiers).index(mod)
    old_cutter_visual = _visual(cutter)
    try:
        with bpy.context.temp_override(active_object=target, object=target,
                                       selected_objects=[target], selected_editable_objects=[target]):
            result = bpy.ops.object.modifier_apply(modifier=mod.name)
        if 'FINISHED' not in result:
            raise ValueError('Blender refused to apply the Boolean')
    except Exception:
        if target.modifiers.get(mod.name) is None:
            new_mod = target.modifiers.new(_MANAGED, 'BOOLEAN')
            _restore_mod(new_mod, old)
        prior_data = target.data
        target.data = before.copy()
        if prior_data.users == 0:
            bpy.data.meshes.remove(prior_data)
        if before.users == 0:
            bpy.data.meshes.remove(before)
        raise
    after = target.data.copy()
    after.name = '.Mesh XR Boolean After'
    session.history.push(('XR_BOOL_APPLY', target, cutter, target.name, cutter.name,
                          before, after, old, position, old_cutter_visual))
    session.status = 'BOOLEAN APPLIED / ORIGINAL CUTTER PRESERVED'


def _history_patch():
    if getattr(mesh.History, '_xr_bool_085', False):
        return
    old_step, old_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == 'XR_BOOL_EDIT':
            return
        if entry[0] == 'XR_BOOL_APPLY':
            for snapshot in entry[5:7]:
                try:
                    if snapshot.users == 0 and bpy.data.meshes.get(snapshot.name) == snapshot:
                        bpy.data.meshes.remove(snapshot)
                except ReferenceError:
                    pass
            return
        return old_release(entry)

    def step(self, backwards=True):
        src, dst = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not src or src[-1][0] not in {'XR_BOOL_EDIT', 'XR_BOOL_APPLY'}:
            return old_step(self, backwards)
        entry = src[-1]
        context = bpy.context
        target, cutter = entry[1:3]
        if (context.mode != 'OBJECT' or
                bpy.data.objects.get(entry[3]) != target or
                bpy.data.objects.get(entry[4]) != cutter):
            raise ValueError('Boolean objects changed outside XR history')
        _valid(context, target)
        _valid(context, cutter)
        current = _mod(target, cutter)
        if entry[0] == 'XR_BOOL_EDIT':
            before, after, position, visual_before, visual_after = entry[5:]
            expected = after if backwards else before
            if (current is None) != (expected is None):
                raise ValueError('Boolean stack changed outside XR history')
            if current is not None and _state(current) != expected:
                raise ValueError('Boolean settings changed outside XR history')
            if _visual(cutter) != (visual_after if backwards else visual_before):
                raise ValueError('Cutter display changed outside XR history')
            wanted = before if backwards else after
            if wanted is None and current is not None:
                target.modifiers.remove(current)
            elif wanted is not None:
                if current is None:
                    current = target.modifiers.new(_MANAGED, 'BOOLEAN')
                    target.modifiers.move(len(target.modifiers)-1,
                                          min(position, len(target.modifiers)-1))
                _restore_mod(current, wanted)
            _set_visual(cutter, visual_before if backwards else visual_after)
        else:
            before, after, modstate, position, cutter_visual = entry[5:]
            if backwards:
                if current is not None:
                    raise ValueError('Applied Boolean has reappeared outside XR history')
                old = target.data
                target.data = before.copy()
                restored = target.modifiers.new(_MANAGED, 'BOOLEAN')
                _restore_mod(restored, modstate)
                target.modifiers.move(len(target.modifiers)-1,
                                      min(position, len(target.modifiers)-1))
            else:
                if current is None or _state(current) != modstate:
                    raise ValueError('Boolean modifier changed outside XR history')
                old = target.data
                target.data = after.copy()
                target.modifiers.remove(current)
            if old.users == 0:
                bpy.data.meshes.remove(old)
        dst.append(src.pop())
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_bool_085 = True


def install_pages():
    menus.PAGES[_PAGE] = (
        ('CUT', 'XR_BOOL_DIFFERENCE'),
        ('UNION', 'XR_BOOL_UNION'),
        ('INTERSECT', 'XR_BOOL_INTERSECT'),
        ('SHOW/HIDE', 'XR_BOOL_TOGGLE'),
        ('APPLY', 'XR_BOOL_APPLY'),
        ('REMOVE', 'XR_BOOL_REMOVE'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'BOOLEAN SHAPE BUILDER'
    buttons = tuple(menus.PAGES['XR_ASSEMBLY_085'])
    if not any(act == 'XR_BOOL_MENU' for _, act in buttons):
        menus.PAGES['XR_ASSEMBLY_085'] = buttons[:-1] + (
            ('BOOLEANS', 'XR_BOOL_MENU'), buttons[-1])
    v065.TOOLTIPS.update({
        'XR_BOOL_MENU': ('Boolean Shapes', 'Select target active and one mesh cutter'),
        'XR_BOOL_DIFFERENCE': ('Cut Mesh', 'Subtract the cutter using an editable native Boolean'),
        'XR_BOOL_UNION': ('Boolean Union', 'Join intersecting volumes without applying'),
        'XR_BOOL_INTERSECT': ('Boolean Intersect', 'Keep only overlapping volume'),
        'XR_BOOL_APPLY': ('Apply Boolean', 'Bake safe editable mesh only, after compatibility checks'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_bool_085_patched', False):
        return
    _history_patch()
    install_pages()
    previous = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous(self, context, action)
        if action == 'XR_BOOL_MENU':
            _choose(self, context)
            return
        if menu.page == _PAGE:
            if action == 'BACK':
                menu.page = 'XR_ASSEMBLY_085'
                return
            if action == 'XR_BOOL_APPLY':
                _safe_apply(self, context)
                return
            if action.startswith('XR_BOOL_'):
                _edit(self, context, action)
                return
        return previous(self, context, action)

    Runtime.command = command
    Runtime._xr_bool_085_patched = True
