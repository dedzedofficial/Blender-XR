# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Blender Light object authoring in the existing offhand XR Shapes menu.

Edits native light data and object transforms only; no helper objects, shadow
handlers, material replacement, or render-engine-specific hidden nodes.
Aim/move operations arm without mutating, then commit on a NEW trigger edge.
"""
import math

import bpy
from mathutils import Matrix, Quaternion, Vector

from . import actions, input_ownership_v080, menus, mesh, native_curves_v080, v065

_HOME = 'XR_LIGHT_HOME'
_EDIT = 'XR_LIGHT_EDIT'
_COLOR = 'XR_LIGHT_COLOR'
_SHAPE = 'XR_LIGHT_SHAPE'
_PRESETS = 'XR_LIGHT_PRESETS'
_KINDS = ('POINT', 'SPOT', 'AREA', 'SUN')
_AIM = frozenset({'XR_LIGHT_MOVE', 'XR_LIGHT_AIM'})
_COLORS = {
    'WHITE': (1.0, 1.0, 1.0),
    'WARM': (1.0, .64, .39),
    'COOL': (.72, .85, 1.0),
    'RED': (1.0, .06, .05),
    'GREEN': (.08, 1.0, .18),
    'BLUE': (.08, .27, 1.0),
}
# Deliberately static editable presets. These do NOT insert animation keys.
_PRESET_COLORS = {
    'CANDLE': (.99, .48, .19),
    'TORCH': (1.0, .61, .27),
    'MOON': (.39, .58, 1.0),
    'NEON': (.13, .95, .88),
    'HORROR': (.9, .055, .075),
}
_PRESET_ENERGY = {
    'CANDLE': 90.0, 'TORCH': 420.0, 'MOON': 650.0,
    'NEON': 900.0, 'HORROR': 220.0,
}


def _editable(context, obj=None):
    if context.mode != 'OBJECT':
        raise ValueError('Light editing requires Object Mode')
    obj = obj or context.view_layer.objects.active
    if obj is None or obj.type != 'LIGHT' or obj.mode != 'OBJECT':
        raise ValueError('Select a native Blender Light')
    if obj.data.type not in _KINDS:
        raise ValueError('Only Point, Spot, Area and Sun lights are supported')
    if obj.library or obj.override_library or obj.data.library or obj.data.override_library:
        raise ValueError('Linked/overridden Lights cannot be edited')
    if obj.data.users != 1:
        raise ValueError('Make Light data single-user before changing its properties')
    if obj.hide_select or not obj.visible_get(view_layer=context.view_layer):
        raise ValueError('Unlock and show the Light before editing it')
    if (getattr(obj.data, 'use_nodes', False) or
            (obj.animation_data and (obj.animation_data.action or obj.animation_data.drivers)) or
            (obj.data.animation_data and
             (obj.data.animation_data.action or obj.data.animation_data.drivers))):
        raise ValueError('Shader-driven or animated Lights need their original editor')
    return obj


def _selection(session, context):
    obj = _editable(context)
    token = getattr(session, '_xr_light_target', None)
    if token != (obj.name, obj.as_pointer(), obj.data.as_pointer()):
        raise ValueError('Light selection changed; reopen the Lights menu')
    return obj


def _props(light):
    common = (float(light.energy), tuple(float(v) for v in light.color))
    if light.type == 'POINT':
        return common + (float(light.shadow_soft_size),)
    if light.type == 'SPOT':
        return common + (float(light.shadow_soft_size),
                         float(light.spot_size), float(light.spot_blend))
    if light.type == 'AREA':
        return common + (str(light.shape), float(light.size), float(light.size_y))
    if light.type == 'SUN':
        return common + (float(light.angle),)
    raise ValueError('Unsupported light type')


def _state(obj):
    return (obj.data.type,
            tuple(tuple(float(v) for v in row) for row in obj.matrix_world),
            _props(obj.data))


def _same(a, b):
    if isinstance(a, (float, int)) and isinstance(b, (float, int)):
        return abs(a - b) <= 2e-5
    if isinstance(a, tuple) and isinstance(b, tuple):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def _restore(obj, snapshot):
    kind, matrix, values = snapshot
    light = obj.data
    if kind != light.type:
        raise ValueError('Light type changed outside XR authoring')
    light.energy = values[0]
    light.color = values[1]
    if kind == 'POINT':
        light.shadow_soft_size = values[2]
    elif kind == 'SPOT':
        light.shadow_soft_size = values[2]
        light.spot_size = values[3]
        light.spot_blend = values[4]
    elif kind == 'AREA':
        light.shape = values[2]
        light.size = values[3]
        light.size_y = values[4]
    elif kind == 'SUN':
        light.angle = values[2]
    obj.matrix_world = Matrix(matrix)


def _page(session, context, target=_EDIT):
    obj = _selection(session, context)
    menus.TITLES[_EDIT] = ('LIGHT / ' + obj.data.type)[:21]
    light = obj.data
    if light.type == 'POINT':
        controls = (
            ('RADIUS -', 'XR_LIGHT_RADIUS_DOWN'),
            ('RADIUS +', 'XR_LIGHT_RADIUS_UP'),
        )
    elif light.type == 'SPOT':
        controls = (
            ('CONE -', 'XR_LIGHT_CONE_DOWN'), ('CONE +', 'XR_LIGHT_CONE_UP'),
            ('SOFT -', 'XR_LIGHT_BLEND_DOWN'), ('SOFT +', 'XR_LIGHT_BLEND_UP'),
            ('RADIUS -', 'XR_LIGHT_RADIUS_DOWN'), ('RADIUS +', 'XR_LIGHT_RADIUS_UP'),
        )
    elif light.type == 'AREA':
        controls = (
            ('WIDTH -', 'XR_LIGHT_WIDTH_DOWN'), ('WIDTH +', 'XR_LIGHT_WIDTH_UP'),
            ('HEIGHT -', 'XR_LIGHT_HEIGHT_DOWN'), ('HEIGHT +', 'XR_LIGHT_HEIGHT_UP'),
            ('SQUARE', 'XR_LIGHT_SQUARE'), ('RECTANGLE', 'XR_LIGHT_RECTANGLE'),
        )
    else:
        controls = (
            ('ANGLE -', 'XR_LIGHT_ANGLE_DOWN'),
            ('ANGLE +', 'XR_LIGHT_ANGLE_UP'),
        )
    menus.PAGES[_SHAPE] = controls + (('BACK', 'BACK'),)
    session.menu.page = target
    session.status = 'EDIT {} / {}'.format(light.type, obj.name[:32])


def _open(session, context):
    session.menu.page = _HOME
    obj = context.view_layer.objects.active
    if obj and obj.type == 'LIGHT':
        _editable(context, obj)
        session._xr_light_target = (obj.name, obj.as_pointer(), obj.data.as_pointer())
        session.status = 'LIGHT SELECTED / ' + obj.name
    else:
        session._xr_light_target = None
        session.status = 'LIGHTS / CREATE OR SELECT A LIGHT IN HIERARCHY'


def _world_position(session, context):
    return native_curves_v080._world_position(session, context)


def _world_direction(session):
    ray = getattr(session, 'ray', None)
    if ray is None:
        raise ValueError('Aim the dominant controller at the scene')
    direction = Vector(ray[1])
    if direction.length < .5:
        raise ValueError('Controller aim pose is unavailable')
    return direction.normalized()


def _aim_matrix(obj, direction):
    before = obj.matrix_world
    loc, old_rot, scale = before.decompose()
    target = Vector((0, 0, -1)).rotation_difference(Vector(direction).normalized())
    # Preserve the native object's scale and world-space position.
    return Matrix.LocRotScale(loc, target, scale)


def _create(session, context, kind):
    if context.mode != 'OBJECT':
        raise ValueError('Switch to Object Mode to create a Light')
    if kind not in _KINDS:
        raise ValueError('Unknown native Blender Light type')
    location = _world_position(session, context)
    direction = _world_direction(session)
    data = bpy.data.lights.new('XR ' + kind.title() + ' Light', type=kind)
    obj = None
    try:
        obj = bpy.data.objects.new('XR ' + kind.title() + ' Light', data)
        context.scene.collection.objects.link(obj)
        obj.location = location
        obj.matrix_world = _aim_matrix(obj, direction)
        for selected in tuple(context.selected_objects):
            selected.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        session._xr_light_target = (obj.name, obj.as_pointer(), data.as_pointer())
        session.history.push(('XR_LIGHT_CREATE', obj.name, data.name, data,
                              tuple(obj.users_collection), obj.matrix_world.copy()))
        _page(session, context)
    except Exception:
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
        if data.users == 0:
            bpy.data.lights.remove(data)
        raise


def _mutate(session, context, action, world=None, direction=None):
    obj = _selection(session, context)
    data = obj.data
    before = _state(obj)
    try:
        if action == 'XR_LIGHT_MOVE':
            if world is None:
                raise ValueError('Aim the controller before moving a Light')
            matrix = obj.matrix_world.copy()
            matrix.translation = Vector(world)
            obj.matrix_world = matrix
        elif action == 'XR_LIGHT_AIM':
            if direction is None or Vector(direction).length < .5:
                raise ValueError('Aim the controller before rotating a Light')
            obj.matrix_world = _aim_matrix(obj, direction)
        elif action == 'XR_LIGHT_POWER_UP':
            data.energy = min(1000000.0, data.energy * 1.25 if data.energy > .01 else 100.0)
        elif action == 'XR_LIGHT_POWER_DOWN':
            data.energy = max(0.0, data.energy / 1.25)
        elif action == 'XR_LIGHT_COLOR_PICKER':
            data.color = tuple(float(v) for v in session.settings.object_color[:3])
        elif action.startswith('XR_LIGHT_COLOR_'):
            name = action.removeprefix('XR_LIGHT_COLOR_')
            if name not in _COLORS:
                raise ValueError('Unknown native Light colour')
            data.color = _COLORS[name]
        elif action.startswith('XR_LIGHT_PRESET_'):
            name = action.removeprefix('XR_LIGHT_PRESET_')
            if name not in _PRESET_COLORS:
                raise ValueError('Unknown Light preset')
            data.color = _PRESET_COLORS[name]
            factor = 0.008 if data.type == 'SUN' else 1.0
            data.energy = _PRESET_ENERGY[name] * factor
        elif action in {'XR_LIGHT_RADIUS_UP', 'XR_LIGHT_RADIUS_DOWN'}:
            if data.type not in {'POINT', 'SPOT'}:
                raise ValueError('Light radius applies to Point/Spot only')
            delta = .05 if action.endswith('UP') else -.05
            data.shadow_soft_size = max(.0, min(100.0, data.shadow_soft_size + delta))
        elif action in {'XR_LIGHT_CONE_UP', 'XR_LIGHT_CONE_DOWN'}:
            if data.type != 'SPOT':
                raise ValueError('Cone size applies to Spot Lights only')
            data.spot_size = max(.01, min(math.pi, data.spot_size +
                                  (.0872665 if action.endswith('UP') else -.0872665)))
        elif action in {'XR_LIGHT_BLEND_UP', 'XR_LIGHT_BLEND_DOWN'}:
            if data.type != 'SPOT':
                raise ValueError('Cone softness applies to Spot Lights only')
            data.spot_blend = max(0., min(1., data.spot_blend +
                                  (.05 if action.endswith('UP') else -.05)))
        elif action in {'XR_LIGHT_WIDTH_UP', 'XR_LIGHT_WIDTH_DOWN',
                        'XR_LIGHT_HEIGHT_UP', 'XR_LIGHT_HEIGHT_DOWN'}:
            if data.type != 'AREA':
                raise ValueError('Area size applies to Area Lights only')
            if 'HEIGHT' in action and data.shape not in {'RECTANGLE', 'ELLIPSE'}:
                raise ValueError('Choose Rectangle before changing Area Light height')
            attr = 'size_y' if 'HEIGHT' in action else 'size'
            current = float(getattr(data, attr))
            delta = .1 if action.endswith('UP') else -.1
            setattr(data, attr, max(.01, min(1000., current + delta)))
        elif action in {'XR_LIGHT_RECTANGLE', 'XR_LIGHT_SQUARE'}:
            if data.type != 'AREA':
                raise ValueError('Area shape applies to Area Lights only')
            data.shape = 'RECTANGLE' if action.endswith('RECTANGLE') else 'SQUARE'
        elif action in {'XR_LIGHT_ANGLE_UP', 'XR_LIGHT_ANGLE_DOWN'}:
            if data.type != 'SUN':
                raise ValueError('Angular size applies to Sun Lights only')
            data.angle = max(0.0, min(math.pi, data.angle +
                             (.0174533 if action.endswith('UP') else -.0174533)))
        else:
            raise ValueError('Unknown Light property')
    except Exception:
        _restore(obj, before)
        raise
    after = _state(obj)
    if _same(before, after):
        session.status = 'LIGHT UNCHANGED'
        return None
    entry = ('XR_LIGHT_EDIT', obj.name, obj.data.name, obj, obj.data, before, after)
    session.history.push(entry)
    session.status = action.replace('XR_LIGHT_', '').replace('_', ' ')
    return entry


def _arm(session, context, action):
    obj = _selection(session, context)
    if input_ownership_v080.owner(session) not in {'IDLE', 'RADIAL'}:
        raise ValueError('Finish the active XR edit before aiming a Light')
    session._xr_light_pending = (obj.name, obj.as_pointer(), action)
    session._xr_light_ready = False
    session._xr_light_was_visible = bool(session.menu.visible)
    session.menu.visible = False
    radial = getattr(session, 'radial', None)
    if radial is not None and radial.active:
        radial.reset(require_release=True)
    session.status = 'LIGHT / RELEASE, AIM, PRESS TRIGGER / OFFHAND CANCEL'


def _cancel_pending(session):
    if getattr(session, '_xr_light_pending', None) is not None:
        session._xr_light_pending = None
        session.menu.visible = bool(getattr(session, '_xr_light_was_visible', True))
        session._xr_light_release_required = True


def _input_sample(session, context):
    state = context.window_manager.xr_session_state
    if state is None or not bpy.types.XrSessionState.is_running(context):
        raise ValueError('XR tracking ended while aiming the Light')
    pose = Quaternion(state.controller_aim_rotation_get(context, session.dom))
    if pose.magnitude < .5:
        raise ValueError('Controller tracking lost while aiming the Light')
    if session.bridge is not None:
        sample = session.bridge.read()
        if sample is None:
            raise ValueError('Finger input lost while aiming the Light')
        pressed = float(sample[session.dom][0]) >= .6
        cancel = float(sample[session.off][0]) >= .6
    else:
        pressed = float(actions.read(context, 'trigger', session.dom)[0]) >= .6
        cancel = float(actions.read(context, 'trigger', session.off)[0]) >= .6
    origin = Vector(state.controller_aim_location_get(context, session.dom))
    direction = pose @ Vector((0, 0, -1))
    return pressed, cancel, origin, direction


def _capture_tick(session, context):
    try:
        pressed, cancel, origin, direction = _input_sample(session, context)
    except (ValueError, RuntimeError, AttributeError, IndexError, TypeError) as exc:
        _cancel_pending(session)
        session._xr_rearm_required = True
        session.status = str(exc).upper() + ' / RELEASE TO REARM'
        return
    if cancel and getattr(session, '_xr_light_ready', False):
        _cancel_pending(session)
        session.status = 'LIGHT AIM CANCELLED'
        return
    if not pressed:
        if getattr(session, '_xr_light_pending', None) and not cancel:
            session._xr_light_ready = True
        else:
            session._xr_light_release_required = False
        if getattr(session, 'trigger', None):
            session.trigger.update(0.0)
        return
    if not getattr(session, '_xr_light_pending', None) or not session._xr_light_ready:
        return
    name, pointer, action = session._xr_light_pending
    session.ray = (origin, direction)
    try:
        obj = _selection(session, context)
        if obj.name != name or obj.as_pointer() != pointer:
            raise ValueError('Light changed while aiming')
        entry = _mutate(session, context, action,
                        world=_world_position(session, context), direction=direction)
        session.status = 'LIGHT APPLIED' if entry else 'LIGHT UNCHANGED'
    except (ValueError, RuntimeError, ReferenceError) as exc:
        session.status = 'LIGHT CANCELLED / ' + str(exc).upper()[:45]
    finally:
        _cancel_pending(session)
        if getattr(session, 'trigger', None):
            session.trigger.update(1.0)


def _patch_history():
    if getattr(mesh.History, '_xr_native_light_history', False):
        return
    original_step, original_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == 'XR_LIGHT_EDIT':
            return
        if entry[0] == 'XR_LIGHT_CREATE':
            data = entry[3]
            try:
                if data.users == 0 and bpy.data.lights.get(data.name) == data:
                    bpy.data.lights.remove(data)
            except ReferenceError:
                pass
            return
        return original_release(entry)

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] not in {'XR_LIGHT_EDIT', 'XR_LIGHT_CREATE'}:
            return original_step(self, backwards)
        entry = source[-1]
        if bpy.context.mode != 'OBJECT':
            raise ValueError('Return to Object Mode to undo Light authoring')
        if entry[0] == 'XR_LIGHT_EDIT':
            _tag, name, data_name, identity, data, before, after = entry
            obj = bpy.data.objects.get(name)
            if (obj is None or obj != identity or obj.data != data or
                    obj.data.name != data_name):
                raise ValueError('Light identity changed outside XR history')
            _editable(bpy.context, obj)
            if not _same(_state(obj), after if backwards else before):
                raise ValueError('Light changed outside XR history')
            _restore(obj, before if backwards else after)
        else:
            _tag, name, data_name, data, collections, matrix = entry
            obj = bpy.data.objects.get(name)
            if backwards:
                if obj is None or obj.data != data or obj.type != 'LIGHT':
                    raise ValueError('Light was removed or replaced outside XR history')
                _editable(bpy.context, obj)
                bpy.data.objects.remove(obj, do_unlink=True)
            else:
                if obj is not None or bpy.data.lights.get(data_name) != data:
                    raise ValueError('Light object or datablock changed outside XR history')
                valid = [coll for coll in collections if (
                    coll == bpy.context.scene.collection or
                    bpy.data.collections.get(coll.name) == coll)]
                if not valid:
                    raise ValueError('Original Light collection was removed')
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
    mesh.History._xr_native_light_history = True


def install_pages():
    # Preserve existing six mesh primitives, native Curve and Back slots.
    if not any(action == 'XR_LIGHT_MENU' for _label, action in menus.PAGES['PRIMITIVES']):
        original = tuple(menus.PAGES['PRIMITIVES'])
        menus.PAGES['PRIMITIVES'] = original[:-1] + (
            ('LIGHTS', 'XR_LIGHT_MENU'), original[-1])
    menus.PAGES[_HOME] = (
        ('POINT', 'XR_LIGHT_NEW_POINT'), ('SPOT', 'XR_LIGHT_NEW_SPOT'),
        ('AREA', 'XR_LIGHT_NEW_AREA'), ('SUN', 'XR_LIGHT_NEW_SUN'),
        ('EDIT ACTIVE', 'XR_LIGHT_OPEN_ACTIVE'), ('BACK', 'BACK'),
    )
    menus.PAGES[_EDIT] = (
        ('MOVE', 'XR_LIGHT_MOVE'), ('AIM', 'XR_LIGHT_AIM'),
        ('ENERGY -', 'XR_LIGHT_POWER_DOWN'), ('ENERGY +', 'XR_LIGHT_POWER_UP'),
        ('COLOR', 'XR_LIGHT_COLOR_MENU'), ('SHAPE', 'XR_LIGHT_SHAPE_MENU'),
        ('PRESETS', 'XR_LIGHT_PRESET_MENU'), ('BACK', 'BACK'),
    )
    menus.PAGES[_COLOR] = (
        ('PICKER', 'XR_LIGHT_COLOR_PICKER'),
        ('WHITE', 'XR_LIGHT_COLOR_WHITE'), ('WARM', 'XR_LIGHT_COLOR_WARM'),
        ('COOL', 'XR_LIGHT_COLOR_COOL'), ('RED', 'XR_LIGHT_COLOR_RED'),
        ('GREEN', 'XR_LIGHT_COLOR_GREEN'), ('BLUE', 'XR_LIGHT_COLOR_BLUE'),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_SHAPE] = (('BACK', 'BACK'),)
    menus.PAGES[_PRESETS] = (
        ('CANDLE', 'XR_LIGHT_PRESET_CANDLE'),
        ('TORCH', 'XR_LIGHT_PRESET_TORCH'),
        ('MOON', 'XR_LIGHT_PRESET_MOON'),
        ('NEON', 'XR_LIGHT_PRESET_NEON'),
        ('HORROR', 'XR_LIGHT_PRESET_HORROR'), ('BACK', 'BACK'),
    )
    menus.TITLES.update({_HOME: 'NATIVE LIGHTS', _EDIT: 'EDIT LIGHT',
                         _COLOR: 'LIGHT COLOR', _SHAPE: 'LIGHT SIZE',
                         _PRESETS: 'LIGHT PRESETS'})
    v065.TOOLTIPS.update({
        'XR_LIGHT_MENU': ('Native Lighting', 'Create or edit Point, Spot, Area or Sun Lights'),
        'XR_LIGHT_MOVE': ('Move Light', 'Release, aim and trigger to reposition in scene'),
        'XR_LIGHT_AIM': ('Aim Light', 'Release, aim and trigger to orient the light local -Z axis'),
        'XR_LIGHT_COLOR_PICKER': ('Use Material Colour Picker',
                                  'Apply the current XR colour preview to this Light'),
        'XR_LIGHT_PRESET_MENU': ('Lighting Presets', 'Editable static presets; no animation added'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_native_lights_patched', False):
        return
    _patch_history()
    install_pages()
    previous_command, previous_tick, previous_cancel = (
        Runtime.command, Runtime.tick, Runtime.cancel_work)

    def cancel_work(self):
        _cancel_pending(self)
        return previous_cancel(self)

    def tick(self, context):
        if (getattr(self, '_xr_light_pending', None) is not None or
                getattr(self, '_xr_light_release_required', False)):
            _capture_tick(self, context)
            return
        return previous_tick(self, context)

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous_command(self, context, action)
        page = menu.page
        if action == 'XR_LIGHT_MENU':
            if input_ownership_v080.owner(self) not in {'IDLE', 'RADIAL'}:
                raise ValueError('Finish current XR interaction before editing lights')
            _open(self, context)
            return
        if action == 'BACK' and page in {_HOME, _EDIT, _COLOR, _SHAPE, _PRESETS}:
            if page == _HOME:
                menu.page = 'PRIMITIVES'
            elif page == _EDIT:
                menu.page = _HOME
            else:
                _page(self, context)
            return
        if page == _HOME:
            if action.startswith('XR_LIGHT_NEW_'):
                _create(self, context, action.removeprefix('XR_LIGHT_NEW_'))
                return
            if action == 'XR_LIGHT_OPEN_ACTIVE':
                obj = _editable(context)
                self._xr_light_target = (obj.name, obj.as_pointer(),
                                         obj.data.as_pointer())
                _page(self, context)
                return
        if page not in {_EDIT, _COLOR, _SHAPE, _PRESETS}:
            return previous_command(self, context, action)
        if action in {'XR_LIGHT_COLOR_MENU', 'XR_LIGHT_SHAPE_MENU',
                      'XR_LIGHT_PRESET_MENU'}:
            subpage = {'XR_LIGHT_COLOR_MENU': _COLOR,
                       'XR_LIGHT_SHAPE_MENU': _SHAPE,
                       'XR_LIGHT_PRESET_MENU': _PRESETS}[action]
            _page(self, context, subpage)
            return
        if action in _AIM:
            _arm(self, context, action)
            return
        if action.startswith('XR_LIGHT_'):
            _mutate(self, context, action)
            return
        return previous_command(self, context, action)

    Runtime.cancel_work = cancel_work
    Runtime.tick = tick
    Runtime.command = command
    Runtime._xr_native_lights_patched = True
