# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared material helpers for Blender XR."""
import colorsys
import bpy
import bmesh


PRESET_COLORS = {
    'COLOR_RED': (1.0, 0.08, 0.05, 1.0),
    'COLOR_ORANGE': (1.0, 0.35, 0.04, 1.0),
    'COLOR_YELLOW': (1.0, 0.9, 0.03, 1.0),
    'COLOR_GREEN': (0.08, 0.8, 0.16, 1.0),
    'COLOR_CYAN': (0.04, 0.8, 0.9, 1.0),
    'COLOR_BLUE': (0.08, 0.24, 1.0, 1.0),
    'COLOR_PURPLE': (0.55, 0.12, 0.95, 1.0),
    'COLOR_PINK': (1.0, 0.12, 0.58, 1.0),
}


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


def adjust_hsv(color, hue=0.0, saturation=0.0, value=0.0):
    """Legacy incremental HSV adjustment kept for compatibility."""
    red, green, blue, alpha = rgba(color)
    h, s, v = colorsys.rgb_to_hsv(red, green, blue)
    h = (h + float(hue)) % 1.0
    s = max(0.0, min(1.0, s + float(saturation)))
    v = max(0.0, min(1.0, v + float(value)))
    red, green, blue = colorsys.hsv_to_rgb(h, s, v)
    return red, green, blue, alpha


def color_hsl(color):
    """Return hue, saturation and lightness in normalized 0..1 ranges."""
    red, green, blue, _alpha = rgba(color)
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    return float(hue), float(saturation), float(lightness)


def color_from_hsl(hue, saturation, lightness, alpha=1.0):
    """Create RGBA from normalized HSL controls."""
    hue = max(0.0, min(1.0, float(hue)))
    saturation = max(0.0, min(1.0, float(saturation)))
    lightness = max(0.0, min(1.0, float(lightness)))
    red, green, blue = colorsys.hls_to_rgb(hue % 1.0, lightness, saturation)
    return red, green, blue, max(0.0, min(1.0, float(alpha)))


def adjust_hsl(color, hue=0.0, saturation=0.0, lightness=0.0):
    """Increment an RGBA color in HSL space."""
    red, green, blue, alpha = rgba(color)
    h, s, l = color_hsl((red, green, blue, alpha))
    return color_from_hsl((h + float(hue)) % 1.0,
                          max(0.0, min(1.0, s + float(saturation))),
                          max(0.0, min(1.0, l + float(lightness))), alpha)


def color_summary(color):
    red, green, blue, _alpha = rgba(color)
    return 'R{} G{} B{}'.format(round(red * 255), round(green * 255), round(blue * 255))


def hsl_summary(hsl_or_color, is_hsl=False):
    """Compact headset-readable HSL summary."""
    if is_hsl:
        hue, saturation, lightness = (float(v) for v in hsl_or_color[:3])
    else:
        hue, saturation, lightness = color_hsl(hsl_or_color)
    hue = max(0.0, min(1.0, hue))
    saturation = max(0.0, min(1.0, saturation))
    lightness = max(0.0, min(1.0, lightness))
    return 'H{} S{} L{}'.format(round(hue * 360), round(saturation * 100), round(lightness * 100))


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


def picked_color(obj):
    """Return the active/selected material color for the VR PICK command."""
    obj = editable_mesh_object(obj)
    material = None
    if obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(obj.data)
        faces = [face for face in bm.faces if face.is_valid and face.select and not face.hide]
        if not faces:
            raise ValueError('Select a face before picking its color')
        index = int(faces[0].material_index)
        if 0 <= index < len(obj.material_slots):
            material = obj.material_slots[index].material
    else:
        material = obj.active_material
    color = material_color(material)
    if color is None:
        raise ValueError('The selected mesh has no material color to pick')
    return rgba(color)


def active_material_summary(obj):
    if not obj or obj.type != 'MESH':
        return 'None', 0, 0
    slots = len(obj.material_slots)
    if slots == 0:
        return 'None', 0, 0
    index = min(max(int(obj.active_material_index), 0), slots - 1)
    material = obj.material_slots[index].material
    return (material.name if material else 'Empty'), index + 1, slots
