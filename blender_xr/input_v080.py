# SPDX-License-Identifier: GPL-3.0-or-later
"""v0.8 alpha controller snapshot and non-dominant radial capture.

When a radial menu is active this wrapper does NOT dispatch the legacy XR
tick: locomotion, turning, picking and editing cannot run underneath the menu.
"""
from mathutils import Vector, Quaternion
from . import actions, radial_logic_v080, input_ownership_v080, input_safety_v086


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
        self._xr_neutral_count = 0

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
            # A stopped session can bypass pose-loss handling entirely.
            # Roll back every live mutation, not just the paint brush.
            cancelled = input_ownership_v080.cancel_session_loss(self)
            if hasattr(self, 'radial') and not cancelled:
                self.radial.reset(require_release=True)
            return old_tick(self, context)

        # Validate both hands before allowing *any* legacy handler to process
        # a movement, trigger release, radial selection or transform finish.
        # A NaN rotation (or position) is NOT a valid tracked pose.
        try:
            for hand in (self.dom, self.off):
                input_safety_v086.validate_pose(
                    Quaternion(state.controller_aim_rotation_get(context, hand)),
                    Vector(state.controller_aim_location_get(context, hand)))
                input_safety_v086.validate_pose(
                    Quaternion(state.controller_grip_rotation_get(context, hand)),
                    Vector(state.controller_grip_location_get(context, hand)))
        except (RuntimeError, TypeError, ValueError, AttributeError, OverflowError):
            input_ownership_v080.cancel_tracking_loss(self)
            return
        # The pure owner diagnostic is also a runtime safety invariant:
        # overlapping legacy handlers must be rolled back before either
        # receives another sample, never merely reported as CONFLICT.
        if input_ownership_v080.cancel_conflict(self):
            return
        # Invalid or missing inputs are never silently mapped to (0, 0).
        # Zero would masquerade as a trigger release and could commit a
        # partially completed mesh edit or direct object transform.
        try:
            self.hand_controls = input_safety_v086.controller_sample(
                context, getattr(self, 'bridge', None))
        except (RuntimeError, TypeError, ValueError, IndexError, AttributeError):
            input_ownership_v080.cancel_tracking_loss(self)
            self.status = 'CONTROLLER SAMPLE LOST / RELEASE BOTH HANDS'
            return
        if getattr(self, '_xr_rearm_required', False):
            if not input_safety_v086.neutral(self.hand_controls):
                self._xr_neutral_count = 0
                self.status = 'RELEASE TRIGGER AND GRIP TO REARM'
                return
            self._xr_neutral_count = getattr(self, '_xr_neutral_count', 0) + 1
            if self._xr_neutral_count < input_safety_v086.NEUTRAL_FRAMES:
                self.status = 'CONTROLLERS NEUTRAL / STABILIZING'
                return
            self._xr_neutral_count = 0
            self._xr_rearm_required = False
            self.trigger.update(0.0)
            self.off_trigger.update(0.0)
            self.grip.update(0.0)
            self.other_grip.update(0.0)
            self.status = 'CONTROLS REARMED'
            # No action is dispatched on the rearm frame: it is a barrier
            # between interrupted edits and subsequent fresh presses.
            return

        if (getattr(self.settings, 'menu_style', 'CLASSIC') != 'RADIAL'
                or self.bridge is not None):
            self.radial_supported = self.bridge is None
            if self.radial.active:
                self.radial.reset(require_release=True)
                self._xr_rearm_required = True
                self._xr_neutral_count = 0
                self.status = 'MENU MODE CHANGED / RELEASE CONTROLS'
                return
            return old_tick(self, context)

        # A single shared rule now owns arbitration for radial capture,
        # recovery guards and the in-headset input diagnostic.
        blocked = input_ownership_v080.owner(self) != 'IDLE'
        try:
            off_pose = Quaternion(state.controller_grip_rotation_get(context, self.off))
            off_position = Vector(state.controller_grip_location_get(context, self.off))
            if off_pose.magnitude < .5:
                if self.radial.active:
                    input_ownership_v080.cancel_tracking_loss(self)
                    self.status = 'RADIAL CANCELLED / TRACKING LOST / RELEASE CONTROLS'
                    return
                return old_tick(self, context)
            off_held = self.hand_controls[self.off][0] > .55
            raw_stick = actions.read(context, 'stick', self.off)
        except (RuntimeError, IndexError, TypeError, AttributeError):
            if self.radial.active:
                input_ownership_v080.cancel_tracking_loss(self)
                self.status = 'RADIAL CANCELLED / INPUT LOST / RELEASE CONTROLS'
                return
            # Missing thumbstick action: retain the original classic menu.
            self.radial_supported = False
            return old_tick(self, context)
        try:
            off_stick = input_safety_v086.stick_axes(raw_stick)
        except ValueError:
            input_ownership_v080.cancel_tracking_loss(self)
            self.status = 'INVALID THUMBSTICK / RELEASE CONTROLS'
            return
        self.radial_supported = True

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
                # Only the radial selection event is allowed to issue a
                # command while RADIAL owns the controllers. The shared
                # command guard rejects unrelated callers and active edits.
                self._xr_command_source = 'RADIAL'
                try:
                    try:
                        self.command(context, action)
                    except (ValueError, RuntimeError, TypeError, AttributeError) as exc:
                        self.status = 'RADIAL: ' + str(exc)[:68]
                finally:
                    self._xr_command_source = None
            elif kind == 'close':
                self.status = 'RADIAL CANCELLED'
        # No old_tick call: movement/turning, interactions and legacy menu
        # action dispatch are all suspended for this frame.
        return

    Runtime.__init__ = init
    Runtime.configure = configure
    Runtime.tick = tick
    Runtime._v080_radial_patched = True
