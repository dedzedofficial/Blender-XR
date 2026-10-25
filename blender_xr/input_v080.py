# SPDX-License-Identifier: GPL-3.0-or-later
"""v0.8 alpha controller snapshot and non-dominant radial capture.

When a radial menu is active this wrapper does NOT dispatch the legacy XR
tick: locomotion, turning, picking and editing cannot run underneath the menu.
"""
from mathutils import Vector, Quaternion
from . import actions, radial_logic_v080


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
        self._radial_captured = False

    def configure(self):
        old_configure(self)
        if getattr(self.settings, 'hand_display', 'CONTROLLERS') == 'HANDS':
            xr = self.context.window_manager.xr_session_settings
            if hasattr(xr, 'show_controllers'):
                xr.show_controllers = False

    def tick(self, context):
        state = context.window_manager.xr_session_state
        running = (state is not None and
                   __import__('bpy').types.XrSessionState.is_running(context))
        if not running:
            self.radial.reset()
            return old_tick(self, context)

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
            if self.radial.active:
                self.radial.reset()
            return old_tick(self, context)

        blocked = any((self.transaction, self.grab, self.axis_move,
                       self.air_grab, self.two_hand_scale,
                       getattr(self, '_xr_gesture', None)))
        try:
            off_pose = Quaternion(state.controller_grip_rotation_get(context, self.off))
            off_position = Vector(state.controller_grip_location_get(context, self.off))
            if off_pose.magnitude < .5:
                if self.radial.active:
                    self.radial.reset()
                    self.status = 'RADIAL CANCELLED / TRACKING LOST'
                    return
                return old_tick(self, context)
            off_held = bool(actions.read(context, 'trigger', self.off)[0] > .55)
            off_stick = tuple(float(v) for v in actions.read(context, 'stick', self.off))
            if len(off_stick) != 2:
                raise ValueError('No thumbstick axes available')
        except (ValueError, RuntimeError, IndexError, TypeError):
            if self.radial.active:
                self.radial.reset()
                self.status = 'RADIAL CANCELLED / INPUT LOST'
                return
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
