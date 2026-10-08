# SPDX-License-Identifier: GPL-3.0-or-later
"""Own OpenXR action set; never depends on VR Scene Inspection bindings."""
SET = 'dedzed_blender_xr'
HANDS = ('/user/hand/left', '/user/hand/right')
PROFILES = {
    'touch': ('/interaction_profiles/oculus/touch_controller', '/input/squeeze/value'),
    'index': ('/interaction_profiles/valve/index_controller', '/input/squeeze/value'),
    'vive': ('/interaction_profiles/htc/vive_controller', '/input/squeeze/click'),
    'simple': ('/interaction_profiles/khr/simple_controller', '/input/select/click'),
}


def build_map(state, family='AUTO', finger_touch=False):
    amap = state.actionmaps.new(state, SET, replace_existing=True)
    definitions = [
        ('grip_pose', 'POSE', '/input/grip/pose'),
        ('aim_pose', 'POSE', '/input/aim/pose'),
        ('trigger', 'FLOAT', '/input/trigger/value'),
        ('grab', 'FLOAT', None),
        ('stick', 'VECTOR2D', '/input/thumbstick'),
    ]
    if finger_touch:
        definitions += [('trigger_touch', 'BOOLEAN', '/input/trigger/touch'),
                        ('thumb_touch', 'BOOLEAN', '/input/thumbstick/touch')]
    families = {'AUTO': set(PROFILES), 'META': {'touch', 'simple'},
                'VALVE': {'index', 'touch', 'vive', 'simple'}}
    for name, kind, component in definitions:
        item = amap.actionmap_items.new(name, replace_existing=True)
        item.type = kind
        item.pose_is_controller_grip = name == 'grip_pose'
        item.pose_is_controller_aim = name == 'aim_pose'
        for hand in HANDS:
            item.user_paths.new(hand)
        for key, (profile, squeeze) in PROFILES.items():
            if key not in families[family]:
                continue
            if name.endswith('_touch') and key not in {'touch', 'index'}:
                continue
            # Simple controllers have no stick or independent grab control.
            if key == 'simple' and name in {'grab', 'stick'}:
                continue
            if key == 'vive' and name == 'stick':
                path = '/input/trackpad'
            elif key == 'simple' and name == 'trigger':
                path = '/input/select/click'
            else:
                path = squeeze if name == 'grab' else component
            binding = item.bindings.new(key, replace_existing=True)
            binding.profile = profile
            binding.threshold = 0.55
            for _ in HANDS:
                binding.component_paths.new(path)
    return amap


def activate(context):
    state = context.window_manager.xr_session_state
    settings = context.scene.blender_xr
    amap = build_map(state, settings.controller_family, settings.finger_touch)
    if not state.action_set_create(context, amap):
        raise RuntimeError('OpenXR could not create the Blender XR action set')
    for item in amap.actionmap_items:
        if not state.action_create(context, amap, item):
            raise RuntimeError('OpenXR could not create action: ' + item.name)
        for binding in item.bindings:
            if not state.action_binding_create(context, amap, item, binding):
                if not item.name.endswith('_touch'):
                    raise RuntimeError('OpenXR could not bind: ' + item.name)
    if not state.controller_pose_actions_set(context, SET, 'grip_pose', 'aim_pose'):
        raise RuntimeError('OpenXR could not attach controller poses')
    if not state.active_action_set_set(context, SET):
        raise RuntimeError('OpenXR could not activate controller actions')


def read(context, name, hand):
    return context.window_manager.xr_session_state.action_state_get(
        context, SET, name, HANDS[hand])


def touch(context, hand):
    try:
        return (read(context, 'trigger_touch', hand)[0] > 0.5 and
                read(context, 'thumb_touch', hand)[0] > 0.5)
    except (RuntimeError, ValueError):
        return False
