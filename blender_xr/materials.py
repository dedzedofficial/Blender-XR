# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared material helpers for Blender XR."""
import bpy
import bmesh


def editable_mesh_object(obj):
    if not obj or obj.type != 'MESH':
        raise ValueError('Select a mesh object first')
    if obj.library or obj.data.library:
        raise ValueError('Use a local mesh object')
    return obj


def rgba(color):
    values = tuple(max(0.0, min(1.0, float(value))) for value in color[:4])
    if len(values) != 4:
        raise ValueError('Color must contain RGBA values')
    return values


def set_material_color(material, color):
    color = rgba(color)
    material.use_nodes = True
    material.diffuse_color = color
    principled = material.node_tree.nodes.get('Principled BSDF') if material.node_tree else None
    if principled:
        base = principled.inputs.get('Base Color')
        if base is not None:
            base.default_value = color
        alpha = principled.inputs.get('Alpha')
        if alpha is not None:
            alpha.default_value = color[3]
    return material


def material_color(material):
    if not material:
        return None
    if material.use_nodes and material.node_tree:
        principled = material.node_tree.nodes.get('Principled BSDF')
        if principled:
            base = principled.inputs.get('Base Color')
            if base is not None:
                return tuple(float(v) for v in base.default_value[:4])
    return tuple(float(v) for v in material.diffuse_color[:4])


def colors_match(a, b, epsilon=1e-4):
    return a is not None and b is not None and all(abs(float(x)-float(y)) <= epsilon for x, y in zip(a, b))


def matching_slot(obj, color):
    wanted = rgba(color)
    for index, slot in enumerate(obj.material_slots):
        material = slot.material
        if material and colors_match(material_color(material), wanted):
            return index, material
    return None, None


def create_material(obj, color, name=None):
    obj = editable_mesh_object(obj)
    material = bpy.data.materials.new(name=name or (obj.name + ' Material'))
    set_material_color(material, color)
    obj.data.materials.append(material)
    return len(obj.data.materials) - 1, material


def ensure_color_material(obj, color, name=None):
    obj = editable_mesh_object(obj)
    index, material = matching_slot(obj, color)
    if material:
        return index, material
    return create_material(obj, color, name)


def apply_object_color(obj, color):
    obj = editable_mesh_object(obj)
    color = rgba(color)
    material = obj.active_material
    if material is None:
        slot, material = create_material(obj, color, obj.name + ' Color')
        obj.active_material_index = slot
    elif material.library or material.users > 1:
        material = material.copy()
        material.name = obj.name + ' Color'
        obj.active_material = material
        set_material_color(material, color)
    else:
        set_material_color(material, color)
    obj.color = color
    return material


def selected_face_count(obj):
    obj = editable_mesh_object(obj)
    if obj.mode != 'EDIT':
        return 0
    bm = bmesh.from_edit_mesh(obj.data)
    return sum(1 for face in bm.faces if face.is_valid and face.select and not face.hide)


def assign_color_to_selected_faces(obj, color):
    obj = editable_mesh_object(obj)
    if obj.mode != 'EDIT':
        raise ValueError('Enter Edit Mode and select faces first')
    bm = bmesh.from_edit_mesh(obj.data)
    faces = [face for face in bm.faces if face.is_valid and face.select and not face.hide]
    if not faces:
        raise ValueError('Select one or more faces first')
    slot, material = ensure_color_material(obj, color, obj.name + ' Face Material')
    for face in faces:
        face.material_index = slot
    obj.active_material_index = slot
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    return material, len(faces), slot


def active_material_summary(obj):
    if not obj or obj.type != 'MESH':
        return 'None', 0, 0
    slots = len(obj.material_slots)
    if slots == 0:
        return 'None', 0, 0
    index = min(max(int(obj.active_material_index), 0), slots - 1)
    material = obj.material_slots[index].material
    return (material.name if material else 'Empty'), index + 1, slots
