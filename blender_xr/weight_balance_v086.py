# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Weight Paint Normalize / Limit 4 / non-destructive influence audit.

All write operations preserve locked vertex groups, native Blender group
identities, mesh topology and UV/rig data. One session-local history entry
covers an entire operation, not one entry per vertex or group.
"""
import math

import bpy

from . import input_ownership_v080, menus, mesh, rigging_v076, runtime, v065

_PAGE = 'WEIGHT_MIRROR_086'
_ACTIONS = {'WEIGHT_NORMALIZE_ALL': 'NORMALIZE',
            'WEIGHT_LIMIT_FOUR': 'LIMIT_FOUR'}
_LIMIT = 150000
_MAX_WRITES = 300000


def _eligible(context, writable=True):
    obj = context.view_layer.objects.active
    if obj is None or obj.type != 'MESH' or obj.mode != 'WEIGHT_PAINT':
        raise ValueError('Select a native mesh in Weight Paint Mode')
    if not writable:
        return obj
    if (obj.library or obj.override_library or obj.data.library or
            obj.data.users != 1 or obj.hide_select or obj.hide_get() or
            not obj.visible_get()):
        raise ValueError('Unlock and use a local single-user mesh for weight repair')
    if len(obj.data.vertices) > _LIMIT:
        raise ValueError('Weight repair supports up to 150,000 mesh vertices')
    return obj


def _topology(mesh_data):
    """Compact deterministic edge-connectivity fingerprint for XR history."""
    value = 1469598103934665603
    mask = (1 << 64) - 1
    for edge in mesh_data.edges:
        left, right = (int(x) for x in edge.vertices)
        value = ((value ^ (left + 1)) * 1099511628211) & mask
        value = ((value ^ (right + 1)) * 1099511628211) & mask
    return value


def _same_weight(a, b):
    return rigging_v076._same_weight(a, b)


def _weight_elements(vertex, groups):
    result = []
    for member in vertex.groups:
        group = groups.get(int(member.group))
        if group is None:
            raise ValueError('Vertex references missing native weight group')
        weight = float(member.weight)
        if not math.isfinite(weight) or weight < 0 or weight > 1.00001:
            raise ValueError('Vertex has an invalid native group weight')
        result.append((group, min(1.0, weight)))
    return result


def inspect(context):
    """Read-only creator diagnostic; inspect real Blender assignments."""
    obj = _eligible(context, writable=False)
    groups = {group.index: group for group in obj.vertex_groups}
    unweighted = overflow = locked_excess = 0
    for vertex in obj.data.vertices:
        entries = _weight_elements(vertex, groups)
        positive = [(group, weight) for group, weight in entries if weight > 1e-6]
        if not positive:
            unweighted += 1
        if len(positive) > 4:
            overflow += 1
        if sum(weight for group, weight in positive if group.lock_weight) > 1.00001:
            locked_excess += 1
    return len(obj.data.vertices), unweighted, overflow, locked_excess


def _plan(context, operation):
    obj = _eligible(context)
    if operation not in {'NORMALIZE', 'LIMIT_FOUR'}:
        raise ValueError('Unknown weight repair action')
    groups = {group.index: group for group in obj.vertex_groups}
    changes = []
    skipped_locked = 0
    vertices_affected = 0

    for vertex in obj.data.vertices:
        entries = _weight_elements(vertex, groups)
        locked = [(group, value) for group, value in entries if group.lock_weight and value > 1e-8]
        editable = [(group, value) for group, value in entries if not group.lock_weight]
        locked_total = sum(value for _group, value in locked)
        if locked_total > 1.00001:
            skipped_locked += 1
            continue
        available = max(0.0, 1.0 - locked_total)
        positive_unlocked = [(group, value) for group, value in editable if value > 1e-8]
        if not positive_unlocked:
            continue

        desired = {}
        if operation == 'NORMALIZE':
            total = sum(value for _group, value in positive_unlocked)
            if total > 0:
                desired = {group.index: (value * available / total)
                           for group, value in positive_unlocked}
        else:
            if len(locked) + len(positive_unlocked) <= 4:
                continue
            slots = 4 - len(locked)
            if slots < 0:
                skipped_locked += 1
                continue
            ordered = sorted(positive_unlocked,
                             key=lambda item: (-item[1], item[0].index))
            kept = ordered[:slots]
            total = sum(value for _group, value in kept)
            desired = {group.index: (value * available / total if total > 0 else 0.0)
                       for group, value in kept}
            for group, _value in ordered[slots:]:
                desired[group.index] = None

        modified = False
        for group, before in editable:
            if group.index not in desired:
                continue
            after = desired[group.index]
            # Assigned zero is not the same as an absent assignment.
            if after is not None:
                after = max(0.0, min(1.0, float(after)))
            if _same_weight(before, after):
                continue
            changes.append((vertex.index, group.index, before, after))
            modified = True
            if len(changes) > _MAX_WRITES:
                raise ValueError('Too many weight writes; split this mesh into parts')
        if modified:
            vertices_affected += 1

    if not changes:
        return obj, None, 0, skipped_locked
    ids = {group_index for _index, group_index, _before, _after in changes}
    group_guard = tuple(sorted((index, groups[index].name, groups[index].as_pointer())
                               for index in ids))
    positions = tuple((index, tuple(float(c) for c in obj.data.vertices[index].co))
                      for index in sorted({idx for idx, _g, _b, _a in changes}))
    data = obj.data
    # Include all native group identities and lock flags, not only modified
    # groups. Undo must reject changes to the locked groups that determined
    # how much weight was available for normalization/limiting.
    layout = tuple((group.index, group.name, group.as_pointer(), bool(group.lock_weight))
                   for group in obj.vertex_groups)
    locked_totals = []
    for index, _coords in positions:
        total = sum(float(member.weight) for member in data.vertices[index].groups
                    if groups[int(member.group)].lock_weight)
        locked_totals.append((index, total))
    entry = ('XR_WEIGHT_BALANCE_086', obj.name, obj.as_pointer(),
             data.name, data.as_pointer(),
             (len(data.vertices), len(data.edges), len(data.polygons), _topology(data)),
             group_guard, positions, tuple(changes), operation,
             layout, tuple(locked_totals))
    return obj, entry, vertices_affected, skipped_locked


def _guard(context, entry):
    (_tag, name, token, data_name, data_token, shape, group_guard,
     positions, _changes, _op) = entry
    obj = bpy.data.objects.get(name)
    if (obj is None or context.view_layer.objects.get(name) != obj or
            obj.as_pointer() != token or obj.type != 'MESH' or
            obj.mode not in {'OBJECT', 'WEIGHT_PAINT'} or
            obj.data.name != data_name or obj.data.as_pointer() != data_token or
            obj.library or obj.override_library or obj.data.library or
            obj.data.users != 1 or obj.hide_select or obj.hide_get() or
            not obj.visible_get()):
        raise ValueError('Original native mesh is unavailable or protected')
    data = obj.data
    current_shape = (len(data.vertices), len(data.edges), len(data.polygons),
                     _topology(data))
    if current_shape != shape:
        raise ValueError('Mesh topology changed outside XR weight repair history')
    groups = {}
    for index, original_name, original_ptr in group_guard:
        if index >= len(obj.vertex_groups):
            raise ValueError('Vertex group removed from the painted mesh')
        group = obj.vertex_groups[index]
        if (group.index != index or group.name != original_name or
                group.as_pointer() != original_ptr or group.lock_weight):
            raise ValueError('Vertex group identity or lock changed outside XR')
        groups[index] = group
    layout = entry[10]
    if len(obj.vertex_groups) != len(layout):
        raise ValueError('Vertex group layout changed outside XR weight repair')
    for index, name, pointer, locked in layout:
        group = obj.vertex_groups[index]
        if (group.index != index or group.name != name or
                group.as_pointer() != pointer or bool(group.lock_weight) != locked):
            raise ValueError('Vertex group identity or locks changed outside XR')
    for index, coords in positions:
        if index >= len(data.vertices) or tuple(data.vertices[index].co) != coords:
            raise ValueError('Vertex positions changed outside XR weight repair')
    for index, total in entry[11]:
        now = sum(float(member.weight) for member in data.vertices[index].groups
                  if obj.vertex_groups[int(member.group)].lock_weight)
        if not math.isfinite(now) or abs(now - total) > 1e-5:
            raise ValueError('Locked weights changed outside XR weight repair')
    return obj, groups


def _write(context, entry, backwards):
    obj, groups = _guard(context, entry)
    changes = entry[8]
    expected_index = 3 if backwards else 2
    target_index = 2 if backwards else 3
    # Validate every weight before modifying any native group.
    for vertex, group, before, after in changes:
        current = rigging_v076._vertex_weight(groups[group], vertex)
        expected = (before, after)[expected_index - 2]
        if not _same_weight(current, expected):
            raise ValueError('Weight assignments changed outside XR history')
    written = []
    try:
        for vertex, group, before, after in changes:
            target = (before, after)[target_index - 2]
            rigging_v076._write_weight(groups[group], vertex, target)
            written.append((vertex, group, (before, after)[expected_index - 2], target))
        obj.data.update()
        context.view_layer.update()
    except Exception:
        for vertex, group, previous, last in reversed(written):
            if _same_weight(rigging_v076._vertex_weight(groups[group], vertex), last):
                rigging_v076._write_weight(groups[group], vertex, previous)
        obj.data.update()
        context.view_layer.update()
        raise


def _apply(context, operation, history=None):
    obj, entry, count, skipped = _plan(context, operation)
    if entry is None:
        return 0, skipped
    # Before applying, recheck geometry and source weights to refuse stale
    # plans. On a failed history push the original data is restored.
    _write(context, entry, backwards=False)
    try:
        if history is not None:
            history.push(entry)
    except Exception:
        _write(context, entry, backwards=True)
        raise
    return count, skipped


class BXR_OT_weight_balance(bpy.types.Operator):
    bl_idname = 'blender_xr.weight_balance'
    bl_label = 'Normalize / Limit Native Vertex Influences'
    bl_description = 'Preserve locked groups while normalizing and limiting native Blender weights'
    bl_options = {'REGISTER', 'UNDO'}
    operation: bpy.props.EnumProperty(items=[
        ('NORMALIZE', 'Normalize All', 'Normalize unlocked groups on every vertex'),
        ('LIMIT_FOUR', 'Limit to Four', 'Keep strongest four influences and renormalize'),
    ], default='NORMALIZE')

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and obj.mode == 'WEIGHT_PAINT')

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the Weight Repair wrist menu during XR')
            return {'CANCELLED'}
        try:
            count, skipped = _apply(context, self.operation)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Weight repair: {} vertices modified; {} locked overflow'.format(
            count, skipped))
        return {'FINISHED'} if count else {'CANCELLED'}


def _history():
    if getattr(mesh.History, '_xr_weight_balance_086_patched', False):
        return
    previous_step, previous_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == 'XR_WEIGHT_BALANCE_086':
            return
        return previous_release(entry)

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] != 'XR_WEIGHT_BALANCE_086':
            return previous_step(self, backwards)
        entry = source[-1]
        _write(bpy.context, entry, backwards)
        dest.append(source.pop())
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_weight_balance_086_patched = True


def install_pages():
    parent = tuple(menus.PAGES[_PAGE])
    if parent[-1][1] != 'BACK' or len(parent) > 9:
        raise ValueError('Weight mirror submenu lacks room for influence tools')
    menus.PAGES[_PAGE] = parent[:-1] + (
        ('NORMALIZE', 'WEIGHT_NORMALIZE_ALL'),
        ('LIMIT 4', 'WEIGHT_LIMIT_FOUR'),
        ('AUDIT', 'WEIGHT_INFLUENCE_AUDIT'),
        parent[-1],
    )
    v065.TOOLTIPS.update({
        'WEIGHT_NORMALIZE_ALL': ('Normalize Vertex Weights', 'Scale unlocked assignments to sum to 1 without overwriting locked groups'),
        'WEIGHT_LIMIT_FOUR': ('Limit to Four Influences', 'Keep up to four strongest groups per vertex and normalize remaining unlocked weights'),
        'WEIGHT_INFLUENCE_AUDIT': ('Weight Influence Audit', 'Read-only check for vertices with no weight, more than four influences or locked overflow'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_weight_balance_086_patched', False):
        return
    _history()
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if page == _PAGE and action == 'WEIGHT_INFLUENCE_AUDIT':
            total, unweighted, overflow, locked = inspect(context)
            self.status = 'WEIGHTS {} V / {} EMPTY / {} >4 / {} LOCKED'.format(
                total, unweighted, overflow, locked)
            return
        if page == _PAGE and action in _ACTIONS:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR controllers before weight repair')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('XR Undo is required before weight repair')
            count, skipped = _apply(context, _ACTIONS[action], history)
            self.status = '{} / {} VERTICES / {} LOCKED SKIPPED'.format(
                _ACTIONS[action], count, skipped)
            return
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_weight_balance_086_patched = True


CLASSES = (BXR_OT_weight_balance,)
