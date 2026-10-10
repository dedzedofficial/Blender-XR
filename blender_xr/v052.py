# SPDX-License-Identifier: GPL-3.0-or-later
"""v0.5.2 quality-of-life helpers: color/materials, shading and scene stats."""
import bpy
import bmesh


def _editable_object(obj):
    if not obj or obj.type != 'MESH':
        raise ValueError('Select a mesh object first')
    if obj.library or obj.data.library:
        raise ValueError('Use a local mesh object')
    return obj


def _rgba(color):
    rgba = tuple(max(0.0, min(1.0, float(value))) for value in color[:4])
    if len(rgba) != 4:
        raise ValueError('Object color must contain RGBA values')
    return rgba


def _set_material_color(material, rgba):
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
    return material


def _color_matches(material, rgba, epsilon=1e-4):
    if material is None:
        return False
    current = tuple(material.diffuse_color)
    return len(current) == 4 and all(abs(current[i] - rgba[i]) <= epsilon for i in range(4))


def _create_color_material(obj, rgba):
    material = bpy.data.materials.new(name=obj.name + ' Color')
    _set_material_color(material, rgba)
    obj.data.materials.append(material)
    obj.active_material_index = len(obj.material_slots) - 1
    return material, obj.active_material_index


def assign_color_to_selected_faces(obj, color):
    """Create/reuse a colored material and assign it only to selected edit-mode faces."""
    obj = _editable_object(obj)
    if obj.mode != 'EDIT':
        raise ValueError('Enter Face Edit Mode and select faces first')
    rgba = _rgba(color)
    bm = bmesh.from_edit_mesh(obj.data)
    faces = [face for face in bm.faces if face.is_valid and face.select and not face.hide]
    if not faces:
        raise ValueError('Select one or more faces first')

    material = None
    material_index = None
    for index, slot in enumerate(obj.material_slots):
        if _color_matches(slot.material, rgba):
            material = slot.material
            material_index = index
            break
    if material is None:
        material, material_index = _create_color_material(obj, rgba)

    for face in faces:
        face.material_index = material_index
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    obj.active_material_index = material_index
    return material, len(faces)


def apply_object_color(obj, color):
    """Apply color to an object, or only selected faces while in Edit Mode.

    In Object Mode this preserves the v0.5.2 behavior of recoloring the active
    object/material. In Edit Mode it creates or reuses a matching material slot
    and assigns that material to only the selected faces.
    """
    obj = _editable_object(obj)
    rgba = _rgba(color)

    if obj.mode == 'EDIT':
        material, _ = assign_color_to_selected_faces(obj, rgba)
        return material

    material = obj.active_material
    if material is None:
        material, _ = _create_color_material(obj, rgba)
    elif material.library or material.users > 1:
        material = material.copy()
        material.name = obj.name + ' Color'
        obj.active_material = material
        _set_material_color(material, rgba)
    else:
        _set_material_color(material, rgba)

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
