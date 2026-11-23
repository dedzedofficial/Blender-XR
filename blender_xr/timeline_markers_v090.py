# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Blender TimelineMarker authoring and navigation for XR creators.

Markers are scene-owned Blender TimelineMarker objects, not duplicated
keyframes or custom project data. History stores guarded marker identities
and delegates frame stepping to the existing native XR timeline.
"""
import bpy

from . import input_ownership_v080, menus, mesh, runtime, timeline_v090, v065

_PAGE = 'XR_MARKERS_090'
_TAG = 'XR_TIMELINE_MARKER_090'
_MAX_MARKERS = 256
_ADD = 'XR_MARKER_ADD'
_REMOVE = 'XR_MARKER_REMOVE'
_PREV = 'XR_MARKER_PREVIOUS'
_NEXT = 'XR_MARKER_NEXT'


def _scene(context):
    return timeline_v090._scene(context)


def _layout(scene, ignore=None):
    return tuple(sorted(
        (marker.name, int(marker.frame), marker.as_pointer())
        for marker in scene.timeline_markers
        if marker.name != ignore
    ))


def _name(scene):
    names = {marker.name for marker in scene.timeline_markers}
    for number in range(1, 10000):
        name = 'XR Marker {:03d}'.format(number)
        if name not in names:
            return name
    raise ValueError('No free XR Marker names')


def _at_frame(scene):
    frame = int(scene.frame_current)
    matches = [marker for marker in scene.timeline_markers
               if int(marker.frame) == frame and
               marker.name.startswith('XR Marker ')]
    if not matches:
        raise ValueError('No XR Marker at the current Blender frame')
    if len(matches) != 1:
        raise ValueError('Several XR Markers share this frame; remove in Blender')
    return matches[0]


def _state(context, marker_name, frame, action, marker=None):
    scene = _scene(context)
    return {
        'action': action, 'scene': scene.name, 'scene_ptr': scene.as_pointer(),
        'frame': int(frame), 'name': marker_name,
        'ptr': marker.as_pointer() if marker is not None else 0,
        'others': _layout(scene, ignore=marker_name),
    }


def _validate(context, state, *, present):
    scene = _scene(context)
    if scene.name != state['scene'] or scene.as_pointer() != state['scene_ptr']:
        raise ValueError('Blender scene changed outside XR marker history')
    if _layout(scene, ignore=state['name']) != state['others']:
        raise ValueError('Other timeline markers changed outside XR')
    marker = scene.timeline_markers.get(state['name'])
    if present:
        if (marker is None or marker.as_pointer() != state['ptr'] or
                int(marker.frame) != state['frame']):
            raise ValueError('Native marker was renamed, replaced or moved')
    elif marker is not None:
        raise ValueError('A timeline marker now occupies the original name')
    return scene, marker


def _create(context, state):
    scene, _marker = _validate(context, state, present=False)
    if len(scene.timeline_markers) >= _MAX_MARKERS:
        raise ValueError('XR marker limit reached (256)')
    marker = scene.timeline_markers.new(state['name'], frame=state['frame'])
    if marker.name != state['name'] or marker.frame != state['frame']:
        scene.timeline_markers.remove(marker)
        raise ValueError('Blender could not create the exact timeline marker')
    state['ptr'] = marker.as_pointer()
    context.view_layer.update()


def _remove(context, state):
    scene, marker = _validate(context, state, present=True)
    scene.timeline_markers.remove(marker)
    context.view_layer.update()


def _apply(context, action, history=None):
    if action not in {_ADD, _REMOVE}:
        raise ValueError('Unknown timeline marker operation')
    if history is None:
        raise ValueError('XR marker authoring requires session Undo history')
    scene = _scene(context)
    if action == _ADD:
        if len(scene.timeline_markers) >= _MAX_MARKERS:
            raise ValueError('XR marker limit reached (256)')
        name, frame, marker = _name(scene), int(scene.frame_current), None
        mode = 'ADD'
    else:
        marker = _at_frame(scene)
        name, frame, mode = marker.name, int(marker.frame), 'REMOVE'
    state = _state(context, name, frame, mode, marker)
    if mode == 'ADD':
        _create(context, state)
    else:
        _remove(context, state)
    try:
        history.push((_TAG, state))
    except Exception:
        try:
            if mode == 'ADD':
                _remove(context, state)
            else:
                _create(context, state)
        except Exception:
            # Native scene data might have been edited externally while
            # history was failing. Do not overwrite it with a forced restore.
            import traceback
            traceback.print_exc()
        raise
    return name, frame, mode


def _step_to_marker(context, forwards, history):
    scene = _scene(context)
    start, end = timeline_v090._frame_limits(scene)
    current = int(scene.frame_current)
    frames = sorted({int(marker.frame) for marker in scene.timeline_markers
                     if start <= marker.frame <= end})
    candidates = [frame for frame in frames
                  if (frame > current if forwards else frame < current)]
    if not candidates:
        raise ValueError('No further timeline marker within playback range')
    target = candidates[0] if forwards else candidates[-1]
    state, _changed = timeline_v090.jump_frame(context, target, history)
    return state[0]


def _history():
    if getattr(mesh.History, '_xr_timeline_markers_090_patched', False):
        return
    original_step, original_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] == _TAG:
            return
        return original_release(entry)

    def step(self, backwards=True):
        source, destination = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] != _TAG:
            return original_step(self, backwards)
        entry = source[-1]
        state = entry[1]
        destination.append(entry)
        try:
            # Undo Add removes the new native marker. Undo Remove restores it.
            create = ((state['action'] == 'REMOVE') == backwards)
            if create:
                _create(bpy.context, state)
            else:
                _remove(bpy.context, state)
        except Exception:
            destination.pop()
            raise
        source.pop()
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_timeline_markers_090_patched = True


class BXR_OT_timeline_marker(bpy.types.Operator):
    bl_idname = 'blender_xr.timeline_marker'
    bl_label = 'Create or Remove Native Blender Timeline Marker'
    bl_description = 'Add or remove an XR-named marker on Blender’s real timeline'
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(items=(
        (_ADD, 'Add Marker', 'Create a uniquely named marker at the current frame'),
        (_REMOVE, 'Remove Marker', 'Remove the uniquely matching XR marker at the current frame'),
    ), default=_ADD)

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Timeline Markers wrist menu during VR')
            return {'CANCELLED'}
        # Desktop Blender's own Undo owns these operator mutations; the
        # XR-only history is created when the headset runtime calls _apply.
        try:
            scene = _scene(context)
            if self.action == _ADD:
                if len(scene.timeline_markers) >= _MAX_MARKERS:
                    raise ValueError('XR marker limit reached (256)')
                name = _name(scene)
                marker = scene.timeline_markers.new(name, frame=scene.frame_current)
                if marker.name != name:
                    scene.timeline_markers.remove(marker)
                    raise ValueError('Blender changed the requested marker name')
            else:
                marker = _at_frame(scene)
                name = marker.name
                scene.timeline_markers.remove(marker)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Blender timeline marker: ' + name)
        return {'FINISHED'}


def install_pages():
    page = tuple(menus.PAGES[timeline_v090._PAGE])
    if not page or page[-1][1] != 'BACK':
        raise ValueError('Native Timeline menu is unavailable')
    if not any(action == 'XR_MARKER_MENU' for _label, action in page):
        page = page[:-1] + (('MARKERS', 'XR_MARKER_MENU'), page[-1])
    if len(page) > 12:
        raise ValueError('Timeline menu has no free button for Markers')
    menus.PAGES[timeline_v090._PAGE] = page
    menus.PAGES[_PAGE] = (
        ('ADD HERE', _ADD),
        ('REMOVE XR', _REMOVE),
        ('PREVIOUS', _PREV),
        ('NEXT', _NEXT),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'TIMELINE MARKERS'
    v065.TOOLTIPS.update({
        'XR_MARKER_MENU': ('Native Timeline Markers',
            'Create native Blender timeline markers or jump between existing markers'),
        _ADD: ('Add Marker Here',
            'Create a unique XR Marker at the current Blender frame'),
        _REMOVE: ('Remove XR Marker',
            'Remove exactly one XR-named marker on this frame with guarded Undo'),
        _PREV: ('Previous Marker',
            'Jump to the previous scene marker using the existing XR frame history'),
        _NEXT: ('Next Marker',
            'Jump to the next scene marker using the existing XR frame history'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_timeline_markers_090_patched', False):
        return
    _history()
    install_pages()
    old_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if action == 'XR_MARKER_MENU' and page == timeline_v090._PAGE:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Finish current XR gesture before Timeline Markers')
            _scene(context)
            self.menu.page = _PAGE
            self.status = 'MARKERS / ADD, REMOVE XR, PREVIOUS, NEXT'
            return
        if page == _PAGE:
            if action == 'BACK':
                self.menu.page = timeline_v090._PAGE
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR controller gestures before editing markers')
            history = getattr(self, 'history', None)
            if history is None:
                raise ValueError('XR Undo history is required for timeline markers')
            if action in {_ADD, _REMOVE}:
                name, frame, operation = _apply(context, action, history)
                self.status = '{} / {} / FRAME {} / UNDO READY'.format(
                    operation, name.upper()[:26], frame)
                return
            if action in {_PREV, _NEXT}:
                frame = _step_to_marker(context, action == _NEXT, history)
                self.status = 'JUMPED TO MARKER / FRAME {}'.format(frame)
                return
            raise ValueError('Unknown Timeline Marker action')
        return old_command(self, context, action)

    Runtime.command = command
    Runtime._xr_timeline_markers_090_patched = True


CLASSES = (BXR_OT_timeline_marker,)
