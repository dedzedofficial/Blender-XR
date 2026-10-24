# SPDX-License-Identifier: GPL-3.0-or-later
"""Material, texture and desktop v0.6 controls for XR Mesh."""
import colorsys
from pathlib import Path
import bpy
import bmesh
from bpy.props import EnumProperty, FloatProperty, StringProperty
from . import materials, statistics, status, uv_tools

IMAGE_NODE_NAME = 'XR Mesh Image'
DIAGNOSTIC_PREFIX = 'XR Mesh UV '


def _obj(obj):
    return materials.editable_mesh_object(obj)


def _material(obj, create=False, color=(0.18, 0.55, 0.95, 1.0)):
    obj = _obj(obj)
    material = obj.active_material
    if material is None and create:
        _slot, material = materials.create_material(obj, color, obj.name + ' Material')
        obj.active_material = material
    if material is None:
        raise ValueError('The selected mesh has no active material')
    return material


def _principled(material):
    material.use_nodes = True
    if not material.node_tree:
        raise ValueError('The material has no node tree')
    principled = material.node_tree.nodes.get('Principled BSDF')
    if principled is None:
        principled = next((node for node in material.node_tree.nodes
                           if node.type == 'BSDF_PRINCIPLED'), None)
    if principled is None:
        raise ValueError('The active material has no Principled BSDF')
    return principled


def _socket(principled, *names):
    for name in names:
        socket = principled.inputs.get(name)
        if socket is not None:
            return socket
    return None


def parameters(material):
    principled = _principled(material)
    metallic = _socket(principled, 'Metallic')
    roughness = _socket(principled, 'Roughness')
    alpha = _socket(principled, 'Alpha')
    emission = _socket(principled, 'Emission Strength')
    return {
        'metallic': float(metallic.default_value) if metallic else 0.0,
        'roughness': float(roughness.default_value) if roughness else 0.5,
        'alpha': float(alpha.default_value) if alpha else float(material.diffuse_color[3]),
        'emission': float(emission.default_value) if emission else 0.0,
    }


def set_parameters(material, metallic=None, roughness=None, alpha=None,
                   emission=None, emission_color=None):
    principled = _principled(material)
    values = (
        (_socket(principled, 'Metallic'), metallic),
        (_socket(principled, 'Roughness'), roughness),
        (_socket(principled, 'Alpha'), alpha),
        (_socket(principled, 'Emission Strength'), emission),
    )
    for socket, value in values:
        if socket is not None and value is not None:
            socket.default_value = max(0.0, min(1.0, float(value))) if socket.name != 'Emission Strength' else max(0.0, float(value))
    if alpha is not None:
        color = tuple(material.diffuse_color)
        material.diffuse_color = (color[0], color[1], color[2], max(0.0, min(1.0, float(alpha))))
    if emission_color is not None:
        socket = _socket(principled, 'Emission Color', 'Emission')
        if socket is not None:
            color = materials.rgba(emission_color)
            socket.default_value = color
    return material


def sync_settings(obj, settings):
    material = _material(obj, False)
    color = materials.material_color(material)
    if color is not None:
        settings.object_color = color
    values = parameters(material)
    settings.material_metallic = values['metallic']
    settings.material_roughness = values['roughness']
    settings.material_alpha = values['alpha']
    settings.material_emission = values['emission']
    image = current_texture(material)
    settings.texture_name = image.name if image else ''
    return material


def apply_settings(obj, settings):
    material = _material(obj, True, settings.object_color)
    materials.set_material_color(material, settings.object_color)
    set_parameters(material,
                   metallic=settings.material_metallic,
                   roughness=settings.material_roughness,
                   alpha=settings.material_alpha,
                   emission=settings.material_emission,
                   emission_color=settings.object_color)
    obj.color = tuple(settings.object_color[:3]) + (settings.material_alpha,)
    statistics.invalidate()
    return material


def new_material(obj, color, name=None):
    obj = _obj(obj)
    slot, material = materials.create_material(obj, color,
        name or (obj.name + ' Material'))
    obj.active_material_index = slot
    statistics.invalidate()
    return material


def duplicate_material(obj):
    obj = _obj(obj)
    material = _material(obj, False)
    duplicate = material.copy()
    duplicate.name = material.name + ' Copy'
    obj.data.materials.append(duplicate)
    obj.active_material_index = len(obj.data.materials) - 1
    statistics.invalidate()
    return duplicate


def add_slot(obj, color=(0.18, 0.55, 0.95, 1.0)):
    obj = _obj(obj)
    material = obj.active_material
    if material is None:
        return new_material(obj, color)
    obj.data.materials.append(material)
    obj.active_material_index = len(obj.data.materials) - 1
    return material


def _safe_slot_index(obj):
    if not obj.material_slots:
        raise ValueError('The mesh has no material slots')
    return min(max(int(obj.active_material_index), 0), len(obj.material_slots) - 1)


def remove_slot(obj):
    obj = _obj(obj)
    index = _safe_slot_index(obj)
    obj.data.materials.pop(index=index)
    if obj.material_slots:
        obj.active_material_index = min(index, len(obj.material_slots) - 1)
    statistics.invalidate()
    return index


def delete_material(obj):
    obj = _obj(obj)
    index = _safe_slot_index(obj)
    material = obj.material_slots[index].material
    # Capture the name before Blender potentially destroys the RNA datablock.
    material_name = material.name if material else 'Empty slot'
    obj.data.materials.pop(index=index)
    if material and material.users == 0:
        bpy.data.materials.remove(material)
    if obj.material_slots:
        obj.active_material_index = min(index, len(obj.material_slots) - 1)
    statistics.invalidate()
    return material_name


def rename_material(obj, name):
    material = _material(obj, False)
    name = str(name).strip()
    if not name:
        raise ValueError('Material name cannot be blank')
    material.name = name[:63]
    return material.name


def auto_rename(obj):
    obj = _obj(obj)
    index = _safe_slot_index(obj)
    return rename_material(obj, 'XR Material {:02d}'.format(index + 1))


def cycle_slot(obj, direction):
    obj = _obj(obj)
    count = len(obj.material_slots)
    if not count:
        raise ValueError('The mesh has no material slots')
    obj.active_material_index = (int(obj.active_material_index) + int(direction)) % count
    return obj.active_material_index


def assign_active_slot(obj):
    obj = _obj(obj)
    if obj.mode != 'EDIT':
        raise ValueError('Enter Edit Mode and select faces first')
    index = _safe_slot_index(obj)
    bm = bmesh.from_edit_mesh(obj.data)
    faces = [face for face in bm.faces if face.select and not face.hide]
    if not faces:
        raise ValueError('Select one or more faces first')
    for face in faces:
        face.material_index = index
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    return len(faces)


def select_faces_with_active_material(obj):
    obj = _obj(obj)
    if obj.mode != 'EDIT':
        raise ValueError('Enter Edit Mode first')
    index = _safe_slot_index(obj)
    bm = bmesh.from_edit_mesh(obj.data)
    count = 0
    for face in bm.faces:
        selected = face.material_index == index and not face.hide
        face.select_set(selected)
        count += int(selected)
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    return count


def texture_images():
    return [image for image in bpy.data.images
            if image.name not in {'Render Result', 'Viewer Node'} and image.size[0] and image.size[1]]


def select_texture(settings, direction=1):
    images = texture_images()
    if not images:
        raise ValueError('Load or create a texture image first')
    current = next((index for index, image in enumerate(images)
                    if image.name == settings.texture_name), -1)
    index = (current + int(direction)) % len(images)
    settings.texture_name = images[index].name
    return images[index]


def selected_texture(settings):
    image = bpy.data.images.get(settings.texture_name) if settings.texture_name else None
    if image is None:
        images = texture_images()
        if not images:
            raise ValueError('Load or create a texture image first')
        image = images[0]
        settings.texture_name = image.name
    return image


def current_texture(material):
    if not material or not material.use_nodes or not material.node_tree:
        return None
    node = material.node_tree.nodes.get(IMAGE_NODE_NAME)
    return node.image if node and node.type == 'TEX_IMAGE' else None


def apply_texture(obj, image, color=(0.18, 0.55, 0.95, 1.0)):
    material = _material(obj, True, color)
    principled = _principled(material)
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    node = nodes.get(IMAGE_NODE_NAME)
    if node is None or node.type != 'TEX_IMAGE':
        node = nodes.new('ShaderNodeTexImage')
        node.name = IMAGE_NODE_NAME
        node.label = 'XR Mesh Texture'
    node.image = image
    base = _socket(principled, 'Base Color')
    if base is None:
        raise ValueError('The Principled shader has no Base Color input')
    for link in tuple(base.links):
        links.remove(link)
    links.new(node.outputs['Color'], base)
    return material


def clear_texture(obj, fallback_color=None):
    material = _material(obj, False)
    principled = _principled(material)
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    node = nodes.get(IMAGE_NODE_NAME)
    base = _socket(principled, 'Base Color')
    if node and base:
        for link in tuple(base.links):
            if link.from_node == node:
                links.remove(link)
        node.image = None
    if base is not None and fallback_color is not None:
        base.default_value = materials.rgba(fallback_color)
    return material


_DIGITS = {
    '0': ('111','101','101','101','111'), '1': ('010','110','010','010','111'),
    '2': ('111','001','111','100','111'), '3': ('111','001','111','001','111'),
    '4': ('101','101','111','001','001'), '5': ('111','100','111','001','111'),
    '6': ('111','100','111','101','111'), '7': ('111','001','010','010','010'),
    '8': ('111','101','111','101','111'), '9': ('111','101','111','001','111'),
}


def _set_pixel(pixels, size, x, y, color):
    if not (0 <= x < size and 0 <= y < size):
        return
    offset = (y * size + x) * 4
    pixels[offset:offset + 4] = color


def _draw_number(pixels, size, text, x, y, scale, color):
    cursor = x
    for char in str(text):
        glyph = _DIGITS.get(char)
        if not glyph:
            cursor += 4 * scale
            continue
        for row, line in enumerate(glyph):
            for column, value in enumerate(line):
                if value == '1':
                    for yy in range(scale):
                        for xx in range(scale):
                            _set_pixel(pixels, size, cursor + column * scale + xx,
                                       y + (4 - row) * scale + yy, color)
        cursor += 4 * scale


def diagnostic_image(kind, size=128):
    kind = kind.upper()
    names = {'CHECKER':'Numbered Checker', 'DIRECTION':'Directional', 'GRID':'Color Grid'}
    if kind not in names:
        raise ValueError('Unknown diagnostic texture')
    name = DIAGNOSTIC_PREFIX + names[kind]
    image = bpy.data.images.get(name)
    if image and tuple(image.size) == (size, size):
        return image
    if image:
        bpy.data.images.remove(image)
    image = bpy.data.images.new(name, width=size, height=size, alpha=True)
    pixels = [0.0] * (size * size * 4)
    tiles = 8
    tile = size // tiles
    for y in range(size):
        for x in range(size):
            u = x / max(1, size - 1)
            v = y / max(1, size - 1)
            tx, ty = x // tile, y // tile
            if kind == 'CHECKER':
                value = 0.82 if (tx + ty) % 2 == 0 else 0.18
                color = [value, value, value, 1.0]
            elif kind == 'DIRECTION':
                color = [u, v, max(0.0, 1.0 - u), 1.0]
            else:
                hue = ((tx + ty * tiles) % (tiles * tiles)) / (tiles * tiles)
                red, green, blue = colorsys.hsv_to_rgb(hue, 0.75, 1.0)
                color = [red, green, blue, 1.0]
            if x % tile == 0 or y % tile == 0:
                color = [0.02, 0.02, 0.02, 1.0]
            _set_pixel(pixels, size, x, y, color)
    if kind == 'CHECKER':
        scale = max(1, tile // 12)
        for ty in range(tiles):
            for tx in range(tiles):
                number = ty * tiles + tx + 1
                text = str(number)
                width = len(text) * 4 * scale
                _draw_number(pixels, size, text,
                             tx * tile + max(1, (tile - width) // 2),
                             ty * tile + max(1, (tile - 5 * scale) // 2),
                             scale, [1.0, 0.2, 0.1, 1.0] if (tx + ty) % 2 else [0.05, 0.05, 0.05, 1.0])
    image.pixels.foreach_set(pixels)
    image.pack()
    image.update()
    return image


def toggle_material_preview(context, session=None):
    area = getattr(session, 'area', None) if session else getattr(context, 'area', None)
    if not area or area.type != 'VIEW_3D':
        raise ValueError('Material preview requires a 3D Viewport')
    space = area.spaces.active
    shading = getattr(space, 'shading', None)
    if shading is None:
        raise ValueError('The active 3D Viewport has no shading controls')
    if shading.type == 'MATERIAL':
        previous = getattr(session, '_material_preview_previous', 'SOLID') if session else 'SOLID'
        shading.type = previous if previous in {'WIREFRAME','SOLID','MATERIAL','RENDERED'} else 'SOLID'
    else:
        if session is not None:
            session._material_preview_previous = shading.type
        shading.type = 'MATERIAL'
    return shading.type


def load_image(filepath):
    path = Path(filepath)
    if not path.exists() or not path.is_file():
        raise ValueError('Choose a valid texture image file')
    return bpy.data.images.load(str(path), check_existing=True)


class BXR_OT_material_action(bpy.types.Operator):
    bl_idname = 'blender_xr.material_action'
    bl_label = 'XR Mesh Material Action'
    bl_options = {'REGISTER', 'UNDO'}
    action: EnumProperty(items=[
        ('NEW','New Material',''), ('DUPLICATE','Duplicate Material',''),
        ('DELETE','Delete Material',''), ('SLOT_ADD','Add Slot',''),
        ('SLOT_REMOVE','Remove Slot',''), ('SLOT_PREV','Previous Slot',''),
        ('SLOT_NEXT','Next Slot',''), ('ASSIGN','Assign Slot',''),
        ('SELECT_FACES','Select Faces',''), ('SYNC','Read Material',''),
        ('APPLY_PROPS','Apply Properties',''), ('CLEAR_TEXTURE','Clear Texture',''),
        ('CHECKER','Numbered Checker',''), ('DIRECTION','Directional UV',''),
        ('GRID','Color Grid',''), ('PREVIEW','Material Preview',''),
    ])

    def execute(self, context):
        settings = context.scene.blender_xr
        obj = context.view_layer.objects.active
        try:
            if self.action == 'NEW':
                material = new_material(obj, settings.object_color)
                sync_settings(obj, settings); message = 'Created ' + material.name
            elif self.action == 'DUPLICATE':
                material = duplicate_material(obj)
                sync_settings(obj, settings); message = 'Duplicated ' + material.name
            elif self.action == 'DELETE':
                message = 'Deleted ' + delete_material(obj)
            elif self.action == 'SLOT_ADD':
                add_slot(obj, settings.object_color); message = 'Material slot added'
            elif self.action == 'SLOT_REMOVE':
                remove_slot(obj); message = 'Material slot removed'
            elif self.action == 'SLOT_PREV':
                cycle_slot(obj, -1); sync_settings(obj, settings); message = 'Previous material slot'
            elif self.action == 'SLOT_NEXT':
                cycle_slot(obj, 1); sync_settings(obj, settings); message = 'Next material slot'
            elif self.action == 'ASSIGN':
                message = 'Assigned slot to {} faces'.format(assign_active_slot(obj))
            elif self.action == 'SELECT_FACES':
                message = 'Selected {} matching faces'.format(select_faces_with_active_material(obj))
            elif self.action == 'SYNC':
                sync_settings(obj, settings); message = 'Material values read'
            elif self.action == 'APPLY_PROPS':
                apply_settings(obj, settings); message = 'Material properties applied'
            elif self.action == 'CLEAR_TEXTURE':
                clear_texture(obj, settings.object_color); settings.texture_name = ''; message = 'Texture cleared'
            elif self.action in {'CHECKER','DIRECTION','GRID'}:
                image = diagnostic_image(self.action)
                apply_texture(obj, image, settings.object_color)
                settings.texture_name = image.name; message = 'Applied ' + image.name
            elif self.action == 'PREVIEW':
                message = 'Viewport shading: ' + toggle_material_preview(context)
            else:
                raise ValueError('Unknown material action')
            status.set_status(settings, message)
            return {'FINISHED'}
        except ValueError as exc:
            self.report({'ERROR'}, str(exc)); status.set_status(settings, str(exc)); return {'CANCELLED'}


class BXR_OT_material_rename(bpy.types.Operator):
    bl_idname = 'blender_xr.material_rename'
    bl_label = 'Rename Material'
    bl_options = {'REGISTER', 'UNDO'}
    name: StringProperty(name='Material Name', maxlen=63)

    def invoke(self, context, _event):
        obj = context.view_layer.objects.active
        try:
            self.name = _material(obj, False).name
        except ValueError as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        try:
            name = rename_material(context.view_layer.objects.active, self.name)
            status.set_status(context.scene.blender_xr, 'Renamed material: ' + name)
            return {'FINISHED'}
        except ValueError as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}


class BXR_OT_texture_load(bpy.types.Operator):
    bl_idname = 'blender_xr.texture_load'
    bl_label = 'Load Texture Image'
    filepath: StringProperty(subtype='FILE_PATH')
    filter_glob: StringProperty(default='*.png;*.jpg;*.jpeg;*.tga;*.bmp;*.tif;*.tiff;*.exr;*.hdr', options={'HIDDEN'})

    def invoke(self, context, _event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        settings = context.scene.blender_xr
        try:
            image = load_image(self.filepath)
            apply_texture(context.view_layer.objects.active, image, settings.object_color)
            settings.texture_name = image.name
            status.set_status(settings, 'Texture: ' + image.name)
            return {'FINISHED'}
        except (ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}


class BXR_OT_uv_action(bpy.types.Operator):
    bl_idname = 'blender_xr.uv_action'
    bl_label = 'XR Mesh UV Action'
    bl_options = {'REGISTER', 'UNDO'}
    action: EnumProperty(items=[
        ('UNWRAP','Unwrap',''), ('SMART','Smart Project',''), ('CUBE','Cube Project',''),
        ('PLANAR','Planar Project',''), ('MARK','Mark Seams',''), ('CLEAR','Clear Seams',''),
        ('RESET','Reset UVs',''), ('PACK','Pack Islands',''), ('MOVE_U','Move U',''),
        ('MOVE_V','Move V',''), ('ROTATE','Rotate',''), ('SCALE','Scale',''),
    ])
    value: FloatProperty(default=0.0)

    def execute(self, context):
        obj = context.view_layer.objects.active
        try:
            if self.action == 'UNWRAP': count = uv_tools.unwrap(obj)
            elif self.action == 'SMART': count = uv_tools.smart_project(obj)
            elif self.action == 'CUBE': count = uv_tools.cube_project(obj)
            elif self.action == 'PLANAR': count = uv_tools.planar_project(obj)
            elif self.action == 'MARK': count = uv_tools.mark_seams(obj, False)
            elif self.action == 'CLEAR': count = uv_tools.mark_seams(obj, True)
            elif self.action == 'RESET': count = uv_tools.reset(obj)
            elif self.action == 'PACK': count = uv_tools.pack_islands(obj)
            elif self.action == 'MOVE_U': count = uv_tools.transform(obj, move=(self.value, 0))
            elif self.action == 'MOVE_V': count = uv_tools.transform(obj, move=(0, self.value))
            elif self.action == 'ROTATE': count = uv_tools.transform(obj, rotate=self.value)
            elif self.action == 'SCALE': count = uv_tools.transform(obj, scale=self.value)
            else: raise ValueError('Unknown UV action')
            status.set_status(context.scene.blender_xr, '{}: {}'.format(self.action.replace('_',' ').title(), count))
            return {'FINISHED'}
        except ValueError as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}


class BXR_PT_materials_v060(bpy.types.Panel):
    bl_label = 'Advanced Materials + Textures'
    bl_idname = 'BXR_PT_materials_v060'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Blender XR'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, 'blender_xr', None)
        return settings is not None and settings.ui_section == 'MATERIAL'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.blender_xr
        obj = context.view_layer.objects.active
        name, slot, total = materials.active_material_summary(obj)
        layout.label(text='Active: {}  Slot {}/{}'.format(name, slot, total), icon='MATERIAL')
        row = layout.row(align=True)
        row.operator('blender_xr.material_action', text='New', icon='ADD').action = 'NEW'
        row.operator('blender_xr.material_action', text='Duplicate', icon='DUPLICATE').action = 'DUPLICATE'
        row.operator('blender_xr.material_action', text='Delete', icon='REMOVE').action = 'DELETE'
        layout.operator('blender_xr.material_rename', text='Rename Material', icon='GREASEPENCIL')
        row = layout.row(align=True)
        row.operator('blender_xr.material_action', text='Prev Slot', icon='TRIA_LEFT').action = 'SLOT_PREV'
        row.operator('blender_xr.material_action', text='Next Slot', icon='TRIA_RIGHT').action = 'SLOT_NEXT'
        row = layout.row(align=True)
        row.operator('blender_xr.material_action', text='Add Slot', icon='ADD').action = 'SLOT_ADD'
        row.operator('blender_xr.material_action', text='Remove Slot', icon='REMOVE').action = 'SLOT_REMOVE'
        if obj and obj.type == 'MESH' and obj.mode == 'EDIT':
            row = layout.row(align=True)
            row.operator('blender_xr.material_action', text='Assign Selected Faces', icon='MATERIAL').action = 'ASSIGN'
            row.operator('blender_xr.material_action', text='Select Slot Faces', icon='RESTRICT_SELECT_OFF').action = 'SELECT_FACES'
        layout.separator()
        layout.prop(settings, 'object_color', text='Base Color', icon='COLOR')
        layout.prop(settings, 'material_metallic', icon='MATERIAL')
        layout.prop(settings, 'material_roughness', icon='SHADING_SOLID')
        layout.prop(settings, 'material_alpha', icon='IMAGE_ALPHA')
        layout.prop(settings, 'material_emission', icon='LIGHT')
        row = layout.row(align=True)
        row.operator('blender_xr.material_action', text='Read Active', icon='FILE_REFRESH').action = 'SYNC'
        row.operator('blender_xr.material_action', text='Apply Properties', icon='CHECKMARK').action = 'APPLY_PROPS'
        layout.separator()
        layout.label(text='Texture: ' + (settings.texture_name or 'None'), icon='IMAGE_DATA')
        row = layout.row(align=True)
        row.operator('blender_xr.texture_load', text='Load Image', icon='FILE_FOLDER')
        row.operator('blender_xr.material_action', text='Clear', icon='X').action = 'CLEAR_TEXTURE'
        row = layout.row(align=True)
        row.operator('blender_xr.material_action', text='Checker', icon='TEXTURE').action = 'CHECKER'
        row.operator('blender_xr.material_action', text='Direction', icon='ORIENTATION_VIEW').action = 'DIRECTION'
        row.operator('blender_xr.material_action', text='Color Grid', icon='COLOR').action = 'GRID'
        layout.operator('blender_xr.material_action', text='Toggle Material Preview', icon='SHADING_TEXTURE').action = 'PREVIEW'


class BXR_PT_uv_v060(bpy.types.Panel):
    bl_label = 'UV Mapping'
    bl_idname = 'BXR_PT_uv_v060'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Blender XR'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, 'blender_xr', None)
        return settings is not None and settings.ui_section == 'UV'

    def draw(self, context):
        layout = self.layout
        obj = context.view_layer.objects.active
        layout.label(text=uv_tools.summary(obj), icon='UV')
        if not obj or obj.type != 'MESH' or obj.mode != 'EDIT':
            layout.label(text='Enter mesh Edit Mode and select faces', icon='INFO')
            return
        row = layout.row(align=True)
        row.operator('blender_xr.uv_action', text='Unwrap', icon='UV').action = 'UNWRAP'
        row.operator('blender_xr.uv_action', text='Smart', icon='MODIFIER').action = 'SMART'
        row = layout.row(align=True)
        row.operator('blender_xr.uv_action', text='Cube', icon='MESH_CUBE').action = 'CUBE'
        row.operator('blender_xr.uv_action', text='Planar', icon='MESH_PLANE').action = 'PLANAR'
        row = layout.row(align=True)
        row.operator('blender_xr.uv_action', text='Mark Seams', icon='ADD').action = 'MARK'
        row.operator('blender_xr.uv_action', text='Clear Seams', icon='REMOVE').action = 'CLEAR'
        step = context.scene.blender_xr.uv_step
        row = layout.row(align=True)
        op = row.operator('blender_xr.uv_action', text='U -', icon='EMPTY_ARROWS'); op.action = 'MOVE_U'; op.value = -step
        op = row.operator('blender_xr.uv_action', text='U +', icon='EMPTY_ARROWS'); op.action = 'MOVE_U'; op.value = step
        row = layout.row(align=True)
        op = row.operator('blender_xr.uv_action', text='V -', icon='EMPTY_ARROWS'); op.action = 'MOVE_V'; op.value = -step
        op = row.operator('blender_xr.uv_action', text='V +', icon='EMPTY_ARROWS'); op.action = 'MOVE_V'; op.value = step
        row = layout.row(align=True)
        op = row.operator('blender_xr.uv_action', text='Rotate -15', icon='FILE_REFRESH'); op.action = 'ROTATE'; op.value = -15
        op = row.operator('blender_xr.uv_action', text='Rotate +15', icon='FILE_REFRESH'); op.action = 'ROTATE'; op.value = 15
        row = layout.row(align=True)
        op = row.operator('blender_xr.uv_action', text='Scale 90%', icon='FULLSCREEN_ENTER'); op.action = 'SCALE'; op.value = 0.9
        op = row.operator('blender_xr.uv_action', text='Scale 110%', icon='FULLSCREEN_ENTER'); op.action = 'SCALE'; op.value = 1.1
        row = layout.row(align=True)
        row.operator('blender_xr.uv_action', text='Reset UVs', icon='LOOP_BACK').action = 'RESET'
        row.operator('blender_xr.uv_action', text='Pack Islands', icon='UV').action = 'PACK'
        layout.prop(context.scene.blender_xr, 'uv_step', icon='UV')


CLASSES = (
    BXR_OT_material_action, BXR_OT_material_rename, BXR_OT_texture_load,
    BXR_OT_uv_action, BXR_PT_materials_v060, BXR_PT_uv_v060,
)
