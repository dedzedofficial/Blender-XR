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


def controller_poses(state, context, hands):
    """Capture and validate all aim/grip poses before any gesture dispatch.

    Do not validate one sample then query a potentially different sample
    later in the same XR frame. Callers may use the returned immutable
    quaternion/location pairs for their own menu placement and ray.
    """
    from mathutils import Quaternion, Vector

    # Reject a misconfigured dominant/offhand pair before querying the XR
    # runtime. Otherwise one hand silently overwrites the other in the map,
    # and an editor may consume the same controller for both roles.
    hands = tuple(hands)
    if len(hands) != 2 or set(hands) != {0, 1}:
        raise ValueError('Expected two distinct tracked XR hands')
    poses = {}
    for hand in hands:
        aim_rotation = Quaternion(state.controller_aim_rotation_get(context, hand))
        aim_location = Vector(state.controller_aim_location_get(context, hand))
        grip_rotation = Quaternion(state.controller_grip_rotation_get(context, hand))
        grip_location = Vector(state.controller_grip_location_get(context, hand))
        validate_pose(aim_rotation, aim_location)
        validate_pose(grip_rotation, grip_location)
        # OpenXR quaternions should be unit length, but valid tracking packets
        # can contain rounding drift. Normalize the validated local copies so
        # rays and gesture deltas never inherit that scale error. Do not
        # normalize before validation: a zero or malformed pose is tracking
        # loss, not an identity rotation.
        aim_rotation.normalize()
        grip_rotation.normalize()
        poses[hand] = ((aim_rotation, aim_location),
                       (grip_rotation, grip_location))
    return poses


def viewer_frame(state):
    """Validate viewer placement before writing headset menu transforms."""
    from mathutils import Vector

    viewer = Vector(state.viewer_pose_location)
    if not valid_position(viewer):
        raise ValueError('XR viewer location is invalid')
    scale = float(getattr(state, 'viewer_scale', 1.0))
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError('XR viewer scale is invalid')
    return viewer, scale



def viewer_orientation(state):
    """Return a validated headset rotation for locomotion direction.

    A lost headset orientation must not feed non-finite values into the
    OpenXR navigation transform even if both controllers remain tracked.
    """
    from mathutils import Quaternion

    rotation = Quaternion(state.viewer_pose_rotation)
    if not valid_rotation(rotation):
        raise ValueError('XR viewer rotation is invalid')
    return rotation


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


STICK_REARM_THRESHOLD = 0.25


def neutral_rearm_frame(session, context, samples):
    """Require released buttons AND a centered radial stick before rearming.

    A controller that reconnects with its offhand stick deflected must not
    immediately open or select a radial wedge on the first resumed frame.
    SteamVR hand-bridge input does not provide the same native stick action;
    it is intentionally guarded by its validated trigger/grip packet only.
    An absent native stick is input loss, not a neutral sample.
    """
    if not neutral(samples):
        return False
    if (getattr(session, 'bridge', None) is not None or
            getattr(getattr(session, 'settings', None), 'menu_style', 'CLASSIC') != 'RADIAL'):
        return True
    snapshot = getattr(session, '_xr_validated_sticks', None)
    if snapshot is None or session.off >= len(snapshot):
        # This path is retained for older callers of advance_rearm only.
        # The shared frame preflight always captures sticks *before* rearm.
        stick = stick_axes(actions.read(context, 'stick', session.off))
    else:
        stick = stick_axes(snapshot[session.off])
    return max(abs(stick[0]), abs(stick[1])) < STICK_REARM_THRESHOLD


def advance_rearm(session, context, samples):
    """Advance one fully neutral frame; never dispatch on the release frame.

    Returns True only when the caller must suppress normal input handling.
    A malformed stick invalidates the entire frame and restarts the neutral
    count; it never produces an accidental selection.
    """
    if getattr(session, '_xr_rollback_blocked', False):
        session._xr_rearm_required = True
        session._xr_neutral_count = 0
        session.status = 'XR ROLLBACK BLOCKED / REVIEW SCENE / RESTART XR'
        return True
    if not getattr(session, '_xr_rearm_required', False):
        return False
    try:
        is_neutral = neutral_rearm_frame(session, context, samples)
    except (RuntimeError, TypeError, ValueError, IndexError, AttributeError, OverflowError):
        from . import input_ownership_v080
        input_ownership_v080.cancel_tracking_loss(session)
        session._xr_neutral_count = 0
        session.status = 'REARM INPUT LOST / RELEASE BOTH HANDS'
        return True
    if not is_neutral:
        session._xr_neutral_count = 0
        session.status = 'RELEASE TRIGGERS, GRIPS AND RADIAL STICK'
        return True
    session._xr_neutral_count = getattr(session, '_xr_neutral_count', 0) + 1
    if session._xr_neutral_count < NEUTRAL_FRAMES:
        session.status = 'CONTROLLERS NEUTRAL / STABILIZING'
        return True
    session._xr_neutral_count = 0
    session._xr_rearm_required = False
    # A snap-turn may have been armed before tracking disappeared. Reset its
    # edge state as well; the next non-neutral stick motion must be fresh.
    turning = getattr(session, 'turning', None)
    if turning is not None and hasattr(turning, 'armed'):
        turning.armed = True
    for field in ('trigger', 'off_trigger', 'grip', 'other_grip'):
        button = getattr(session, field, None)
        if button is not None:
            button.update(0.0)
    session.status = 'CONTROLS REARMED'
    return True

def preflight_controller_frame(session, context):
    """Shared fail-closed input router front end for legacy and XR authoring.

    Both the outer controller tick and the specialized Curve/Paint/Light/
    modifier handlers consume exactly one validated pose, control and native
    stick snapshot. No edit handler sees a partial frame or a synthesized
    button-release when OpenXR data is unavailable. The legacy dispatcher
    only runs after this ownership and neutral-rearm barrier accepts a frame.
    """
    import bpy
    from . import input_ownership_v080

    session._xr_validated_controls = None
    session._xr_validated_poses = None
    session._xr_validated_sticks = None
    # Failed Undo/cancel must not be converted into a harmless neutral
    # rearm on the next controller tick. Require a fresh XR runtime session.
    if getattr(session, '_xr_rollback_blocked', False):
        session._xr_rearm_required = True
        session.status = 'XR ROLLBACK BLOCKED / REVIEW SCENE / RESTART XR'
        return False
    try:
        state = context.window_manager.xr_session_state
        if state is None or not bpy.types.XrSessionState.is_running(context):
            input_ownership_v080.cancel_session_loss(session)
            return False
        poses = controller_poses(state, context, (session.dom, session.off))
        if input_ownership_v080.cancel_conflict(session):
            return False
        samples = controller_sample(context, getattr(session, 'bridge', None))
        sticks = None
        if getattr(session, 'bridge', None) is None:
            # Capture native sticks before neutral rearm. Re-reading a stick
            # after release could accept a frame inconsistent with the radial
            # menu or locomotion dispatch in this same controller tick.
            sticks = tuple(stick_axes(actions.read(context, 'stick', hand))
                           for hand in (0, 1))
        session._xr_validated_poses = poses
        session._xr_validated_controls = samples
        session._xr_validated_sticks = sticks
        session.hand_controls = samples
        if advance_rearm(session, context, samples):
            return False
        return True
    except (RuntimeError, TypeError, ValueError, IndexError, AttributeError,
            OverflowError, ReferenceError) as exc:
        input_ownership_v080.cancel_tracking_loss(session)
        session.status = ('XR FRAME INVALID / EDIT CANCELLED / ' +
                          str(exc).upper()[:30] + ' / RELEASE CONTROLS')
        return False


def guard_specialized_frame(session, context):
    """Apply the same complete snapshot barrier to intercepting XR editors."""
    return preflight_controller_frame(session, context)
