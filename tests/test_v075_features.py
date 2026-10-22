"""v0.7.5 asset audit, precision settings and starter rig regression checks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import bmesh
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
        assert hasattr(bpy.ops.blender_xr, 'weight_paint')
        assert 'haptic_feedback' in bpy.context.scene.blender_xr.bl_rna.properties
        assert runtime.haptic_pulse(bpy.context, bpy.context.scene.blender_xr, 0) is False
        assert 'precision_mode' in bpy.context.scene.blender_xr.bl_rna.properties
        assert 'triangle_budget' in bpy.context.scene.blender_xr.bl_rna.properties
        # Uniform scaling preserves the matrix origin; two-hand scaling adds midpoint translation.
        from mathutils import Matrix, Vector
        before = Matrix.Translation(Vector((1.0, 2.0, 3.0)))
        scaled = runtime.uniform_scaled(before, 2.0)
        assert (scaled.translation - Vector((1.0, 2.0, 3.0))).length < 1e-6

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
        assert audit['boundary_edges'] == 0
        assert audit['loose_vertices'] == 0
        assert audit['loose_edges'] == 0

        # An open plane should be reported as boundary edges, not as edges
        # shared by too many faces.
        bpy.ops.mesh.primitive_plane_add()
        plane = bpy.context.object
        plane_audit = v075_features.mesh_health(plane)
        assert plane_audit['boundary_edges'] == 4
        assert plane_audit['non_manifold_edges'] == 0
        bpy.data.objects.remove(plane, do_unlink=True)

        # Three faces sharing one edge must report one true non-manifold edge.
        bm = bmesh.new()
        v0 = bm.verts.new((0, 0, 0))
        v1 = bm.verts.new((1, 0, 0))
        v2 = bm.verts.new((0, 1, 0))
        v3 = bm.verts.new((0, -1, 0))
        v4 = bm.verts.new((0, 0, 1))
        bm.faces.new((v0, v1, v2))
        bm.faces.new((v1, v0, v3))
        bm.faces.new((v0, v1, v4))
        bad_mesh = bpy.data.meshes.new('Mesh XR non-manifold audit test')
        bm.to_mesh(bad_mesh)
        bm.free()
        bad_obj = bpy.data.objects.new('Mesh XR non-manifold audit test', bad_mesh)
        bpy.context.collection.objects.link(bad_obj)
        bad_audit = v075_features.mesh_health(bad_obj)
        assert bad_audit['non_manifold_edges'] == 1
        assert bad_audit['boundary_edges'] == 6
        bpy.data.objects.remove(bad_obj, do_unlink=True)
        bpy.data.meshes.remove(bad_mesh)

        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        result = bpy.ops.blender_xr.create_basic_rig()
        assert 'FINISHED' in result, result
        armature = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
        expected_bones = {
            'root', 'pelvis', 'spine', 'chest', 'neck', 'head',
            'upper_arm.L', 'forearm.L', 'hand.L',
            'upper_arm.R', 'forearm.R', 'hand.R',
            'thigh.L', 'shin.L', 'foot.L', 'thigh.R', 'shin.R', 'foot.R',
        }
        assert expected_bones <= {bone.name for bone in armature.data.bones}
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
