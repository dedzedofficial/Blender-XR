# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Rest / Pose comparison with guarded XR history.

Only switches Armature.pose_position, never the rest bones, constraints,
skinning, keyframes, vertex groups or bone transforms. The actual Blender
Armature datablock remains authoritative in the saved project.
"""
import bpy

from . import input_ownership_v080, menus, mesh, v065

_TAG = 'XR_REST_POSE_VIEW_090'
_ACTIONS = {'XR_POSE_SHOW_REST': 'REST', 'XR_POSE_SHOW_POSE': 'POSE'}


def _target(context):
    obj = context.view_layer.objects.active
    if (obj is None or obj.type != 'ARMATURE' or obj.mode != 'POSE' or
            context.mode != 'POSE' or
            context.view_layer.objects.get(obj.name) != obj):
        raise ValueError('Enter Blender Pose Mode on an armature first')
    if (obj.library or obj.override_library or obj.data.library or
            obj.data.override_library or obj.data.users != 1 or
            obj.hide_select or obj.hide_get() or not obj.visible_get()):
        raise ValueError('Use an unlocked local single-user armature')
    return obj


def _identity(context, obj, before, after):
    return (_TAG, context.scene.name, context.view_layer.name,
            obj.name, obj.as_pointer(), obj.data.name,
            obj.data.as_pointer(), before, after)


def _write(context, entry, backwards):
    (_kind, scene, layer, obj_name, obj_ptr, data_name,
     data_ptr, before, after) = entry
    if (context.scene.name != scene or context.view_layer.name != layer):
        raise ValueError('Return to the original scene/view layer for pose-view Undo')
    obj = _target(context)
    if (obj.name != obj_name or obj.as_pointer() != obj_ptr or
            obj.data.name != data_name or obj.data.as_pointer() != data_ptr):
        raise ValueError('Armature changed since XR Rest/Pose comparison')
    expected = after if backwards else before
    if obj.data.pose_position != expected:
        raise ValueError('Rest/Pose display was changed outside XR history')
    replacement = before if backwards else after
    obj.data.pose_position = replacement
    try:
        context.view_layer.update()
    except Exception:
        # A failed dependency-graph update must not consume the XR history
        # entry or leave a partially applied Rest/Pose display switch.
        if obj.data.pose_position == replacement:
            obj.data.pose_position = expected
            context.view_layer.update()
        raise


def _apply(context, action, history=None):
    if action not in _ACTIONS:
        raise ValueError('Unknown Rest/Pose display action')
    obj = _target(context)
    before, after = str(obj.data.pose_position), _ACTIONS[action]
    if before == after:
        return False, after
    if history is None:
        raise ValueError('XR history is unavailable for Rest/Pose comparison')
    entry = _identity(context, obj, before, after)
    obj.data.pose_position = after
    try:
        context.view_layer.update()
        history.push(entry)
    except Exception:
        if obj.data.pose_position == after:
            obj.data.pose_position = before
            context.view_layer.update()
        raise
    return True, after


def _history():
    if getattr(mesh.History, '_xr_pose_rest_compare_090_patched', False):
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
        # Reserve the destination before mutating Blender data: an allocation
        # failure must not apply the view switch without a matching history.
        entry = src[-1]
        dst.append(entry)
        try:
            _write(bpy.context, entry, backwards)
        except Exception:
            dst.pop()
            raise
        src.pop()
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_pose_rest_compare_090_patched = True


def install_pages():
    existing = tuple(menus.PAGES['POSE_EDIT'])
    if not existing or existing[-1][1] != 'RIG_EXIT_POSE':
        raise ValueError('Native Pose Edit menu is unavailable')
    if not any(action == 'XR_POSE_SHOW_REST' for _label, action in existing):
        existing = existing[:-1] + (
            ('REST VIEW', 'XR_POSE_SHOW_REST'),
            ('POSE VIEW', 'XR_POSE_SHOW_POSE'),
            existing[-1])
    if len(existing) > 12:
        raise ValueError('Pose Edit menu does not have room for Rest/Pose views')
    menus.PAGES['POSE_EDIT'] = existing
    v065.TOOLTIPS.update({
        'XR_POSE_SHOW_REST': ('Rest Bone Display',
             'Display original Blender rest positions without editing armature bones'),
        'XR_POSE_SHOW_POSE': ('Posed Bone Display',
             'Display the actual current Blender pose and deformation again'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_pose_compare_090_patched', False):
        return
    _history()
    install_pages()
    original_command = Runtime.command

    def command(self, context, action):
        if action in _ACTIONS:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release active XR gestures before comparing rest and pose')
            changed, mode = _apply(context, action, getattr(self, 'history', None))
            self.status = ('ARMATURE ' + mode + ' VIEW / ' +
                           ('XR UNDO READY' if changed else 'UNCHANGED'))
            return
        return original_command(self, context, action)

    Runtime.command = command
    Runtime._xr_pose_compare_090_patched = True
