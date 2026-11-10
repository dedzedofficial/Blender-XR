# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Bézier curve authoring in the existing offhand Mesh XR Shapes menu.

A point/handle is placed by choosing a menu command, releasing the trigger,
aiming in the scene and pressing the dominant trigger again. No temporary
mesh or uncommitted curve data is created while a command is armed.
"""
import math

import bpy
from mathutils import Quaternion, Vector

from . import actions, input_ownership_v080, menus, mesh, v065

_MAIN = 'XR_CURVE_MAIN'
_HANDLES = 'XR_CURVE_HANDLES'
_DISPLAY = 'XR_CURVE_DISPLAY'
_MAX_POINTS = 128
_MOVE_ACTIONS = frozenset({'CURVE_ADD_POINT', 'CURVE_MOVE_POINT',
                            'CURVE_HANDLE_LEFT', 'CURVE_HANDLE_RIGHT'})


def _editable(context, obj=None):
    if context.mode != 'OBJECT':
        raise ValueError('Curve authoring requires Object Mode')
    obj = obj or context.view_layer.objects.active
    if obj is None or obj.type != 'CURVE' or obj.mode != 'OBJECT':
        raise ValueError('Select a native Curve object')
    if (obj.library or obj.override_library or obj.data.library or
            obj.data.override_library or obj.data.users != 1):
        raise ValueError('Use a local single-user Curve object')
    if obj.hide_select or not obj.visible_get(view_layer=context.view_layer):
        raise ValueError('Unlock and show the Curve before editing it')
    if len(obj.data.splines) != 1 or obj.data.splines[0].type != 'BEZIER':
        raise ValueError('This editor requires a single Bézier spline; other splines were preserved')
    return obj


def _selected(session, context):
    obj = _editable(context)
    selection = getattr(session, '_xr_curve_target', None)
    if not selection or (selection !=
                         (obj.name, obj.as_pointer(), obj.data.as_pointer())):
        raise ValueError('Curve selection changed; reopen the Curve menu')
    return obj


def _float_equal(a, b):
    if isinstance(a, (float, int)) and isinstance(b, (float, int)):
        return abs(a - b) < 2e-5
    if isinstance(a, tuple) and isinstance(b, tuple):
        return len(a) == len(b) and all(_float_equal(x, y) for x, y in zip(a, b))
    return a == b


def _point_state(pt):
    return (tuple(pt.co), tuple(pt.handle_left), tuple(pt.handle_right),
            pt.handle_left_type, pt.handle_right_type,
            float(pt.tilt), float(pt.radius))


def _state(obj):
    data = obj.data
    spline = data.splines[0]
    return (bool(spline.use_cyclic_u), int(spline.resolution_u),
            float(data.bevel_depth), int(data.bevel_resolution),
            int(data.resolution_u),
            tuple(_point_state(point) for point in spline.bezier_points))


def _set_points(spline, records):
    # Blender's SplineBezierPoints supports add() but NOT remove(); rebuild
    # this single supported spline only when the point count changes.
    points = spline.bezier_points
    if len(points) < len(records):
        points.add(len(records) - len(points))
    for point, state in zip(points, records):
        co, left, right, left_type, right_type, tilt, radius = state
        point.handle_left_type = 'FREE'
        point.handle_right_type = 'FREE'
        point.co = co
        point.handle_left = left
        point.handle_right = right
        point.tilt = tilt
        point.radius = radius
        point.handle_left_type = left_type
        point.handle_right_type = right_type


def _restore(obj, snapshot):
    cyclic, spline_resolution, depth, bevel_resolution, resolution, records = snapshot
    if len(records) < 2 or len(records) > _MAX_POINTS:
        raise ValueError('Cannot restore an invalid Bézier point count')
    data = obj.data
    spline = data.splines[0]
    if len(spline.bezier_points) > len(records):
        # No bpy.ops.curve.editmode_toggle, no replacement of the Curve datablock,
        # and no changes to materials or unrelated objects.
        data.splines.remove(spline)
        spline = data.splines.new('BEZIER')
    _set_points(spline, records)
    spline.use_cyclic_u = cyclic
    spline.resolution_u = spline_resolution
    data.bevel_depth = depth
    data.bevel_resolution = bevel_resolution
    data.resolution_u = resolution


def _world_position(session, context):
    ray = getattr(session, 'ray', None)
    if ray is None:
        raise ValueError('Point the dominant controller at the scene')
    origin, direction = (Vector(ray[0]), Vector(ray[1]))
    if direction.length < .5:
        raise ValueError('Controller aim pose is not ready')
    distance = float(session.settings.placement_distance)
    scale = float(getattr(getattr(context.window_manager, 'xr_session_state', None),
                          'viewer_scale', 1.0))
    return origin + direction.normalized() * distance * max(.01, scale)


def _create(session, context):
    if context.mode != 'OBJECT':
        raise ValueError('Switch to Object Mode to create a Curve')
    center = _world_position(session, context)
    data = bpy.data.curves.new('XR Bézier Curve', type='CURVE')
    obj = None
    try:
        data.dimensions = '3D'
        data.resolution_u = 16
        data.bevel_depth = .012
        spline = data.splines.new('BEZIER')
        spline.bezier_points.add(1)
        for point, co in zip(spline.bezier_points, ((0, 0, 0), (.25, 0, 0))):
            point.co = co
            point.handle_left_type = 'AUTO'
            point.handle_right_type = 'AUTO'
        obj = bpy.data.objects.new('XR Bézier Curve', data)
        context.scene.collection.objects.link(obj)
        obj.location = center
        for selected in tuple(context.selected_objects):
            selected.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        session._xr_curve_target = (obj.name, obj.as_pointer(), data.as_pointer())
        session._xr_curve_index = 1
        session.history.push(('XR_CURVE_CREATE', obj.name, data.name, data,
                              tuple(obj.users_collection), obj.matrix_world.copy()))
        _page(session, context)
    except Exception:
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
        if data.users == 0:
            bpy.data.curves.remove(data)
        raise


def _page(session, context, subpage=_MAIN):
    obj = _selected(session, context)
    count = len(obj.data.splines[0].bezier_points)
    session._xr_curve_index = min(max(0, int(getattr(
        session, '_xr_curve_index', 0))), count-1)
    menus.TITLES[_MAIN] = 'CURVE / POINT {}/{}'.format(
        session._xr_curve_index + 1, count)
    session.menu.page = subpage
    session.status = 'NATIVE BEZIER / POINT {} OF {}'.format(
        session._xr_curve_index + 1, count)


def _edit(session, context, action, world=None):
    obj = _selected(session, context)
    spline = obj.data.splines[0]
    points = spline.bezier_points
    index = min(max(0, int(getattr(session, '_xr_curve_index', 0))), len(points)-1)
    before = _state(obj)
    try:
        if action == 'CURVE_ADD_POINT':
            if len(points) >= _MAX_POINTS:
                raise ValueError('Curve reached the 128-point XR limit')
            if world is None:
                raise ValueError('Aim the controller to place the next point')
            points.add(1)
            point = points[-1]
            point.co = obj.matrix_world.inverted() @ Vector(world)
            point.handle_left_type = 'AUTO'
            point.handle_right_type = 'AUTO'
            session._xr_curve_index = len(points) - 1
        elif action == 'CURVE_DEL_POINT':
            if len(points) <= 2:
                raise ValueError('A Bézier spline needs at least two points')
            records = tuple(_point_state(p) for i, p in enumerate(points) if i != index)
            # Rebuild the sole spline, retaining all point coordinates/handles.
            obj.data.splines.remove(spline)
            spline = obj.data.splines.new('BEZIER')
            _set_points(spline, records)
            spline.use_cyclic_u = before[0]
            spline.resolution_u = before[1]
            session._xr_curve_index = min(index, len(records)-1)
        elif action == 'CURVE_MOVE_POINT':
            if world is None:
                raise ValueError('Aim the controller to move the selected point')
            points[index].co = obj.matrix_world.inverted() @ Vector(world)
        elif action in {'CURVE_HANDLE_LEFT', 'CURVE_HANDLE_RIGHT'}:
            if world is None:
                raise ValueError('Aim the controller to move a Bézier handle')
            point = points[index]
            attr = 'handle_left' if action.endswith('LEFT') else 'handle_right'
            kind = attr + '_type'
            point.__setattr__(kind, 'FREE')
            point.__setattr__(attr, obj.matrix_world.inverted() @ Vector(world))
        elif action.startswith('CURVE_HANDLE_TYPE_'):
            handle_type = action.removeprefix('CURVE_HANDLE_TYPE_')
            if handle_type not in {'AUTO', 'ALIGNED', 'FREE', 'VECTOR'}:
                raise ValueError('Unknown handle mode')
            points[index].handle_left_type = handle_type
            points[index].handle_right_type = handle_type
        elif action == 'CURVE_CYCLIC':
            spline.use_cyclic_u = not spline.use_cyclic_u
        elif action == 'CURVE_BEVEL_UP':
            obj.data.bevel_depth = min(2.0, obj.data.bevel_depth + .01)
        elif action == 'CURVE_BEVEL_DOWN':
            obj.data.bevel_depth = max(0.0, obj.data.bevel_depth - .01)
        elif action == 'CURVE_RES_UP':
            obj.data.resolution_u = min(64, obj.data.resolution_u + 2)
        elif action == 'CURVE_RES_DOWN':
            obj.data.resolution_u = max(1, obj.data.resolution_u - 2)
        elif action == 'CURVE_BEVEL_RES_UP':
            obj.data.bevel_resolution = min(16, obj.data.bevel_resolution + 1)
        elif action == 'CURVE_BEVEL_RES_DOWN':
            obj.data.bevel_resolution = max(0, obj.data.bevel_resolution - 1)
        else:
            raise ValueError('Unknown Curve action')
    except Exception:
        _restore(obj, before)
        raise
    after = _state(obj)
    if not _float_equal(before, after):
        session.history.push(('XR_CURVE_EDIT', obj.name, obj.data.name,
                              obj, obj.data, before, after))
    _page(session, context, session.menu.page)
    return not _float_equal(before, after)


def _arm(session, context, action):
    obj = _selected(session, context)
    if input_ownership_v080.owner(session) not in {'IDLE', 'RADIAL'}:
        raise ValueError('Release the active XR edit before placing a Curve point')
    session._xr_curve_pending = (obj.name, obj.as_pointer(), action)
    session._xr_curve_ready = False
    radial = getattr(session, 'radial', None)
    if radial is not None and getattr(radial, 'active', False):
        radial.reset(require_release=True)
    session._xr_curve_was_visible = bool(session.menu.visible)
    session.menu.visible = False
    session.status = 'CURVE: RELEASE, AIM, TRIGGER TO PLACE / OFFHAND CANCEL'


def _cancel_pending(session):
    if getattr(session, '_xr_curve_pending', None) is not None:
        session._xr_curve_pending = None
        session.menu.visible = bool(getattr(session, '_xr_curve_was_visible', True))
        session._xr_curve_release_required = True


def _input_sample(session, context):
    state = context.window_manager.xr_session_state
    if state is None or not bpy.types.XrSessionState.is_running(context):
        raise ValueError('XR tracking ended while placing a Curve point')
    pose = Quaternion(state.controller_aim_rotation_get(context, session.dom))
    if pose.magnitude < .5:
        raise ValueError('Controller tracking lost while placing a Curve point')
    if getattr(session, 'bridge', None) is not None:
        sample = session.bridge.read()
        if sample is None:
            raise ValueError('Finger input lost while placing a Curve point')
        held = float(sample[session.dom][0])
        cancel = float(sample[session.off][0]) >= .6
    else:
        held = float(actions.read(context, 'trigger', session.dom)[0])
        cancel = float(actions.read(context, 'trigger', session.off)[0]) >= .6
    origin = Vector(state.controller_aim_location_get(context, session.dom))
    direction = pose @ Vector((0, 0, -1))
    return held >= .6, cancel, origin, direction


def _capture_tick(session, context):
    try:
        pressed, cancel, origin, direction = _input_sample(session, context)
    except (ValueError, RuntimeError, AttributeError, IndexError, TypeError) as exc:
        _cancel_pending(session)
        session._xr_rearm_required = True
        session.status = str(exc).upper() + ' / RELEASE TO REARM'
        return
    if cancel and getattr(session, '_xr_curve_ready', False):
        _cancel_pending(session)
        session.status = 'CURVE POINT PLACEMENT CANCELLED'
        return
    if not pressed:
        if getattr(session, '_xr_curve_pending', None) and not cancel:
            session._xr_curve_ready = True
        else:
            session._xr_curve_release_required = False
        if getattr(session, 'trigger', None):
            session.trigger.update(0)
        return
    if not getattr(session, '_xr_curve_pending', None) or not session._xr_curve_ready:
        return
    name, pointer, action = session._xr_curve_pending
    session.ray = origin, direction
    try:
        obj = _selected(session, context)
        if obj.name != name or obj.as_pointer() != pointer:
            raise ValueError('Curve changed during point placement')
        result = _edit(session, context, action, _world_position(session, context))
        session.status = 'CURVE POINT SAVED' if result else 'CURVE POINT UNCHANGED'
    except (ValueError, RuntimeError, ReferenceError) as exc:
        session.status = 'CURVE CANCELLED / ' + str(exc).upper()[:50]
    finally:
        _cancel_pending(session)
        if getattr(session, 'trigger', None):
            session.trigger.update(1.0)


def _patch_history():
    if getattr(mesh.History, '_xr_native_curve_history', False):
        return
    original_step, original_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == 'XR_CURVE_EDIT':
            return
        if entry[0] == 'XR_CURVE_CREATE':
            data = entry[3]
            try:
                if data.users == 0 and bpy.data.curves.get(data.name) == data:
                    bpy.data.curves.remove(data)
            except ReferenceError:
                pass
            return
        return original_release(entry)

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] not in {'XR_CURVE_EDIT', 'XR_CURVE_CREATE'}:
            return original_step(self, backwards)
        entry = source[-1]
        if bpy.context.mode != 'OBJECT':
            raise ValueError('Return to Object Mode to undo Curve authoring')
        if entry[0] == 'XR_CURVE_EDIT':
            _tag, name, data_name, identity, data, before, after = entry
            obj = bpy.data.objects.get(name)
            if (obj is None or obj != identity or obj.data != data or
                    obj.data.name != data_name):
                raise ValueError('Curve identity changed outside XR history')
            _editable(bpy.context, obj)
            expected = after if backwards else before
            if not _float_equal(_state(obj), expected):
                raise ValueError('Curve was edited outside XR history')
            _restore(obj, before if backwards else after)
        else:
            _tag, name, data_name, data, collections, matrix = entry
            obj = bpy.data.objects.get(name)
            if backwards:
                if obj is None or obj.data != data or obj.type != 'CURVE':
                    raise ValueError('Curve was removed or replaced outside XR history')
                _editable(bpy.context, obj)
                bpy.data.objects.remove(obj, do_unlink=True)
            else:
                if obj is not None or bpy.data.curves.get(data_name) != data:
                    raise ValueError('Curve name or data changed outside XR history')
                valid = [coll for coll in collections if (coll == bpy.context.scene.collection or
                         bpy.data.collections.get(coll.name) == coll)]
                if not valid:
                    raise ValueError('Original Curve collection was removed')
                obj = bpy.data.objects.new(name, data)
                obj.matrix_world = matrix.copy()
                for coll in valid:
                    coll.objects.link(obj)
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
        dest.append(source.pop())
        return True

    mesh.History.release = staticmethod(release)
    mesh.History.step = step
    mesh.History._xr_native_curve_history = True


def install_pages():
    # Shapes menu currently has six mesh primitives and Back: add one native
    # Curve entry, keeping all original primitive operator IDs intact.
    if not any(action == 'CURVE_MENU' for _label, action in menus.PAGES['PRIMITIVES']):
        buttons = tuple(menus.PAGES['PRIMITIVES'])
        menus.PAGES['PRIMITIVES'] = buttons[:-1] + (
            ('CURVE', 'CURVE_MENU'), buttons[-1])
    menus.PAGES[_MAIN] = (
        ('NEW CURVE', 'CURVE_NEW'), ('PREV PT', 'CURVE_PREV'),
        ('NEXT PT', 'CURVE_NEXT'), ('ADD PT', 'CURVE_ADD_POINT'),
        ('MOVE PT', 'CURVE_MOVE_POINT'), ('DELETE PT', 'CURVE_DEL_POINT'),
        ('CLOSE/OPEN', 'CURVE_CYCLIC'), ('HANDLES', 'CURVE_HANDLE_MENU'),
        ('APPEARANCE', 'CURVE_DISPLAY_MENU'), ('BACK', 'BACK'),
    )
    menus.PAGES[_HANDLES] = (
        ('AUTO', 'CURVE_HANDLE_TYPE_AUTO'),
        ('ALIGNED', 'CURVE_HANDLE_TYPE_ALIGNED'),
        ('FREE', 'CURVE_HANDLE_TYPE_FREE'),
        ('VECTOR', 'CURVE_HANDLE_TYPE_VECTOR'),
        ('LEFT AIM', 'CURVE_HANDLE_LEFT'),
        ('RIGHT AIM', 'CURVE_HANDLE_RIGHT'), ('BACK', 'BACK'),
    )
    menus.PAGES[_DISPLAY] = (
        ('DEPTH -', 'CURVE_BEVEL_DOWN'), ('DEPTH +', 'CURVE_BEVEL_UP'),
        ('DETAIL -', 'CURVE_RES_DOWN'), ('DETAIL +', 'CURVE_RES_UP'),
        ('BEVEL -', 'CURVE_BEVEL_RES_DOWN'),
        ('BEVEL +', 'CURVE_BEVEL_RES_UP'), ('BACK', 'BACK'),
    )
    menus.TITLES.update({_MAIN: 'EDIT BEZIER CURVE', _HANDLES: 'CURVE HANDLES',
                         _DISPLAY: 'CURVE APPEARANCE'})
    v065.TOOLTIPS.update({
        'CURVE_MENU': ('Curve Authoring', 'Create a native Bézier curve or edit a selected one'),
        'CURVE_NEW': ('Create Bézier Curve', 'Add a new native editable curve at the controller aim'),
        'CURVE_MOVE_POINT': ('Move Point in 3D', 'Release then aim into the scene; dominant trigger commits'),
        'CURVE_ADD_POINT': ('Extend Curve', 'Release then aim to place a new Bézier point'),
        'CURVE_HANDLE_MENU': ('Bézier Handles', 'Change selected point handle type or position'),
        'CURVE_CYCLIC': ('Open or Close', 'Toggle cyclic spline without replacing geometry'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_native_curves_patched', False):
        return
    _patch_history()
    install_pages()
    previous_command = Runtime.command
    previous_tick = Runtime.tick
    previous_cancel = Runtime.cancel_work

    def cancel_work(self):
        _cancel_pending(self)
        return previous_cancel(self)

    def tick(self, context):
        if (getattr(self, '_xr_curve_pending', None) is not None or
                getattr(self, '_xr_curve_release_required', False)):
            _capture_tick(self, context)
            return
        return previous_tick(self, context)

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous_command(self, context, action)
        page = menu.page
        if action == 'CURVE_MENU':
            if input_ownership_v080.owner(self) not in {'IDLE', 'RADIAL'}:
                raise ValueError('Finish the active XR edit before opening Curves')
            self.menu.page = _MAIN
            obj = context.view_layer.objects.active
            if obj and obj.type == 'CURVE':
                _editable(context, obj)
                self._xr_curve_target = (obj.name, obj.as_pointer(), obj.data.as_pointer())
                self._xr_curve_index = 0
                _page(self, context)
            else:
                self._xr_curve_target = None
                self.status = 'CURVE / PRESS NEW TO CREATE'
            return
        if action == 'CURVE_NEW' and page == _MAIN:
            _create(self, context)
            return
        if action == 'BACK' and page in {_MAIN, _HANDLES, _DISPLAY}:
            if page == _MAIN:
                self.menu.page = 'PRIMITIVES'
            else:
                _page(self, context)
            return
        if page not in {_MAIN, _HANDLES, _DISPLAY}:
            return previous_command(self, context, action)
        if action in {'CURVE_HANDLE_MENU', 'CURVE_DISPLAY_MENU'}:
            _page(self, context, _HANDLES if action == 'CURVE_HANDLE_MENU' else _DISPLAY)
            return
        if action in {'CURVE_PREV', 'CURVE_NEXT'}:
            obj = _selected(self, context)
            count = len(obj.data.splines[0].bezier_points)
            self._xr_curve_index = (self._xr_curve_index + (1 if action.endswith('NEXT')
                                    else -1)) % count
            _page(self, context)
            return
        if action in _MOVE_ACTIONS:
            _arm(self, context, action)
            return
        if action.startswith('CURVE_'):
            _edit(self, context, action)
            return
        return previous_command(self, context, action)

    Runtime.cancel_work = cancel_work
    Runtime.command = command
    Runtime.tick = tick
    Runtime._xr_native_curves_patched = True
