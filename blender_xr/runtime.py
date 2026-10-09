# SPDX-License-Identifier: GPL-3.0-or-later
import math
import time
import bpy
from mathutils import Matrix, Vector, Quaternion
from . import actions, drawing, mesh, gestures, primitives

CURRENT = None
PENDING = False
START_ERROR = ''


def timer_due(session, now=None):
    return (time.monotonic() if now is None else now) - session.last_tick >= 1/60


def stick_delta(rotation, stick, dt, speed, scale):
    """Camera-local -Z is forward; remove pitch without changing walking speed."""
    amount = Vector((stick[0], stick[1]))
    magnitude = amount.length
    if magnitude <= 0.15:
        return Vector()
    forward = rotation @ Vector((0, 0, -1))
    forward.z = 0
    if forward.length < 1e-6:
        # Stable direction even when looking straight down/up.
        right = rotation @ Vector((1, 0, 0))
        right.z = 0
        if right.length < 1e-6:
            return Vector()
        forward = Vector((0, 0, 1)).cross(right.normalized())
    forward.normalize()
    right = forward.cross(Vector((0, 0, 1)))
    strength = (min(magnitude, 1.0) - 0.15) / 0.85
    amount *= strength / magnitude
    return (right*amount.x + forward*amount.y) * min(max(dt, 0), 0.1) * speed * scale


def session_pre(*_args):
    global START_ERROR
    if PENDING or CURRENT is not None:
        try:
            actions.activate(bpy.context)
        except Exception as exc:
            START_ERROR = str(exc)


class Button:
    def __init__(self):
        self.down = False

    def update(self, value):
        old = self.down
        self.down = value > (0.35 if old else 0.60)
        return self.down and not old, old and not self.down


class Runtime:
    def __init__(self, context):
        self.context = context
        self.window = context.window
        self.area = context.area
        self.region = next(r for r in context.area.regions if r.type == 'WINDOW')
        self.settings = context.scene.blender_xr
        self.dom = 0 if self.settings.dominant_hand == 'LEFT' else 1
        self.off = 1-self.dom
        self.menu = drawing.Menu()
        self.history = mesh.History()
        self.tool = 'SELECT'
        self.status = 'SELECT A MESH'
        self.hover = None
        self.ray = None
        self.pointer = None
        self.transaction = None
        self.grab = None
        self.air_grab = None
        self.other_grip = Button()
        self.pending_primitive = None
        self.spawn_preview = None
        self.trigger = Button()
        self.off_trigger = Button()
        self.grip = Button()
        self.active = True
        self.started = time.monotonic()
        self.last_tick = self.started
        self.timer = None
        self.draw_handle = None
        self.saved_settings = {}
        self.request_stop = False
        self.error = ''
        self.last_amount = None
        self.navigation_initialized = False
        self.bridge = None
        self.touch_holds = [gestures.HoldGesture(), gestures.HoldGesture()]
        self.input_source = self.settings.input_source
        self.finger_touch = self.settings.finger_touch

    def configure(self):
        if self.input_source == 'STEAMVR_HANDS':
            self.bridge = gestures.HandBridge(self.settings.bridge_port)
        settings = self.context.window_manager.xr_session_settings
        values = dict(show_controllers=True, show_custom_overlays=True,
                      show_selection=True, use_positional_tracking=True,
                      clip_start=0.01, clip_end=1000.0,
                      base_pose_type='CUSTOM',
                      base_pose_location=tuple(self.context.scene.cursor.location),
                      base_pose_angle=0.0, base_scale=1.0)
        for name, value in values.items():
            if hasattr(settings, name):
                previous = getattr(settings, name)
                self.saved_settings[name] = previous.copy() if hasattr(previous, 'copy') else previous
                setattr(settings, name, value)
        self.draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            drawing.draw, (self,), 'XR', 'POST_VIEW')

    def cancel_work(self):
        self.air_grab = None
        if self.transaction:
            transaction, self.transaction = self.transaction, None
            try:
                transaction.cancel()
            except (ReferenceError, ValueError):
                transaction.dispose()
        if self.grab:
            obj, before, _ = self.grab
            try:
                obj.matrix_world = before
            except ReferenceError:
                pass
            self.grab = None
        self.status = 'CANCELLED'

    def cleanup(self, context):
        self.active = False
        if self.bridge:
            self.bridge.close()
            self.bridge = None
        self.cancel_work()
        if self.draw_handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self.draw_handle, 'XR')
            self.draw_handle = None
        if self.timer:
            context.window_manager.event_timer_remove(self.timer)
            self.timer = None
        self.history.clear()
        xr = context.window_manager.xr_session_settings
        for name, value in self.saved_settings.items():
            try:
                setattr(xr, name, value)
            except (ReferenceError, TypeError):
                pass
        self.saved_settings.clear()

    def command(self, context, action):
        if action == 'PANEL':
            return
        if action == 'ADD_MENU':
            self.menu.page = 'PRIMITIVES'
            self.status = 'CHOOSE A SHAPE'
            return
        if action == 'BACK':
            self.menu.page = 'TOOLS'
            return
        if action.startswith('ADD_') and action[4:] in primitives.KINDS:
            self.pending_primitive = action[4:]
            self.menu.page = 'TOOLS'
            self.tool = 'PLACE'
            self.status = 'PLACE ' + self.pending_primitive
            return
        if action in {'SELECT','EXTRUDE','BEVEL','INSET','MOVE'}:
            self.pending_primitive = None
            self.spawn_preview = None
            self.tool = action
            self.status = action + ' READY'
        elif action == 'MODE':
            obj = context.view_layer.objects.active
            if not obj or obj.type != 'MESH':
                raise ValueError('Select a mesh object')
            if obj.mode == 'OBJECT':
                if obj.library or obj.data.library or obj.data.users > 1 or obj.data.shape_keys:
                    raise ValueError('Use a local single-user mesh without shape keys')
                if any(o.mode == 'EDIT' for o in context.view_layer.objects):
                    raise ValueError('Leave other edit modes first')
                # Deselect other objects so mode_set cannot enter multi-object editing.
                for other in context.selected_objects:
                    if other != obj:
                        other.select_set(False)
                bpy.ops.object.mode_set(mode='EDIT')
                context.tool_settings.mesh_select_mode = (False, False, True)
                self.tool = 'SELECT'
                self.status = 'FACE EDIT MODE'
            else:
                bpy.ops.object.mode_set(mode='OBJECT')
                self.tool = 'MOVE'
                self.status = 'OBJECT MODE'
        elif action == 'LESS':
            self.settings.step = max(0.0001, self.settings.step/2)
        elif action == 'MORE':
            self.settings.step = min(10, self.settings.step*2)
        elif action in {'UNDO','REDO'}:
            self.status = action if self.history.step(action=='UNDO') else 'HISTORY EMPTY'
        elif action == 'RESET':
            context.window_manager.xr_session_state.navigation_location = (0, 0, 0)
            context.window_manager.xr_session_state.navigation_rotation = Quaternion()
            context.window_manager.xr_session_state.reset_to_base_pose(context)
            self.status = 'VIEW RESET'
        elif action == 'STOP':
            self.request_stop = True

    def object_hit(self, context, origin, direction):
        result = context.scene.ray_cast(context.evaluated_depsgraph_get(), origin, direction)
        if result[0]:
            obj = result[4].original
            if obj.type == 'MESH' and obj.visible_get(view_layer=context.view_layer):
                return obj, result[1]
        return None

    def placement(self, context, origin, direction, scale):
        size = self.settings.primitive_size * scale
        hit = context.scene.ray_cast(context.evaluated_depsgraph_get(), origin, direction)
        if hit[0]:
            offset = 0 if self.pending_primitive == 'PLANE' else size/2
            return hit[1] + hit[2]*offset, size
        return origin + direction * self.settings.placement_distance * scale, size

    def spawn(self, context):
        if self.spawn_preview is None or not self.pending_primitive:
            raise ValueError('Point away from the menu to place the shape')
        location, size = self.spawn_preview
        obj = primitives.add(context, self.pending_primitive, location, size)
        self.history.push(mesh.creation_entry(obj))
        self.pending_primitive = None
        self.spawn_preview = None
        self.tool = 'MOVE'
        self.status = 'ADDED ' + obj.name.upper()

    def move_air(self, state, hand_position, held):
        if not held:
            self.air_grab = None
            self.status = 'MOVE RELEASED'
            return
        # Poses include the current navigation offset. A fixed world anchor
        # avoids feeding our own previous offset back into the next frame.
        _, anchor = self.air_grab
        state.navigation_location = Vector(state.navigation_location) + anchor - hand_position
        self.status = 'GRAB AIR TO MOVE'

    def select(self, context, origin, direction, additive=False):
        obj = context.view_layer.objects.active
        if obj and obj.mode == 'EDIT':
            hit = mesh.face_hit(obj, origin, direction)
            if hit:
                mesh.select_face(obj, hit[0], additive)
                self.status = 'FACE SELECTED'
            else:
                self.status = 'POINT AT A FACE'
        else:
            hit = self.object_hit(context, origin, direction)
            if hit:
                obj, self.pointer = hit
                for selected in context.selected_objects:
                    selected.select_set(False)
                obj.select_set(True)
                context.view_layer.objects.active = obj
                self.status = 'MESH SELECTED'

    def begin_tool(self, context, origin, rotation):
        obj = context.view_layer.objects.active
        bm = mesh.editable(obj)
        selected = [f for f in bm.faces if f.select and not f.hide]
        if not selected:
            raise ValueError('Use SELECT to pick a face first')
        if self.tool == 'EXTRUDE':
            normal = sum((f.normal*f.calc_area() for f in selected), Vector())
            if normal.length < 1e-8:
                raise ValueError('Select faces with a common direction')
            self.local_axis = normal.normalized()
        else:
            self.local_axis = (obj.matrix_world.inverted().to_3x3() @
                               (rotation @ Vector((1,0,0)))).normalized()
        self.start_pos = origin.copy()
        self.start_step = self.settings.step
        self.transaction = mesh.Transaction(obj, self.tool)
        self.last_amount = None

    def tick(self, context):
        now = time.monotonic()
        dt = min(now-self.last_tick, 0.1)
        self.last_tick = now
        state = context.window_manager.xr_session_state
        if state is None or not bpy.types.XrSessionState.is_running(context):
            if now-self.started > 8:
                self.error = 'No VR session. Check the active OpenXR runtime and headset connection.'
                self.request_stop = True
            return
        if not self.navigation_initialized:
            if not state.active_action_set_set(context, actions.SET):
                self.error = 'Controller actions could not be activated'
                self.request_stop = True
                return
            state.navigation_location = (0, 0, 0)
            state.navigation_rotation = Quaternion()
            state.navigation_scale = 1.0
            self.navigation_initialized = True
        if START_ERROR:
            self.error = START_ERROR
            self.request_stop = True
            return
        pose = Quaternion(state.controller_aim_rotation_get(context, self.dom))
        off_pose = Quaternion(state.controller_grip_rotation_get(context, self.off))
        if pose.magnitude < 0.5 or off_pose.magnitude < 0.5:
            self.cancel_work()
            self.trigger = Button()
            self.off_trigger = Button()
            self.grip = Button()
            self.other_grip = Button()
            self.spawn_preview = None
            if self.bridge:
                self.bridge.armed = False
            self.status = 'WAITING FOR TRACKED HAND POSES'
            return
        origin = Vector(state.controller_aim_location_get(context, self.dom))
        direction = pose @ Vector((0,0,-1))
        hand = Vector(state.controller_grip_location_get(context, self.off))
        scale = state.viewer_scale if hasattr(state,'viewer_scale') else 1.0
        self.menu.position(hand, Vector(state.viewer_pose_location), scale)
        self.ray = (origin, direction)
        self.hover, self.pointer = self.menu.hit(origin, direction)
        if self.bridge:
            inputs = self.bridge.read()
            if inputs is None:
                self.cancel_work()
                self.trigger = Button()
                self.off_trigger = Button()
                self.grip = Button()
                self.other_grip = Button()
                self.spawn_preview = None
                self.status = 'WAITING FOR FINGERS / RELEASE BOTH HANDS'
                return
            trigger_value, grab_value = inputs[self.dom]
            off_value = inputs[self.off][0]
            other_grab_value = inputs[self.off][1]
        else:
            trigger_value = actions.read(context, 'trigger', self.dom)[0]
            grab_value = actions.read(context, 'grab', self.dom)[0]
            off_value = actions.read(context, 'trigger', self.off)[0]
            other_grab_value = actions.read(context, 'grab', self.off)[0]
            if self.finger_touch:
                # Holding both touch sensors fires once, until the fingers lift.
                touch_events = [self.touch_holds[i].update(actions.touch(context, i), now)
                                for i in range(2)]
                if touch_events[self.dom] and (self.transaction or self.grab):
                    self.cancel_work()
                    return
                if touch_events[self.off]:
                    if self.transaction or self.grab:
                        self.cancel_work()
                        return
                    self.menu.visible = not self.menu.visible
        press, release = self.trigger.update(trigger_value)
        off_press, _ = self.off_trigger.update(off_value)
        grab_press, grab_release = self.grip.update(grab_value)
        other_grab_press, _ = self.other_grip.update(other_grab_value)
        obj = context.view_layer.objects.active
        if off_press:
            if self.transaction or self.grab or self.air_grab:
                self.cancel_work()
                return
            self.menu.visible = not self.menu.visible
        if self.air_grab:
            index = self.air_grab[0]
            held = self.grip.down if index == self.dom else self.other_grip.down
            self.move_air(state, Vector(state.controller_grip_location_get(context, index)), held)
            return
        if self.transaction:
            if obj != self.transaction.obj or obj.mode != 'EDIT':
                self.cancel_work()
                raise ValueError('Active mesh changed; operation cancelled')
            delta = obj.matrix_world.inverted().to_3x3() @ (origin-self.start_pos)
            amount = self.start_step + delta.dot(self.local_axis)
            if self.tool != 'EXTRUDE':
                amount = max(0, amount)
            amount = max(-10, min(10, amount))
            if self.last_amount is None or abs(amount-self.last_amount)>0.00005:
                self.transaction.preview(amount, self.settings.bevel_segments)
                self.last_amount = amount
            self.status = self.tool + ' ' + format(amount,'.4f')
            if release:
                transaction, self.transaction = self.transaction, None
                self.history.push(transaction.finish())
                self.status = 'APPLIED'
            return
        grip_pos = Vector(state.controller_grip_location_get(context,self.dom))
        grip_rot = Quaternion(state.controller_grip_rotation_get(context,self.dom))
        grip_matrix = Matrix.LocRotScale(grip_pos,grip_rot,Vector((1,1,1)))
        if self.grab:
            target, before, inverse_start = self.grab
            target.matrix_world = grip_matrix @ inverse_start @ before
            if grab_release:
                self.history.push(('OBJECT',target.name,None,before,target.matrix_world.copy()))
                self.grab = None
                self.status = 'MOVED OBJECT'
            return
        self.spawn_preview = (self.placement(context, origin, direction, scale)
                              if self.pending_primitive and not self.hover else None)
        if press:
            if self.hover:
                self.command(context,self.hover)
            elif self.tool in {'SELECT','MOVE'}:
                self.select(context,origin,direction,additive=self.grip.down)
            elif self.tool == 'PLACE':
                self.spawn(context)
            else:
                self.begin_tool(context,origin,pose)
        if self.transaction:
            return
        for index, pressed in ((self.dom, grab_press), (self.off, other_grab_press)):
            if not pressed:
                continue
            aim_origin = Vector(state.controller_aim_location_get(context, index))
            aim_rotation = Quaternion(state.controller_aim_rotation_get(context, index))
            if aim_rotation.magnitude < 0.5:
                continue
            aim_direction = aim_rotation @ Vector((0,0,-1))
            if self.menu.hit(aim_origin, aim_direction)[0]:
                continue
            hit = self.object_hit(context, aim_origin, aim_direction)
            if hit is None and self.settings.grab_air:
                self.air_grab = (index, Vector(state.controller_grip_location_get(context, index)))
                self.status = 'GRAB AIR TO MOVE'
                return
            if index == self.dom and self.tool == 'MOVE' and hit:
                target = hit[0]
                if context.mode != 'OBJECT':
                    raise ValueError('Use MODE to enter object mode')
                if target.library or target.parent or target.constraints:
                    raise ValueError('Movement requires a local unparented object without constraints')
                for selected in context.selected_objects:
                    selected.select_set(False)
                target.select_set(True)
                context.view_layer.objects.active = target
                self.grab = (target,target.matrix_world.copy(),grip_matrix.inverted())
                self.status = 'GRAB OBJECT'
                return
        # Always the physical LEFT stick, independent of dominant-hand choice.
        stick = (0, 0) if self.bridge else actions.read(context,'stick',0)
        delta = stick_delta(Quaternion(state.viewer_pose_rotation), stick, dt,
                            self.settings.move_speed, scale)
        if delta.length:
            state.navigation_location = Vector(state.navigation_location) + delta
