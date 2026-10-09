# SPDX-License-Identifier: GPL-3.0-or-later
"""Create ordinary editable Blender meshes; no desktop-only modeling workflow."""
import bpy

KINDS = ('CUBE', 'SPHERE', 'CYLINDER', 'CONE', 'TORUS', 'PLANE')


def add(context, kind, location, size):
    if kind not in KINDS:
        raise ValueError('Unknown primitive')
    if context.mode not in {'OBJECT', 'EDIT_MESH'} or len(context.objects_in_mode) > 1:
        raise ValueError('Use object mode or a single mesh edit mode')
    if context.object and context.object.mode == 'EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for obj in context.selected_objects:
        obj.select_set(False)
    common = dict(location=location, enter_editmode=False, align='WORLD')
    if kind == 'CUBE':
        bpy.ops.mesh.primitive_cube_add(size=size, **common)
    elif kind == 'SPHERE':
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=size/2, **common)
    elif kind == 'CYLINDER':
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=size/2, depth=size, **common)
    elif kind == 'CONE':
        bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=size/2, radius2=0, depth=size, **common)
    elif kind == 'TORUS':
        bpy.ops.mesh.primitive_torus_add(major_segments=32, minor_segments=12,
                                       major_radius=size*0.35, minor_radius=size*0.15,
                                       location=location, align='WORLD')
    else:
        bpy.ops.mesh.primitive_plane_add(size=size, **common)
    obj = context.view_layer.objects.active
    obj.name = 'XR ' + kind.title()
    return obj
