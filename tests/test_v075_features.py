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
        assert version.VERSION >= (0, 7, 5)
        # The v0.7.5 headset toolbar must expose functional rigging routes,
        # clear labels/tooltips, a separate tooltip strip and pickable gizmos.
        assert 'RIG_MENU' in {action for _label, action in menus.PAGES['TOOLS']}
        assert {'RIG_CREATE', 'RIG_BIND', 'RIG_WEIGHT', 'RIG_CLEAN',
                'RIG_POSE', 'RIG_AUDIT'} <= {
                    action for _label, action in menus.PAGES['RIGGING']}
        assert 'RIGGING' in v065.CORE_PAGES
        assert 'DEFAULT_CLOSED' in getattr(v075_features.BXR_PT_workflow, 'bl_options', set()), 'Compact UI keeps the advanced workflow folded'
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
        # Deliberately wide, non-humanoid object: a normal armature must work.
        for vertex in obj.data.vertices:
            vertex.co.x *= 3.0
            vertex.co.y *= 0.6
            vertex.co.z *= 0.15
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
        armature = bpy.context.view_layer.objects.active
        assert armature.type == 'ARMATURE'
        assert len(armature.data.bones) == 1
        assert armature.data.bones[0].name == 'Bone'
        assert armature.show_in_front
        assert obj.select_get(), 'Selected mesh must remain selected for binding'

        assert 'FINISHED' in bpy.ops.blender_xr.add_bone()
        assert len(armature.data.bones) == 2
        assert 'FINISHED' in bpy.ops.blender_xr.edit_bones()
        assert armature.mode == 'EDIT'
        assert 'FINISHED' in bpy.ops.blender_xr.add_bone()
        assert len(armature.data.edit_bones) == 3
        assert 'FINISHED' in bpy.ops.blender_xr.finish_bones()
        assert len(armature.data.bones) == 3

        # Manual binding generates bone-named groups without painted weights.
        assert 'FINISHED' in bpy.ops.blender_xr.bind_empty_weights()
        assert obj.parent == armature
        assert all(bone.name in obj.vertex_groups for bone in armature.data.bones
                   if bone.use_deform)
        assert any(mod.type == 'ARMATURE' and mod.object == armature
                   for mod in obj.modifiers)
        for group in obj.vertex_groups:
            assert all(group.index not in {item.group for item in vertex.groups}
                       for vertex in obj.data.vertices), group.name

        # The mesh can now be weight-painted without automatic weights.
        armature.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        assert 'FINISHED' in bpy.ops.blender_xr.weight_paint()
        assert obj.mode == 'WEIGHT_PAINT'
        bpy.ops.object.mode_set(mode='OBJECT')

        # Weight cleanup remains available after painting.
        group = obj.vertex_groups.get('Bone')
        group.add([0, 1, 2, 3], 0.25, 'REPLACE')
        result = bpy.ops.blender_xr.weight_cleanup()
        assert 'FINISHED' in result, result
        assert bpy.context.view_layer.objects.active == obj
        assert obj.select_get()

        # Flat meshes are no longer rejected as failed humanoid preflight.
        bpy.ops.mesh.primitive_plane_add()
        plane = bpy.context.object
        original_armatures = sum(1 for item in bpy.context.scene.objects
                                 if item.type == 'ARMATURE')
        assert 'FINISHED' in bpy.ops.blender_xr.create_basic_rig()
        plane_rig = bpy.context.view_layer.objects.active
        assert len(plane_rig.data.bones) == 1
        assert sum(1 for item in bpy.context.scene.objects if item.type == 'ARMATURE') == original_armatures + 1
        bpy.data.objects.remove(plane_rig, do_unlink=True)
        bpy.data.objects.remove(plane, do_unlink=True)

        # No active mesh is also valid: create a freeform armature at the cursor.
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = None
        assert 'FINISHED' in bpy.ops.blender_xr.create_basic_rig()
        cursor_rig = bpy.context.view_layer.objects.active
        assert cursor_rig.type == 'ARMATURE'
        assert len(cursor_rig.data.bones) == 1
        bpy.data.objects.remove(cursor_rig, do_unlink=True)

        print('PASS Mesh XR v0.7.6 freeform armature, manual weights and asset audit')
    finally:
        blender_xr.unregister()


if __name__ == '__main__':
    run()
