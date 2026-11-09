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
