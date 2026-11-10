# SPDX-License-Identifier: GPL-3.0-or-later
"""Mesh XR v0.8.5: native object parenting and Empty assemblies.

Existing Scene Hierarchy -> Object -> Assembly. All changes use native Blender
Object.parent, no proprietary collection groups. Each operation is a single
guarded XR-local undo entry and preserves the original world transforms.
"""
import bpy
from mathutils import Matrix, Vector

from . import mesh, menus, scene_hierarchy_v080, v065

_PAGE = 'XR_ASSEMBLY_085'


def _object(context, obj):
    if context.mode != 'OBJECT' or obj is None or obj.mode != 'OBJECT':
        raise ValueError('Use Object Mode for assemblies')
    if context.view_layer.objects.get(obj.name) != obj:
        raise ValueError('Object must belong to the active view layer')
    if obj.library or obj.override_library or (obj.data and obj.data.library):
        raise ValueError('Linked or overridden objects are protected')
    if obj.hide_select or not obj.visible_get(view_layer=context.view_layer):
        raise ValueError('Unlock and show the object before editing')
    if obj.constraints or obj.parent_type != 'OBJECT':
        raise ValueError('Constrained or bone/vertex parenting needs Blender object properties')
    if obj.animation_data and (obj.animation_data.action or obj.animation_data.drivers):
        raise ValueError('Animated parenting needs the native Blender editor')
    return obj


def _selected(context):
    selected = tuple(sorted(context.selected_objects, key=lambda obj: obj.name))
    if not selected:
        raise ValueError('Select one or more objects')
    for obj in selected:
        _object(context, obj)
    return selected


def _snapshot(obj):
    return (obj.parent.name if obj.parent else None,
            obj.parent_type, obj.parent_bone,
            obj.matrix_parent_inverse.copy(), obj.matrix_world.copy())


def _eq(left, right):
    if left[:3] != right[:3]:
        return False
    return all(abs(float(left[i][r][c]) - float(right[i][r][c])) < 1e-5
               for i in (3, 4) for r in range(4) for c in range(4))


def _restore(obj, state):
    name, kind, bone, inverse, matrix = state
    parent = bpy.data.objects.get(name) if name else None
    if name and parent is None:
        raise ValueError('Assembly parent was deleted outside XR history')
    obj.parent = parent
    obj.parent_type = kind
    obj.parent_bone = bone
    obj.matrix_parent_inverse = inverse.copy()
    obj.matrix_world = matrix.copy()


def _parent(child, parent):
    if child == parent:
        raise ValueError('An object cannot parent itself')
    check = parent
    while check is not None:
        if check == child:
            raise ValueError('Parent loop detected; choose a different parent')
        check = check.parent
    world = child.matrix_world.copy()
    child.parent = parent
    child.parent_type = 'OBJECT'
    child.matrix_parent_inverse = parent.matrix_world.inverted_safe()
    child.matrix_world = world


def _commit(session, context, objects, operation, empty_name=None, empty_matrix=None):
    before = tuple((obj.name, obj.as_pointer(), _snapshot(obj)) for obj in objects)
    try:
        operation()
    except Exception:
        for name, _pointer, state in reversed(before):
            obj = context.view_layer.objects.get(name)
            if obj:
                _restore(obj, state)
        if empty_name:
            empty = bpy.data.objects.get(empty_name)
            if empty and empty.type == 'EMPTY':
                bpy.data.objects.remove(empty, do_unlink=True)
        raise
    after = tuple((name, token, old, _snapshot(context.view_layer.objects[name]))
                  for name, token, old in before)
    changed = tuple(row for row in after if not _eq(row[2], row[3]))
    if not changed and not empty_name:
        session.status = 'ASSEMBLY ALREADY MATCHES REQUEST'
        return False
    session.history.push(('XR_ASSEMBLY_PARENT', context.scene.name,
                          context.view_layer.name, changed,
                          empty_name, empty_matrix.copy() if empty_matrix else None,
                          context.scene.collection.name))
    session.status = 'ASSEMBLY / {} OBJECTS UPDATED'.format(len(changed))
    return True


def _empty(context, objects):
    loc = (sum((obj.matrix_world.translation for obj in objects), Vector())
           / len(objects) if objects else context.scene.cursor.location.copy())
    obj = bpy.data.objects.new('Mesh XR Assembly', None)
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = .3
    context.scene.collection.objects.link(obj)
    obj.matrix_world = Matrix.Translation(loc)
    return obj


def _act(session, context, action):
    objects = _selected(context)
    active = context.view_layer.objects.active
    if action == 'XR_ASSEMBLY_PARENT':
        if active not in objects or len(objects) < 2:
            raise ValueError('Select the child objects and the active parent')
        children = tuple(obj for obj in objects if obj != active)
        if any(obj == active.parent for obj in children):
            raise ValueError('Parenting selection would create a cycle')
        _commit(session, context, children,
                lambda: [_parent(obj, active) for obj in children])
    elif action == 'XR_ASSEMBLY_CLEAR':
        children = tuple(obj for obj in objects if obj.parent)
        if not children:
            raise ValueError('None of the selected objects has a parent')
        def clear():
            for obj in children:
                matrix = obj.matrix_world.copy()
                obj.parent = None
                obj.matrix_world = matrix
        _commit(session, context, children, clear)
    elif action in {'XR_ASSEMBLY_EMPTY', 'XR_ASSEMBLY_EMPTY_ONLY'}:
        obj = _empty(context, objects)
        try:
            if action == 'XR_ASSEMBLY_EMPTY':
                _commit(session, context, objects,
                        lambda: [_parent(child, obj) for child in objects],
                        obj.name, obj.matrix_world)
            else:
                _commit(session, context, (), lambda: None, obj.name, obj.matrix_world)
            for old in tuple(context.selected_objects):
                old.select_set(False)
            obj.select_set(True)
            context.view_layer.objects.active = obj
        except Exception:
            if bpy.data.objects.get(obj.name) == obj:
                bpy.data.objects.remove(obj, do_unlink=True)
            raise
    elif action == 'XR_ASSEMBLY_PARENT_SELECT':
        if active is None or active.parent is None:
            raise ValueError('The active object has no parent')
        _object(context, active.parent)
        for obj in tuple(context.selected_objects):
            obj.select_set(False)
        active.parent.select_set(True)
        context.view_layer.objects.active = active.parent
        session.status = 'SELECTED PARENT / ' + active.parent.name
    elif action == 'XR_ASSEMBLY_CHILDREN_SELECT':
        if active is None:
            raise ValueError('Select a parent object first')
        children = tuple(obj for obj in context.view_layer.objects if obj.parent == active)
        if not children:
            raise ValueError('Selected parent has no direct children')
        for obj in children:
            _object(context, obj)
        for obj in tuple(context.selected_objects):
            obj.select_set(False)
        for obj in children:
            obj.select_set(True)
        context.view_layer.objects.active = active
        active.select_set(True)
        session.status = 'SELECTED {} CHILDREN'.format(len(children))
    else:
        raise ValueError('Unknown assembly operation')


def _patch_history():
    if getattr(mesh.History, '_xr_assembly_085_history', False):
        return
    old_step = mesh.History.step
    old_release = mesh.History.release

    def release(entry):
        if entry[0] == 'XR_ASSEMBLY_PARENT':
            return
        return old_release(entry)

    def step(self, backwards=True):
        src, dst = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not src or src[-1][0] != 'XR_ASSEMBLY_PARENT':
            return old_step(self, backwards)
        _tag, scene_name, layer_name, records, empty_name, empty_matrix, _collection = src[-1]
        ctx = bpy.context
        if (ctx.mode != 'OBJECT' or ctx.scene.name != scene_name or
                ctx.view_layer.name != layer_name):
            raise ValueError('Restore the original scene and Object Mode for assembly undo')
        expected = 3 if backwards else 2
        for name, pointer, before, after in records:
            obj = _object(ctx, ctx.view_layer.objects.get(name))
            if obj.as_pointer() != pointer or not _eq(_snapshot(obj), (before, after)[0 if expected == 2 else 1]):
                raise ValueError('Assembly changed outside XR history')
        empty = bpy.data.objects.get(empty_name) if empty_name else None
        if empty_name:
            if backwards:
                if empty is None or empty.type != 'EMPTY':
                    raise ValueError('Created Empty changed outside XR history')
                if any(obj.parent == empty and obj.name not in {row[0] for row in records}
                       for obj in ctx.view_layer.objects):
                    raise ValueError('Empty has new children; cannot safely undo')
            else:
                if empty is not None:
                    raise ValueError('Empty name has been reused outside XR history')
                empty = bpy.data.objects.new(empty_name, None)
                empty.empty_display_type = 'PLAIN_AXES'
                empty.empty_display_size = .3
                ctx.scene.collection.objects.link(empty)
                empty.matrix_world = empty_matrix.copy()
        for name, _pointer, before, after in records:
            _restore(ctx.view_layer.objects[name], before if backwards else after)
        if empty_name and backwards:
            bpy.data.objects.remove(empty, do_unlink=True)
        dst.append(src.pop())
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_assembly_085_history = True


def install_pages():
    menus.PAGES[_PAGE] = (
        ('PARENT ACTIVE', 'XR_ASSEMBLY_PARENT'),
        ('PARENT EMPTY', 'XR_ASSEMBLY_EMPTY'),
        ('CREATE EMPTY', 'XR_ASSEMBLY_EMPTY_ONLY'),
        ('CLEAR PARENT', 'XR_ASSEMBLY_CLEAR'),
        ('SELECT PARENT', 'XR_ASSEMBLY_PARENT_SELECT'),
        ('SELECT CHILDREN', 'XR_ASSEMBLY_CHILDREN_SELECT'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'OBJECT ASSEMBLY'
    v065.TOOLTIPS.update({
        'XR_ASSEMBLY_MENU': ('Object Assembly', 'Parent objects and create Empty hierarchies'),
        'XR_ASSEMBLY_PARENT': ('Parent to Active', 'Selected non-active objects become children; keep world position'),
        'XR_ASSEMBLY_EMPTY': ('Group Under Empty', 'Create native Empty at group center and parent selection'),
        'XR_ASSEMBLY_CLEAR': ('Clear Parent', 'Keep each child at its current world position'),
    })
    # The item page is contextual and has capacity; preserve all former
    # hierarchy commands, adding a single entry.
    buttons = tuple(menus.PAGES['SCENE_HIERARCHY_ITEM'])
    if not any(action == 'XR_ASSEMBLY_MENU' for _, action in buttons):
        menus.PAGES['SCENE_HIERARCHY_ITEM'] = buttons[:-1] + (
            ('ASSEMBLY', 'XR_ASSEMBLY_MENU'), buttons[-1])


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_assembly_085_patched', False):
        return
    _patch_history()
    install_pages()
    previous = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous(self, context, action)
        if action == 'XR_ASSEMBLY_MENU':
            if context.mode != 'OBJECT':
                raise ValueError('Enter Object Mode before assembling objects')
            menu.page = _PAGE
            self.status = 'ASSEMBLY / SELECT OBJECTS FROM HIERARCHY'
            return
        if menu.page == _PAGE:
            if action == 'BACK':
                objname = getattr(self, '_xr_hierarchy_object', None)
                if objname and context.view_layer.objects.get(objname):
                    scene_hierarchy_v080._render_item(self, context)
                else:
                    scene_hierarchy_v080._render_list(self, context)
                return
            if action.startswith('XR_ASSEMBLY_'):
                _act(self, context, action)
                return
        return previous(self, context, action)

    Runtime.command = command
    Runtime._xr_assembly_085_patched = True
