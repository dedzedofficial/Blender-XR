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
    if getattr(getattr(session, 'radial', None), 'active', False):
        return 'RADIAL'
    if getattr(session, '_weight_stroke', None) is not None:
        return 'WEIGHT_STROKE'
    if getattr(session, '_xr_gesture', None) is not None:
        return 'DIRECT_TRANSFORM'
    if getattr(session, 'transaction', None) is not None:
        return 'MESH_EDIT'
    if getattr(session, 'two_hand_scale', None) is not None:
        return 'TWO_HAND_SCALE'
    if getattr(session, 'axis_move', None) is not None:
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
