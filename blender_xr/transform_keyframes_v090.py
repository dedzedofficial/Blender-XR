# SPDX-License-Identifier: GPL-3.0-or-later
"""Key individual native object/pose channels through Blender's own Action.

Each headset action inserts exactly one location, Euler-rotation or scale
FCurve point at the active frame. Other keyframes and channels are never
overwritten. Undo/Redo uses session-local guarded single-point mutations;
there is no XR animation format, duplicate rig, or preview animation timer.
"""
import math

import bpy

from . import (input_ownership_v080, menus, mesh, runtime,
               shape_keyframes_v090, v065)

_OBJECT_PAGE = 'XR_ANIM_OBJECT_090'
_POSE_PAGE = 'XR_ANIM_POSE_090'
_TAG = 'XR_NATIVE_TRANSFORM_KEY_090'
_GROUPS = (
    ('LOC', 'location'), ('ROT', 'rotation_euler'), ('SCALE', 'scale'),
)
_CHANNELS = {
    'XR_ANIM_KEY_' + group + '_' + axis:
    (data_path, index)
    for group, data_path in _GROUPS
    for index, axis in enumerate('XYZ')
}
_READ = 'XR_ANIM_KEY_STATUS'
_EPS = 1e-5


def _scene_frame(context):
    window = getattr(context, 'window', None)
    if window is not None and window.screen is not None and window.screen.is_animation_playing:
        raise ValueError('Pause Blender playback before authoring animation')
    value = float(context.scene.frame_current) + float(context.scene.frame_subframe)
    if not math.isfinite(value) or abs(value - round(value)) > 1e-4:
        raise ValueError('Select a whole Blender frame before inserting transform keys')
    return int(round(value))


def _owner(context, pose):
    obj = context.view_layer.objects.active
    mode = 'POSE' if pose else 'OBJECT'
    if (obj is None or obj.mode != mode or context.mode != mode or
            context.view_layer.objects.get(obj.name) != obj):
        raise ValueError('Choose an active Blender object in ' + mode + ' Mode')
    if (obj.library or obj.override_library or
            (obj.data and (obj.data.library or obj.data.override_library)) or
            obj.hide_select or obj.hide_get() or not obj.visible_get()):
        raise ValueError('Unlock and reveal a local Blender object for keyframing')
    if pose:
        if obj.type != 'ARMATURE' or obj.data.pose_position != 'POSE':
            raise ValueError('Enter native Armature Posed View first')
        selected = obj.data.bones.active
        if selected is None or not selected.select or selected.hide:
            raise ValueError('Select the pose bone to keyframe first')
        bone = obj.pose.bones.get(selected.name)
        if (bone is None or bone.bone.hide or bone.bone.hide_select or
                bone.constraints):
            raise ValueError('Use a visible, unlocked, unconstrained pose bone')
        return obj, bone
    if obj.constraints:
        raise ValueError('Constrained objects require Blender animation editing')
    return obj, obj


def _target(context, pose, data_path, index):
    if data_path not in {'location', 'rotation_euler', 'scale'} or index not in (0, 1, 2):
        raise ValueError('Unsupported native transform keyframe channel')
    frame = _scene_frame(context)
    obj, item = _owner(context, pose)
    if data_path == 'rotation_euler' and item.rotation_mode != 'XYZ':
        raise ValueError('Use XYZ Euler rotation mode for per-axis keyframes')
    locks = {'location': 'lock_location', 'rotation_euler': 'lock_rotation',
             'scale': 'lock_scale'}
    if bool(getattr(item, locks[data_path])[index]):
        raise ValueError('Unlock the chosen transform channel before keyframing')
    value = float(getattr(item, data_path)[index])
    if not math.isfinite(value):
        raise ValueError('Transform channel contains a non-finite value')
    path = item.path_from_id(data_path) if pose else data_path
    animation = obj.animation_data
    if animation is not None:
        if any(len(track.strips) for track in animation.nla_tracks):
            raise ValueError('NLA strips require Blender native animation editing')
        if any(driver.data_path == path and driver.array_index == index
               for driver in animation.drivers):
            raise ValueError('Transform channel is driven, not directly keyable')
        action = animation.action
        if action is not None and (action.library or action.override_library
                                   or action.users > 1):
            raise ValueError('Use a local single-user Action before XR keyframing')
    return obj, item, path, frame, value


def _curve(owner, path, index):
    action, curves = shape_keyframes_v090._curves(owner)
    matches = [fc for fc in curves
               if fc.data_path == path and fc.array_index == index]
    if len(matches) > 1:
        raise ValueError('Ambiguous Blender FCurves for this transform channel')
    return action, matches[0] if matches else None


def _point(curve, frame):
    return shape_keyframes_v090._point(curve, frame) if curve is not None else None


def _other_points(curve, frame):
    """Guard the user-authored points; ignore auto-handle coordinates.

    Blender recalculates auto handles when adding a keyframe, so preserve
    their editable handle TYPES rather than comparing evaluated positions.
    """
    return tuple((round(float(p.co.x), 6), round(float(p.co.y), 6),
                  str(p.interpolation), str(p.handle_left_type),
                  str(p.handle_right_type))
                 for p in curve.keyframe_points
                 if abs(float(p.co.x) - frame) > 1e-4)


def _state(context, obj, item, pose, path, prop, axis, frame, value, action, curve):
    point = _point(curve, frame)
    return {
        'scene': context.scene.name, 'scene_ptr': context.scene.as_pointer(),
        'layer': context.view_layer.name,
        'obj': obj.name, 'obj_ptr': obj.as_pointer(),
        'obj_type': obj.type,
        'data_name': obj.data.name if obj.data else None,
        'data_ptr': obj.data.as_pointer() if obj.data else None,
        'pose': bool(pose), 'bone': item.name if pose else None,
        'bone_ptr': item.as_pointer() if pose else None,
        'path': path, 'prop': prop, 'axis': axis, 'frame': frame,
        'rotation_mode': item.rotation_mode, 'value': float(value),
        'action_ptr': action.as_pointer(), 'curve_ptr': curve.as_pointer(),
        'point_meta': shape_keyframes_v090._metadata(point),
        'other': _other_points(curve, frame), 'present': True,
    }


def _guard(context, state):
    pose = state['pose']
    obj, item, path, frame, _value = _target(
        context, pose, state['prop'], state['axis'])
    if (context.scene.name != state['scene'] or
            context.scene.as_pointer() != state['scene_ptr'] or
            context.view_layer.name != state['layer'] or
            obj.name != state['obj'] or obj.as_pointer() != state['obj_ptr'] or
            obj.type != state['obj_type'] or
            (obj.data.name if obj.data else None) != state['data_name'] or
            (obj.data.as_pointer() if obj.data else None) != state['data_ptr'] or
            (item.name if pose else None) != state['bone'] or
            (item.as_pointer() if pose else None) != state['bone_ptr'] or
            item.rotation_mode != state['rotation_mode'] or
            path != state['path'] or frame != state['frame']):
        raise ValueError('Native object, bone or frame changed outside XR history')
    action, curve = _curve(obj, path, state['axis'])
    if (action is None or curve is None or
            action.as_pointer() != state['action_ptr'] or
            curve.as_pointer() != state['curve_ptr'] or
            _other_points(curve, frame) != state['other']):
        raise ValueError('Transform FCurve was replaced or externally edited')
    point = _point(curve, frame)
    if state['present']:
        if (point is None or abs(float(point.co.y)-state['value']) > _EPS or
                shape_keyframes_v090._metadata(point) != state['point_meta']):
            raise ValueError('XR transform keyframe was edited outside headset')
    elif point is not None:
        raise ValueError('Another keyframe occupies the XR Undo frame')
    return obj, item, curve, point


def _toggle(context, state, backwards):
    if state['present'] != bool(backwards):
        raise ValueError('Transform animation history is out of sequence')
    _obj, _item, curve, point = _guard(context, state)
    frame = state['frame']
    if backwards:
        curve.keyframe_points.remove(point)
        try:
            curve.update()
            context.scene.frame_set(frame, subframe=0.0)
            context.view_layer.update()
        except Exception:
            try:
                if _point(curve, frame) is None:
                    restored = curve.keyframe_points.insert(
                        frame, state['value'], options=set())
                    shape_keyframes_v090._set_point_meta(
                        restored, state['point_meta'])
                    curve.update()
            except Exception:
                pass
            raise
        state['present'] = False
    else:
        created = curve.keyframe_points.insert(
            frame, state['value'], options=set())
        try:
            shape_keyframes_v090._set_point_meta(created, state['point_meta'])
            curve.update()
            context.scene.frame_set(frame, subframe=0.0)
            context.view_layer.update()
        except Exception:
            try:
                if _point(curve, frame) == created:
                    curve.keyframe_points.remove(created)
                    curve.update()
            except Exception:
                pass
            raise
        state['present'] = True
    # Auto handles may move as neighbouring keys are inserted/deleted, but
    # Blender's other keyframe values and interpolation remain unchanged.
    state['other'] = _other_points(curve, frame)


def insert(context, pose, data_path, index, history=None):
    obj, item, path, frame, value = _target(context, pose, data_path, index)
    action, curve = _curve(obj, path, index)
    if _point(curve, frame) is not None:
        raise ValueError('A Blender keyframe already exists; XR will not replace it')
    inserted = False
    try:
        inserted = bool(item.keyframe_insert(
            data_path=data_path, index=index, frame=frame))
        if not inserted:
            raise ValueError('Blender did not create the transform keyframe')
        action, curve = _curve(obj, path, index)
        point = _point(curve, frame)
        if action is None or point is None or abs(float(point.co.y)-value) > _EPS:
            raise ValueError('New native FCurve/keyframe could not be resolved')
        state = _state(context, obj, item, pose, path, data_path,
                       index, frame, value, action, curve)
        if history is not None:
            history.push((_TAG, state))
        return state
    except Exception:
        if inserted:
            try:
                _action, new_curve = _curve(obj, path, index)
                new_point = _point(new_curve, frame)
                if new_point is not None and abs(float(new_point.co.y)-value) <= _EPS:
                    new_curve.keyframe_points.remove(new_point)
                    new_curve.update()
            except (RuntimeError, ReferenceError, ValueError, AttributeError):
                pass
        raise


def inspect(context, pose):
    obj, item = _owner(context, pose)
    frame = _scene_frame(context)
    count = 0
    for _name, path in _GROUPS:
        if path == 'rotation_euler' and item.rotation_mode != 'XYZ':
            continue
        full_path = item.path_from_id(path) if pose else path
        for idx in range(3):
            _action, curve = _curve(obj, full_path, idx)
            if _point(curve, frame) is not None:
                count += 1
    return item.name, frame, count


class BXR_OT_transform_keyframe(bpy.types.Operator):
    bl_idname = 'blender_xr.transform_keyframe'
    bl_label = 'Native Object / Pose Bone Channel Keyframe'
    bl_description = 'Insert one existing Blender transform channel into its native Action'
    bl_options = {'REGISTER', 'UNDO'}
    channel: bpy.props.EnumProperty(
        items=[(key, key.replace('XR_ANIM_KEY_', '').replace('_', ' '),
                'Insert one native Blender channel keyframe')
               for key in _CHANNELS], default='XR_ANIM_KEY_LOC_X')

    @classmethod
    def poll(cls, context):
        active = context.view_layer.objects.active
        return bool(active and (active.mode == 'OBJECT' or
                    (active.type == 'ARMATURE' and active.mode == 'POSE')))

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Object/Pose Animation wrist submenu')
            return {'CANCELLED'}
        try:
            prop, axis = _CHANNELS[self.channel]
            pose = context.mode == 'POSE'
            info = insert(context, pose, prop, axis)
        except (ValueError, RuntimeError, ReferenceError, TypeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Keyframe {} / frame {}'.format(
            info['path'], info['frame']))
        return {'FINISHED'}


def _history():
    if getattr(mesh.History, '_xr_native_transform_keys_090', False):
        return
    previous_step, previous_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == _TAG:
            return
        return previous_release(entry)

    def step(self, backwards=True):
        src, dst = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not src or src[-1][0] != _TAG:
            return previous_step(self, backwards)
        entry = src[-1]
        dst.append(entry)
        try:
            _toggle(bpy.context, entry[1], backwards)
        except Exception:
            dst.pop()
            raise
        src.pop()
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_native_transform_keys_090 = True


def install_pages():
    layout = tuple(menus.PAGES['LAYOUT_MENU'])
    pose = tuple(menus.PAGES['POSE_EDIT'])
    if not layout or layout[-1][1] != 'BACK' or len(layout) >= 12:
        raise ValueError('Object Layout has no room for animation category')
    if not pose or pose[-1][1] != 'RIG_EXIT_POSE' or len(pose) >= 12:
        raise ValueError('Pose menu has no room for animation category')
    menus.PAGES['LAYOUT_MENU'] = (layout[:-1] +
        (('ANIMATE', 'XR_ANIM_OBJECT_MENU'), layout[-1]))
    menus.PAGES['POSE_EDIT'] = (pose[:-1] +
        (('KEY BONES', 'XR_ANIM_POSE_MENU'), pose[-1]))
    buttons = tuple((group + ' ' + axis, 'XR_ANIM_KEY_' + group + '_' + axis)
                    for group, _name in _GROUPS for axis in 'XYZ')
    for page, name in ((_OBJECT_PAGE, 'OBJECT CHANNEL KEYFRAMES'),
                       (_POSE_PAGE, 'POSE BONE KEYFRAMES')):
        menus.PAGES[page] = buttons + (('CHECK', _READ), ('BACK', 'BACK'))
        menus.TITLES[page] = name
    v065.TOOLTIPS.update({
        'XR_ANIM_OBJECT_MENU': ('Native Object Transform Keys',
           'Key an object location, Euler rotation or scale channel in Blender Actions'),
        'XR_ANIM_POSE_MENU': ('Native Bone Transform Keys',
           'Key a selected PoseBone location, Euler rotation or scale channel'),
        _READ: ('Inspect Transform Keyframes',
           'Read which of the nine native transform channels have keys at this frame'),
    })
    for action, (prop, axis) in _CHANNELS.items():
        v065.TOOLTIPS[action] = ('Key ' + prop + ' ' + 'XYZ'[axis],
            'Insert one native Blender FCurve point without replacing existing keys')


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_native_transform_keyframe_090_patched', False):
        return
    _history()
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if (action == 'XR_ANIM_OBJECT_MENU' and page == 'LAYOUT_MENU' or
                action == 'XR_ANIM_POSE_MENU' and page == 'POSE_EDIT'):
            pose = action == 'XR_ANIM_POSE_MENU'
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release active XR gesture before authoring animation')
            _owner(context, pose)
            self.menu.page = _POSE_PAGE if pose else _OBJECT_PAGE
            self.status = 'NATIVE ' + ('BONE' if pose else 'OBJECT') + ' KEYFRAMES'
            return
        if page in {_OBJECT_PAGE, _POSE_PAGE}:
            if action == 'BACK':
                self.menu.page = 'POSE_EDIT' if page == _POSE_PAGE else 'LAYOUT_MENU'
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR controllers before keyframing')
            pose = page == _POSE_PAGE
            if action == _READ:
                name, frame, count = inspect(context, pose)
                self.status = '{} / FRAME {} / {} OF 9 CHANNELS KEYED'.format(
                    name.upper()[:25], frame, count)
                return
            if action in _CHANNELS:
                if getattr(self, 'history', None) is None:
                    raise ValueError('XR Undo history is required for animation')
                prop, axis = _CHANNELS[action]
                result = insert(context, pose, prop, axis, self.history)
                self.status = '{} / FRAME {} / KEYED {} / UNDO READY'.format(
                    result['obj'].upper()[:20], result['frame'],
                    action.replace('XR_ANIM_KEY_', ''))
                return
            raise ValueError('Unknown transform animation channel')
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_native_transform_keyframe_090_patched = True


CLASSES = (BXR_OT_transform_keyframe,)
