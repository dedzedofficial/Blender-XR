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
    weight = getattr(session, '_weight_stroke', None) is not None
    # A menu must never share input with *any* active manipulation. Checking
    # only the paint brush missed object grabs, bone edits and mesh previews.
    # Keep the existing two-hand grab and axis-drag pairs valid below.
    editing = (weight or
               getattr(session, '_xr_gesture', None) is not None or
               getattr(session, 'transaction', None) is not None or
               getattr(session, 'two_hand_scale', None) is not None or
               getattr(session, 'axis_move', None) is not None or
               getattr(session, 'axis_drag', None) is not None or
               getattr(session, 'grab', None) is not None or
               getattr(session, 'air_grab', None) is not None or
               getattr(session, 'bone_drag', None) is not None)
    if radial:
        return 'CONFLICT' if editing else 'RADIAL'
    if weight:
        return 'WEIGHT_STROKE'
    if getattr(session, '_xr_gesture', None) is not None:
        return 'DIRECT_TRANSFORM'
    if getattr(session, 'transaction', None) is not None:
        return 'MESH_EDIT'
    if getattr(session, 'two_hand_scale', None) is not None:
        return 'TWO_HAND_SCALE'
    if getattr(session, 'axis_move', None) is not None:
        return 'AXIS_TRANSFORM'
    if getattr(session, 'axis_drag', None) is not None:
        return 'AXIS_TRANSFORM'
    if getattr(session, 'grab', None) is not None:
        return 'OBJECT_GRAB'
    if getattr(session, 'air_grab', None) is not None:
        return 'WORLD_NAVIGATION'
    if getattr(session, 'bone_drag', None) is not None:
        return 'BONE_EDIT'
    return 'IDLE'


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
