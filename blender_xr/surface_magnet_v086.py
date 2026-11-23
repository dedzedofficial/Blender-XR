# SPDX-License-Identifier: GPL-3.0-or-later
"""VR surface magnet for native Blender objects (no helper meshes/constraints).

Choose a placement action, release the controller buttons, aim at a different
visible mesh surface and press the dominant Trigger. Only the active object
matrix is changed, with one guarded Mesh XR Undo/Redo entry.
"""
import math

import bpy
from mathutils import Matrix, Vector

from . import input_ownership_v080, input_safety_v086, menus, mesh, v065

_PAGE = 'XR_SURFACE_MAGNET_086'
_ACTIONS = frozenset({'XR_SURFACE_PLACE', 'XR_SURFACE_ALIGN'})


def _finite(value):
    return all(math.isfinite(float(component)) for component in value)


def _object(context):
    obj = context.view_layer.objects.active
    if (context.mode != 'OBJECT' or obj is None or obj.mode != 'OBJECT'
            or obj.type not in {'MESH', 'CURVE', 'EMPTY', 'FONT', 'ARMATURE'}):
        raise ValueError('Select a native object in Object Mode to place')
    if (obj.library or obj.override_library or
            (obj.data is not None and
             (obj.data.library or obj.data.override_library)) or
            obj.parent is not None or obj.constraints):
        raise ValueError('Surface magnet requires a local unparented, unconstrained object')
    if obj.hide_select or obj.hide_get() or not obj.visible_get():
        raise ValueError('Unlock and reveal the object before placing')
    if abs(obj.matrix_world.determinant()) < 1e-10:
        raise ValueError('Surface placement requires nonzero object scale')
    return obj


def _same(left, right):
    return all(abs(float(left[i][j]) - float(right[i][j])) <= 1e-5
               for i in range(4) for j in range(4))


def _hit(context, moving, origin, direction):
    """Raycast evaluated meshes individually to omit the active object safely.

    No visibility flags are temporarily changed. World-space distance
    comparison remains valid when target objects have different transforms.
    """
    direction = Vector(direction)
    origin = Vector(origin)
    if not _finite(origin) or not _finite(direction) or direction.length_squared < 1e-10:
        raise ValueError('Valid controller aim is required')
    direction.normalize()
    graph = context.evaluated_depsgraph_get()
    best = None
    for candidate in context.view_layer.objects:
        if (candidate == moving or candidate.type != 'MESH' or
                candidate.hide_get() or not candidate.visible_get()):
            continue
        matrix = candidate.matrix_world
        if abs(matrix.determinant()) < 1e-10:
            continue
        inv = matrix.inverted_safe()
        local_origin = inv @ origin
        local_direction = inv.to_3x3() @ direction
        if local_direction.length_squared < 1e-12:
            continue
        try:
            evaluated = candidate.evaluated_get(graph)
            found, local_hit, local_normal, _face_index = evaluated.ray_cast(
                local_origin, local_direction.normalized())
        except (RuntimeError, ValueError, ReferenceError, TypeError):
            continue
        if not found:
            continue
        point = matrix @ local_hit
        along = (point - origin).dot(direction)
        if not math.isfinite(along) or along <= 0.0 or along > 100.0:
            continue
        if (point - (origin + along * direction)).length > .03:
            continue
        normal = inv.to_3x3().transposed() @ local_normal
        if normal.length_squared < 1e-12 or not _finite(normal):
            continue
        normal.normalize()
        if best is None or along < best[0]:
            best = (along, point, normal, candidate.name)
    return best


def _plan(before, point, normal, offset, align):
    result = before.copy()
    position = Vector(point) + Vector(normal) * offset
    if align:
        current_up = before.to_quaternion() @ Vector((0.0, 0.0, 1.0))
        rotation = current_up.rotation_difference(Vector(normal))
        result = (Matrix.Translation(position) @ rotation.to_matrix().to_4x4() @
                  Matrix.Translation(-before.translation) @ before)
    else:
        result.translation = position
    if not all(_finite(row) for row in result):
        raise ValueError('Surface magnet produced an invalid transform')
    return result


def _cancel(session):
    if getattr(session, '_xr_surface_pending', None) is None:
        return
    session._xr_surface_pending = None
    session._xr_surface_ready = False
    session.menu.visible = bool(getattr(session, '_xr_surface_menu_visible', True))
    session._xr_surface_release_required = True


def _arm(session, context, action):
    obj = _object(context)
    if input_ownership_v080.owner(session) not in {'IDLE', 'RADIAL'}:
        raise ValueError('Release the active XR gesture before placing an object')
    session._xr_surface_pending = (obj.name, obj.as_pointer(), obj,
                                   obj.matrix_world.copy(),
                                   action == 'XR_SURFACE_ALIGN')
    session._xr_surface_ready = False
    session._xr_surface_menu_visible = bool(session.menu.visible)
    session.menu.visible = False
    radial = getattr(session, 'radial', None)
    if radial is not None and getattr(radial, 'active', False):
        radial.reset(require_release=True)
    session.status = 'SURFACE MAGNET / RELEASE, AIM, TRIGGER / OFFHAND CANCEL'


def _place(session, context, origin, direction):
    name, ptr, identity, before, align = session._xr_surface_pending
    obj = _object(context)
    if (obj.name != name or obj.as_pointer() != ptr or obj != identity or
            not _same(obj.matrix_world, before)):
        raise ValueError('Object changed since Surface Magnet was armed')
    result = _hit(context, obj, origin, direction)
    if result is None:
        raise ValueError('Aim at a different visible mesh surface')
    _distance, point, normal, surface = result
    offset = float(getattr(session, '_xr_surface_offset', .02))
    if not math.isfinite(offset) or not 0.0 <= offset <= 2.0:
        raise ValueError('Invalid Surface Magnet offset')
    after = _plan(before, point, normal, offset, align)
    if _same(before, after):
        session.status = 'SURFACE MAGNET / ALREADY ALIGNED'
        return False
    history = getattr(session, 'history', None)
    if history is None:
        raise ValueError('Surface Magnet requires XR history')
    obj.matrix_world = after
    try:
        context.view_layer.update()
        history.push(('XR_SURFACE_PLACE_086', name, obj.data.name if obj.data
                      else None, identity, ptr, before, after,
                      context.scene.name))
    except Exception:
        if _same(obj.matrix_world, after):
            obj.matrix_world = before
            context.view_layer.update()
        raise
    session.status = 'SURFACE MAGNET / ' + surface.upper()[:24] + (
        ' / ALIGNED' if align else ' / PLACED')
    return True


def _capture_tick(session, context):
    if not input_safety_v086.guard_specialized_frame(session, context):
        return
    samples = session._xr_validated_controls
    held = samples[session.dom][0] >= .6
    cancel = samples[session.off][0] >= .6
    if getattr(session, '_xr_surface_pending', None) is None:
        if not held and not cancel:
            session._xr_surface_release_required = False
            session.trigger.update(0.0)
        return
    if cancel:
        _cancel(session)
        session.status = 'SURFACE PLACEMENT CANCELLED'
        return
    if not held:
        session._xr_surface_ready = True
        session.trigger.update(0.0)
        return
    if not getattr(session, '_xr_surface_ready', False):
        return
    try:
        rotation, location = session._xr_validated_poses[session.dom][0]
        direction = rotation @ Vector((0.0, 0.0, -1.0))
        _place(session, context, location, direction)
    except (ValueError, RuntimeError, ReferenceError, TypeError, AttributeError) as exc:
        session.status = 'SURFACE MAGNET / ' + str(exc).upper()[:55]
    finally:
        _cancel(session)
        session.trigger.update(1.0)


def _history():
    if getattr(mesh.History, '_xr_surface_magnet_history', False):
        return
    previous_step = mesh.History.step
    previous_release = mesh.History.release

    def release(entry):
        if entry[0] == 'XR_SURFACE_PLACE_086':
            return
        return previous_release(entry)

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] != 'XR_SURFACE_PLACE_086':
            return previous_step(self, backwards)
        _kind, name, data_name, original, pointer, before, after, scene_name = source[-1]
        obj = bpy.data.objects.get(name)
        if (bpy.context.mode != 'OBJECT' or bpy.context.scene.name != scene_name or
                obj is None or obj != original or obj.as_pointer() != pointer or
                obj.mode != 'OBJECT' or obj.hide_select or obj.library or
                obj.parent is not None or obj.constraints or
                (obj.data.name if obj.data else None) != data_name):
            raise ValueError('Surface Magnet object changed outside XR history')
        expected = after if backwards else before
        if not _same(obj.matrix_world, expected):
            raise ValueError('Surface Magnet matrix changed outside XR history')
        obj.matrix_world = (before if backwards else after).copy()
        bpy.context.view_layer.update()
        dest.append(source.pop())
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_surface_magnet_history = True


def install_pages():
    parent = tuple(menus.PAGES['LAYOUT_MENU'])
    if not any(action == 'XR_SURFACE_MENU' for _label, action in parent):
        if parent[-1][1] != 'BACK' or len(parent) >= 12:
            raise ValueError('No room for Surface Magnet in Object Layout menu')
        menus.PAGES['LAYOUT_MENU'] = parent[:-1] + (
            ('SURFACE', 'XR_SURFACE_MENU'), parent[-1])
    menus.PAGES[_PAGE] = (
        ('PLACE', 'XR_SURFACE_PLACE'),
        ('ALIGN Z', 'XR_SURFACE_ALIGN'),
        ('OFFSET -', 'XR_SURFACE_OFFSET_DOWN'),
        ('OFFSET +', 'XR_SURFACE_OFFSET_UP'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'SURFACE MAGNET'
    v065.TOOLTIPS.update({
        'XR_SURFACE_MENU': ('Surface Magnet', 'Place a native object on another visible mesh surface'),
        'XR_SURFACE_PLACE': ('Place Object', 'Move object origin to the controller-hit surface and offset'),
        'XR_SURFACE_ALIGN': ('Align Z and Place', 'Align local object Z to the surface normal and place'),
        'XR_SURFACE_OFFSET_DOWN': ('Offset Down', 'Decrease surface clearance by 2.5 centimetres'),
        'XR_SURFACE_OFFSET_UP': ('Offset Up', 'Increase surface clearance by 2.5 centimetres'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_surface_magnet_086_patched', False):
        return
    _history()
    install_pages()
    previous_tick = Runtime.tick
    previous_command = Runtime.command
    previous_cancel = Runtime.cancel_work

    def cancel_work(self):
        _cancel(self)
        return previous_cancel(self)

    def tick(self, context):
        if (getattr(self, '_xr_surface_pending', None) is not None or
                getattr(self, '_xr_surface_release_required', False)):
            return _capture_tick(self, context)
        return previous_tick(self, context)

    def command(self, context, action):
        if getattr(self, 'menu', None) is None:
            return previous_command(self, context, action)
        if action == 'XR_SURFACE_MENU':
            _object(context)
            if input_ownership_v080.owner(self) not in {'IDLE', 'RADIAL'}:
                raise ValueError('Release XR gestures before Surface Magnet')
            self.menu.page = _PAGE
            self.status = 'SURFACE MAGNET / SELECT PLACE OR ALIGN'
            return
        if self.menu.page == _PAGE:
            if action == 'BACK':
                self.menu.page = 'LAYOUT_MENU'
                return
            if action in _ACTIONS:
                return _arm(self, context, action)
            if action in {'XR_SURFACE_OFFSET_DOWN', 'XR_SURFACE_OFFSET_UP'}:
                value = float(getattr(self, '_xr_surface_offset', .02))
                amount = -.025 if action.endswith('DOWN') else .025
                self._xr_surface_offset = max(0.0, min(2.0, round(value + amount, 4)))
                self.status = 'SURFACE OFFSET / {:.3f} M'.format(self._xr_surface_offset)
                return
            raise ValueError('Surface Magnet menu action unavailable')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime.tick = tick
    Runtime.cancel_work = cancel_work
    Runtime._xr_surface_magnet_086_patched = True
