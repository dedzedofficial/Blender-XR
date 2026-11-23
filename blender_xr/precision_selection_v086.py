# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional precision ray selection for native Blender Edit Mode.

The existing Select/Grip workflow stays unchanged unless Precision Pick is
enabled from Edit > More > Step > Precision. On a selection click, pick the
nearest eligible native vertex, edge or face along the dominant-controller ray. A subsequent
Next/Previous command re-evaluates that *recorded* ray against the current edit
mesh so deleted/replaced elements cannot be reached through stale pointers.

No scene objects, hidden geometry, mesh data, or persistent custom properties
are written. Precision Pick is an XR-session option, not a global Blender mode.
"""
import hashlib
import heapq
import math
import struct

import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import (armature_v076, input_ownership_v080, mesh, menus, selection,
               mesh_axis_snap_v090, mesh_selection_tools_v086,
               selection_quicksets_v090, v065)

_PAGE = 'XR_PRECISION_PICK_086'
_RADII = (0.012, 0.03, 0.07, 0.12)
_MAX_HITS = 32


def _target(context):
    obj = context.view_layer.objects.active
    if context.mode != 'EDIT_MESH' or obj is None or obj.type != 'MESH':
        raise ValueError('Precision selection requires Mesh Edit Mode')
    # Use the same native edit-mesh ownership policy as history-backed
    # selection tools. A linked/overridden mesh cannot be safely restored.
    mesh_selection_tools_v086._editable(context)
    if obj.hide_select or not obj.visible_get(view_layer=context.view_layer):
        raise ValueError('Show and unlock the edited mesh')
    return obj


def _ray(origin, direction):
    origin = Vector(origin)
    direction = Vector(direction)
    if (not all(math.isfinite(float(value)) for value in origin) or
            not all(math.isfinite(float(value)) for value in direction) or
            direction.length_squared <= 1e-12):
        raise ValueError('Controller ray has missing or non-finite coordinates')
    return origin, direction.normalized()


def _face_candidates(obj, origin, direction, through):
    """Hit visible native BMesh faces, including deeper faces on Through mode.

    Blender BVH returns the first polygon on a ray. Advancing an independent
    ray origin through each hit permits bounded front-to-back face cycling
    without selecting hidden/evaluated modifier faces or writing topology.
    """
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    vertices = tuple(v for v in bm.verts if v.is_valid)
    positions = {vertex: i for i, vertex in enumerate(vertices)}
    if any(not all(math.isfinite(float(x)) for x in vertex.co)
           for vertex in vertices):
        raise ValueError('Native face selection requires finite edit coordinates')
    faces = tuple(
        face for face in bm.faces
        if (face.is_valid and not face.hide and len(face.verts) >= 3 and
            all(v.is_valid and not v.hide for v in face.verts) and
            all(edge.is_valid and not edge.hide for edge in face.edges))
    )
    if not faces:
        return []
    tree = BVHTree.FromPolygons(
        [vertex.co.copy() for vertex in vertices],
        [[positions[v] for v in face.verts] for face in faces],
    )
    inverse = obj.matrix_world.inverted()
    source = inverse @ origin
    local_direction = inverse.to_3x3() @ direction
    if (local_direction.length_squared <= 1e-24 or
            not all(math.isfinite(float(x)) for x in local_direction)):
        raise ValueError('Precision face ray has an invalid object transform')
    local_direction.normalize()
    progress = 0.0
    seen = set()
    candidates = []
    # A ray can encounter the same polygon twice at grazing angles; cap
    # attempts even with pathological overlapping surfaces. Next/Previous
    # only needs the first 32 distinct native faces.
    for _attempt in range(96 if through else 1):
        local_hit, _normal, polygon_index, _distance = tree.ray_cast(
            source + local_direction * progress, local_direction)
        if local_hit is None or polygon_index is None:
            break
        if not 0 <= polygon_index < len(faces):
            raise ValueError('Native face BVH returned an invalid polygon index')
        face = faces[polygon_index]
        local_depth = (local_hit - source).dot(local_direction)
        world_hit = obj.matrix_world @ local_hit
        depth = (world_hit - origin).dot(direction)
        if not all(math.isfinite(float(x)) for x in (*world_hit, depth)):
            raise ValueError('Native face ray produced non-finite geometry')
        if depth > 0 and face.index not in seen:
            candidates.append((float(depth), 0.0, int(face.index),
                               world_hit.copy()))
            seen.add(face.index)
            if not through or len(candidates) >= _MAX_HITS:
                break
        # In local edit-mesh units, advance slightly beyond the last hit.
        # Ensure strict progress even if the BVH returns a repeated polygon.
        # Limit the step to local precision rather than controller distance;
        # very small overlapping surfaces can remain independently selectable.
        epsilon = max(1e-8, abs(local_depth) * 1e-8)
        next_progress = max(progress + epsilon, local_depth + epsilon)
        if not math.isfinite(next_progress):
            raise ValueError('Native face ray exceeded safe traversal range')
        progress = next_progress
    return sorted(candidates, key=lambda hit: (hit[0], hit[2]))


def _rank_key(hit, near_first=False):
    """Stable selection priority for a native controller-ray candidate."""
    return ((hit[1], hit[0], hit[2]) if near_first
            else (hit[0], hit[1], hit[2]))


def _bounded_hit(heap, hit, near_first=False):
    """Keep only the 32 best hits, not every mesh element near the ray."""
    key = tuple(-value for value in _rank_key(hit, near_first))
    entry = (key, hit)
    if len(heap) < _MAX_HITS:
        heapq.heappush(heap, entry)
    elif key > heap[0][0]:
        heapq.heapreplace(heap, entry)


def _ranked_hits(heap, near_first=False):
    return sorted((entry[1] for entry in heap),
                  key=lambda hit: _rank_key(hit, near_first))


def _candidates(obj, origin, direction, kind, radius, through,
                near_first=False):
    """Return up to 32 current Blender BMesh hits, ordered front to back.

    A surface depth gate prevents selecting obscured geometry by default.
    The explicit Through toggle removes this depth gate. Loose vertices/edges
    remain selectable when the ray does not hit any visible polygon.
    """
    if kind not in {'VERT', 'EDGE', 'FACE'}:
        return []
    origin, direction = _ray(origin, direction)
    if kind == 'FACE':
        return _face_candidates(obj, origin, direction, through)
    bm = bmesh.from_edit_mesh(obj.data)
    if kind == 'VERT':
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        elements = bm.verts
    else:
        bm.edges.ensure_lookup_table()
        bm.edges.index_update()
        elements = bm.edges

    # Work with the base edit cage, not the modifier-evaluated mesh.
    cutoff = None
    if not through:
        front = mesh.face_hit(obj, origin, direction)
        if front is not None:
            cutoff = (front[1] - origin).dot(direction) + max(0.02, radius)

    hits = []
    # Edge candidates share vertices heavily. Reuse transformed endpoints
    # within this single edit-cage pick, without caching stale Blender data
    # across frames or Undo operations. Vertex mode needs no dictionary.
    world_positions = {} if kind == 'EDGE' else None
    world_matrix = obj.matrix_world
    for element in elements:
        if not element.is_valid or element.hide:
            continue
        # BMesh edge hide state does not guarantee that both endpoints are
        # visible, especially after native hide/unhide operations.
        if kind == 'EDGE' and any(
                not vertex.is_valid or vertex.hide for vertex in element.verts):
            continue
        if kind == 'VERT':
            point = world_matrix @ element.co
            depth = (point - origin).dot(direction)
            if depth <= 0:
                continue
            distance = (point - (origin + direction * depth)).length
        else:
            start, end = element.verts
            a = world_positions.get(start)
            if a is None:
                a = world_matrix @ start.co
                world_positions[start] = a
            b = world_positions.get(end)
            if b is None:
                b = world_matrix @ end.co
                world_positions[end] = b
            # An edge completely behind the controller or behind the front
            # surface cannot be a valid nearest segment target. Pre-filter
            # from its endpoints before invoking the more costly segment
            # closest-point calculation.
            da = (a - origin).dot(direction)
            db = (b - origin).dot(direction)
            if max(da, db) <= 0:
                continue
            if cutoff is not None and min(da, db) > cutoff:
                continue
            hit = armature_v076._closest_segment(
                origin, direction, a, b)
            if hit is None:
                continue
            distance, depth, point, _fraction = hit
        if not math.isfinite(float(depth)) or not math.isfinite(float(distance)):
            continue
        if cutoff is not None and depth > cutoff:
            continue
        # World-space thresholds adapt gently with distance without making
        # far-away objects impossibly small controller targets.
        limit = max(float(radius), min(0.09, depth * 0.007))
        if distance <= limit:
            _bounded_hit(hits, (float(depth), float(distance),
                               int(element.index), Vector(point).copy()),
                         near_first)
    # A fixed-size heap preserves the same front-to-back order as the old
    # all-hits list while avoiding unbounded allocation on dense edit cages.
    return _ranked_hits(hits, near_first)


def _geometry_stamp(bm):
    """Hash native vertex coordinates without a mesh-size or copy limit.

    Precision selection previously worked on large meshes. Use a streaming
    fingerprint rather than the bounded weld-preview snapshot, whose 150k
    vertex cap would otherwise introduce a new precision-picking regression.
    """
    digest = hashlib.blake2b(digest_size=16)
    for vert in bm.verts:
        coordinates = tuple(float(value) for value in vert.co)
        if not all(math.isfinite(value) for value in coordinates):
            raise ValueError('Native precision mesh has invalid coordinates')
        digest.update(struct.pack('<ddd', *coordinates))
    return digest.digest()


def _native_stamp(context, obj):
    """Fingerprint the exact edit cage and object transform under a saved ray.

    Re-evaluating an old ray against only matching indices can select a
    completely different vertex after topology edits, or a moved mesh after
    object transform/Undo. Visibility, all coordinates, and connectivity are
    required to match before Next/Previous is accepted. Selection flags are
    intentionally excluded so XR Undo and additive selection can still cycle.
    """
    bm, _items = mesh_selection_tools_v086._current(obj, selection.mode(context))
    return (
        context.scene.as_pointer(), context.view_layer.name,
        mesh_selection_tools_v086._topology(bm),
        _geometry_stamp(bm),
        _world_matrix_stamp(obj),
    )


def _world_matrix_stamp(obj):
    stamp = mesh_axis_snap_v090._matrix_stamp(obj.matrix_world)
    if not all(math.isfinite(value) for row in stamp for value in row):
        raise ValueError('Native precision object has an invalid world transform')
    return stamp


def _selection_stamp(context, obj, kind):
    """Native selected indices, with no data writes or evaluated modifiers."""
    bm, items = mesh_selection_tools_v086._current(obj, kind)
    return mesh_selection_tools_v086._selected(items)


def _history_pick(session, context, kind, index, additive):
    """Select or toggle a native BMesh index through guarded XR Undo/Redo.

    Quick Set's restore_indices validates the complete destination, records
    Blender's actual flushed selection and restores it if history.push fails.
    Passing the final target (rather than additive=True) preserves the
    existing grip+trigger TOGGLE semantics when the vertex/edge is selected.
    """
    _obj, mode, _bm, items, _topo = selection_quicksets_v090._current(context)
    if mode != kind or index < 0 or index >= len(items):
        raise ValueError('Precision selection mode or index changed')
    element = items[index]
    if not element.is_valid or element.hide:
        raise ValueError('Precision target was hidden or deleted')
    before = set(mesh_selection_tools_v086._selected(items))
    if not additive:
        after = {index}
    elif index in before:
        after = before - {index}
    else:
        after = before | {index}
    _count, changed = selection_quicksets_v090.restore_indices(
        session, context, tuple(sorted(after)), additive=False)
    return changed


def _pick_enabled(session):
    return bool(getattr(session, '_xr_precision_enabled', False))


def _near_first(session):
    return bool(getattr(session, '_xr_precision_near_first', False))


def _radius(session):
    index = max(0, min(len(_RADII) - 1,
                       int(getattr(session, '_xr_precision_radius_index', 1))))
    return _RADII[index]


def _clear(session):
    session._xr_precision_last_ray = None


def _current_candidates(session, context):
    state = getattr(session, '_xr_precision_last_ray', None)
    if not state:
        raise ValueError('Aim at geometry with Select before cycling')
    obj = _target(context)
    if (obj.as_pointer() != state['object_ptr'] or
            obj.data.as_pointer() != state['mesh_ptr'] or
            selection.mode(context) != state['kind']):
        _clear(session)
        raise ValueError('Mesh or selection mode changed; aim and Select again')
    if state.get('stamp') != _native_stamp(context, obj):
        _clear(session)
        raise ValueError('Native geometry or object transform changed; aim and Select again')
    if state.get('selected') != _selection_stamp(context, obj, state['kind']):
        _clear(session)
        raise ValueError('Selection changed outside Precision; aim and Select again')
    # Native scene/topology/geometry/transform and selected indices matched
    # the exact saved ray. Reuse the bounded world-space hit result rather
    # than rebuilding an edit-mesh BVH or rescanning all mesh edges for every
    # Next/Previous press. Store tuples, not BMesh pointers, across XR frames.
    cached = state.get('hits')
    if cached is not None:
        return state, obj, [
            (depth, distance, index, Vector(world_point))
            for depth, distance, index, world_point in cached
        ]
    return state, obj, _candidates(
        obj, state['origin'], state['direction'], state['kind'],
        _radius(session), bool(getattr(session, '_xr_precision_through', False)),
        near_first=_near_first(session))


def _cycle(session, context, step):
    if not _pick_enabled(session):
        raise ValueError('Enable Precision Pick before cycling')
    if getattr(session, 'tool', None) != 'SELECT':
        raise ValueError('Use Select tool before cycling geometry')
    state, obj, candidates = _current_candidates(session, context)
    if not candidates:
        _clear(session)
        raise ValueError('No geometry under the last controller ray')
    indices = [item[2] for item in candidates]
    if state['index'] not in indices:
        _clear(session)
        raise ValueError('Geometry changed; aim and Select again')
    next_pos = (indices.index(state['index']) + step) % len(indices)
    chosen = candidates[next_pos]
    # Cycling is an exclusive selection for vertices, edges and native faces.
    # Ordinary grip+trigger additive toggling still works with Select.
    changed = _history_pick(session, context, state['kind'], chosen[2], False)
    state['index'] = chosen[2]
    state['selected'] = _selection_stamp(context, obj, state['kind'])
    # Selection history recall clears prior precision rays. This particular
    # cycle revalidated the geometry so it can retain its own saved ray.
    session._xr_precision_last_ray = state
    session.pointer = chosen[3].copy()
    session.status = 'PRECISION / {} {} OF {}'.format(
        state['kind'], next_pos + 1, len(candidates)) + (
            ' / XR UNDO READY' if changed else ' / UNCHANGED')


def _select(session, context, origin, direction, additive, legacy_select):
    if not _pick_enabled(session) or getattr(session, 'tool', None) != 'SELECT':
        _clear(session)
        return legacy_select(session, context, origin, direction, additive=additive)
    obj = context.view_layer.objects.active
    if obj is None or obj.type != 'MESH' or obj.mode != 'EDIT':
        _clear(session)
        return legacy_select(session, context, origin, direction, additive=additive)
    obj = _target(context)
    kind = selection.mode(context)
    origin, ray = _ray(origin, direction)
    native_stamp = _native_stamp(context, obj)
    candidates = _candidates(
        obj, origin, ray, kind, _radius(session),
        bool(getattr(session, '_xr_precision_through', False)),
        near_first=_near_first(session))

    # Preserve the original ability to point at another edit mesh.
    # A closer object takes priority over a vertex/edge of the active mesh.
    scene_hit = session.object_hit(context, origin, ray)
    if scene_hit and scene_hit[0] != obj:
        depth = (scene_hit[1] - origin).dot(ray)
        # Even with distance-first ordering, another mesh must genuinely be
        # in front of all available native hits before changing active meshes.
        nearest_depth = min(item[0] for item in candidates) if candidates else None
        if nearest_depth is None or depth < nearest_depth - 0.002:
            _clear(session)
            return legacy_select(session, context, origin, direction,
                                 additive=additive)

    if not candidates:
        _clear(session)
        session.status = 'PRECISION / NO VISIBLE {} NEAR RAY'.format(kind)
        return None
    picked = candidates[0]
    changed = _history_pick(session, context, kind, picked[2], additive)
    session.pointer = picked[3].copy()
    session._xr_precision_last_ray = {
        'object_ptr': obj.as_pointer(),
        'mesh_ptr': obj.data.as_pointer(),
        'kind': kind,
        'origin': origin.copy(),
        'direction': ray.copy(),
        'index': picked[2],
        'stamp': native_stamp,
        'selected': _selection_stamp(context, obj, kind),
        # Up to 32 read-only numeric hits. Never persist BMesh handles, UV
        # data, Blender object pointers or cache across tracking loss.
        'hits': tuple(
            (depth, distance, index, tuple(float(v) for v in world_point))
            for depth, distance, index, world_point in candidates
        ),
    }
    session.status = 'PRECISION / {} / {} NEARBY HITS / {}'.format(
        kind, len(candidates), 'XR UNDO READY' if changed else 'UNCHANGED')
    return picked[2], picked[3]


def install_pages():
    # Existing Edit More page is full. Attach a small precision entry to its
    # existing Step submenu without hiding or replacing modelling actions.
    steps = tuple(menus.PAGES.get('STEP_MENU', ()))
    if not steps:
        raise ValueError('Precision selection requires Edit Step submenu')
    if not any(action == 'XR_PICK_MENU' for _label, action in steps):
        steps = steps[:-1] + (('PRECISION', 'XR_PICK_MENU'), steps[-1])
    menus.PAGES['STEP_MENU'] = steps
    menus.PAGES[_PAGE] = (
        ('ENABLE PICK', 'XR_PICK_TOGGLE'),
        ('NARROW', 'XR_PICK_NARROW'),
        ('NORMAL', 'XR_PICK_NORMAL'),
        ('WIDE', 'XR_PICK_WIDE'),
        ('EXTRA WIDE', 'XR_PICK_EXTRA_WIDE'),
        ('FRONT / THROUGH', 'XR_PICK_THROUGH'),
        ('DEPTH / NEAR', 'XR_PICK_PRIORITY'),
        ('NEXT HIT', 'XR_PICK_NEXT'),
        ('PREVIOUS HIT', 'XR_PICK_PREV'),
        ('RESET RAY', 'XR_PICK_CLEAR'),
        ('BACK', 'BACK'),
    )
    if len(menus.PAGES[_PAGE]) > 12:
        raise ValueError('Native precision wrist page exceeds menu capacity')
    menus.TITLES[_PAGE] = 'MESH PRECISION'
    v065.TOOLTIPS.update({
        'XR_PICK_MENU': ('Precision Pick', 'Pick native vertices, edges or faces and cycle exact controller-ray hits'),
        'XR_PICK_TOGGLE': ('Enable Precision Pick', 'Use precise vertex, edge or face picking with the Select trigger'),
        'XR_PICK_THROUGH': ('Front / Through', 'Allow deeper native faces and vertices/edges behind front surfaces'),
        'XR_PICK_PRIORITY': ('Depth / Nearest Ray', 'Rank vertices and edges by depth or perpendicular ray distance'),
        'XR_PICK_NEXT': ('Next Ray Hit', 'Cycle forward through current geometry under the last Select ray'),
        'XR_PICK_PREV': ('Previous Ray Hit', 'Cycle backward through current geometry under the last Select ray'),
        'XR_PICK_CLEAR': ('Reset Recorded Ray', 'Discard the last selection ray without modifying the mesh'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_precision_selection_086_patched', False):
        return
    install_pages()
    previous_command, previous_select = Runtime.command, Runtime.select

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous_command(self, context, action)
        if action == 'XR_PICK_MENU':
            _target(context)
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release the current gesture before opening Precision')
            menu.page = _PAGE
            self.status = 'PRECISION / SET RAY SIZE AND SELECT MODE'
            return
        if menu.page == _PAGE:
            if action == 'BACK':
                menu.page = 'STEP_MENU'
                return
            if action == 'XR_PICK_TOGGLE':
                self._xr_precision_enabled = not _pick_enabled(self)
                _clear(self)
                self.status = 'PRECISION PICK / ' + ('ON' if _pick_enabled(self) else 'OFF')
                return
            radii = {
                'XR_PICK_NARROW': 0, 'XR_PICK_NORMAL': 1,
                'XR_PICK_WIDE': 2, 'XR_PICK_EXTRA_WIDE': 3}
            if action in radii:
                self._xr_precision_radius_index = radii[action]
                _clear(self)
                self.status = 'PICK RADIUS / {:.0f} MM'.format(_radius(self) * 1000)
                return
            if action == 'XR_PICK_PRIORITY':
                self._xr_precision_near_first = not _near_first(self)
                _clear(self)
                self.status = ('PRECISION HIT ORDER / NEAREST RAY' if _near_first(self)
                               else 'PRECISION HIT ORDER / FRONT FIRST')
                return
            if action == 'XR_PICK_THROUGH':
                self._xr_precision_through = not bool(
                    getattr(self, '_xr_precision_through', False))
                _clear(self)
                self.status = 'THROUGH PICK / ' + (
                    'ON' if self._xr_precision_through else 'OFF')
                return
            if action == 'XR_PICK_NEXT':
                _cycle(self, context, 1)
                return
            if action == 'XR_PICK_PREV':
                _cycle(self, context, -1)
                return
            if action == 'XR_PICK_CLEAR':
                _clear(self)
                self.status = 'PRECISION / RAY CLEARED'
                return
        return previous_command(self, context, action)

    def select(self, context, origin, direction, additive=False):
        return _select(self, context, origin, direction, additive, previous_select)

    Runtime.command = command
    Runtime.select = select
    Runtime._xr_precision_selection_086_patched = True
