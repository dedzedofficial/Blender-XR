"""v0.7.5 asset audit, precision settings and starter rig regression checks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import blender_xr
from blender_xr import runtime, version, v075_features


def run():
    blender_xr.register()
    try:
        assert version.VERSION == (0, 7, 5)
        assert hasattr(bpy.ops.blender_xr, 'asset_audit')
        assert hasattr(bpy.ops.blender_xr, 'create_basic_rig')
        assert hasattr(bpy.ops.blender_xr, 'bind_auto_weights')
        assert hasattr(bpy.ops.blender_xr, 'weight_cleanup')
        assert 'precision_mode' in bpy.context.scene.blender_xr.bl_rna.properties

        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.object
        # Make an upright, non-degenerate mesh for the proportion-based starter rig.
        for vertex in obj.data.vertices:
            vertex.co.x *= 0.35
            vertex.co.y *= 0.3
            vertex.co.z *= 1.5
        bpy.context.view_layer.update()

        audit = v075_features.mesh_health(obj)
        assert audit['vertices'] == 8 and audit['faces'] == 6
        assert audit['triangles'] == 12
        assert audit['non_manifold_edges'] == 0
        assert audit['loose_vertices'] == 0
        assert audit['loose_edges'] == 0

        result = bpy.ops.blender_xr.create_basic_rig()
        assert 'FINISHED' in result, result
        armature = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
        assert len(armature.data.bones) >= 15
        assert bpy.context.view_layer.objects.active == obj

        # Weight cleanup is safe to call on an object with a small valid group.
        group = obj.vertex_groups.new(name='Mesh XR Test Group')
        group.add([0, 1, 2, 3], 0.25, 'REPLACE')
        obj.select_set(True)
        armature.select_set(False)
        bpy.context.view_layer.objects.active = obj
        result = bpy.ops.blender_xr.weight_cleanup()
        assert 'FINISHED' in result, result

        print('PASS Mesh XR v0.7.5 asset audit and starter rig')
    finally:
        blender_xr.unregister()


if __name__ == '__main__':
    run()
