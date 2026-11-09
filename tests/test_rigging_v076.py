"""Blender integration: object selection, armature pairs, weight groups, VR brush.

This test deliberately alternates Object / Armature Edit / Weight Paint / Pose /
Mesh Edit modes, reproducing the two reported 0.7.6 headset blockers.
"""
import sys
from pathlib import Path
from mathutils import Vector, Quaternion
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy
import blender_xr
from blender_xr import armature_v076, drawing, menus, rigging_v076, runtime, mesh as xr_mesh, focus_v080


def main():
    assert blender_xr.VERSION >= (0, 7, 6)
    blender_xr.register()
    try:
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        obj.name = 'VR rigging target'
        obj.scale = (1.5, 0.5, 0.3)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        assert 'FINISHED' in bpy.ops.blender_xr.create_basic_rig()
        rig = bpy.context.view_layer.objects.active
        assert rig.type == 'ARMATURE'
        assert rig.get('mesh_xr_target_mesh') == obj.name
        assert rigging_v076.mesh_for_rig(bpy.context, rig) == obj

        # The old Select Rig button cleared the target mesh, leaving binding
        # unable to find a selected mesh and Weight Paint without groups.
        for selected in bpy.context.selected_objects:
            selected.select_set(False)
        rig.select_set(True)
        bpy.context.view_layer.objects.active = rig
        session = runtime.Runtime.__new__(runtime.Runtime)
        session.menu = SimpleNamespace(page='RIGGING')
        session.tool = 'SELECT'
        session.status = ''
        session.settings = bpy.context.scene.blender_xr
        session.transaction = session.grab = session.air_grab = session.axis_move = None

        session.command(bpy.context, 'RIG_SELECT_MESH')
        assert bpy.context.view_layer.objects.active == obj
        session.command(bpy.context, 'RIG_SELECT_ARMATURE')
        assert bpy.context.view_layer.objects.active == rig
        assert obj.select_get() and rig.select_get()
        session.command(bpy.context, 'RIG_BIND_EMPTY')
        assert obj.parent == rig
        assert obj.vertex_groups.active is not None
        assert obj.vertex_groups.active.name == rig.data.bones[0].name

        # Enter, exit and re-enter native armature Edit Mode while retaining
        # the target mesh. No extra desktop Shift-selection required.
        session.command(bpy.context, 'RIG_EDIT_TOGGLE')
        assert rig.mode == 'EDIT'
        session.command(bpy.context, 'BONE_SEL_ALL')
        session.command(bpy.context, 'RIG_EDIT_TOGGLE')
        assert rig.mode == 'OBJECT'
        session.command(bpy.context, 'RIG_WEIGHT')
        assert obj.mode == 'WEIGHT_PAINT'
        assert obj.vertex_groups.active is not None
        assert session.menu.page == 'WEIGHT_PAINT'
        session.command(bpy.context, 'WEIGHT_BRUSH')

        # Paint a ray at the cube's front surface onto the real native vertex
        # group, and verify Blender sees the resulting vertex weights.
        origin = Vector((0, -3, 0))
        direction = Vector((0, 1, 0))
        count = rigging_v076.paint_vertices(obj, origin, direction, 1.0, 0.6)
        assert count > 0, 'Controller brush could not reach mesh'
        group = obj.vertex_groups.active
        weighted = [vert.index for vert in obj.data.vertices
                    if any(item.group == group.index and item.weight > 0
                           for item in vert.groups)]
        assert weighted, 'Weight Paint did not write native vertex groups'
        # VR Probe reads the exact native active-group weight, never paints.
        from mathutils import Quaternion
        from mathutils import Vector as V
        before_sample = {
            v.index: tuple((item.group, item.weight) for item in v.groups)
            for v in obj.data.vertices
        }
        probe = rigging_v076.sample_vertex_weight(obj, origin, direction)
        assert probe is not None, 'VR Weight Probe should hit the skinned mesh'
        vertex_index, sampled_weight, sampled_group = probe
        assert sampled_group == group.name
        assert abs(sampled_weight - group.weight(vertex_index)) < 1e-7
        assert before_sample == {
            v.index: tuple((item.group, item.weight) for item in v.groups)
            for v in obj.data.vertices
        }, 'Read-only probe altered vertex groups'
        session.command(bpy.context, 'WEIGHT_SAMPLE')
        assert session.tool == 'WEIGHT_SAMPLE'
        aim = V((0, 0, -1)).rotation_difference(direction)
        # A center-face hit is equidistant to several cube vertices. Tiny
        # quaternion roundoff may select a different but equally near vertex,
        # so compare against the exact ray emitted by the controller.
        controller_probe = rigging_v076.sample_vertex_weight(
            obj, origin, aim @ V((0, 0, -1)))
        assert controller_probe is not None
        session.begin_tool(bpy.context, origin, aim)
        assert 'V' + str(controller_probe[0]) in session.status, session.status
        assert session.status.endswith('{:.4f}'.format(controller_probe[1]))
        assert session.tool == 'WEIGHT_SAMPLE'
        assert rigging_v076.sample_vertex_weight(
            obj, Vector((0, -3, 20)), direction) is None
        assert before_sample == {
            v.index: tuple((item.group, item.weight) for item in v.groups)
            for v in obj.data.vertices
        }
        session.command(bpy.context, 'WEIGHT_BRUSH')
        assert session.tool == 'WEIGHT_BRUSH'
        # Normal paint and erase actions remain operational after probing.
        count = rigging_v076.paint_vertices(obj, origin, direction, 1.0, 0.5, erase=True)
        assert count > 0

        # One held stroke with repeated samples produces one history item.
        # Undo and redo restore the exact active native group's assignments.
        def weights(vertex_group):
            return tuple(rigging_v076._vertex_weight(vertex_group, v.index)
                         for v in obj.data.vertices)

        before_stroke = weights(group)
        stroke = rigging_v076.WeightStroke(obj)
        for _ in range(3):
            assert rigging_v076.paint_vertices(
                obj, origin, direction, 1.5, .45, recorder=stroke) > 0
        changed = weights(group)
        assert changed != before_stroke
        entry = stroke.finish()
        assert entry[0] == 'WEIGHT_STROKE' and len(entry[4]) > 0
        history = xr_mesh.History()
        history.push(entry)
        assert len(history.undo) == 1
        assert history.step(True)
        assert weights(group) == before_stroke
        assert history.step(False)
        assert weights(group) == changed
        assert history.step(True)
        assert weights(group) == before_stroke

        # Interrupted stroke rolls back, without adding an undo entry.
        cancelled = rigging_v076.WeightStroke(obj)
        rigging_v076.paint_vertices(
            obj, origin, direction, 1.5, .55, recorder=cancelled)
        assert weights(group) != before_stroke
        cancelled.cancel()
        assert weights(group) == before_stroke
        assert len(history.undo) == 0

        # A previously unassigned vertex must become *unassigned* on Undo.
        absent = obj.vertex_groups.new(name='StrokeUnassignedTest')
        obj.vertex_groups.active_index = absent.index
        assert all(rigging_v076._vertex_weight(absent, v.index) is None
                   for v in obj.data.vertices)
        first_stroke = rigging_v076.WeightStroke(obj)
        rigging_v076.paint_vertices(
            obj, origin, direction, 1.5, .5, recorder=first_stroke)
        entry = first_stroke.finish()
        assert entry and any(before is None for _index, before, _after in entry[4])
        history.push(entry)
        assert history.step(True)
        assert all(rigging_v076._vertex_weight(absent, v.index) is None
                   for v in obj.data.vertices)
        assert history.step(False)
        assert any(rigging_v076._vertex_weight(absent, v.index) is not None
                   for v in obj.data.vertices)
        history.clear()
        obj.vertex_groups.remove(absent)
        obj.vertex_groups.active_index = group.index

        group.lock_weight = True
        try:
            rigging_v076.WeightStroke(obj)
            raise AssertionError('Locked group allowed painting')
        except ValueError:
            pass
        group.lock_weight = False

        session.command(bpy.context, 'WEIGHT_GROUP_NEXT')
        assert obj.vertex_groups.active is not None
        session.command(bpy.context, 'WEIGHT_STRENGTH_UP')
        session.command(bpy.context, 'WEIGHT_RADIUS_DOWN')
        session.command(bpy.context, 'RIG_EXIT_PAINT')
        assert obj.mode == 'OBJECT'
        before_weights = {v.index: tuple((item.group, round(item.weight, 4))
                                         for item in v.groups)
                          for v in obj.data.vertices}
        session.command(bpy.context, 'RIG_BIND_EMPTY')
        assert obj.parent == rig
        assert before_weights == {v.index: tuple(
            (item.group, round(item.weight, 4)) for item in v.groups
        ) for v in obj.data.vertices}, 'Repeated binding destroyed painted weights'

        # The mesh/rigger may now switch to Pose and back without manually
        # reconstructing a temporary multi-object selection.
        session.command(bpy.context, 'RIG_POSE')
        assert rig.mode == 'POSE'
        session.command(bpy.context, 'RIG_POSE')
        assert rig.mode == 'OBJECT'
        session.command(bpy.context, 'RIG_SELECT_MESH')
        assert bpy.context.view_layer.objects.active == obj
        session.command(bpy.context, 'RIG_SELECT_ARMATURE')
        assert bpy.context.view_layer.objects.active == rig
        session.command(bpy.context, 'RIG_CLEAN')
        assert bpy.context.view_layer.objects.active == obj
        assert obj.mode == 'OBJECT'

        # New creator scene focus isolates a bound mesh and its deform rig,
        # then restores an unrelated object's original visibility exactly.
        bpy.ops.mesh.primitive_cube_add(location=(6, 0, 0))
        unrelated = bpy.context.object
        unrelated.name = 'Focus unrelated'
        for selected in bpy.context.selected_objects:
            selected.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        state = focus_v080.FocusState()
        assert 'SCENE / ' in focus_v080.scene_pulse(bpy.context)
        assert state.isolate(bpy.context)
        assert unrelated.hide_get()
        assert not obj.hide_get() and not rig.hide_get()
        assert not state.isolate(bpy.context)
        assert not unrelated.hide_get()
        unrelated.hide_set(True)
        assert state.isolate(bpy.context)
        state.restore()
        assert unrelated.hide_get(), 'Original hidden state was lost'
        unrelated.hide_set(False)

        assert 'FOCUS_MENU' in [action for _, action in menus.PAGES['TRAVEL']]
        assert len(menus.PAGES['FOCUS_MENU']) <= 12
        for label, action in menus.PAGES['FOCUS_MENU']:
            assert drawing._ICON_BY_ACTION.get(action), (label, action)
        session.command(bpy.context, 'FOCUS_MENU')
        assert session.menu.page == 'FOCUS_MENU'
        session.command(bpy.context, 'FOCUS_STATS')
        assert 'SCENE / ' in session.status
        session.command(bpy.context, 'FOCUS_INPUT')
        assert session.status == 'INPUT / IDLE'
        session.command(bpy.context, 'BACK')
        assert session.menu.page == 'TRAVEL'

        # Original mesh editor still works after rigging has been active.
        for selected in bpy.context.selected_objects:
            selected.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        assert 'FINISHED' in bpy.ops.object.mode_set(mode='EDIT')
        assert obj.mode == 'EDIT'
        bpy.ops.object.mode_set(mode='OBJECT')

        assert len(menus.PAGES['RIGGING']) <= 12
        assert len(menus.PAGES['WEIGHT_PAINT']) <= 12
        assert 'WEIGHT_SAMPLE' in [a for _, a in menus.PAGES['WEIGHT_PAINT']]
        for page in ('RIGGING', 'WEIGHT_PAINT'):
            for _, action in menus.PAGES[page]:
                icon = drawing._ICON_BY_ACTION.get(action)
                assert icon and (Path(drawing.__file__).parent / 'icons' / (icon + '.png')).is_file(), (page, action)
        print('PASS v0.7.6 paired selection, bind, group, VR brush, mode coexistence')
    finally:
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        blender_xr.unregister()


if __name__ == '__main__':
    main()
