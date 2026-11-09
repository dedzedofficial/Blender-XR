# SPDX-License-Identifier: GPL-3.0-or-later
"""v0.8 alpha controller snapshot and non-dominant radial capture.

When a radial menu is active this wrapper does NOT dispatch the legacy XR
tick: locomotion, turning, picking and editing cannot run underneath the menu.
"""
from mathutils import Vector, Quaternion
from . import actions, radial_logic_v080, input_ownership_v080


def patch_runtime(Runtime):
    if getattr(Runtime, '_v080_radial_patched', False):
        return
    old_init = Runtime.__init__
    old_tick = Runtime.tick
    old_configure = Runtime.configure

    def init(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        self.radial = radial_logic_v080.RadialState()
        self.hand_controls = ((0., 0.), (0., 0.))
        self.radial_supported = True

    def configure(self):
        old_configure(self)
        if getattr(self.settings, 'hand_display', 'CONTROLLERS') in {'HANDS', 'POINTERS'}:
            xr = self.context.window_manager.xr_session_settings
            if hasattr(xr, 'show_controllers'):
                xr.show_controllers = False

    def tick(self, context):
        state = context.window_manager.xr_session_state
        try:
            running = (state is not None and
                       __import__('bpy').types.XrSessionState.is_running(context))
        except (TypeError, RuntimeError, ValueError):
            # Blender's older regression tests intentionally provide a
            # lightweight simulated context, not a native bpy.Context.
            return old_tick(self, context)
        if not running:
            if hasattr(self, 'radial'):
                self.radial.reset()
            if getattr(self, '_weight_stroke', None) is not None:
                self.cancel_work()
            return old_tick(self, context)

        # Tracking-loss rearm: after a lost pose, do not act upon a still-held
        # trigger/grip when the controller comes back into range.
        try:
            dom_pose = Quaternion(state.controller_aim_rotation_get(context, self.dom))
            off_pose = Quaternion(state.controller_grip_rotation_get(context, self.off))
            if dom_pose.magnitude < .5 or off_pose.magnitude < .5:
                if not getattr(self, '_xr_rearm_required', False):
                    self.cancel_work()
                self._xr_rearm_required = True
                self.radial.reset(require_release=True)
                self.status = 'TRACKING LOST / RELEASE ALL CONTROLS'
                return
        except (RuntimeError, TypeError, ValueError):
            self.cancel_work()
            self._xr_rearm_required = True
            self.status = 'TRACKING LOST / RELEASE ALL CONTROLS'
            return
        if getattr(self, '_xr_rearm_required', False):
            try:
                if self.bridge is None:
                    values = [actions.read(context, control, hand)[0]
                              for hand in (0, 1) for control in ('trigger', 'grab')]
                else:
                    sample = self.bridge.read()
                    values = ([v for pair in sample for v in pair]
                              if sample is not None else [1.0])
                if any(float(v) >= .25 for v in values):
                    self.status = 'RELEASE TRIGGER AND GRIP TO REARM'
                    return
            except (RuntimeError, TypeError, ValueError, IndexError):
                self.status = 'WAITING FOR CONTROLLER INPUT'
                return
            self._xr_rearm_required = False
            self.trigger.update(0.0)
            self.off_trigger.update(0.0)
            self.grip.update(0.0)
            self.other_grip.update(0.0)
            self.status = 'CONTROLS REARMED'
        # Collect one consistent, visual controller sample. Menu acquisition
        # uses the exact same physical offhand index as the trigger.
        if self.bridge:
            self.hand_controls = ((0., 0.), (0., 0.))
        else:
            try:
                values = tuple((float(actions.read(context, 'trigger', h)[0]),
                                float(actions.read(context, 'grab', h)[0]))
                               for h in (0, 1))
                self.hand_controls = values
            except (ValueError, RuntimeError, IndexError, TypeError):
                self.hand_controls = ((0., 0.), (0., 0.))

        if (getattr(self.settings, 'menu_style', 'CLASSIC') != 'RADIAL'
                or self.bridge is not None):
            self.radial_supported = self.bridge is None
            if self.radial.active:
                self.radial.reset()
            return old_tick(self, context)

        # A single shared rule now owns arbitration for radial capture,
        # recovery guards and the in-headset input diagnostic.
        blocked = input_ownership_v080.owner(self) != 'IDLE'
        try:
            off_pose = Quaternion(state.controller_grip_rotation_get(context, self.off))
            off_position = Vector(state.controller_grip_location_get(context, self.off))
            if off_pose.magnitude < .5:
                if self.radial.active:
                    self.radial.reset(require_release=True)
                    self.status = 'RADIAL CANCELLED / TRACKING LOST'
                    return
                return old_tick(self, context)
            off_held = bool(actions.read(context, 'trigger', self.off)[0] > .55)
            off_stick = tuple(float(v) for v in actions.read(context, 'stick', self.off))
            if len(off_stick) != 2:
                raise ValueError('No thumbstick axes available')
            self.radial_supported = True
        except (ValueError, RuntimeError, IndexError, TypeError):
            if self.radial.active:
                self.radial.reset(require_release=True)
                self.status = 'RADIAL CANCELLED / INPUT LOST'
                return
            self.radial_supported = False  # Restore the classic ray menu.
            return old_tick(self, context)

        capture = self.radial.active or (off_held and not blocked)
        if not capture:
            self.radial.update(False, (0., 0.), self.menu.buttons, self.menu.page)
            return old_tick(self, context)

        # Reuse the world-space menu's original offhand-facing placement, but
        # never let the dominant controller decide radial wedges.
        viewer = Vector(state.viewer_pose_location)
        scale = float(getattr(state, 'viewer_scale', 1.0))
        self.menu.position(off_position, viewer, scale)
        self.menu.visible = True
        self.ray = (
            Vector(state.controller_aim_location_get(context, self.dom)),
            Quaternion(state.controller_aim_rotation_get(context, self.dom))
            @ Vector((0., 0., -1.)))
        self.pointer = None
        self.hover = None
        self.target = None
        self.gizmo_hover = None
        self.gizmo = None
        # Keep the legacy Button edge detector synchronized so release does
        # not reopen the old menu, and suppress latent dominant trigger presses.
        self.off_trigger.update(1.0 if off_held else 0.0)
        try:
            self.trigger.update(self.hand_controls[self.dom][0])
        except (ValueError, RuntimeError, IndexError, TypeError):
            pass
        event = self.radial.update(off_held, off_stick, self.menu.buttons,
                                   self.menu.page)
        if event:
            kind, action = event
            if kind == 'open':
                self.status = 'RADIAL / OFFHAND STICK TO CHOOSE'
            elif kind == 'hover':
                self.status = ('RADIAL / ' + action.replace('_', ' ')) if action else 'RADIAL / CENTER TO CANCEL'
            elif kind == 'next':
                self.status = 'RADIAL / NEXT PAGE'
            elif kind in {'navigate', 'select'} and action:
                try:
                    self.command(context, action)
                except (ValueError, RuntimeError, TypeError, AttributeError) as exc:
                    self.status = 'RADIAL: ' + str(exc)[:68]
            elif kind == 'close':
                self.status = 'RADIAL CANCELLED'
        # No old_tick call: movement/turning, interactions and legacy menu
        # action dispatch are all suspended for this frame.
        return

    Runtime.__init__ = init
    Runtime.configure = configure
    Runtime.tick = tick
    Runtime._v080_radial_patched = True
