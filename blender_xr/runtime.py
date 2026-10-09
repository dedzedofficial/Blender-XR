# SPDX-License-Identifier: GPL-3.0-or-later
import math
import time
import bpy
from mathutils import Matrix, Vector, Quaternion
from . import actions, drawing, mesh, gestures, primitives, project, gizmo

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


def flight_delta(rotation, stick, lift, dt, speed, scale, fly=True):
    if not fly:
        delta = stick_delta(rotation, stick, dt, speed, scale)
        velocity = delta / max(min(max(dt, 0), 0.1) * speed * scale, 1e-9)
    else:
        amount = Vector(stick)
        magnitude = amount.length
        amount = (amount / magnitude * (min(magnitude, 1)-0.15)/0.85
                  if magnitude > 0.15 else Vector((0,0)))
        velocity = rotation @ Vector((amount.x,0,-amount.y))
    vertical = (math.copysign((min(abs(lift),1)-0.15)/0.85, lift)
                if abs(lift)>0.15 else 0)
    velocity.z += vertical
    if velocity.length > 1:
        velocity.normalize()
    return velocity * min(max(dt,0),0.1) * speed * scale


class Turning:
    def __init__(self):
        self.armed = True

    def angle(self, value, dt, mode, snap, speed):
        if abs(value) < 0.3:
            self.armed = True
        if mode == 'SMOOTH':
            return (-math.copysign((min(abs(value),1)-0.2)/0.8,value)*speed*min(max(dt,0),0.1)
                    if abs(value)>0.2 else 0)
        if self.armed and abs(value)>0.65:
            self.armed = False
            return -math.copysign(snap,value)
        return 0


def turn_view(state, angle, base_origin, pivot=None):
    turn = Quaternion(Vector((0,0,1)), math.radians(angle))
    offset = Vector(state.navigation_location)
    relative = Vector(state.viewer_pose_location if pivot is None else pivot) - Vector(base_origin) - offset
    state.navigation_location = offset + relative - turn @ relative
    state.navigation_rotation = turn @ Quaternion(state.navigation_rotation)


def matrix_changed(first, second, epsilon=1e-8):
    return any(abs(first[row][column]-second[row][column]) > epsilon
               for row in range(4) for column in range(4))


def uniform_scaled(matrix, factor):
    """Uniformly scale an object's local basis while keeping its world origin fixed."""
    result = matrix.copy()
    for row in range(3):
        for column in range(3):
            result[row][column] = matrix[row][column] * factor
    result.translation = matrix.translation
    return result


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
        self.axis_move = None
        self.axis_drag = None
        self.gizmo = None
        self.gizmo_hover = None
        self.air_grab = None
        self.other_grip = Button()
        self.turning = Turning()
        self.base_origin = Vector(context.scene.cursor.location)
        self.target = None
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
        if self.axis_move:
            obj,before,*_ = self.axis_move
            try:obj.matrix_world=before
            except ReferenceError:pass
            self.axis_move=None
        self.axis_drag=None
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
        if action == 'SAVE':
            if self.transaction or self.grab or self.air_grab or self.axis_move:
                raise ValueError('Finish or cancel the current operation before saving')
            path = project.save(context, self.history)
            self.status = 'SAVED ' + path.name.upper()
            self.settings.status = 'Saved: ' + str(path)
            return
        if action == 'ADD_MENU':
            self.menu.page = 'PRIMITIVES'
            self.status = 'CHOOSE A SHAPE'
            return
        if action == 'EDIT_MENU':
            self.menu.page = 'EDIT'
            return
        if action == 'DELETE_FACES':
            if self.transaction or self.grab or self.axis_move or self.air_grab:
                raise ValueError('Finish or cancel the current operation before deleting faces')
            self.history.push(mesh.delete_selected(context.view_layer.objects.active))
            self.status = 'FACES DELETED / UNDO TO RESTORE'
            return
        if action == 'BACK':
            self.menu.page = 'TOOLS'
            return
        if action == 'NAV_MENU':
            self.menu.page = 'TRAVEL'
            return
        if action in {'FASTER','SLOWER'}:
            self.settings.move_speed = max(0.1,min(1000,self.settings.move_speed*(2 if action=='FASTER' else .5)))
            self.status = 'SPEED ' + format(self.settings.move_speed,'.1f')
            return
        if action == 'FLY_TOGGLE':
            self.settings.fly_mode = not self.settings.fly_mode
            return
        if action == 'TURBO':
            self.settings.fast_flight = not self.settings.fast_flight
            return
        if action == 'TURN_TOGGLE':
            self.settings.turn_mode = 'SMOOTH' if self.settings.turn_mode=='SNAP' else 'SNAP'
            self.turning.armed = False
            return
        if action.startswith('ADD_') and action[4:] in primitives.KINDS:
            self.pending_primitive = action[4:]
            self.menu.page = 'TOOLS'
            self.tool = 'PLACE'
            self.status = 'PLACE ' + self.pending_primitive
            return
        if action in {'SELECT','EXTRUDE','BEVEL','INSET','MOVE','SCALE','MOVE_FACE','SCALE_FACE'}:
            obj=context.view_layer.objects.active
            if action in {'MOVE_FACE','SCALE_FACE'} and (not obj or obj.type!='MESH' or obj.mode!='EDIT'):
                raise ValueError('Enter FACE MODE before using face transforms')
            if action in {'MOVE','SCALE'} and obj and obj.mode=='EDIT':
                raise ValueError('Use OBJECT MODE before transforming the whole object')
            self.pending_primitive = None
            self.spawn_preview = None
            self.tool = action
            self.status = action.replace('_',' ') + ' READY'
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
                self.menu.page = 'EDIT'
                self.status = 'FACE EDIT MODE'
            else:
                bpy.ops.object.mode_set(mode='OBJECT')
                self.tool = 'MOVE'
                self.menu.page = 'TOOLS'
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
        if self.transaction or self.grab or self.air_grab or self.axis_move:
            raise ValueError('Finish or cancel the current operation before switching meshes')
        obj = context.view_layer.objects.active
        editing = bool(obj and obj.mode == 'EDIT')
        hit = self.object_hit(context, origin, direction)
        face = mesh.face_hit(obj, origin, direction) if editing else None
        face_tools={'SELECT','MOVE_FACE','SCALE_FACE'}
        if editing and self.tool in face_tools and face:
            # Keep face editing when the current cage is the closest hit.
            if not hit or hit[0] == obj or (face[1]-origin).length <= (hit[1]-origin).length:
                mesh.select_face(obj, face[0], additive)
                self.pointer = face[1]
                self.status = 'FACE SELECTED / ' + self.tool.replace('_',' ')
                return
        if not hit:
            self.status = 'POINT AT A MESH'
            return
        target, point = hit
        keep_edit = editing and self.tool in face_tools
        if keep_edit:
            # Validate before leaving the old mesh so a refused target does not
            # disturb the user's active mesh or editing mode.
            mesh.check_editable(target)
        if editing:
            bpy.ops.object.mode_set(mode='OBJECT')
        for selected in context.selected_objects:
            selected.select_set(False)
        target.select_set(True)
        context.view_layer.objects.active = target
        self.pointer = point
        if keep_edit:
            bpy.ops.object.mode_set(mode='EDIT')
            context.tool_settings.mesh_select_mode = (False,False,True)
            picked = mesh.face_hit(target, origin, direction)
            if picked:
                mesh.select_face(target, picked[0])
        self.status = 'SELECTED ' + target.name.upper()

    def begin_tool(self, context, origin, rotation):
        obj = context.view_layer.objects.active
        bm = mesh.editable(obj)
        selected = [f for f in bm.faces if f.select and not f.hide]
        if not selected:
            raise ValueError('Use SELECT FACE to pick a face first')
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

    def begin_axis(self,context,origin,direction,handle):
        name,axis=handle
        obj=context.view_layer.objects.active
        anchor=self.gizmo.anchor.copy()
        value=gizmo.parameter(origin,direction,anchor,axis)
        if value is None:raise ValueError('Aim across the handle to drag it')
        if obj.mode=='OBJECT' and self.tool in {'MOVE','SCALE'}:
            if obj.library or obj.parent or obj.constraints:
                raise ValueError('Object transforms require a local unparented object without constraints')
            self.axis_move=(obj,obj.matrix_world.copy(),self.tool)
            local_axis=None
            factor=(1/max(self.gizmo.length,1e-6) if self.tool=='SCALE' else 1)
        else:
            if obj.mode!='EDIT' or self.tool not in {'MOVE_FACE','SCALE_FACE','EXTRUDE','BEVEL','INSET'}:
                raise ValueError('This handle is not available in the current mode')
            if self.tool=='SCALE_FACE':
                factor=1/max(self.gizmo.length,1e-6)
                local_axis=None
            else:
                local=obj.matrix_world.inverted().to_3x3()@axis
                factor=local.length
                if factor<1e-9:raise ValueError('Object scale must be non-zero')
                local_axis=local.normalized()
            self.transaction=mesh.Transaction(obj,self.tool)
            self.start_step=0.0 if self.tool in {'MOVE_FACE','SCALE_FACE'} else self.settings.step
            self.last_amount=None
        self.axis_drag=(anchor,axis.copy(),value[0],factor,local_axis,name)
        self.status='DRAG '+name+' / RELEASE TO APPLY'

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
        viewer = Vector(state.viewer_pose_location)
        scale = state.viewer_scale if hasattr(state,'viewer_scale') else 1.0
        self.menu.position(hand, viewer, scale)
        self.ray = (origin, direction)
        self.hover, self.pointer = self.menu.hit(origin, direction)
        if not self.transaction and not self.axis_move:
            self.gizmo=gizmo.make(context,self.tool,scale,viewer)
        self.gizmo_hover=(self.gizmo.pick(origin,direction)
                          if self.gizmo and not self.hover else None)
        self.target = None
        if not self.hover:
            target_hit = self.object_hit(context,origin,direction)
            if target_hit:
                self.target, self.pointer = target_hit
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
                if touch_events[self.dom] and (self.transaction or self.grab or self.axis_move):
                    self.cancel_work()
                    return
                if touch_events[self.off]:
                    if self.transaction or self.grab or self.axis_move:
                        self.cancel_work()
                        return
                    self.menu.visible = not self.menu.visible
        press, release = self.trigger.update(trigger_value)
        off_press, _ = self.off_trigger.update(off_value)
        grab_press, grab_release = self.grip.update(grab_value)
        other_grab_press, _ = self.other_grip.update(other_grab_value)
        obj = context.view_layer.objects.active
        if off_press:
            if self.transaction or self.grab or self.air_grab or self.axis_move:
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
            axis=None
            if self.axis_drag:
                anchor,world_axis,start,factor,axis,name=self.axis_drag
                value=gizmo.parameter(origin,direction,anchor,world_axis)
                amount=(self.start_step+(value[0]-start)*factor if value is not None
                        else self.last_amount if self.last_amount is not None else self.start_step)
            else:
                delta = obj.matrix_world.inverted().to_3x3() @ (origin-self.start_pos)
                amount = self.start_step + delta.dot(self.local_axis)
            if self.tool in {'BEVEL','INSET'}:
                amount = max(0, amount)
            elif self.tool == 'SCALE_FACE':
                amount = max(-0.98, amount)
            amount = max(-10, min(10, amount))
            if self.last_amount is None or abs(amount-self.last_amount)>0.00005:
                self.transaction.preview(amount, self.settings.bevel_segments,axis)
                self.last_amount = amount
            self.status = self.tool.replace('_',' ') + ' ' + format(amount,'.4f')
            if release:
                transaction, self.transaction = self.transaction, None
                self.history.push(transaction.finish())
                self.axis_drag=None
                self.status = 'APPLIED'
            return
        if self.axis_move:
            target,before,mode=self.axis_move
            if context.view_layer.objects.active!=target or target.mode!='OBJECT':
                self.cancel_work()
                raise ValueError('Active object changed; transform cancelled')
            anchor,axis,start,factor,_,name=self.axis_drag
            value=gizmo.parameter(origin,direction,anchor,axis)
            if value is not None:
                delta=value[0]-start
                if mode=='MOVE':
                    result=before.copy()
                    result.translation=before.translation+axis*delta
                else:
                    result=uniform_scaled(before,max(0.02,1+delta*factor))
                target.matrix_world=result
            if release:
                if matrix_changed(target.matrix_world,before):
                    self.history.push(('OBJECT',target.name,None,before,target.matrix_world.copy()))
                self.axis_move=None;self.axis_drag=None
                self.status='OBJECT '+('MOVED' if mode=='MOVE' else 'SCALED')
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
            elif self.gizmo_hover:
                self.begin_axis(context,origin,direction,self.gizmo_hover)
            elif self.tool in {'SELECT','MOVE','SCALE','MOVE_FACE','SCALE_FACE'}:
                self.select(context,origin,direction,additive=self.grip.down)
            elif self.tool == 'PLACE':
                self.spawn(context)
            else:
                self.begin_tool(context,origin,pose)
        if self.transaction or self.axis_move:
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
        right = (0,0) if self.bridge else actions.read(context,'stick',1)
        boosted = self.settings.fast_flight or (not self.bridge and actions.boost(context))
        delta = flight_delta(Quaternion(state.viewer_pose_rotation),stick,right[1],dt,
                             self.settings.move_speed*(4 if boosted else 1),scale,
                             self.settings.fly_mode)
        if delta.length:
            state.navigation_location = Vector(state.navigation_location) + delta
        angle = self.turning.angle(right[0],dt,self.settings.turn_mode,
                                   self.settings.turn_angle,self.settings.turn_speed)
        if angle:
            # Include this tick's translation in the pivot to keep the head fixed.
            pivot = Vector(state.viewer_pose_location) + delta
            turn_view(state,angle,self.base_origin,pivot)
