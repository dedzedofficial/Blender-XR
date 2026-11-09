"""Blender integration checks for Mesh XR v0.8 quality, calibration and recovery."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy
from mathutils import Vector, Quaternion
import blender_xr
from blender_xr import quality_v080, recovery_v080, interaction_v076, rigging_v076, input_ownership_v080


def run():
    blender_xr.register()
    try:
        settings = bpy.context.scene.blender_xr
        assert settings.recovery_enabled
        assert settings.recovery_keep >= 1
        settings.hand_offset_x = .028
        bpy.ops.blender_xr.reset_hand_calibration()
        assert settings.hand_offset_x == 0 and settings.hand_scale == 1.0

        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        original = [tuple(v.co) for v in obj.data.vertices]
        names = set(bpy.data.objects.keys())
        findings = quality_v080.pre_export_findings(obj, 2)
        assert any('Triangles' in t for _, t in findings), findings
        assert [tuple(v.co) for v in obj.data.vertices] == original
        assert set(bpy.data.objects.keys()) == names

        # Weight audit must count positive influences, not zero-weight entries.
        bpy.ops.object.armature_add()
        rig = bpy.context.object
        rig.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        arm = obj.modifiers.new('Quality test armature', 'ARMATURE')
        arm.object = rig
        for index in range(5):
            group = obj.vertex_groups.new(name='Quality group %d' % index)
            group.add([0], 0.2, 'REPLACE')
        findings = quality_v080.pre_export_findings(obj)
        assert ('WARNING', '7 unweighted vertices') in findings, findings
        assert ('WARNING', '1 vertices have more than 4 influences') in findings, findings
        # Zero-weight entries are deliberately excluded from influence counts.
        zero_group = obj.vertex_groups.new(name='Quality zero weight')
        zero_group.add([1], 0.0, 'REPLACE')
        findings = quality_v080.pre_export_findings(obj)
        assert ('WARNING', '7 unweighted vertices') in findings, findings
        assert ('WARNING', '1 vertices have more than 4 influences') in findings, findings

        # A full held-trigger stroke is one atomic history entry. Verify
        # absent group assignments are restored as *absent*, not zero.
        from blender_xr import mesh
        paint_group = obj.vertex_groups.get('Quality group 0')
        obj.vertex_groups.active_index = paint_group.index
        def weight_at(index):
            return rigging_v076._vertex_weight(paint_group, index)

        assert weight_at(2) is None and weight_at(3) is None
        history = mesh.History()
        stroke = rigging_v076.WeightStroke(obj)
        for index, value in ((2, .25), (3, .8), (2, .65)):
            stroke.record(index)
            rigging_v076._write_weight(paint_group, index, value)
        entry = stroke.finish()
        assert entry is not None and len(entry[4]) == 2
        history.push(entry)
        assert len(history.undo) == 1 and not history.redo
        for _ in range(30):
            assert history.step(True)
            assert weight_at(2) is None and weight_at(3) is None
            assert history.step(False)
            assert abs(weight_at(2) - .65) < 1e-5
            assert abs(weight_at(3) - .8) < 1e-5
        assert len(history.undo) == 1 and not history.redo

        # An interrupted stroke must restore its exact prior assignments
        # without adding a history entry or altering the previous stroke.
        cancelled = rigging_v076.WeightStroke(obj)
        cancelled.record(2)
        cancelled.record(4)
        rigging_v076._write_weight(paint_group, 2, .12)
        rigging_v076._write_weight(paint_group, 4, .55)
        cancelled.cancel()
        assert abs(weight_at(2) - .65) < 1e-5
        assert weight_at(4) is None
        assert len(history.undo) == 1

        # Stale weights cannot be overwritten by XR Undo: detect the
        # conflicting external edit before changing either touched vertex.
        rigging_v076._write_weight(paint_group, 3, .33)
        try:
            history.step(True)
        except ValueError as exc:
            assert 'outside XR history' in str(exc)
        else:
            raise AssertionError('Stale paint history overwrote external weights')
        assert abs(weight_at(2) - .65) < 1e-5
        assert abs(weight_at(3) - .33) < 1e-5
        assert len(history.undo) == 1 and not history.redo
        rigging_v076._write_weight(paint_group, 3, .8)
        assert history.step(True)
        assert weight_at(2) is None and weight_at(3) is None
        history.clear()

        bpy.ops.blender_xr.measure()
        assert 'dimensions' in settings.status
        bpy.ops.blender_xr.export_check()
        assert 'export finding' in settings.status

        settings.fine_grab_enabled = True
        settings.fine_grab_factor = .20
        obj.location = (0, 0, 0)
        drag = interaction_v076.begin_transform(bpy.context, 'MOVE',
                                                (0, 0, 0), Quaternion())
        assert abs(drag['fine_factor'] - .20) < 1e-5
        interaction_v076.update_transform(bpy.context, drag, Vector((1, 0, 0)), Quaternion())
        assert abs(obj.matrix_world.translation.x - .20) < 1e-4
        interaction_v076.restore_transform(bpy.context, drag)
        assert abs(obj.location.x) < 1e-4

        bpy.ops.blender_xr.object_lock()
        assert obj.hide_select
        try:
            interaction_v076.begin_transform(bpy.context, 'MOVE',
                                            (0, 0, 0), Quaternion())
        except ValueError as exc:
            assert 'locked' in str(exc).lower()
        else:
            raise AssertionError('Locked object unexpectedly transformed')
        bpy.ops.blender_xr.object_lock()
        assert not obj.hide_select

        # A checkpoint removed between glob and stat must not break UI/poll.
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            older = folder / 'meshxr-old.blend'
            newer = folder / 'meshxr-new.blend'
            older.write_bytes(b'old')
            newer.write_bytes(b'new')
            original_stat = Path.stat

            def stat_with_missing(path, *args, **kwargs):
                if path == older:
                    raise FileNotFoundError(str(path))
                return original_stat(path, *args, **kwargs)

            with patch.object(recovery_v080, 'folder', return_value=folder):
                with patch.object(Path, 'stat', stat_with_missing):
                    assert recovery_v080.checkpoints() == [newer]
                assert set(recovery_v080.checkpoints()) == {older, newer}

        # Shared menu/recovery ownership arbitration is deterministic and
        # must refuse checkpoints during a held stroke or lost tracking.
        from types import SimpleNamespace
        owner = input_ownership_v080.owner
        stub = SimpleNamespace()
        assert owner(stub) == 'IDLE'
        stub._weight_stroke = object()
        assert owner(stub) == 'WEIGHT_STROKE'
        assert input_ownership_v080.is_editing(stub)
        stub.radial = SimpleNamespace(active=True)
        # Both an active stroke and radial menu are an input conflict, never
        # permission to dispatch a new edit or silently overwrite weights.
        assert owner(stub) == 'CONFLICT'
        try:
            input_ownership_v080.validate_command(stub, 'SAVE')
        except ValueError:
            pass
        else:
            raise AssertionError('Conflicting owners were allowed to save')
        stub._weight_stroke = None
        # Every live manipulation conflicts with radial capture. These
        # regressions exercise the pure arbitration rule without hardware.
        for field in ('_xr_gesture', 'transaction', 'two_hand_scale',
                      'axis_move', 'axis_drag', 'grab', 'air_grab', 'bone_drag'):
            setattr(stub, field, object())
            assert owner(stub) == 'CONFLICT', field
            stub._xr_command_source = 'RADIAL'
            try:
                input_ownership_v080.validate_command(stub, 'SAVE')
            except ValueError:
                pass
            else:
                raise AssertionError('Radial bypassed active ' + field)
            stub._xr_command_source = None
            setattr(stub, field, None)
        assert owner(stub) == 'RADIAL'
        try:
            input_ownership_v080.validate_command(stub, 'MODE')
        except ValueError:
            pass
        else:
            raise AssertionError('Uncaptured edit was allowed during radial input')
        stub._xr_command_source = 'RADIAL'
        input_ownership_v080.validate_command(stub, 'MODE')
        stub._xr_command_source = None
        stub.radial.active = False
        stub._weight_stroke = object()
        stub._xr_rearm_required = True
        assert owner(stub) == 'REARM'
        stub._xr_rearm_required = False
        stub._weight_stroke = None
        stub.transaction = object()
        assert owner(stub) == 'MESH_EDIT'
        stub.transaction = None
        # Conflicting non-radial owners must also be refused, not silently
        # resolved by the first matching legacy handler.
        stub.grab = object()
        stub.bone_drag = object()
        assert owner(stub) == 'CONFLICT'
        try:
            input_ownership_v080.validate_command(stub, 'UNDO')
        except ValueError:
            pass
        else:
            raise AssertionError('Overlapping grab and bone edit allowed Undo')
        # A conflicting tick must cancel once, reset radial capture, and
        # require release before any held control can restart the edit.
        cancelled = []
        radial_resets = []
        stub.radial.reset = lambda require_release=False: radial_resets.append(require_release)
        stub.cancel_work = lambda: (cancelled.append(True), setattr(stub, 'grab', None),
                                    setattr(stub, 'bone_drag', None))
        assert input_ownership_v080.cancel_conflict(stub)
        assert radial_resets == [True]
        assert cancelled == [True]
        assert stub._xr_rearm_required
        assert 'REARM' in stub.status
        assert owner(stub) == 'REARM'
        assert not input_ownership_v080.cancel_conflict(stub)
        assert cancelled == [True]
        # A session stop while grabbing or painting must roll back once.
        # It cannot rely on the pose-loss handler, which may never run.
        stub._xr_rearm_required = False
        stub.grab = object()
        stub.bone_drag = None
        assert input_ownership_v080.cancel_session_loss(stub)
        assert cancelled == [True, True]
        assert radial_resets == [True, True]
        assert stub._xr_rearm_required
        assert owner(stub) == 'REARM'
        assert not input_ownership_v080.cancel_session_loss(stub)
        assert cancelled == [True, True]
        stub._xr_rearm_required = False
        stub._weight_stroke = object()
        stub.cancel_work = lambda: (cancelled.append('stroke'), setattr(stub, '_weight_stroke', None))
        assert input_ownership_v080.cancel_session_loss(stub)
        assert cancelled[-1] == 'stroke'
        assert stub._xr_rearm_required
        # The rearm latch is not proof that every legacy handler released
        # its gesture. A late-running handler must still be rolled back.
        stub._weight_stroke = object()
        assert owner(stub) == 'REARM'
        assert input_ownership_v080.cancel_session_loss(stub)
        assert cancelled[-1] == 'stroke'
        assert stub._weight_stroke is None
        assert not input_ownership_v080.cancel_session_loss(stub)
        # Also cover a late object grab under the same latch.
        stub.grab = object()
        stub.cancel_work = lambda: (cancelled.append('grab'), setattr(stub, 'grab', None))
        assert input_ownership_v080.cancel_session_loss(stub)
        assert cancelled[-1] == 'grab'
        assert not input_ownership_v080.cancel_session_loss(stub)
        # Invalid pose and pose-read exceptions share an idempotent rollback
        # path, including late gestures while already awaiting neutral input.
        stub._xr_rearm_required = False
        stub.grab = None
        before = len(cancelled)
        assert not input_ownership_v080.cancel_tracking_loss(stub)
        assert stub._xr_rearm_required
        assert len(cancelled) == before
        assert radial_resets[-1] is True
        assert not input_ownership_v080.cancel_tracking_loss(stub)
        assert len(cancelled) == before
        stub.grab = object()
        assert input_ownership_v080.cancel_tracking_loss(stub)
        assert cancelled[-1] == 'grab'
        assert stub.grab is None
        assert not input_ownership_v080.cancel_tracking_loss(stub)
        assert len(cancelled) == before + 1
        stub._xr_rearm_required = False
        stub.grab = object()
        stub.bone_drag = None
        assert owner(stub) == 'OBJECT_GRAB'
        stub.two_hand_scale = object()
        assert owner(stub) == 'TWO_HAND_SCALE'
        stub.grab = None
        stub.two_hand_scale = None
        stub.transaction = object()
        stub.axis_drag = object()
        assert owner(stub) == 'MESH_EDIT'
        stub.transaction = None
        assert owner(stub) == 'AXIS_TRANSFORM'
        stub.axis_drag = None
        assert owner(stub) == 'IDLE'
        assert 'INPUT / IDLE' == input_ownership_v080.diagnostic(stub)
        assert blender_xr.runtime.Runtime._v080_command_guard_patched
        input_ownership_v080.validate_command(stub, 'SAVE')
        stub._xr_rearm_required = True
        input_ownership_v080.validate_command(stub, 'FOCUS_INPUT')
        input_ownership_v080.validate_command(stub, 'FOCUS_STATS')
        try:
            input_ownership_v080.validate_command(stub, 'SAVE')
        except ValueError as exc:
            assert 'rearm' in str(exc).lower()
        else:
            raise AssertionError('Save was allowed before controller rearm')
        stub._xr_rearm_required = False

        # Exercise the actual command wrapper, not only the pure permission
        # function. A blocked command must have no effect on scene data.
        guarded = blender_xr.runtime.Runtime.__new__(blender_xr.runtime.Runtime)
        guarded.menu = SimpleNamespace(page='FOCUS_MENU')
        guarded.status = 'BEFORE'
        guarded._weight_stroke = object()
        original_vertex = tuple(obj.data.vertices[0].co)
        try:
            guarded.command(bpy.context, 'FOCUS_ISOLATE')
        except ValueError as exc:
            assert 'weight stroke' in str(exc).lower()
        else:
            raise AssertionError('Active brush stroke allowed a visibility edit')
        assert guarded.status == 'BEFORE'
        assert tuple(obj.data.vertices[0].co) == original_vertex
        guarded.command(bpy.context, 'FOCUS_INPUT')
        assert guarded.status == 'INPUT / WEIGHT STROKE'
        assert guarded._weight_stroke is not None, (
            'Read-only Input State must not discard an active paint stroke')
        guarded.command(bpy.context, 'FOCUS_STATS')
        assert guarded._weight_stroke is not None, (
            'Read-only Scene Pulse must not discard an active paint stroke')

        assert recovery_v080.safe_to_save(bpy.context) is False, 'Headless test cannot checkpoint'
        assert settings.recovery_enabled
        cache_a = rigging_v076.cached_weight_tree(obj)
        cache_b = rigging_v076.cached_weight_tree(obj)
        assert cache_a is cache_b, 'Rapid brush samples must reuse spatial lookup'
        assert len(obj.data.vertices) == 8
        print('PASS 0.8 read-only checks, measurement, fine grab, lock, calibration, safe recovery guard and brush cache')
    finally:
        blender_xr.unregister()


if __name__ == '__main__':
    run()
