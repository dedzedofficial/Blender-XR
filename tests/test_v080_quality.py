"""Blender integration checks for Mesh XR v0.8 quality, calibration and recovery."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy
from mathutils import Vector, Quaternion
import blender_xr
from blender_xr import quality_v080, recovery_v080, interaction_v076, rigging_v076


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
