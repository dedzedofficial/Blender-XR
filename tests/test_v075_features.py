"""v0.7.5 asset audit, precision settings and starter rig regression checks."""
import sys
import struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import bmesh
import blender_xr
from blender_xr import drawing, gizmo, menus, runtime, version, v065, v075_features


def run():
    blender_xr.register()
    try:
        assert version.VERSION == (0, 7, 5)
        # The v0.7.5 headset toolbar must expose functional rigging routes,
        # clear labels/tooltips, a separate tooltip strip and pickable gizmos.
        assert 'RIG_MENU' in {action for _label, action in menus.PAGES['TOOLS']}
        assert {'RIG_CREATE', 'RIG_BIND', 'RIG_WEIGHT', 'RIG_CLEAN',
                'RIG_POSE', 'RIG_AUDIT'} <= {
                    action for _label, action in menus.PAGES['RIGGING']}
        assert 'RIGGING' in v065.CORE_PAGES
        assert 'DEFAULT_CLOSED' not in getattr(v075_features.BXR_PT_workflow, 'bl_options', set())
        assert {'RIG_MENU', 'RIG_CREATE', 'RIG_BIND', 'RIG_WEIGHT',
                'RIG_CLEAN', 'RIG_POSE', 'RIG_AUDIT'} <= set(v065.TOOLTIPS)
        assert drawing.button_rect(0)[2] >= 0.19
        # Official Blender SVG sources are shipped with their generated transparent
        # PNG textures; the VR renderer uses the packaged PNGs, not drawn glyphs.
        icon_dir = Path(drawing.__file__).resolve().parent / "icons"
        source_dir = Path(drawing.__file__).resolve().parent / "icons_src"
        expected_icons = set(drawing._ICON_BY_ACTION.values()) - {None}
        # Every mapped texture must ship both the original SVG and its generated PNG.
        assert all((icon_dir / (name + ".png")).is_file() for name in expected_icons)
        assert all((source_dir / (name + ".svg")).is_file() for name in expected_icons)
        # Every packaged icon must be a readable PNG rasterized at the current
        # high-resolution target, not an empty placeholder or stale lower-resolution texture.
        for name in expected_icons:
            png = icon_dir / (name + ".png")
            with png.open("rb") as handle:
                header = handle.read(24)
            assert header[:8] == b"\x89PNG\r\n\x1a\n", name
            width, height = struct.unpack(">II", header[16:24])
            assert (width, height) == (256, 256), (name, width, height)
        # Rigging actions deliberately use Blender's armature, modifier, weight and pose icons.
        assert drawing._ICON_BY_ACTION["RIG_CREATE"] == "armature_data"
        assert drawing._ICON_BY_ACTION["RIG_BIND"] == "mod_armature"
        assert drawing._ICON_BY_ACTION["RIG_WEIGHT"] == "mod_vertex_weight"
        assert drawing._ICON_BY_ACTION["RIG_POSE"] == "pose_hlt"
        assert drawing._ICON_BY_ACTION["RIG_AUDIT"] == "mesh_data"
        # Every declared page action must have an icon mapping (PANEL is intentionally blank).
        page_actions = {action for page in menus.PAGES.values()
                        for _label, action in page}
        assert page_actions <= set(drawing._ICON_BY_ACTION), page_actions - set(drawing._ICON_BY_ACTION)
        from mathutils import Vector
        vr_menu = drawing.Menu()
        vr_menu.page = 'TOOLS'
        vr_menu.ready = True
        vr_menu.center = Vector((0, 0, 0))
        vr_menu.right = Vector((1, 0, 0))
        vr_menu.up = Vector((0, 1, 0))
        vr_menu.normal = Vector((0, 0, 1))
        vr_menu.scale = 1.0
        bx, by, bw, bh = drawing.button_rect(0)
        action, _hit_point = vr_menu.hit(
            Vector((bx + bw * 0.5, by + bh * 0.5, 1.0)), Vector((0, 0, -1)))
        assert action == 'MODE_MENU', action
        assert "ty=0.247" in Path(v065.__file__).read_text(encoding='utf-8')
        # A controller ray slightly off the drawn axis should still acquire a
        # handle; this models normal headset aiming variance.
        handle = gizmo.Handles((0, 0, 0), [('X', (1, 0, 0))], 1.0, (0, 0, 5))
        assert handle.pick((0.15, 0.06, 1.0), (0, 0, -1.0)) is not None
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
        # Two-hand scaling keeps the object's midpoint relationship consistent.
        pivot = Vector((0.0, 0.0, 0.0))
        moved_midpoint = Vector((2.0, 0.0, 0.0))
        scaled_around_pivot = runtime.two_hand_scaled(before, pivot, moved_midpoint, 2.0)
        assert (scaled_around_pivot.translation - Vector((4.0, 4.0, 6.0))).length < 1e-6

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
        assert audit['base_triangles'] == 12
        assert audit['evaluated_triangles'] == 12

        # Modifier evaluation must contribute to the triangle budget report.
        subdivision = obj.modifiers.new('Mesh XR audit subdivision test', 'SUBSURF')
        subdivision.levels = 1
        bpy.context.view_layer.update()
        evaluated_audit = v075_features.mesh_health(obj)
        assert evaluated_audit['base_triangles'] == 12
        assert evaluated_audit['evaluated_triangles'] is not None
        assert evaluated_audit['evaluated_triangles'] > evaluated_audit['base_triangles']
        assert evaluated_audit['triangles'] == evaluated_audit['evaluated_triangles']
        obj.modifiers.remove(subdivision)
        bpy.context.view_layer.update()
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
        assert bpy.context.view_layer.objects.active == obj
        assert obj.select_get()

        # Failed rig preflight must not strand selection or leave a partial armature.
        bpy.ops.mesh.primitive_plane_add()
        invalid = bpy.context.object
        original_armatures = sum(1 for item in bpy.context.scene.objects if item.type == 'ARMATURE')
        try:
            result = bpy.ops.blender_xr.create_basic_rig()
            assert 'CANCELLED' in result, result
        except RuntimeError as exc:
            # Blender background mode may raise for an operator that reports an error.
            assert 'Starter rig creation failed' in str(exc), str(exc)
        assert bpy.context.view_layer.objects.active == invalid
        assert list(bpy.context.selected_objects) == [invalid]
        assert sum(1 for item in bpy.context.scene.objects if item.type == 'ARMATURE') == original_armatures
        bpy.data.objects.remove(invalid, do_unlink=True)
        obj.select_set(True)
        armature.select_set(False)
        bpy.context.view_layer.objects.active = obj

        print('PASS Mesh XR v0.7.5 asset audit and starter rig')
    finally:
        blender_xr.unregister()


if __name__ == '__main__':
    run()
