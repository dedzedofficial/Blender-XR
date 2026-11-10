# SPDX-License-Identifier: GPL-3.0-or-later
"""Mesh XR v0.8.5: native Join, Join as Copy, Split and exact Unmerge.

Native source objects remain in the .blend while combined or separated: they
are hidden/locked for Join and Split, visible for Join as Copy. Unmerge restores
exact original objects (names, mesh data, UVs, materials, weights and transforms)
rather than falsely attempting to invert destructive topology operations.
"""
from array import array
import hashlib
import json
import uuid

import bpy

from . import menus, mesh, v065

_PAGE = 'XR_JOIN_SPLIT_085'
_MARKER = '_meshxr_parts_group'
_META = '_meshxr_parts_meta'
_SIGNATURE = '_meshxr_parts_signature'


def _editable(context, obj, allow_existing=False):
    if context.mode != 'OBJECT' or obj is None or obj.type != 'MESH' or obj.mode != 'OBJECT':
        raise ValueError('Select a mesh object in Object Mode')
    if context.view_layer.objects.get(obj.name) != obj:
        raise ValueError('Selected mesh must belong to the active view layer')
    if obj.library or obj.override_library or obj.data.library or obj.data.users != 1:
        raise ValueError('Use local, single-user meshes for Join/Separate')
    if obj.hide_select or not obj.visible_get(view_layer=context.view_layer):
        raise ValueError('Unlock and show the mesh before editing')
    if obj.parent or obj.constraints or obj.parent_type != 'OBJECT':
        raise ValueError('Clear parenting/constraints before joining or separating meshes')
    if obj.data.shape_keys or obj.data.animation_data or obj.animation_data:
        raise ValueError('Animated/shape-key meshes need native Blender review before joining')
    if obj.modifiers:
        raise ValueError('Apply or remove existing modifiers in Blender before joining')
    if not allow_existing and (_MARKER in obj or _META in obj):
        raise ValueError('Object is already part of a Mesh XR assembly; unmerge it first')
    return obj


def _fingerprint(data):
    digest = hashlib.sha256()
    digest.update(str((len(data.vertices), len(data.polygons),
                       len(data.loops))).encode())
    values = array('f', [0.0]) * (len(data.vertices) * 3)
    if values:
        data.vertices.foreach_get('co', values)
    digest.update(values.tobytes())
    for polygon in data.polygons:
        digest.update(bytes(str((tuple(polygon.vertices), polygon.material_index)), 'ascii'))
    for layer in data.uv_layers:
        digest.update(layer.name.encode('utf8'))
        uv = array('f', [0.0]) * (len(layer.data) * 2)
        if uv:
            layer.data.foreach_get('uv', uv)
        digest.update(uv.tobytes())
    for material in data.materials:
        digest.update((material.name if material else '').encode('utf8'))
    return digest.hexdigest()


def _source_state(context, obj):
    return {'name': obj.name,
            'hidden': bool(obj.hide_get(view_layer=context.view_layer)),
            'select_lock': bool(obj.hide_select), 'render_hide': bool(obj.hide_render),
            'fingerprint': _fingerprint(obj.data)}


def _sources(context, names):
    mapping = {obj.name: obj for obj in context.view_layer.objects}
    results = []
    for state in names:
        obj = mapping.get(state['name'])
        if obj is None or obj.type != 'MESH':
            raise ValueError('An original source object is missing')
        if _fingerprint(obj.data) != state['fingerprint']:
            raise ValueError('An original source mesh changed since joining')
        results.append(obj)
    return results


def _hide_sources(context, sources, record):
    for obj, state in zip(sources, record['sources']):
        if _fingerprint(obj.data) != state['fingerprint']:
            raise ValueError('Source geometry changed; cannot safely rebuild assembly')
        obj[_MARKER] = record['group']
        if record['mode'] != 'COPY':
            obj.hide_select = True
            obj.hide_render = True
            obj.hide_set(True, view_layer=context.view_layer)


def _restore_sources(context, record):
    objects = _sources(context, record['sources'])
    for obj, state in zip(objects, record['sources']):
        if obj.get(_MARKER) != record['group']:
            raise ValueError('Original source ownership marker changed')
        obj.hide_select = False
        obj.hide_set(state['hidden'], view_layer=context.view_layer)
        obj.hide_select = state['select_lock']
        obj.hide_render = state['render_hide']
        del obj[_MARKER]
    return objects


def _record_metadata(record):
    return json.dumps({'group': record['group'], 'mode': record['mode'],
                       'sources': record['sources']}, sort_keys=True)


def _outputs(context, record):
    objlist = [obj for obj in context.view_layer.objects
               if obj.get(_META) and obj.get(_MARKER) == record['group']]
    expected = {item['name'] for item in record['outputs']}
    if {obj.name for obj in objlist} != expected:
        raise ValueError('Combined mesh parts were renamed, removed or duplicated')
    for obj in objlist:
        if obj.type != 'MESH' or _fingerprint(obj.data) != obj.get(_SIGNATURE):
            raise ValueError('Joined mesh changed; use Separate instead of exact Unmerge')
    return objlist


def _remember(context, mode, source_objects, output_objects):
    group = uuid.uuid4().hex
    record = {
        'group': group, 'mode': mode,
        'scene': context.scene.name, 'layer': context.view_layer.name,
        'sources': [_source_state(context, obj) for obj in source_objects],
        'outputs': [],
    }
    data = _record_metadata(record)
    for obj in output_objects:
        obj[_META] = data
        obj[_MARKER] = group
        obj[_SIGNATURE] = _fingerprint(obj.data)
        snapshot = obj.data.copy()
        snapshot.name = '.Mesh XR Join Snapshot'
        record['outputs'].append({
            'name': obj.name, 'matrix': obj.matrix_world.copy(),
            'mesh': snapshot, 'signature': obj[_SIGNATURE],
            'display': obj.display_type,
            'hide_render': bool(obj.hide_render),
        })
    _hide_sources(context, source_objects, record)
    return record


def _take_snapshot(context, obj):
    raw = obj.get(_META)
    if not raw:
        raise ValueError('No saved original components; use Separate Loose/Material')
    meta = json.loads(str(raw))
    group = meta['group']
    objects = [candidate for candidate in context.view_layer.objects
               if candidate.get(_MARKER) == group and candidate.get(_META)]
    if not objects:
        raise ValueError('No joined components found')
    states = {item['name']: item for item in meta['sources']}
    if len(states) != len(meta['sources']):
        raise ValueError('Duplicate assembly source metadata')
    record = {'scene': context.scene.name, 'layer': context.view_layer.name,
              'group': group, 'mode': meta['mode'],
              'sources': list(meta['sources']), 'outputs': []}
    _sources(context, record['sources'])
    for part in objects:
        if part.get(_META) != raw or _fingerprint(part.data) != part.get(_SIGNATURE):
            raise ValueError('Joined mesh changed; exact original restoration is unsafe')
        snapshot = part.data.copy()
        snapshot.name = '.Mesh XR Join Snapshot'
        record['outputs'].append({
            'name': part.name, 'matrix': part.matrix_world.copy(),
            'mesh': snapshot, 'signature': part[_SIGNATURE],
            'display': part.display_type, 'hide_render': bool(part.hide_render)})
    return record


def _activate_outputs(context, record):
    for part in record['outputs']:
        if context.view_layer.objects.get(part['name']):
            raise ValueError('Output name reused; cannot redo Join/Separate')
    sources = _sources(context, record['sources'])
    for obj in sources:
        if obj.get(_MARKER):
            raise ValueError('Source already belongs to another active assembly')
    collection = context.scene.collection
    outputs = []
    data = _record_metadata(record)
    try:
        for part in record['outputs']:
            obj = bpy.data.objects.new(part['name'], part['mesh'].copy())
            collection.objects.link(obj)
            obj.matrix_world = part['matrix'].copy()
            obj.display_type = part['display']
            obj.hide_render = part['hide_render']
            obj[_META] = data
            obj[_MARKER] = record['group']
            obj[_SIGNATURE] = part['signature']
            outputs.append(obj)
        _hide_sources(context, sources, record)
    except Exception:
        for part in outputs:
            bpy.data.objects.remove(part, do_unlink=True)
        raise
    return outputs


def _activate_sources(context, record):
    outputs = _outputs(context, record)
    for state in record['sources']:
        obj = context.view_layer.objects.get(state['name'])
        if obj is None or obj.get(_MARKER) != record['group']:
            raise ValueError('Source object changed outside Mesh XR assembly')
    for obj in outputs:
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data.users == 0:
            bpy.data.meshes.remove(data)
    return _restore_sources(context, record)


def _select(context, objects, active=None):
    for item in tuple(context.selected_objects):
        item.select_set(False)
    for obj in objects:
        if obj.hide_select or obj.hide_get(view_layer=context.view_layer):
            continue
        obj.select_set(True)
    context.view_layer.objects.active = active or (objects[0] if objects else None)


def _input_objects(context):
    selection = tuple(sorted(context.selected_objects, key=lambda obj: obj.name))
    if len(selection) < 2:
        raise ValueError('Select two or more native mesh objects to Join')
    for obj in selection:
        _editable(context, obj)
    return selection


def _join(context):
    selection = _input_objects(context)
    active = context.view_layer.objects.active
    if active not in selection:
        raise ValueError('The active mesh must be included in the selection')
    created = []
    try:
        for obj in selection:
            copy = obj.copy()
            copy.data = obj.data.copy()
            context.scene.collection.objects.link(copy)
            copy.matrix_world = obj.matrix_world.copy()
            copy.hide_select = False
            copy.hide_render = False
            created.append((obj, copy))
        _select(context, [copy for _original, copy in created],
                next(copy for original, copy in created if original == active))
        result = bpy.ops.object.join()
        if 'FINISHED' not in result:
            raise ValueError('Blender could not join the selected meshes')
        output = context.view_layer.objects.active
        if output is None or output.type != 'MESH':
            raise ValueError('Joined Blender mesh was not created')
        return selection, [output]
    except Exception:
        for _original, clone in created:
            present = bpy.data.objects.get(clone.name) if clone else None
            if present is not None:
                data = present.data
                bpy.data.objects.remove(present, do_unlink=True)
                if data and data.users == 0:
                    bpy.data.meshes.remove(data)
        _select(context, selection, active)
        raise


def _split(context, kind):
    original = _editable(context, context.view_layer.objects.active)
    if len(context.selected_objects) != 1:
        raise ValueError('Select exactly one source mesh to Separate')
    preexisting = set(context.view_layer.objects)
    clone = original.copy()
    clone.data = original.data.copy()
    context.scene.collection.objects.link(clone)
    clone.matrix_world = original.matrix_world.copy()
    try:
        _select(context, [clone])
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        result = bpy.ops.mesh.separate(type=kind)
        if 'FINISHED' not in result:
            raise ValueError('Blender could not separate this mesh')
        bpy.ops.object.mode_set(mode='OBJECT')
        parts = sorted(set(context.view_layer.objects) - preexisting, key=lambda obj: obj.name)
        if len(parts) < 2 or any(obj.type != 'MESH' for obj in parts):
            raise ValueError('There are no separate mesh parts for this method')
        return [original], parts
    except Exception:
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for obj in tuple(set(context.view_layer.objects) - preexisting):
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if data and data.users == 0:
                bpy.data.meshes.remove(data)
        _select(context, [original])
        raise


def _create(session, context, action):
    if action in {'XR_JOIN_JOIN', 'XR_JOIN_COPY'}:
        sources, outputs = _join(context)
        mode = 'COPY' if action == 'XR_JOIN_COPY' else 'JOIN'
    elif action in {'XR_JOIN_LOOSE', 'XR_JOIN_MATERIAL'}:
        mode = 'SPLIT'
        kind = 'LOOSE' if action == 'XR_JOIN_LOOSE' else 'MATERIAL'
        sources, outputs = _split(context, kind)
    else:
        raise ValueError('Unknown Join/Separate command')
    record = _remember(context, mode, sources, outputs)
    _select(context, outputs, outputs[0])
    session.history.push(('XR_PARTS_085', 'MAKE', record))
    session.status = '{} / {} NATIVE MESH OBJECTS'.format(mode, len(outputs))


def _restore(session, context):
    active = context.view_layer.objects.active
    if active is None or _META not in active:
        raise ValueError('Select a Mesh XR joined/separated result to restore original parts')
    record = _take_snapshot(context, active)
    sources = _activate_sources(context, record)
    _select(context, sources, sources[0])
    session.history.push(('XR_PARTS_085', 'UNMERGE', record))
    session.status = 'UNMERGED / {} EXACT ORIGINAL OBJECTS'.format(len(sources))


def _history_patch():
    if getattr(mesh.History, '_xr_parts_085', False):
        return
    old_step, old_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == 'XR_PARTS_085':
            for part in entry[2]['outputs']:
                data = part['mesh']
                try:
                    if data.users == 0 and bpy.data.meshes.get(data.name) == data:
                        bpy.data.meshes.remove(data)
                except ReferenceError:
                    pass
            return
        return old_release(entry)

    def step(self, backwards=True):
        src, dst = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not src or src[-1][0] != 'XR_PARTS_085':
            return old_step(self, backwards)
        _tag, operation, record = src[-1]
        context = bpy.context
        if (context.mode != 'OBJECT' or context.scene.name != record['scene'] or
                context.view_layer.name != record['layer']):
            raise ValueError('Restore the original scene and Object Mode for Join history')
        show_sources = (backwards if operation == 'MAKE' else not backwards)
        if show_sources:
            originals = _activate_sources(context, record)
            _select(context, originals, originals[0])
        else:
            outputs = _activate_outputs(context, record)
            _select(context, outputs, outputs[0])
        dst.append(src.pop())
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_parts_085 = True


def install_pages():
    menus.PAGES[_PAGE] = (
        ('JOIN', 'XR_JOIN_JOIN'),
        ('JOIN AS COPY', 'XR_JOIN_COPY'),
        ('UNMERGE', 'XR_JOIN_RESTORE'),
        ('LOOSE PARTS', 'XR_JOIN_LOOSE'),
        ('BY MATERIAL', 'XR_JOIN_MATERIAL'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'JOIN & UNMERGE'
    buttons = tuple(menus.PAGES['XR_ASSEMBLY_085'])
    if not any(action == 'XR_JOIN_MENU' for _, action in buttons):
        menus.PAGES['XR_ASSEMBLY_085'] = buttons[:-1] + (
            ('JOIN / SPLIT', 'XR_JOIN_MENU'), buttons[-1])
    v065.TOOLTIPS.update({
        'XR_JOIN_MENU': ('Join/Separate Meshes', 'Join while retaining original parts for exact Unmerge'),
        'XR_JOIN_JOIN': ('Join + Retain Sources', 'Create one native mesh; hide and preserve originals in .blend'),
        'XR_JOIN_COPY': ('Join as Copy', 'Create one native mesh and keep source parts visible'),
        'XR_JOIN_RESTORE': ('Unmerge Original Parts', 'Restore retained original native source objects exactly'),
        'XR_JOIN_LOOSE': ('Separate Loose Parts', 'Split disconnected mesh islands into native meshes'),
        'XR_JOIN_MATERIAL': ('Separate by Material', 'Split material regions without deleting original'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_parts_085_patched', False):
        return
    _history_patch()
    install_pages()
    previous = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous(self, context, action)
        if action == 'XR_JOIN_MENU':
            if context.mode != 'OBJECT':
                raise ValueError('Switch to Object Mode for Join/Separate')
            menu.page = _PAGE
            self.status = 'JOIN/UNMERGE / SELECT NATIVE MESHES'
            return
        if menu.page == _PAGE:
            if action == 'BACK':
                menu.page = 'XR_ASSEMBLY_085'
                return
            if action == 'XR_JOIN_RESTORE':
                _restore(self, context)
                return
            if action.startswith('XR_JOIN_'):
                _create(self, context, action)
                return
        return previous(self, context, action)

    Runtime.command = command
    Runtime._xr_parts_085_patched = True
