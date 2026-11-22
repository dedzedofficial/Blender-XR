# SPDX-License-Identifier: GPL-3.0-or-later
"""Validated OpenXR controller snapshots and safe rearm thresholds.

An absent action, malformed bridge packet or non-finite controller value is
NOT a released trigger: treating it as zero may commit an unfinished mesh
edit/transform. The runtime's input owner handles failures as tracking loss
and waits for two complete neutral samples before accepting new gestures.
This module performs validation only, with no Blender data side effects.
"""
import math

from . import actions

REARM_THRESHOLD = 0.25
NEUTRAL_FRAMES = 2


def _floats(values, expected, label):
    try:
        result = tuple(float(value) for value in values)
    except (TypeError, ValueError, OverflowError):
        raise ValueError('Invalid {} sample'.format(label)) from None
    if len(result) != expected or not all(math.isfinite(x) for x in result):
        raise ValueError('Missing or non-finite {} sample'.format(label))
    return result


def valid_rotation(quaternion):
    """Reject missing/zero, non-finite or implausibly scaled tracked poses."""
    try:
        values = _floats(quaternion, 4, 'controller rotation')
    except ValueError:
        return False
    magnitude = math.sqrt(sum(value * value for value in values))
    return math.isfinite(magnitude) and 0.5 <= magnitude <= 1.5


def valid_position(position):
    try:
        _floats(position, 3, 'controller position')
    except ValueError:
        return False
    return True


def validate_pose(rotation, position):
    if not valid_rotation(rotation) or not valid_position(position):
        raise ValueError('Controller tracking pose is missing or invalid')


def control_value(value):
    """Normalize a trigger or grip with a small hardware rounding tolerance."""
    (number,) = _floats((value,), 1, 'trigger/grip')
    if number < -0.05 or number > 1.05:
        raise ValueError('Controller trigger/grip is outside expected range')
    return max(0.0, min(1.0, number))


def stick_axes(values):
    x, y = _floats(values, 2, 'thumbstick')
    if max(abs(x), abs(y)) > 1.2:
        raise ValueError('Controller thumbstick is outside expected range')
    return max(-1.0, min(1.0, x)), max(-1.0, min(1.0, y))


def controller_sample(context, bridge=None):
    """Read one full, validated two-handed trigger/grip snapshot.

    Bridge and native OpenXR have the same normalized shape. No unavailable
    action is converted to a button release. The caller must cancel/rearm
    rather than dispatching the ordinary XR input handlers on failure.
    """
    if bridge is not None:
        sample = bridge.read()
        if sample is None:
            raise ValueError('Hand bridge has no current controller sample')
    else:
        sample = tuple((
            actions.read(context, 'trigger', hand)[0],
            actions.read(context, 'grab', hand)[0],
        ) for hand in (0, 1))
    try:
        if len(sample) != 2 or any(len(pair) != 2 for pair in sample):
            raise ValueError('Expected two complete controller samples')
    except TypeError:
        raise ValueError('Controller sample is incomplete') from None
    return tuple(tuple(control_value(value) for value in pair) for pair in sample)


def neutral(sample):
    return all(value < REARM_THRESHOLD for hand in sample for value in hand)


def guard_specialized_frame(session, context):
    """Preflight editing wrappers that intercept tick before the radial router.

    Live modifier preview, Curve point placement, Light aiming and texture
    painting take exclusive ownership and never enter input_v080.tick until
    they are finished. Apply the same pose/control/rearm guarantees here,
    rather than letting their own held-button readers interpret bad data as
    a release. Returns False when the caller must not process this frame.
    """
    import bpy
    from mathutils import Quaternion, Vector
    from . import input_ownership_v080

    session._xr_validated_controls = None
    state = context.window_manager.xr_session_state
    try:
        if state is None or not bpy.types.XrSessionState.is_running(context):
            input_ownership_v080.cancel_session_loss(session)
            return False
        for hand in (session.dom, session.off):
            validate_pose(
                Quaternion(state.controller_aim_rotation_get(context, hand)),
                Vector(state.controller_aim_location_get(context, hand)))
            validate_pose(
                Quaternion(state.controller_grip_rotation_get(context, hand)),
                Vector(state.controller_grip_location_get(context, hand)))
        if input_ownership_v080.cancel_conflict(session):
            return False
        samples = controller_sample(context, getattr(session, 'bridge', None))
    except (RuntimeError, TypeError, ValueError, IndexError, AttributeError,
            OverflowError, ReferenceError):
        input_ownership_v080.cancel_tracking_loss(session)
        session.status = 'XR INPUT LOST / EDIT CANCELLED / RELEASE HANDS'
        return False
    session._xr_validated_controls = samples
    if getattr(session, '_xr_rearm_required', False):
        if not neutral(samples):
            session._xr_neutral_count = 0
            session.status = 'RELEASE TRIGGERS AND GRIPS TO REARM'
            return False
        session._xr_neutral_count = getattr(session, '_xr_neutral_count', 0) + 1
        if session._xr_neutral_count < NEUTRAL_FRAMES:
            session.status = 'CONTROLLERS NEUTRAL / STABILIZING'
            return False
        session._xr_neutral_count = 0
        session._xr_rearm_required = False
        for field in ('trigger', 'off_trigger', 'grip', 'other_grip'):
            button = getattr(session, field, None)
            if button is not None:
                button.update(0.0)
        session.status = 'CONTROLS REARMED'
        return False
    return True
