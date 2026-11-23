# SPDX-License-Identifier: GPL-3.0-or-later
"""Native one-way X mirror for Blender Weight Paint vertex groups.

Preserves all mesh topology, UVs and every non-active vertex group. Source
hemisphere is never modified. Uses the existing XR WeightStroke transaction
for cancellation and guarded Undo/Redo, or native Blender operator Undo on
desktop. No persistent custom mesh attributes or mirror modifiers.
"""
import math

import bpy
from mathutils.kdtree import KDTree

from . import input_ownership_v080, menus, rigging_v076, runtime, v065

_TUNE = 'WEIGHT_TUNE_086'
_MIRROR = 'WEIGHT_MIRROR_086'
_TOLERANCES = {
    'WEIGHT_MIRROR_1MM': 0.001,
    'WEIGHT_MIRROR_5MM': 0.005,
    'WEIGHT_MIRROR_2CM': 0.02,
}
_DIRECTIONS = {
    'WEIGHT_MIRROR_NEG_POS': -1,
    'WEIGHT_MIRROR_POS_NEG': 1,
}
_MAX_VERTICES = 150000


def _eligible(context):
    obj = context.view_layer.objects.active
    if obj is None or obj.type != 'MESH' or obj.mode != 'WEIGHT_PAINT':
        raise ValueError('Select a mesh in native Weight Paint mode')
    if obj.library or obj.override_library or obj.data.library or obj.data.users != 1:
        raise ValueError('Use an editable local, single-user mesh for mirroring')
    if obj.hide_select or obj.hide_get() or not obj.visible_get():
        raise ValueError('Unlock and reveal the painted mesh')
    group = rigging_v076.active_group(obj)
    if group.lock_weight:
        raise ValueError('Unlock the active vertex group before mirroring')
    if len(obj.data.vertices) > _MAX_VERTICES:
        raise ValueError('Mirror accepts at most 150,000 vertices per operation')
    return obj, group


def _plan(obj, group, direction, tolerance):
    """Compute every mirrored assignment before any Blender data is written.

    Source and destination halves are defined in *object local X*, so the
    result does not change merely because the avatar was rotated in a scene.
    The tolerance is also in the object's native local mesh units.
    """
    if direction not in (-1, 1):
        raise ValueError('Invalid X mirror direction')
    tolerance = float(tolerance)
    if not math.isfinite(tolerance) or not 0.0001 <= tolerance <= 0.1:
        raise ValueError('Mirror tolerance must be 0.0001 through 0.1 local units')
    src = []
    targets = []
    # A small seam exclusion prevents central vertices being mirrored onto
    # themselves; never change the seam or the source hemisphere.
    seam = min(tolerance * 0.5, .001)
    for vert in obj.data.vertices:
        point = tuple(float(x) for x in vert.co)
        if not all(math.isfinite(x) for x in point):
            raise ValueError('Mesh vertex has non-finite coordinates')
        x = point[0] * direction
        if x > seam:
            src.append((vert.index, point, rigging_v076._vertex_weight(group, vert.index)))
        elif x < -seam:
            targets.append((vert.index, point))
    if not src or not targets:
        raise ValueError('Both X hemispheres need vertices; choose a mesh with two sides')

    tree = KDTree(len(src))
    weights = {}
    for source_id, source_point, weight in src:
        tree.insert(source_point, source_id)
        weights[source_id] = weight
    tree.balance()

    planned = []
    for index, position in targets:
        target = (-position[0], position[1], position[2])
        found = tree.find(target)
        if found is None:
            continue
        _point, mirrored_index, distance = found
        if distance <= tolerance:
            planned.append((index, weights[mirrored_index]))
    if not planned:
        raise ValueError('No symmetric vertex pairs within tolerance')
    return tuple(planned)


def mirror_group(context, direction, tolerance, history=None):
    """Commit one guarded operation without modifying the source hemisphere.

    Desktop callers rely on Blender's REGISTER/UNDO operator. XR callers must
    supply their own Mesh XR history; both use WeightStroke for failure
    rollback. A missing assignment is copied as *missing*, not as weight 0.
    """
    obj, group = _eligible(context)
    planned = _plan(obj, group, direction, tolerance)
    recorder = rigging_v076.WeightStroke(obj)
    changed = 0
    try:
        for index, value in planned:
            if rigging_v076._paint_weight_index(group, index, value, recorder):
                changed += 1
        if not changed:
            recorder.discard()
            return 0, len(planned)
        obj.data.update()
        context.view_layer.update()
        if not recorder.unchanged_target(context):
            raise ValueError('Mesh or active group changed during mirror')
        entry = recorder.finish()
        if entry is None:
            recorder.discard()
            return 0, len(planned)
        if history is not None:
            history.push(entry)
        recorder.discard()
        return changed, len(planned)
    except Exception:
        # Refuse rollback if a different Blender editor has already changed
        # affected weights or topology; do not overwrite unrelated edits.
        recorder.cancel()
        raise


class BXR_OT_weight_mirror(bpy.types.Operator):
    bl_idname = 'blender_xr.weight_mirror_x'
    bl_label = 'Mirror Native Vertex Group Across Local X'
    bl_description = 'Copy active vertex-group weights from one local X hemisphere to the other'
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(items=[
        ('NEG_POS', '-X to +X', 'Copy negative X weights to corresponding positive X vertices'),
        ('POS_NEG', '+X to -X', 'Copy positive X weights to corresponding negative X vertices'),
    ], default='NEG_POS')

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return bool(obj and obj.type == 'MESH' and obj.mode == 'WEIGHT_PAINT')

    def execute(self, context):
        if runtime.CURRENT is not None:
            self.report({'WARNING'}, 'Use the XR Weight Mirror wrist menu during an active session')
            return {'CANCELLED'}
        try:
            count, paired = mirror_group(context,
                -1 if self.direction == 'NEG_POS' else 1,
                context.scene.blender_xr.weight_mirror_tolerance)
        except (ValueError, RuntimeError, ReferenceError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'X mirror: {} assignments updated ({} pairs)'.format(
            count, paired))
        return {'FINISHED'} if count else {'CANCELLED'}


def install_pages():
    page = tuple(menus.PAGES['WEIGHT_PAINT'])
    tune_actions = {'WEIGHT_STRENGTH_DOWN', 'WEIGHT_STRENGTH_UP',
                    'WEIGHT_RADIUS_DOWN', 'WEIGHT_RADIUS_UP'}
    if set(action for _, action in page) & tune_actions != tune_actions:
        raise ValueError('Weight brush tuning actions were removed unexpectedly')
    if not any(action == 'WEIGHT_TUNE_MENU' for _, action in page):
        first = next(i for i, (_, action) in enumerate(page) if action in tune_actions)
        retained = [(label, action) for label, action in page
                    if action not in tune_actions]
        retained.insert(first, ('BRUSH TUNE', 'WEIGHT_TUNE_MENU'))
        retained.insert(first + 1, ('MIRROR X', 'WEIGHT_MIRROR_MENU'))
        if len(retained) > 12:
            raise ValueError('Weight Paint wrist menu has no room for mirror controls')
        menus.PAGES['WEIGHT_PAINT'] = tuple(retained)
    menus.PAGES[_TUNE] = (
        ('WEIGHT -', 'WEIGHT_STRENGTH_DOWN'),
        ('WEIGHT +', 'WEIGHT_STRENGTH_UP'),
        ('SIZE -', 'WEIGHT_RADIUS_DOWN'),
        ('SIZE +', 'WEIGHT_RADIUS_UP'),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_MIRROR] = (
        ('-X TO +X', 'WEIGHT_MIRROR_NEG_POS'),
        ('+X TO -X', 'WEIGHT_MIRROR_POS_NEG'),
        ('TOL 1 MM', 'WEIGHT_MIRROR_1MM'),
        ('TOL 5 MM', 'WEIGHT_MIRROR_5MM'),
        ('TOL 2 CM', 'WEIGHT_MIRROR_2CM'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_TUNE] = 'WEIGHT BRUSH TUNE'
    menus.TITLES[_MIRROR] = 'X WEIGHT MIRROR'
    v065.TOOLTIPS.update({
        'WEIGHT_TUNE_MENU': ('Brush Size and Strength', 'Adjust the existing Weight Paint brush without changing weights'),
        'WEIGHT_MIRROR_MENU': ('Mirror Active Vertex Group', 'Copy native weights across object-local X, no extra groups created'),
        'WEIGHT_MIRROR_NEG_POS': ('Mirror Negative to Positive X', 'Copy active group weights from local -X vertices to nearest mirrored local +X vertices'),
        'WEIGHT_MIRROR_POS_NEG': ('Mirror Positive to Negative X', 'Copy active group weights from local +X vertices to nearest mirrored local -X vertices'),
        'WEIGHT_MIRROR_1MM': ('1 mm Match Tolerance', 'Match vertices within 0.001 local mesh units'),
        'WEIGHT_MIRROR_5MM': ('5 mm Match Tolerance', 'Match vertices within 0.005 local mesh units'),
        'WEIGHT_MIRROR_2CM': ('2 cm Match Tolerance', 'Match vertices within 0.02 local mesh units'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_weight_mirror_086_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        page = getattr(getattr(self, 'menu', None), 'page', None)
        if action in {'WEIGHT_TUNE_MENU', 'WEIGHT_MIRROR_MENU'}:
            _eligible(context)
            if input_ownership_v080.is_editing(self):
                raise ValueError('Finish active XR gesture before opening weight tools')
            self.menu.page = _TUNE if action == 'WEIGHT_TUNE_MENU' else _MIRROR
            self.status = 'WEIGHT / ' + ('BRUSH TUNE' if self.menu.page == _TUNE
                                         else 'LOCAL X MIRROR')
            return
        if page in {_TUNE, _MIRROR}:
            if action == 'BACK':
                self.menu.page = 'WEIGHT_PAINT'
                return
            if page == _TUNE and action in {
                    'WEIGHT_STRENGTH_DOWN', 'WEIGHT_STRENGTH_UP',
                    'WEIGHT_RADIUS_DOWN', 'WEIGHT_RADIUS_UP'}:
                return previous_command(self, context, action)
            if page == _MIRROR and action in _TOLERANCES:
                _eligible(context)
                self.settings.weight_mirror_tolerance = _TOLERANCES[action]
                self.status = 'X MIRROR / TOLERANCE {:.4f} LOCAL'.format(
                    self.settings.weight_mirror_tolerance)
                return
            if page == _MIRROR and action in _DIRECTIONS:
                if input_ownership_v080.is_editing(self):
                    raise ValueError('Release live XR editing gestures before mirroring')
                history = getattr(self, 'history', None)
                if history is None:
                    raise ValueError('XR history unavailable; cannot mirror safely')
                count, paired = mirror_group(context, _DIRECTIONS[action],
                        self.settings.weight_mirror_tolerance, history=history)
                self.status = 'X MIRROR / {} CHANGED / {} MATCHED'.format(count, paired)
                return
            raise ValueError('Use the active Weight Paint submenu actions')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_weight_mirror_086_patched = True


CLASSES = (BXR_OT_weight_mirror,)
