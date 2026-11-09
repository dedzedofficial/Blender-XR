# SPDX-License-Identifier: GPL-3.0-or-later
"""Low-poly articulated XR controller hands; no Blender scene meshes or objects."""
import math
from mathutils import Vector, Quaternion


def _cuboid(out, a, b, width, depth):
    """Append a rectangular tapered-looking phalanx/hand segment."""
    forward = b - a
    if forward.length < 1e-7:
        return
    forward.normalize()
    up = Vector((0, 1, 0))
    right = up.cross(forward)
    if right.length < .001:
        right = Vector((1, 0, 0))
    right.normalize()
    up = forward.cross(right).normalized()
    corners = []
    for center in (a, b):
        corners.extend(center + right * (x * width / 2) + up * (y * depth / 2)
                       for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1)))
    for indices in ((0, 1, 2, 0, 2, 3), (4, 6, 5, 4, 7, 6),
                    (0, 4, 5, 0, 5, 1), (1, 5, 6, 1, 6, 2),
                    (2, 6, 7, 2, 7, 3), (3, 7, 4, 3, 4, 0)):
        out.extend(corners[i] for i in indices)


def hand_mesh(grip=0.0, trigger=0.0, left=False, finger_curls=None):
    """One solid low-poly palm and 5 articulated fingers in hand-local metres."""
    grip = max(0.0, min(1.0, float(grip)))
    trigger = max(0.0, min(1.0, float(trigger)))
    if finger_curls is not None and len(finger_curls) == 5:
        fingers = tuple(max(0., min(1., float(v))) for v in finger_curls)
    else:
        # Trigger is an estimated index-finger bend, grip the other digits.
        fingers = (max(grip, trigger * .6), trigger, grip, grip, grip)
    mirror = -1 if left else 1
    triangles = []
    _cuboid(triangles, Vector((0, 0, .021)), Vector((0, 0, -.048)), .083, .027)
    _cuboid(triangles, Vector((0, 0, .049)), Vector((0, 0, .023)), .053, .031)
    # Finger roots across knuckles, four fingers with individual bend profiles.
    for index, x in enumerate((-.030, -.010, .011, .030)):
        # SteamVR skeletal summary supplies independent finger bends in v2.
        # Controller-only mode uses clearly estimated trigger/grip curves.
        curve = fingers[index + 1]
        base = Vector((mirror * x, -.001, -.044))
        for section, length in enumerate((.031, .025, .019)):
            angle = min(2.5, curve * (0.50 + .63 * section))
            end = base + Vector((0, -math.sin(angle) * length,
                                 -math.cos(angle) * length))
            _cuboid(triangles, base, end, (.016 - section * .0023),
                    (.016 - section * .0021))
            base = end
    # The real thumb originates beside the palm, not in the finger row.
    root = Vector((mirror * .040, -.003, -.016))
    bend = fingers[0]
    for section, length in enumerate((.029, .024)):
        end = root + Vector((mirror * (.8 - bend * .42) * length,
                             -.2 * length - bend * .60 * length,
                             -.30 * length + bend * .12 * length))
        _cuboid(triangles, root, end, .021 - section * .004,
                .020 - section * .004)
        root = end
    return triangles


def draw(runtime, shader):
    """Render stereo-compatible GPU geometry from Blender's tracked grip poses."""
    if getattr(runtime.settings, 'hand_display', 'CONTROLLERS') != 'HANDS':
        return
    state = runtime.context.window_manager.xr_session_state
    if state is None:
        return
    from . import drawing
    import gpu
    depth = gpu.state.depth_test_get()
    try:
        gpu.state.depth_test_set('LESS_EQUAL')
        scale = float(getattr(runtime.settings, 'hand_scale', 1.0))
        vr_scale = float(getattr(state, 'viewer_scale', 1.0))
        # Calibrate hand overlay in controller-local coordinates, not geometry
        # or the precise editing ray.
        calibration = Vector((
            float(getattr(runtime.settings, 'hand_offset_x', 0.0)),
            float(getattr(runtime.settings, 'hand_offset_y', 0.0)),
            float(getattr(runtime.settings, 'hand_offset_z', 0.0))))
        for index in (0, 1):
            try:
                origin = Vector(state.controller_grip_location_get(runtime.context, index))
                rotation = Quaternion(state.controller_grip_rotation_get(runtime.context, index))
                if rotation.magnitude < .5:
                    continue
                values = getattr(runtime, 'hand_controls', ((0., 0.), (0., 0.)))
                trigger, grip = values[index]
                skeletal = getattr(getattr(runtime, 'bridge', None),
                                   'finger_curls', None)
                individual = skeletal[index] if skeletal is not None else None
                local_mesh = hand_mesh(grip, trigger, left=index == 0,
                                       finger_curls=individual)
                points = [origin + rotation @ ((point * scale + calibration) * vr_scale)
                          for point in local_mesh]
                drawing.draw_batch(shader, 'TRIS', points,
                                   (.67, .77, .84, .97))
            except (AttributeError, ReferenceError, RuntimeError, ValueError, TypeError):
                continue
    finally:
        gpu.state.depth_test_set(depth)
