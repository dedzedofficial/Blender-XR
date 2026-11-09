# SPDX-License-Identifier: GPL-3.0-or-later
"""One inspectable gesture-owner arbitration rule for Mesh XR controls.

This central definition is shared by menu capture, checkpoint guards and
creator diagnostics. It is intentionally pure: existing mode handlers still
own their state transitions until the staged dispatcher migration is tested.
"""


def owner(session):
    """Return a single action owner or IDLE; no controller reads or mutation."""
    if session is None:
        return 'IDLE'
    if getattr(session, '_xr_rearm_required', False):
        return 'REARM'
    radial = bool(getattr(getattr(session, 'radial', None), 'active', False))
    active = set()
    fields = (
        ('_weight_stroke', 'WEIGHT_STROKE'),
        ('_xr_gesture', 'DIRECT_TRANSFORM'),
        ('transaction', 'MESH_EDIT'),
        ('two_hand_scale', 'TWO_HAND_SCALE'),
        ('axis_move', 'AXIS_TRANSFORM'),
        ('axis_drag', 'AXIS_TRANSFORM'),
        ('grab', 'OBJECT_GRAB'),
        ('air_grab', 'WORLD_NAVIGATION'),
        ('bone_drag', 'BONE_EDIT'),
    )
    for field, name in fields:
        if getattr(session, field, None) is not None:
            active.add(name)
    if radial:
        return 'CONFLICT' if active else 'RADIAL'
    # Two-hand scale deliberately upgrades an existing object grab. Likewise
    # axis_drag stores the parameter of axis_move, not a second gesture.
    if active == {'TWO_HAND_SCALE', 'OBJECT_GRAB'}:
        return 'TWO_HAND_SCALE'
    # Mesh preview may use the same axis parameter state as object movement.
    if active == {'MESH_EDIT', 'AXIS_TRANSFORM'}:
        return 'MESH_EDIT'
    if len(active) > 1:
        return 'CONFLICT'
    return next(iter(active)) if active else 'IDLE'


def cancel_conflict(session):
    """Roll back incompatible concurrent gestures before another XR tick.

    The legacy cancel_work chain restores mesh previews, object matrices,
    bone drags and recorded paint samples. Require neutral controls before
    accepting a new gesture so a still-held trigger cannot immediately
    restart the interrupted operation.
    """
    if owner(session) != 'CONFLICT':
        return False
    session.cancel_work()
    radial = getattr(session, 'radial', None)
    if radial is not None:
        radial.reset(require_release=True)
    session._xr_rearm_required = True
    session.status = 'INPUT CONFLICT / RELEASE BOTH HANDS TO REARM'
    return True


def is_editing(session):
    return owner(session) not in {'IDLE', 'RADIAL'}


def diagnostic(session):
    current = owner(session)
    return 'INPUT / ' + current.replace('_', ' ')


# Read-only status actions are safe even while another gesture owns input.
# Everything else, including SAVE, mode changes and Undo, must be exclusive.
_READ_ONLY_COMMANDS = frozenset({'FOCUS_STATS', 'FOCUS_INPUT'})


def validate_command(session, action):
    """Reject an action before any of the historical mode handlers can mutate.

    The offhand radial control is itself the owner while its wedge is active.
    Only commands explicitly tagged by that input source may pass the guard.
    Other callers must release the active edit/gesture first.
    """
    active = owner(session)
    if active == 'IDLE' or action in _READ_ONLY_COMMANDS:
        return
    if (active == 'RADIAL'
            and getattr(session, '_xr_command_source', None) == 'RADIAL'):
        return
    raise ValueError(
        'Release {} before {}'.format(
            active.replace('_', ' ').lower(), str(action).replace('_', ' ')))


def patch_runtime(Runtime):
    """Single outer action gate; keep tested Blender command handlers intact.

    This is the first central command-dispatch stage. Removing the legacy
    handlers requires a separate, headset-tested migration. Bare Runtime
    proxies in older Blender tests are supported as usual.
    """
    if getattr(Runtime, '_v080_command_guard_patched', False):
        return
    original_command = Runtime.command

    def command(self, context, action):
        # Nested, already-authorized mode actions must reach their existing
        # implementation without being treated as a second input gesture.
        if getattr(self, '_xr_command_depth', 0):
            return original_command(self, context, action)
        validate_command(self, action)
        self._xr_command_depth = 1
        try:
            return original_command(self, context, action)
        finally:
            self._xr_command_depth = 0

    Runtime.command = command
    Runtime._v080_command_guard_patched = True


def cancel_session_loss(session):
    """Roll back a held gesture when the OpenXR session stops unexpectedly.

    The legacy tick can stop before its tracking-loss branch is reached.
    This transition is idempotent: do not repeatedly cancel a released
    gesture, and require neutral controls if the session is restarted.
    """
    current = owner(session)
    if current in {'IDLE', 'REARM'}:
        return False
    session.cancel_work()
    radial = getattr(session, 'radial', None)
    if radial is not None:
        radial.reset(require_release=True)
    session._xr_rearm_required = True
    session.status = 'XR SESSION LOST / EDIT CANCELLED / RELEASE CONTROLS'
    return True
