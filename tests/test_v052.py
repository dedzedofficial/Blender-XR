# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
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

bpy.ops.mesh.primitive_plane_add(location=(3, 0, 0))
stats = v052.scene_stats(bpy.context)
assert stats['objects'] == 2
assert stats['meshes'] == 2
assert stats['vertices'] == 12
assert stats['edges'] == 16
assert stats['faces'] == 7
assert stats['triangles'] == 14
assert stats['materials'] == 1

print('PASS v0.5.2 object color, shading and scene statistics')
