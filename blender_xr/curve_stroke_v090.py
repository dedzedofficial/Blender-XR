# SPDX-License-Identifier: GPL-3.0-or-later
"""Controller-drawn native Blender Bézier curves for Mesh XR.

The controller grip pose is sampled only from the shared validated XR frame.
A temporary GPU line preview is used; no Blender object or Curve datablock is
created until the artist explicitly confirms the stroke.
"""
import math

import bpy
from mathutils import Vector

from . import input_ownership_v080, menus, native_curves_v080, v065

_PAGE = 'XR_CURVE_STROKE_PREVIEW_090'
_MAX_POINTS = 128
_MIN_POINT_DISTANCE = 0.015
_COORDINATE_LIMIT = 1.0e6
_DRAW_ACTIONS = frozenset({
    'CURVE_STROKE_CONFIRM',
    'CURVE_STROKE_CANCEL',
    'CURVE_STROKE_CYCLE',
})


def _point(value):
    result = Vector(value)
    if len(result) != 3 or not all(math.isfinite(float(v)) for v in result):
        raise ValueError('Controller path contains invalid coordinates')
    if max(abs(float(v)) for v in result) > _COORDINATE_LIMIT:
        raise ValueError('Controller path exceeds the supported scene range')
    return result


def _context_fingerprint(context):
    selected = tuple(sorted(
        (obj.name, int(obj.as_pointer())) for obj in context.selected_objects
    ))
    active = context.view_layer.objects.active
    active_token = ((active.name, int(active.as_pointer()))
                    if active is not None else None)
    return (
        int(context.scene.as_pointer()),
        int(context.view_layer.as_pointer()),
        str(context.mode),
        selected,
        active_token,
    )


def _restore_menu(session, state=None, preview=None):
    menu = getattr(session, 'menu', None)
    if menu is None:
        return
    if getattr(menu, 'page', None) == _PAGE:
        menu.page = native_curves_v080._MAIN
    if state is not None:
        menu.visible = bool(state.get('menu_visible', True))
    elif preview is not None:
        menu.visible = bool(preview.get('menu_visible', True))


def _clear_stroke(session, message=None):
    state = getattr(session, '_xr_curve_stroke', None)
    preview = getattr(session, '_xr_curve_stroke_preview', None)
    session._xr_curve_stroke = None
    session._xr_curve_stroke_preview = None
    _restore_menu(session, state, preview)
    if message:
        session.status = str(message)


def _begin_stroke(session, context):
    if context.mode != 'OBJECT':
        raise ValueError('Switch to Object Mode before drawing a Curve')
    if input_ownership_v080.owner(session) not in {'IDLE', 'RADIAL'}:
        raise ValueError('Release the active XR edit before drawing a Curve')
    if getattr(session, '_xr_curve_stroke_preview', None) is not None:
        raise ValueError('Confirm or cancel the existing Curve preview first')
    menu = getattr(session, 'menu', None)
    if menu is None:
        raise ValueError('XR Curve menu is unavailable')
    radial = getattr(session, 'radial', None)
    if radial is not None and getattr(radial, 'active', False):
        radial.reset(require_release=True)
    session._xr_curve_stroke = {
        'phase': 'WAIT_RELEASE',
        'points': [],
        'fingerprint': _context_fingerprint(context),
        'menu_visible': bool(menu.visible),
    }
    menu.visible = False
    for field in ('pointer', 'hover', 'target', 'gizmo', 'gizmo_hover'):
        if hasattr(session, field):
            setattr(session, field, None)
    session.status = 'CURVE DRAW / RELEASE TRIGGER, THEN HOLD TO DRAW'


def _smooth_points(records):
    points = [_point(item) for item in records]
    if len(points) <= 2:
        return tuple(tuple(float(v) for v in p) for p in points)
    smoothed = [points[0]]
    for index in range(1, len(points) - 1):
        value = points[index] * 0.75 + (
            points[index - 1] + points[index + 1]
        ) * 0.125
        smoothed.append(value)
    smoothed.append(points[-1])
    compact = [smoothed[0]]
    for value in smoothed[1:]:
        if (value - compact[-1]).length > 1.0e-5:
            compact.append(value)
    if len(compact) < 2:
        raise ValueError('Draw a longer path with at least two distinct points')
    return tuple(tuple(float(v) for v in p) for p in compact)


def _append_sample(state, position, scale):
    point = _point(position)
    points = state['points']
    minimum = max(0.003, min(0.05, _MIN_POINT_DISTANCE * float(scale)))
    if points and (point - Vector(points[-1])).length < minimum:
        return False
    if len(points) >= _MAX_POINTS:
        return False
    points.append(tuple(float(v) for v in point))
    return True


def _make_preview(session, state):
    if len(state['points']) < 2:
        _clear_stroke(session, 'CURVE DRAW NEEDS TWO DISTINCT POINTS')
        return False
    try:
        points = _smooth_points(state['points'])
    except ValueError as exc:
        _clear_stroke(session, str(exc).upper())
        return False
    session._xr_curve_stroke = None
    session._xr_curve_stroke_preview = {
        'points': points,
        'cyclic': False,
        'fingerprint': state['fingerprint'],
        'menu_visible': state['menu_visible'],
    }
    session.menu.page = _PAGE
    session.menu.visible = True
    session.status = 'CURVE PREVIEW / {} POINTS / CONFIRM OR CANCEL'.format(
        len(points)
    )
    return True


def _advance_stroke(session, context, pressed, cancel, position, scale=1.0):
    state = getattr(session, '_xr_curve_stroke', None)
    if state is None:
        return False
    if _context_fingerprint(context) != state['fingerprint']:
        _clear_stroke(session, 'SCENE OR SELECTION CHANGED / CURVE DRAW CANCELLED')
        session._xr_rearm_required = True
        session._xr_neutral_count = 0
        return False
    if cancel:
        _clear_stroke(session, 'CURVE DRAW CANCELLED / RELEASE BOTH TRIGGERS')
        session._xr_rearm_required = True
        session._xr_neutral_count = 0
        return False
    phase = state['phase']
    if phase == 'WAIT_RELEASE':
        if not pressed:
            state['phase'] = 'READY'
            session.status = 'CURVE DRAW READY / HOLD TRIGGER TO DRAW'
        return True
    if phase == 'READY':
        if pressed:
            state['phase'] = 'DRAWING'
            _append_sample(state, position, scale)
            session.status = 'CURVE DRAWING / MOVE CONTROLLER / RELEASE TO PREVIEW'
        return True
    if phase == 'DRAWING':
        if pressed:
            added = _append_sample(state, position, scale)
            if not added and len(state['points']) >= _MAX_POINTS:
                session.status = 'CURVE POINT LIMIT / RELEASE TO PREVIEW'
        else:
            _make_preview(session, state)
        return True
    _clear_stroke(session, 'UNKNOWN CURVE DRAW STATE / CANCELLED')
    return False


def _capture_tick(session, context):
    try:
        poses = getattr(session, '_xr_validated_poses', None)
        controls = getattr(session, '_xr_validated_controls', None)
        viewer = getattr(session, '_xr_validated_viewer', None)
        if (not poses or controls is None or session.dom not in poses or
                session.off not in poses or len(controls) != 2 or
                session.dom not in (0, 1) or session.off not in (0, 1) or
                viewer is None):
            raise ValueError('Validated controller frame is missing')
        aim_rotation, aim_position = poses[session.dom][0]
        _grip_rotation, grip_position = poses[session.dom][1]
        pressed = float(controls[session.dom][0]) >= 0.6
        cancel = float(controls[session.off][0]) >= 0.6
        scale = float(viewer[1])
        if not math.isfinite(scale) or scale <= 0.0:
            raise ValueError('XR viewer scale is invalid')
        session.ray = (
            Vector(aim_position).copy(),
            aim_rotation @ Vector((0.0, 0.0, -1.0)),
        )
        if getattr(session, 'trigger', None):
            session.trigger.update(1.0 if pressed else 0.0)
        if getattr(session, 'off_trigger', None):
            session.off_trigger.update(1.0 if cancel else 0.0)
        _advance_stroke(
            session, context, pressed, cancel, grip_position, scale
        )
    except (ValueError, RuntimeError, TypeError, AttributeError,
            IndexError, ReferenceError, OverflowError) as exc:
        _clear_stroke(session, 'CURVE DRAW CANCELLED / ' + str(exc).upper()[:52])
        session._xr_rearm_required = True
        session._xr_neutral_count = 0


def _restore_selection(context, selected, active):
    for obj in tuple(context.selected_objects):
        try:
            obj.select_set(False)
        except (ReferenceError, RuntimeError):
            pass
    for obj in selected:
        try:
            if context.view_layer.objects.get(obj.name) == obj:
                obj.select_set(True)
        except (ReferenceError, RuntimeError):
            pass
    try:
        context.view_layer.objects.active = (
            active if active is not None and
            context.view_layer.objects.get(active.name) == active else None
        )
    except (ReferenceError, RuntimeError):
        context.view_layer.objects.active = None


def _commit_preview(session, context):
    preview = getattr(session, '_xr_curve_stroke_preview', None)
    if preview is None:
        raise ValueError('No drawn Curve preview is awaiting confirmation')
    if context.mode != 'OBJECT':
        raise ValueError('Return to Object Mode before confirming the Curve')
    if _context_fingerprint(context) != preview['fingerprint']:
        raise ValueError('Scene or selection changed; redraw the Curve preview')
    points = tuple(_point(item) for item in preview['points'])
    if len(points) < (3 if preview['cyclic'] else 2) or len(points) > _MAX_POINTS:
        raise ValueError('Curve preview has an invalid point count')
    if any((points[i] - points[i - 1]).length <= 1.0e-5
           for i in range(1, len(points))):
        raise ValueError('Curve preview contains duplicate consecutive points')
    if preview['cyclic'] and (points[-1] - points[0]).length <= 1.0e-5:
        raise ValueError('Closed Curve endpoints must be distinct')

    selected = tuple(context.selected_objects)
    active = context.view_layer.objects.active
    origin = points[0].copy()
    data = bpy.data.curves.new('XR Drawn Curve', type='CURVE')
    obj = None
    try:
        data.dimensions = '3D'
        data.resolution_u = 16
        data.bevel_depth = 0.012
        data.bevel_resolution = 2
        spline = data.splines.new('BEZIER')
        spline.bezier_points.add(len(points) - 1)
        for bezier, world in zip(spline.bezier_points, points):
            bezier.co = world - origin
            bezier.handle_left_type = 'AUTO'
            bezier.handle_right_type = 'AUTO'
            bezier.tilt = 0.0
            bezier.radius = 1.0
        spline.use_cyclic_u = bool(preview['cyclic'])
        obj = bpy.data.objects.new('XR Drawn Curve', data)
        context.scene.collection.objects.link(obj)
        obj.location = origin
        for item in selected:
            item.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        if getattr(session, 'history', None) is None:
            raise ValueError('XR Undo history is unavailable')
        session.history.push((
            'XR_CURVE_CREATE', obj.name, data.name, data,
            tuple(obj.users_collection), obj.matrix_world.copy()
        ))
    except Exception:
        cleanup_failed = False
        if obj is not None:
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
            except Exception:
                cleanup_failed = True
        try:
            if data.users == 0 and bpy.data.curves.get(data.name) == data:
                bpy.data.curves.remove(data)
        except Exception:
            cleanup_failed = True
        _restore_selection(context, selected, active)
        if cleanup_failed:
            session._xr_rollback_blocked = True
            session._xr_rearm_required = True
            session.status = 'CURVE CREATE ROLLBACK FAILED / REVIEW SCENE / RESTART XR'
        raise
    session._xr_curve_stroke_preview = None
    session._xr_curve_target = (obj.name, obj.as_pointer(), data.as_pointer())
    session._xr_curve_index = 0
    native_curves_v080._page(session, context)
    session.status = 'NATIVE CURVE SAVED / XR UNDO READY'
    return obj


def _cancel_preview(session):
    if getattr(session, '_xr_curve_stroke_preview', None) is None:
        raise ValueError('No Curve preview is awaiting confirmation')
    _clear_stroke(session, 'CURVE PREVIEW CANCELLED')


def install_pages():
    page = native_curves_v080._MAIN
    buttons = list(menus.PAGES.get(page, ()))
    if not any(action == 'CURVE_STROKE_START' for _label, action in buttons):
        buttons.insert(max(0, len(buttons) - 1), ('DRAW PATH', 'CURVE_STROKE_START'))
    menus.PAGES[page] = tuple(buttons[:12])
    menus.PAGES[_PAGE] = (
        ('CONFIRM', 'CURVE_STROKE_CONFIRM'),
        ('CLOSE PATH', 'CURVE_STROKE_CYCLE'),
        ('CANCEL', 'CURVE_STROKE_CANCEL'),
    )
    menus.TITLES[_PAGE] = 'CURVE STROKE PREVIEW'
    v065.TOOLTIPS.update({
        'CURVE_STROKE_START': (
            'Draw Curve Path',
            'Hold the dominant trigger and move the controller grip to draw a native Bézier path'
        ),
        'CURVE_STROKE_CONFIRM': (
            'Confirm Drawn Curve',
            'Create one editable native Blender Curve and one XR Undo entry'
        ),
        'CURVE_STROKE_CYCLE': (
            'Close Curve Path',
            'Toggle a closed spline preview; closed paths need at least three points'
        ),
        'CURVE_STROKE_CANCEL': (
            'Cancel Curve Preview',
            'Discard the GPU preview without creating Blender data'
        ),
    })


def draw_preview(session, shader, draw_batch):
    stroke = getattr(session, '_xr_curve_stroke', None)
    preview = getattr(session, '_xr_curve_stroke_preview', None)
    source = preview if preview is not None else stroke
    if source is None:
        return
    points = source.get('points', ())
    if len(points) < 2:
        return
    world = [_point(item) for item in points]
    segments = []
    for index in range(1, len(world)):
        segments.extend((world[index - 1], world[index]))
    if preview is not None and preview.get('cyclic') and len(world) > 2:
        segments.extend((world[-1], world[0]))
    draw_batch(shader, 'LINES', segments, (1.0, 0.58, 0.12, 1.0))


def cancel(session):
    """Discard an unfinished stroke or preview during the shared cancel path."""
    _clear_stroke(session)


def handle_tick(session, context):
    """Handle the live stroke inside the existing native Curve tick route."""
    if getattr(session, '_xr_curve_stroke', None) is None:
        return False
    from . import input_safety_v086
    if not input_safety_v086.guard_specialized_frame(session, context):
        if getattr(session, '_xr_curve_stroke', None) is not None:
            _clear_stroke(session, 'CURVE DRAW CANCELLED / INPUT REARM REQUIRED')
        return True
    _capture_tick(session, context)
    return True


def handle_command(session, context, action):
    """Handle stroke actions before the existing native Curve command route."""
    menu = getattr(session, 'menu', None)
    if menu is None:
        return False
    preview = getattr(session, '_xr_curve_stroke_preview', None)
    if preview is not None:
        if action == 'CURVE_STROKE_CONFIRM':
            _commit_preview(session, context)
            return True
        if action == 'CURVE_STROKE_CANCEL':
            _cancel_preview(session)
            return True
        if action == 'CURVE_STROKE_CYCLE':
            if len(preview['points']) < 3:
                raise ValueError('Draw at least three points to close a Curve')
            preview['cyclic'] = not bool(preview.get('cyclic'))
            session.status = 'CURVE PREVIEW / ' + (
                'CLOSED' if preview['cyclic'] else 'OPEN'
            )
            return True
        if action == 'STOP':
            _clear_stroke(session)
            return False
        raise ValueError('Confirm or cancel the current Curve preview first')
    if action == 'CURVE_STROKE_START' and menu.page == native_curves_v080._MAIN:
        _begin_stroke(session, context)
        return True
    if action in _DRAW_ACTIONS:
        raise ValueError('No drawn Curve preview is active')
    return False
