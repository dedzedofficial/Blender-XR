# SPDX-License-Identifier: GPL-3.0-or-later
"""Validated OpenXR controller snapshots and safe rearm thresholds.

An absent action, malformed bridge packet or non-finite controller value is
NOT a released trigger: treating it as zero may commit an unfinished mesh
edit/transform. The runtime's input owner handles failures as tracking loss
and waits for two complete neutral samples before accepting new gestures.
This module performs validation only, with no Blender data side effects.
"""
import math
import time

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
    if not math.isfinite(scale) or not 1e-6 <= scale <= 1e6:
        raise ValueError('XR viewer scale is invalid or unsafe')
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
    # A small OpenXR quaternion norm drift must never scale locomotion or
    # ray orientation. Validate before normalising; zero/invalid is loss.
    rotation.normalize()
    return rotation


def headset_frame(state):
    """Capture a complete, finite viewer frame once per controller preflight.

    Specialized editors, legacy navigation and radial menus consume the same
    validated viewer location/scale/rotation instead of mixing later HMD reads
    with the controller snapshot already accepted by the input router.
    """
    viewer, scale = viewer_frame(state)
    orientation = viewer_orientation(state)
    return viewer, scale, orientation


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


def optional_controller_sample(session, context):
    """Capture optional touch/menu and boost actions in the controller frame.

    Unavailable optional bindings intentionally remain inactive, as they did
    with the original action helpers. Never turn a missing optional action
    into a trigger/grip release or query a second time after dispatch starts.
    """
    if getattr(session, 'bridge', None) is not None:
        return ((False, False), False)
    touches = ((bool(actions.touch(context, 0)),
                bool(actions.touch(context, 1)))
               if getattr(session, 'finger_touch', False) else (False, False))
    return touches, bool(actions.boost(context))


def neutral(sample):
    return all(value < REARM_THRESHOLD for hand in sample for value in hand)


STICK_REARM_THRESHOLD = 0.25

# A Blender stall or an OpenXR re-localisation must not be mistaken for a
# normal continuous controller motion while a geometry edit is in progress.
# The thresholds are deliberately permissive of fast real hand movements.
MAX_EDIT_SAMPLE_GAP = 0.5
MIN_TRACKING_JUMP = 1.25
MAX_TRACKED_HAND_SPEED = 7.0
# Room-scale controllers should stay near the tracked headset. These bounds
# are intentionally generous: reject clearly corrupted or mismatched spaces,
# not an artist reaching across a room or moving their head independently.
MAX_HEAD_RELATIVE_REACH = 12.0
MAX_AIM_GRIP_SEPARATION = 2.0


def _head_relative_pose(poses, viewer):
    """Use HMD-local metres to ignore world navigation and snap turns.

    Comparing scene-space coordinates alone would incorrectly reject ordinary
    room locomotion or a VR snap turn. Both aim and grip positions are checked
    so an aim-ray tracking teleport cannot be hidden behind a steady grip.
    """
    position, scale, rotation = viewer
    inverse = rotation.inverted()
    relative = {}
    for hand, (aim, grip) in poses.items():
        local = []
        for _orientation, location in (aim, grip):
            point = inverse @ (location - position) / scale
            if not all(math.isfinite(float(v)) for v in point):
                raise ValueError('Invalid HMD-relative controller pose')
            local.append(tuple(float(v) for v in point))
        # Both poses describe the *same* physical controller. Even when
        # individual coordinates are finite, a lost tracking origin or a
        # mixed action-space packet can place aim and grip metres apart.
        # Reject the whole frame before the ray or mesh editor sees it.
        if any(sum(component * component for component in point) >
               MAX_HEAD_RELATIVE_REACH ** 2 for point in local):
            raise ValueError('XR controller is outside plausible headset reach')
        if sum((a - b) ** 2 for a, b in zip(local[0], local[1])) > (
                MAX_AIM_GRIP_SEPARATION ** 2):
            raise ValueError('XR controller aim/grip tracking spaces disagree')
        relative[hand] = tuple(local)
    return relative


def _head_relative_rotations(poses, viewer):
    """Return HMD-relative aim/grip quaternion components for both hands."""
    inverse = viewer[2].inverted()
    result = {}
    for hand, (aim, grip) in poses.items():
        orientations = []
        for rotation, _point in (aim, grip):
            relative = inverse @ rotation
            relative.normalize()
            components = tuple(float(value) for value in relative)
            if len(components) != 4 or not all(math.isfinite(v) for v in components):
                raise ValueError('Invalid HMD-relative controller rotation')
            orientations.append(components)
        result[hand] = tuple(orientations)
    return result


def _angular_difference_degrees(first, second):
    """Quaternion sign is irrelevant: q and -q describe the same rotation."""
    dot = abs(sum(a * b for a, b in zip(first, second)))
    return math.degrees(2.0 * math.acos(max(0.0, min(1.0, dot))))


def enforce_edit_pose_continuity(session, poses, viewer):
    """Reject tracking jumps/gaps during live XR gestures before dispatch.

    The saved sample is per runtime, never a Blender datablock. Normal frames
    advance the baseline, while tracking/session cancellation destroys it.
    Idle artists may reposition their tracking origin without an edit failing.
    """
    from . import input_ownership_v080

    now = time.monotonic()
    relative = _head_relative_pose(poses, viewer)
    rotations = _head_relative_rotations(poses, viewer)
    previous = getattr(session, '_xr_motion_sample', None)
    live_owner = input_ownership_v080._gesture_owner(
        session, honor_rearm=False)
    if previous is not None and live_owner not in {'IDLE'}:
        old_time, old_positions = previous[:2]
        old_rotations = previous[2] if len(previous) > 2 else None
        dt = now - old_time
        if not math.isfinite(dt) or dt < 0 or dt > MAX_EDIT_SAMPLE_GAP:
            raise ValueError('XR input gap during live gesture')
        max_distance = max(MIN_TRACKING_JUMP, MAX_TRACKED_HAND_SPEED * dt)
        for hand, positions in relative.items():
            earlier = old_positions.get(hand)
            if earlier is None or len(earlier) != len(positions):
                raise ValueError('XR tracked hand assignments changed')
            for a, b in zip(earlier, positions):
                delta_sq = sum((x - y) ** 2 for x, y in zip(a, b))
                if not math.isfinite(delta_sq) or delta_sq > max_distance ** 2:
                    raise ValueError('XR controller pose jumped during gesture')
        if old_rotations is not None:
            max_angle = min(180.0, max(150.0, 1100.0 * dt))
            for hand, pair in rotations.items():
                earlier = old_rotations.get(hand)
                if earlier is None or len(earlier) != len(pair):
                    raise ValueError('XR controller rotation tracking changed')
                for rotation, last_rotation in zip(pair, earlier):
                    if _angular_difference_degrees(rotation, last_rotation) > max_angle:
                        raise ValueError('XR controller orientation jumped during gesture')
    session._xr_motion_sample = (now, relative, rotations)




REARM_HAND_STABILITY = 0.35


def neutral_rearm_frame(session, context, samples):
    """Require all native controls released before controller dispatch resumes.

    Both thumbsticks can move the viewer in CLASSIC mode, not only the radial
    offhand stick. A reconnect with either deflected would start locomotion or
    turn the scene on the first resumed edit frame. Hand bridges cannot report
    thumbsticks, so their existing complete neutral button packet is used.
    """
    if not neutral(samples):
        return False
    if getattr(session, 'bridge', None) is not None:
        return True
    sticks = getattr(session, '_xr_validated_sticks', None)
    if sticks is None:
        # Compatibility with direct callers; the shared frame router always
        # populates a validated native pair before invoking advance_rearm.
        sticks = tuple(stick_axes(actions.read(context, 'stick', i))
                       for i in (0, 1))
    if len(sticks) != 2:
        raise ValueError('Both tracked thumbsticks are required to rearm')
    if any(max(abs(axis) for axis in stick_axes(stick)) >= STICK_REARM_THRESHOLD
           for stick in sticks):
        return False
    if getattr(session, 'finger_touch', False):
        aux = getattr(session, '_xr_validated_aux', None)
        if aux is not None and any(aux[0]):
            # A held two-finger toggle must start a fresh HoldGesture rather
            # than fire immediately after a tracking interruption.
            return False
    return True


def stable_rearm_pose(session):
    """Compare consecutive neutral frames in HMD-relative coordinates.

    Large localization jumps may produce individually finite 'neutral' frames.
    Never approve a reconnect from two unrelated hand placements. Direct
    legacy callers without router snapshots retain the original rearm API.
    """
    poses = getattr(session, '_xr_validated_poses', None)
    viewer = getattr(session, '_xr_validated_viewer', None)
    if poses is None and viewer is None:
        return True
    if poses is None or viewer is None:
        raise ValueError('Incomplete controller/headset rearm frame')
    current = _head_relative_pose(poses, viewer)
    orientations = _head_relative_rotations(poses, viewer)
    previous = getattr(session, '_xr_rearm_pose', None)
    previous_rotations = getattr(session, '_xr_rearm_rotations', None)
    session._xr_rearm_pose = current
    session._xr_rearm_rotations = orientations
    if previous is None or previous_rotations is None:
        return True
    if set(previous) != set(current):
        return False
    for hand, positions in current.items():
        old_positions = previous[hand]
        if len(positions) != len(old_positions):
            return False
        for xyz, old_xyz in zip(positions, old_positions):
            if sum((a - b) ** 2 for a, b in zip(xyz, old_xyz)) > REARM_HAND_STABILITY ** 2:
                return False
        prior = previous_rotations.get(hand)
        current_pair = orientations[hand]
        if prior is None or len(prior) != len(current_pair):
            return False
        if any(_angular_difference_degrees(new, old) > 110.0
               for new, old in zip(current_pair, prior)):
            return False
    return True


def advance_rearm(session, context, samples):
    """Advance one fully neutral frame; never dispatch on the release frame.

    Returns True only when the caller must suppress normal input handling.
    A malformed stick invalidates the entire frame and restarts the neutral
    count; it never produces an accidental selection.
    """
    if (getattr(session, '_xr_rollback_blocked', False) or
            getattr(getattr(session, 'history', None),
                    '_xr_mesh_rollback_blocked', False)):
        session._xr_rollback_blocked = True
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
        session._xr_rearm_pose = None
        session._xr_rearm_rotations = None
        session.status = 'RELEASE TRIGGERS, GRIPS, STICKS AND TOUCHES'
        return True
    try:
        stable = stable_rearm_pose(session)
    except (RuntimeError, TypeError, ValueError, IndexError, AttributeError, OverflowError):
        from . import input_ownership_v080
        input_ownership_v080.cancel_tracking_loss(session)
        session._xr_neutral_count = 0
        session.status = 'REARM TRACKING LOST / RELEASE CONTROLS'
        return True
    if not stable:
        # Keep the current finite pose as the next neutral baseline; require
        # another complete stable sample rather than accepting a pose jump.
        session._xr_neutral_count = 0
        session.status = 'REARM HAND TRACKING / STABILIZING'
        return True
    session._xr_neutral_count = getattr(session, '_xr_neutral_count', 0) + 1
    if session._xr_neutral_count < NEUTRAL_FRAMES:
        session.status = 'CONTROLLERS NEUTRAL / STABILIZING'
        return True
    session._xr_neutral_count = 0
    session._xr_rearm_required = False
    session._xr_rearm_pose = None
    session._xr_rearm_rotations = None
    # Discard any touch hold begun before tracking was lost. After rearm, a
    # finger-touch toggle must complete a full new hold, not inherit elapsed
    # time from an interrupted OpenXR session.
    from . import input_ownership_v080
    input_ownership_v080.reset_touch_holds(session)
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
    session._xr_validated_viewer = None
    session._xr_validated_aux = None
    # Failed Undo/cancel must not be converted into a harmless neutral
    # rearm on the next controller tick. Require a fresh XR runtime session.
    if (getattr(session, '_xr_rollback_blocked', False) or
            getattr(getattr(session, 'history', None),
                    '_xr_mesh_rollback_blocked', False)):
        session._xr_rollback_blocked = True
        session._xr_rearm_required = True
        session.status = 'XR ROLLBACK BLOCKED / REVIEW SCENE / RESTART XR'
        return False
    try:
        state = context.window_manager.xr_session_state
        if state is None or not bpy.types.XrSessionState.is_running(context):
            input_ownership_v080.cancel_session_loss(session)
            return False
        # Validate HMD placement and rotation before accepting any controller
        # release/gesture. Previously the legacy renderer checked the viewer
        # only after the router had already allowed the frame, while some
        # specialised editors bypassed that late check altogether.
        viewer = headset_frame(state)
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
        aux = optional_controller_sample(session, context)
        # Plausibility is required even when no gesture is active. A finite
        # but wildly misplaced aim pose must never produce a destructive
        # selection ray, a menu at infinity, or an unsafe first gesture.
        # The continuity guard reuses the same HMD-relative checks for
        # active edits and catches jumps across otherwise plausible frames.
        enforce_edit_pose_continuity(session, poses, viewer)
        session._xr_validated_poses = poses
        session._xr_validated_controls = samples
        session._xr_validated_sticks = sticks
        session._xr_validated_viewer = viewer
        session._xr_validated_aux = aux
        session.hand_controls = samples
        if advance_rearm(session, context, samples):
            return False
        return True
    except (RuntimeError, TypeError, ValueError, IndexError, AttributeError,
            OverflowError, ReferenceError) as exc:
        input_ownership_v080.cancel_tracking_loss(session)
        session.status = ('XR ROLLBACK BLOCKED / REVIEW SCENE / RESTART XR'
                          if getattr(session, '_xr_rollback_blocked', False) else
                          'XR FRAME INVALID / EDIT CANCELLED / ' +
                          str(exc).upper()[:30] + ' / RELEASE CONTROLS')
        return False


def guard_specialized_frame(session, context):
    """Apply the same complete snapshot barrier to intercepting XR editors."""
    return preflight_controller_frame(session, context)
