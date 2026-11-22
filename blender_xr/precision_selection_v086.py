# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional precision ray selection for native Blender Edit Mode.

The existing Select/Grip workflow stays unchanged unless Precision Pick is
enabled from Edit > More > Step > Precision. On a selection click, pick the
nearest eligible vertex or edge along the dominant-controller ray. A subsequent
Next/Previous command re-evaluates that *recorded* ray against the current edit
mesh so deleted/replaced elements cannot be reached through stale pointers.

No scene objects, hidden geometry, mesh data, or persistent custom properties
are written. Precision Pick is an XR-session option, not a global Blender mode.
"""
import heapq
import math

import bmesh
from mathutils import Vector

from . import armature_v076, input_ownership_v080, mesh, menus, selection, v065

_PAGE = 'XR_PRECISION_PICK_086'
_RADII = (0.012, 0.03, 0.07, 0.12)
_MAX_HITS = 32


def _target(context):
    obj = context.view_layer.objects.active
    if context.mode != 'EDIT_MESH' or obj is None or obj.type != 'MESH':
        raise ValueError('Precision selection requires Mesh Edit Mode')
    mesh.check_editable(obj)
    if obj.hide_select or not obj.visible_get(view_layer=context.view_layer):
        raise ValueError('Show and unlock the edited mesh')
    return obj


def _ray(origin, direction):
    origin = Vector(origin)
    direction = Vector(direction)
    if direction.length_squared <= 1e-12:
        raise ValueError('Controller ray has no direction')
    return origin, direction.normalized()


def _candidates(obj, origin, direction, kind, radius, through):
    """Return up to 32 current Blender BMesh hits, ordered front to back.

    A surface depth gate prevents selecting obscured geometry by default.
    The explicit Through toggle removes this depth gate. Loose vertices/edges
    remain selectable when the ray does not hit any visible polygon.
    """
    if kind not in {'VERT', 'EDGE'}:
        return []
    origin, direction = _ray(origin, direction)
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
    for element in elements:
        if not element.is_valid or element.hide:
            continue
        if kind == 'VERT':
            point = obj.matrix_world @ element.co
            depth = (point - origin).dot(direction)
            if depth <= 0:
                continue
            distance = (point - (origin + direction * depth)).length
        else:
            start, end = element.verts
            hit = armature_v076._closest_segment(
                origin, direction,
                obj.matrix_world @ start.co,
                obj.matrix_world @ end.co)
            if hit is None:
                continue
            distance, depth, point, _fraction = hit
        if cutoff is not None and depth > cutoff:
            continue
        # World-space thresholds adapt gently with distance without making
        # far-away objects impossibly small controller targets.
        limit = max(float(radius), min(0.09, depth * 0.007))
        if distance <= limit:
            hits.append((float(depth), float(distance), int(element.index),
                         Vector(point).copy()))
    # Deterministic ordering and bounded output. Depth is primary for cycling;
    # the closest controller-ray distance disambiguates same-depth elements.
    return heapq.nsmallest(_MAX_HITS, hits, key=lambda h: (h[0], h[1], h[2]))


def _pick_enabled(session):
    return bool(getattr(session, '_xr_precision_enabled', False))


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
    return state, obj, _candidates(
        obj, state['origin'], state['direction'], state['kind'],
        _radius(session), bool(getattr(session, '_xr_precision_through', False)))


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
    # Cycling is an exclusive selection. Ordinary grip+trigger additive
    # selection still works on the existing Select tool.
    mesh.select_element(obj, state['kind'], chosen[2], additive=False)
    state['index'] = chosen[2]
    session.pointer = chosen[3].copy()
    session.status = 'PRECISION / {} {} OF {}'.format(
        state['kind'], next_pos + 1, len(candidates))


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
    if kind == 'FACE':
        _clear(session)
        return legacy_select(session, context, origin, direction, additive=additive)
    origin, ray = _ray(origin, direction)
    candidates = _candidates(
        obj, origin, ray, kind, _radius(session),
        bool(getattr(session, '_xr_precision_through', False)))

    # Preserve the original ability to point at another edit mesh.
    # A closer object takes priority over a vertex/edge of the active mesh.
    scene_hit = session.object_hit(context, origin, ray)
    if scene_hit and scene_hit[0] != obj:
        depth = (scene_hit[1] - origin).dot(ray)
        if not candidates or depth < candidates[0][0] - 0.002:
            _clear(session)
            return legacy_select(session, context, origin, direction,
                                 additive=additive)

    if not candidates:
        _clear(session)
        session.status = 'PRECISION / NO VISIBLE {} NEAR RAY'.format(kind)
        return None
    picked = candidates[0]
    mesh.select_element(obj, kind, picked[2], additive=additive)
    session.pointer = picked[3].copy()
    session._xr_precision_last_ray = {
        'object_ptr': obj.as_pointer(),
        'mesh_ptr': obj.data.as_pointer(),
        'kind': kind,
        'origin': origin.copy(),
        'direction': ray.copy(),
        'index': picked[2],
    }
    session.status = 'PRECISION / {} / {} NEARBY HITS'.format(
        kind, len(candidates))
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
        ('NEXT HIT', 'XR_PICK_NEXT'),
        ('PREVIOUS HIT', 'XR_PICK_PREV'),
        ('RESET RAY', 'XR_PICK_CLEAR'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'MESH PRECISION'
    v065.TOOLTIPS.update({
        'XR_PICK_MENU': ('Precision Pick', 'Set ray tolerance and cycle vertices or edges in Mesh Edit Mode'),
        'XR_PICK_TOGGLE': ('Enable Precision Pick', 'Use precise vertex/edge picking with the Select trigger'),
        'XR_PICK_THROUGH': ('Front / Through', 'Choose whether the picker can target mesh elements behind front surfaces'),
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
