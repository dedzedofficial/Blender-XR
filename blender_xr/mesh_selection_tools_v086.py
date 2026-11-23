# SPDX-License-Identifier: GPL-3.0-or-later
"""Native edit-mesh selection operations for the Mesh XR wrist controls.

All operations work on the existing Blender edit BMesh, respect hidden mesh
elements, and preserve selected vertex/edge/face mode. Selection changes
use XR-local undo/redo with a topology fingerprint; they never create mesh
duplicates, modifiers, custom layers or proprietary object properties.
"""
import hashlib
import struct

import bmesh

from . import input_ownership_v080, menus, mesh, selection, v065

_PAGE = 'XR_SELECTION_TOOLS_086'
_FLOWS_PAGE = 'XR_EDGE_FLOWS_086'
_TAG = 'XR_MESH_SELECTION_086'
_ACTIONS = {
    'XR_SEL_ALL': 'ALL',
    'XR_SEL_NONE': 'NONE',
    'XR_SEL_INVERT': 'INVERT',
    'XR_SEL_LINKED': 'LINKED',
    'XR_SEL_GROW': 'GROW',
    'XR_SEL_SHRINK': 'SHRINK',
    'XR_SEL_BOUNDARY': 'BOUNDARY',
    'XR_SEL_NONMANIFOLD': 'NONMANIFOLD',
    'XR_SEL_LOOSE': 'LOOSE',
    'XR_SEL_SHARP': 'SHARP',
    'XR_SEL_EDGE_LOOP': 'EDGE_LOOP',
    'XR_SEL_EDGE_RING': 'EDGE_RING',
    'XR_SEL_BOUNDARY_CHAIN': 'BOUNDARY_CHAIN',
    'XR_SEL_SEAM_CHAIN': 'SEAM_CHAIN',
    'XR_SEL_SHARP_CHAIN': 'SHARP_CHAIN',
}
_GROUPS = {'VERT': 'verts', 'EDGE': 'edges', 'FACE': 'faces'}


def _editable(context):
    obj = context.view_layer.objects.active
    if (obj is None or obj.type != 'MESH' or obj.mode != 'EDIT' or
            context.mode != 'EDIT_MESH'):
        raise ValueError('Use Mesh Edit Mode for Selection Tools')
    mesh.editable(obj)
    if obj.override_library or obj.hide_select or not obj.visible_get(view_layer=context.view_layer):
        raise ValueError('Selection needs a visible, unlocked, local mesh')
    return obj


def _current(obj, mode):
    if mode not in _GROUPS:
        raise ValueError('Choose vertex, edge or face selection mode')
    bm = bmesh.from_edit_mesh(obj.data)
    for group in (bm.verts, bm.edges, bm.faces):
        group.ensure_lookup_table()
        group.index_update()
    return bm, getattr(bm, _GROUPS[mode])


def _topology(bm):
    """Hash only connectivity, not coordinates or selection state.

    Count equality alone is not enough: Blender can change mesh topology
    outside an XR history record without changing vertex/edge/face totals.
    """
    h = hashlib.blake2b(digest_size=16)
    h.update(struct.pack('<III', len(bm.verts), len(bm.edges), len(bm.faces)))
    for vert in bm.verts:
        h.update(struct.pack('<B', int(vert.hide)))
    for edge in bm.edges:
        h.update(struct.pack('<IIB', edge.verts[0].index, edge.verts[1].index,
                             int(edge.hide)))
    for face in bm.faces:
        h.update(struct.pack('<IB', len(face.verts), int(face.hide)))
        for vert in face.verts:
            h.update(struct.pack('<I', vert.index))
    return h.digest()


def _selected(items):
    return tuple(item.index for item in items
                 if item.is_valid and not item.hide and item.select)


def _set_selection(obj, mode, indices):
    bm, items = _current(obj, mode)
    # Validate the entire destination before clearing *any* selection.
    # A partial selection clear is not an acceptable failed Undo/Redo.
    targets = []
    for index in indices:
        if index < 0 or index >= len(items):
            raise ValueError('Selection indices changed outside XR history')
        item = items[index]
        if not item.is_valid or item.hide:
            raise ValueError('Cannot select a hidden or deleted mesh element')
        targets.append(item)
    for group in (bm.faces, bm.edges, bm.verts):
        for item in group:
            if item.is_valid and item.select:
                item.select_set(False)
    for item in targets:
        item.select_set(True)
    bm.select_mode = {mode}
    bm.select_flush_mode()
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)


def _neighbors(item, mode):
    if mode == 'VERT':
        return tuple(other for edge in item.link_edges if edge.is_valid and not edge.hide
                     for other in edge.verts
                     if other != item and other.is_valid and not other.hide)
    if mode == 'EDGE':
        return tuple(other for vert in item.verts
                     for other in vert.link_edges
                     if other != item and other.is_valid and not other.hide)
    return tuple(other for edge in item.edges if edge.is_valid and not edge.hide
                 for other in edge.link_faces
                 if other != item and other.is_valid and not other.hide)


def _boundary(item, mode):
    if mode == 'VERT':
        return any(edge.is_valid and not edge.hide and edge.is_boundary
                   for edge in item.link_edges)
    if mode == 'EDGE':
        return item.is_boundary
    return any(edge.is_valid and not edge.hide and edge.is_boundary
               for edge in item.edges)


def _nonmanifold(item, mode):
    if mode == 'VERT':
        return any(edge.is_valid and not edge.hide and not edge.is_manifold
                   for edge in item.link_edges)
    if mode == 'EDGE':
        return not item.is_manifold
    return any(edge.is_valid and not edge.hide and not edge.is_manifold
               for edge in item.edges)


def _loose(item, mode):
    if mode == 'VERT':
        return not any(edge.is_valid and not edge.hide for edge in item.link_edges)
    if mode == 'EDGE':
        return not any(face.is_valid and not face.hide for face in item.link_faces)
    raise ValueError('Loose geometry needs vertex or edge selection mode')


def _sharp(item, mode):
    if mode == 'EDGE':
        return not item.smooth
    if mode == 'VERT':
        return any(edge.is_valid and not edge.hide and not edge.smooth
                   for edge in item.link_edges)
    raise ValueError('Sharp geometry needs vertex or edge selection mode')


def _target_indices(bm, items, mode, operation):
    visible = tuple(item for item in items if item.is_valid and not item.hide)
    selected = {item for item in visible if item.select}
    if operation in {'EDGE_LOOP', 'EDGE_RING', 'BOUNDARY_CHAIN',
                     'SEAM_CHAIN', 'SHARP_CHAIN'}:
        if mode != 'EDGE':
            raise ValueError('Enter Edge Select mode before selecting edge flows')
        from . import edge_selection_v086
        return edge_selection_v086.select_flow(bm, operation)
    if operation == 'ALL':
        target = set(visible)
    elif operation == 'NONE':
        target = set()
    elif operation == 'INVERT':
        target = set(visible) - selected
    elif operation == 'LINKED':
        if not selected:
            raise ValueError('Select a mesh element first to find linked geometry')
        target = set(selected)
        pending = list(selected)
        while pending:
            for other in _neighbors(pending.pop(), mode):
                if other not in target:
                    target.add(other)
                    pending.append(other)
    elif operation == 'GROW':
        if not selected:
            raise ValueError('Select geometry before growing the selection')
        target = set(selected)
        for item in selected:
            target.update(_neighbors(item, mode))
    elif operation == 'SHRINK':
        if not selected:
            raise ValueError('Select geometry before shrinking the selection')
        target = {item for item in selected if not _boundary(item, mode) and
                  all(other in selected for other in _neighbors(item, mode))}
    elif operation == 'BOUNDARY':
        target = {item for item in visible if _boundary(item, mode)}
    elif operation == 'NONMANIFOLD':
        target = {item for item in visible if _nonmanifold(item, mode)}
    elif operation == 'LOOSE':
        target = {item for item in visible if _loose(item, mode)}
    elif operation == 'SHARP':
        target = {item for item in visible if _sharp(item, mode)}
    else:
        raise ValueError('Unknown selection operation')
    return tuple(sorted(item.index for item in target))


def _apply(session, context, action):
    if input_ownership_v080.is_editing(session):
        raise ValueError('Release active controller gestures before selecting')
    if getattr(session, 'history', None) is None:
        raise ValueError('XR selection history is unavailable')
    obj = _editable(context)
    mode = selection.mode(context)
    bm, items = _current(obj, mode)
    operation = _ACTIONS[action]
    before = _selected(items)
    after = _target_indices(bm, items, mode, operation)
    if before == after:
        session.status = 'SELECTION / {} / ALREADY MATCHED'.format(operation)
        return False
    # Delegate to the same guarded native recall used by Quick Sets and
    # persistent attributes. Blender may flush implied vertex/edge/face
    # selection after setting a target: the historical "after" tuple must
    # describe what Blender ACTUALLY selected, not just the requested list.
    # The shared helper also restores selection on failed history pushes.
    from . import selection_quicksets_v090
    count, changed = selection_quicksets_v090.restore_indices(
        session, context, after, additive=False)
    session.status = 'SELECTION / {} / {} {} / {}'.format(
        operation, count, mode,
        'XR UNDO READY' if changed else 'UNCHANGED')
    return changed


def _patch_history():
    if getattr(mesh.History, '_xr_select_tools_086_history', False):
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
        (_tag, scene_name, layer_name, obj_name, obj_id, data_name, data_id,
         mode, topo, before, after) = src[-1]
        import bpy
        ctx = bpy.context
        if (ctx.scene.name != scene_name or
                ctx.view_layer.name != layer_name or
                ctx.mode != 'EDIT_MESH' or selection.mode(ctx) != mode):
            raise ValueError('Restore the original mesh selection mode and view layer')
        obj = _editable(ctx)
        if (obj.name != obj_name or obj.as_pointer() != obj_id or
                obj.data.name != data_name or obj.data.as_pointer() != data_id):
            raise ValueError('Mesh changed outside XR selection history')
        bm, items = _current(obj, mode)
        if _topology(bm) != topo:
            raise ValueError('Mesh topology changed outside XR selection history')
        current = _selected(items)
        if current != (after if backwards else before):
            raise ValueError('Selection changed outside XR selection history')
        expected = after if backwards else before
        target = before if backwards else after
        # Reserve the destination entry before any native selection write.
        # On failure leave both Undo/Redo stacks intact and restore the
        # visible selection when Blender has not changed topology/mode.
        entry = src[-1]
        dst.append(entry)
        try:
            _set_selection(obj, mode, target)
            check_bm, check_items = _current(obj, mode)
            if (_topology(check_bm) != topo or
                    _selected(check_items) != target):
                raise ValueError('Blender selection flush changed the XR history target')
        except Exception:
            try:
                check_bm, check_items = _current(obj, mode)
                if _topology(check_bm) == topo and _selected(check_items) != expected:
                    _set_selection(obj, mode, expected)
            except Exception:
                import traceback
                traceback.print_exc()
            dst.pop()
            raise
        src.pop()
        return True

    mesh.History.release = staticmethod(release)
    mesh.History.step = step
    mesh.History._xr_select_tools_086_history = True


def install_pages():
    options = tuple(menus.PAGES.get('STEP_MENU', ()))
    if not options or options[-1][1] != 'BACK':
        raise ValueError('Selection Tools requires the existing Edit Options page')
    if not any(action == 'XR_SEL_MENU' for _label, action in options):
        options = options[:-1] + (('SELECTION', 'XR_SEL_MENU'), options[-1])
    if len(options) > 12:
        raise ValueError('Edit Options menu is full')
    menus.PAGES['STEP_MENU'] = options
    menus.TITLES['STEP_MENU'] = 'EDIT OPTIONS'
    more = tuple(menus.PAGES.get('EDIT_MORE', ()))
    menus.PAGES['EDIT_MORE'] = tuple(
        ('OPTIONS' if action == 'STEP_MENU' else label, action)
        for label, action in more)
    menus.PAGES[_PAGE] = (
        ('SELECT ALL', 'XR_SEL_ALL'),
        ('SELECT NONE', 'XR_SEL_NONE'),
        ('INVERT', 'XR_SEL_INVERT'),
        ('SELECT LINKED', 'XR_SEL_LINKED'),
        ('GROW +1', 'XR_SEL_GROW'),
        ('SHRINK -1', 'XR_SEL_SHRINK'),
        ('MESH BOUNDARY', 'XR_SEL_BOUNDARY'),
        ('NON-MANIFOLD', 'XR_SEL_NONMANIFOLD'),
        ('LOOSE', 'XR_SEL_LOOSE'),
        ('SHARP', 'XR_SEL_SHARP'),
        ('EDGE FLOWS', 'XR_SEL_LOOPS_MENU'),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_FLOWS_PAGE] = (
        ('EDGE LOOP', 'XR_SEL_EDGE_LOOP'),
        ('EDGE RING', 'XR_SEL_EDGE_RING'),
        ('BOUNDARY', 'XR_SEL_BOUNDARY_CHAIN'),
        ('SEAM CHAIN', 'XR_SEL_SEAM_CHAIN'),
        ('SHARP CHAIN', 'XR_SEL_SHARP_CHAIN'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'MESH SELECTION'
    menus.TITLES[_FLOWS_PAGE] = 'EDGE FLOWS'
    v065.TOOLTIPS['STEP_MENU'] = (
        'Edit Options', 'Step size, precision picking, axis movement and mesh selection')
    v065.TOOLTIPS.update({
        'XR_SEL_MENU': ('Mesh Selection Tools', 'Operate on selected native vertices, edges or faces'),
        'XR_SEL_ALL': ('Select All Visible', 'Select all unhidden geometry of the current mode'),
        'XR_SEL_NONE': ('Deselect All', 'Clear the current edit-mesh selection'),
        'XR_SEL_INVERT': ('Invert Selection', 'Swap selected and unselected visible geometry'),
        'XR_SEL_LINKED': ('Select Linked', 'Select connected geometry starting from selected elements'),
        'XR_SEL_GROW': ('Grow Selection', 'Include one neighboring ring of visible geometry'),
        'XR_SEL_SHRINK': ('Shrink Selection', 'Remove the current outer selection boundary'),
        'XR_SEL_BOUNDARY': ('Select Mesh Boundary', 'Select elements bordering open mesh edges'),
        'XR_SEL_NONMANIFOLD': ('Select Non-Manifold', 'Select elements associated with non-manifold edges'),
        'XR_SEL_LOOSE': ('Select Loose Elements', 'Find disconnected vertices or edges with no faces'),
        'XR_SEL_SHARP': ('Select Sharp Elements', 'Find hard-shaded edges or adjoining vertices'),
        'XR_SEL_LOOPS_MENU': ('Edge Flow Selection', 'Follow visible quad loops/rings and marked edge chains'),
        'XR_SEL_EDGE_LOOP': ('Select Quad Edge Loop', 'Continue across regular quad vertices; stop at poles and boundaries'),
        'XR_SEL_EDGE_RING': ('Select Quad Edge Ring', 'Traverse opposite edges on successive visible quad faces'),
        'XR_SEL_BOUNDARY_CHAIN': ('Select Boundary Chain', 'Follow an existing open boundary without branching'),
        'XR_SEL_SEAM_CHAIN': ('Select Seam Chain', 'Follow connected edges marked as native Blender UV seams'),
        'XR_SEL_SHARP_CHAIN': ('Select Sharp Chain', 'Follow connected hard-shaded edges without branching'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_select_tools_086_patched', False):
        return
    _patch_history()
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous_command(self, context, action)
        if action == 'XR_SEL_MENU':
            _editable(context)
            if input_ownership_v080.is_editing(self):
                raise ValueError('Finish active controller gesture before Selection Tools')
            menu.page = _PAGE
            self.status = 'SELECTION / CHOOSE NATIVE MESH OPERATION'
            return
        if menu.page == _PAGE:
            if action == 'BACK':
                menu.page = 'STEP_MENU'
                return
            if action == 'XR_SEL_LOOPS_MENU':
                if selection.mode(context) != 'EDGE':
                    raise ValueError('Use Edge Select mode for edge flow tools')
                menu.page = _FLOWS_PAGE
                self.status = 'EDGE FLOWS / LOOP, RING, BOUNDARY, SEAM, SHARP'
                return
            if action in _ACTIONS and not action.endswith('_CHAIN'):
                return _apply(self, context, action)
            raise ValueError('Finish or exit Selection Tools first')
        if menu.page == _FLOWS_PAGE:
            if action == 'BACK':
                menu.page = _PAGE
                return
            if action in {
                    'XR_SEL_EDGE_LOOP', 'XR_SEL_EDGE_RING',
                    'XR_SEL_BOUNDARY_CHAIN', 'XR_SEL_SEAM_CHAIN',
                    'XR_SEL_SHARP_CHAIN'}:
                return _apply(self, context, action)
            raise ValueError('Finish or exit Edge Flow tools first')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_select_tools_086_patched = True
