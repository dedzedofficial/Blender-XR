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
        self._xr_validated_controls = None
        self._xr_validated_poses = None
        self._xr_validated_sticks = None
        self._xr_validated_viewer = None
        self._xr_validated_aux = None
        self._xr_motion_sample = None
        self._xr_rearm_pose = None
        self.radial_supported = True
        self._xr_neutral_count = 0
        # A fresh runtime instance is the only safe reset for a failed
        # native-data rollback. Reconnecting controllers alone is not.
        self._xr_rollback_blocked = False

    def configure(self):
        old_configure(self)
        if getattr(self.settings, 'hand_display', 'CONTROLLERS') in {'HANDS', 'POINTERS'}:
            xr = self.context.window_manager.xr_session_settings
            if hasattr(xr, 'show_controllers'):
                xr.show_controllers = False

    def tick(self, context):
        # This snapshot is valid for only the current outer XR frame. Legacy
        # handlers reuse it so a second read cannot invent a trigger release.
        self._xr_validated_controls = None
        self._xr_validated_poses = None
        self._xr_validated_sticks = None
        self._xr_validated_viewer = None
        self._xr_validated_aux = None
        if (getattr(self, '_xr_rollback_blocked', False) or
                getattr(getattr(self, 'history', None),
                        '_xr_mesh_rollback_blocked', False)):
            self._xr_rollback_blocked = True
            self._xr_rearm_required = True
            self.status = 'XR ROLLBACK BLOCKED / REVIEW SCENE / RESTART XR'
            return
        state = context.window_manager.xr_session_state
        import bpy
        if not isinstance(context, bpy.types.Context):
            # Preserve compatibility with lightweight non-Blender proxies.
            return old_tick(self, context)
        try:
            running = (state is not None and
                       bpy.types.XrSessionState.is_running(context))
        except (TypeError, RuntimeError, ValueError, AttributeError):
            input_ownership_v080.cancel_session_loss(self)
            return
        if not running:
            # A stopped session can bypass pose-loss handling entirely.
            # Roll back every live mutation, not just the paint brush.
            input_ownership_v080.cancel_session_loss(self)
            # Never forward a stopped OpenXR frame into the legacy tick.
            # That path can read stale button edges and accidentally commit
            # an interrupted transform as if the controller were released.
            self._xr_validated_controls = None
            return
        if (not getattr(self, 'navigation_initialized', False)
                and hasattr(self, 'initialize_navigation')):
            # The action set must be activated before querying trigger/grip
            # states. Activate once, then require two neutral frames; never
            # interpret startup-held buttons as a first edit or menu press.
            if not self.initialize_navigation(context, state):
                return
            self._xr_rearm_required = True
            self._xr_neutral_count = 0
            self.status = 'XR CONTROLLERS READY / RELEASE TRIGGERS AND GRIPS'
            return

        # The shared router preflight now owns pose, button, stick, conflict
        # and rearm validation for every controller frame. Specialized XR
        # editing wrappers call the same function before intercepting tick.
        if not input_safety_v086.preflight_controller_frame(self, context):
            return

        if (getattr(self.settings, 'menu_style', 'CLASSIC') != 'RADIAL'
                or self.bridge is not None):
            self.radial_supported = self.bridge is None
            if self.radial.active:
                self.radial.reset(require_release=True)
                self._xr_rearm_required = True
                self._xr_neutral_count = 0
                self._xr_rearm_pose = None
                input_ownership_v080.reset_touch_holds(self)
                self.status = 'MENU MODE CHANGED / RELEASE CONTROLS'
                return
            return old_tick(self, context)

        # A single shared rule now owns arbitration for radial capture,
        # recovery guards and the in-headset input diagnostic.
        blocked = input_ownership_v080.owner(self) != 'IDLE'
        try:
            off_pose, off_position = self._xr_validated_poses[self.off][1]
            off_held = self.hand_controls[self.off][0] > .55
            raw_stick = self._xr_validated_sticks[self.off]
        except (RuntimeError, ValueError, IndexError, TypeError, AttributeError):
            # A missing stick action is not a neutral stick. Do not silently
            # fall through to legacy interaction with partially read inputs.
            input_ownership_v080.cancel_tracking_loss(self)
            self.radial_supported = False
            self.status = ('XR ROLLBACK BLOCKED / REVIEW SCENE / RESTART XR'
                           if getattr(self, '_xr_rollback_blocked', False) else
                           'OFFHAND INPUT LOST / RELEASE CONTROLS')
            return
        try:
            off_stick = input_safety_v086.stick_axes(raw_stick)
        except ValueError:
            input_ownership_v080.cancel_tracking_loss(self)
            self.status = ('XR ROLLBACK BLOCKED / REVIEW SCENE / RESTART XR'
                           if getattr(self, '_xr_rollback_blocked', False) else
                           'INVALID THUMBSTICK / RELEASE CONTROLS')
            return
        self.radial_supported = True

        capture = self.radial.active or (off_held and not blocked)
        if not capture:
            self.radial.update(False, (0., 0.), self.menu.buttons, self.menu.page)
            return old_tick(self, context)

        # Reuse the world-space menu's original offhand-facing placement, but
        # never let the dominant controller decide radial wedges.
        try:
            viewer_snapshot = getattr(self, '_xr_validated_viewer', None)
            if viewer_snapshot is None:
                raise ValueError('Validated headset frame is missing')
            viewer, scale, _viewer_rotation = viewer_snapshot
        except (RuntimeError, TypeError, ValueError, OverflowError, AttributeError):
            input_ownership_v080.cancel_tracking_loss(self)
            self.status = ('XR ROLLBACK BLOCKED / REVIEW SCENE / RESTART XR'
                           if getattr(self, '_xr_rollback_blocked', False) else
                           'VIEWER TRACKING LOST / RELEASE CONTROLS')
            return
        self.menu.position(off_position, viewer, scale)
        self.menu.visible = True
        aim_rotation, aim_location = self._xr_validated_poses[self.dom][0]
        self.ray = (aim_location.copy(), aim_rotation @ Vector((0., 0., -1.)))
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
