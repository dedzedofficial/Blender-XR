# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
import bmesh
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender_xr import v052


def clear_scene():
    bpy.ops.object.mode_set(mode='OBJECT') if bpy.context.object and bpy.context.object.mode != 'OBJECT' else None
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


clear_scene()
bpy.ops.mesh.primitive_cube_add()
obj = bpy.context.active_object

stats = v052.scene_stats(bpy.context)
assert stats['objects'] == 1
assert stats['selected'] == 1
assert stats['meshes'] == 1
assert stats['vertices'] == 8
assert stats['edges'] == 12
assert stats['faces'] == 6
assert stats['triangles'] == 12
assert stats['active']['triangles'] == 12

material = v052.apply_object_color(obj, (0.25, 0.5, 0.75, 1.0))
assert obj.active_material == material
assert tuple(round(v, 4) for v in material.diffuse_color) == (0.25, 0.5, 0.75, 1.0)
assert tuple(round(v, 4) for v in obj.color) == (0.25, 0.5, 0.75, 1.0)
principled = material.node_tree.nodes.get('Principled BSDF')
assert principled is not None
assert tuple(round(v, 4) for v in principled.inputs['Base Color'].default_value) == (0.25, 0.5, 0.75, 1.0)

v052.set_shading(obj, True)
assert all(poly.use_smooth for poly in obj.data.polygons)
v052.set_shading(obj, False)
assert not any(poly.use_smooth for poly in obj.data.polygons)

# Real requested workflow: orange cone with a grey base using selected-face material assignment.
clear_scene()
bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=1.0, radius2=0.0, depth=2.0)
cone = bpy.context.active_object
orange = v052.apply_object_color(cone, (1.0, 0.25, 0.02, 1.0))
orange_index = cone.active_material_index
assert len(cone.material_slots) == 1

bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(cone.data)
for face in bm.faces:
    face.select_set(face.normal.z < -0.9)
bmesh.update_edit_mesh(cone.data, loop_triangles=False, destructive=False)
grey = v052.apply_object_color(cone, (0.25, 0.25, 0.25, 1.0))
assert grey != orange
assert len(cone.material_slots) == 2
grey_index = cone.active_material_index
assert grey_index != orange_index
bpy.ops.object.mode_set(mode='OBJECT')
base_faces = [poly for poly in cone.data.polygons if poly.normal.z < -0.9]
side_faces = [poly for poly in cone.data.polygons if poly.normal.z >= -0.9]
assert len(base_faces) == 1
assert all(poly.material_index == grey_index for poly in base_faces)
assert all(poly.material_index == orange_index for poly in side_faces)

# Reusing the same grey should reuse the existing material slot instead of making duplicates.
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(cone.data)
for face in bm.faces:
    face.select_set(face.normal.z < -0.9)
bmesh.update_edit_mesh(cone.data, loop_triangles=False, destructive=False)
v052.apply_object_color(cone, (0.25, 0.25, 0.25, 1.0))
assert len(cone.material_slots) == 2
bpy.ops.object.mode_set(mode='OBJECT')

bpy.ops.mesh.primitive_plane_add(location=(3, 0, 0))
stats = v052.scene_stats(bpy.context)
assert stats['objects'] == 2
assert stats['meshes'] == 2
assert stats['materials'] == 2

print('PASS v0.5.2 object color, per-face materials, shading and scene statistics')
