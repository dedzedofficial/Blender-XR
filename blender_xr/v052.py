# SPDX-License-Identifier: GPL-3.0-or-later
"""Small v0.5.2 quality-of-life helpers: object color, shading and scene stats."""
import bpy


def _editable_object(obj):
    if not obj or obj.type != 'MESH':
        raise ValueError('Select a mesh object first')
    if obj.library or obj.data.library:
        raise ValueError('Use a local mesh object')
    return obj


def apply_object_color(obj, color):
    """Apply one RGBA color without unexpectedly recoloring shared materials."""
    obj = _editable_object(obj)
    rgba = tuple(max(0.0, min(1.0, float(value))) for value in color[:4])
    if len(rgba) != 4:
        raise ValueError('Object color must contain RGBA values')

    material = obj.active_material
    if material is None:
        material = bpy.data.materials.new(name=obj.name + ' Color')
        if len(obj.material_slots):
            obj.active_material = material
        else:
            obj.data.materials.append(material)
    elif material.library or material.users > 1:
        material = material.copy()
        material.name = obj.name + ' Color'
        obj.active_material = material

    material.use_nodes = True
    material.diffuse_color = rgba
    principled = material.node_tree.nodes.get('Principled BSDF') if material.node_tree else None
    if principled:
        base = principled.inputs.get('Base Color')
        if base is not None:
            base.default_value = rgba
        alpha = principled.inputs.get('Alpha')
        if alpha is not None:
            alpha.default_value = rgba[3]
    obj.color = rgba
    return material


def set_shading(obj, smooth):
    obj = _editable_object(obj)
    for polygon in obj.data.polygons:
        polygon.use_smooth = bool(smooth)
    obj.data.update()
    return len(obj.data.polygons)


def scene_stats(context):
    """Return compact base-mesh statistics for visible objects in the current view layer."""
    visible = []
    for obj in context.view_layer.objects:
        try:
            shown = obj.visible_get(view_layer=context.view_layer)
        except TypeError:
            shown = obj.visible_get()
        if shown:
            visible.append(obj)

    meshes = [obj for obj in visible if obj.type == 'MESH']
    vertices = edges = faces = triangles = 0
    materials = set()
    for obj in meshes:
        data = obj.data
        vertices += len(data.vertices)
        edges += len(data.edges)
        faces += len(data.polygons)
        triangles += sum(max(0, len(poly.vertices) - 2) for poly in data.polygons)
        for slot in obj.material_slots:
            if slot.material:
                materials.add(slot.material.name_full)

    active = context.view_layer.objects.active
    active_stats = None
    if active and active.type == 'MESH' and active in visible:
        data = active.data
        active_stats = {
            'name': active.name,
            'vertices': len(data.vertices),
            'edges': len(data.edges),
            'faces': len(data.polygons),
            'triangles': sum(max(0, len(poly.vertices) - 2) for poly in data.polygons),
        }

    return {
        'objects': len(visible),
        'selected': sum(1 for obj in visible if obj.select_get()),
        'meshes': len(meshes),
        'vertices': vertices,
        'edges': edges,
        'faces': faces,
        'triangles': triangles,
        'materials': len(materials),
        'active': active_stats,
    }
