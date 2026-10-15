# SPDX-License-Identifier: GPL-3.0-or-later
"""v0.6 headset workflow for materials, textures and UV mapping."""
import bpy
from mathutils import Vector
from . import drawing, material_uv, materials, statistics, uv_tools, v056, v065


_MATERIAL_PAGES = {'MATERIAL_HOME','MATERIAL_PROPS','MATERIAL_SLOTS','MATERIAL_TEXTURES'}
_UV_PAGES = {'UV','UV_TRANSFORM','UV_PREVIEW'}


def _ensure_idle(session):
    if session.transaction or session.grab or session.air_grab or session.axis_move:
        raise ValueError('Finish or cancel the current operation first')


def _active(context):
    return materials.editable_mesh_object(context.view_layer.objects.active)


def _sync(session, context, create=False):
    obj = _active(context)
    if create and obj.active_material is None:
        material_uv.new_material(obj, session.settings.object_color)
    material_uv.sync_settings(obj, session.settings)
    return obj


def _material_adjust(session, context, name, delta, minimum=0.0, maximum=1.0):
    obj = _sync(session, context, create=True)
    value = max(minimum, min(maximum, float(getattr(session.settings, name)) + float(delta)))
    setattr(session.settings, name, value)
    material_uv.apply_settings(obj, session.settings)
    session.status = name.replace('material_', '').upper() + ' ' + format(value, '.2f')


def _back(session, context):
    page = session.menu.page
    if page in {'MATERIAL_PROPS','MATERIAL_SLOTS','MATERIAL_TEXTURES'}:
        session.menu.page = 'MATERIAL_HOME'
        session.status = 'MATERIALS'
        return True
    if page in {'UV_TRANSFORM','UV_PREVIEW'}:
        session.menu.page = 'UV'
        session.status = 'UV TOOLS'
        return True
    if page == 'UV':
        session.menu.page = 'MATERIAL_HOME'
        session.status = 'MATERIALS'
        return True
    if page == 'MATERIAL_HOME':
        obj = context.view_layer.objects.active
        session.menu.page = getattr(session, 'material_return_page',
                                    'EDIT' if obj and obj.mode == 'EDIT' else 'TOOLS')
        session.status = 'MATERIALS CLOSED'
        return True
    return False


def _material_summary(page, settings, obj):
    name, slot, total = materials.active_material_summary(obj)
    if page == 'MATERIAL_PROPS':
        return 'M{} R{} A{} E{}'.format(
            round(settings.material_metallic * 100),
            round(settings.material_roughness * 100),
            round(settings.material_alpha * 100),
            round(settings.material_emission * 10) / 10)
    if page == 'MATERIAL_TEXTURES':
        return ('IMG ' + (settings.texture_name or 'NONE'))[:25]
    if page == 'MATERIAL_SLOTS':
        return ('SLOT {}/{} '.format(slot, total) + name)[:25]
    return name[:25]


def _patch_menu_draw():
    if getattr(drawing.Menu, '_v060_material_uv_draw', False):
        return
    original_draw = drawing.Menu.draw

    def draw(self, shader, tool, hover, step, status, settings=None, selection='', select_mode='FACE'):
        original_draw(self, shader, tool, hover, step, status, settings, selection, select_mode)
        if not settings or not self.ready or not self.visible:
            return
        page = self.page
        if page not in _MATERIAL_PAGES | _UV_PAGES:
            return
        obj = bpy.context.view_layer.objects.active
        v056._draw_rect(self, shader, -0.108, 0.135, 0.280, 0.026,
                        (0.015, 0.025, 0.04, 0.99), 0.0020)
        summary = uv_tools.summary(obj) if page in _UV_PAGES else _material_summary(page, settings, obj)
        v056._draw_text(self, shader, summary, -0.105, 0.153, 0.0021)
        if page != 'UV_PREVIEW':
            return
        # A compact, normalized wireframe preview keeps UV inspection in-headset
        # without trying to recreate Blender's complete UV Editor in VR.
        v056._draw_rect(self, shader, -0.145, -0.145, 0.290, 0.235,
                        (0.025, 0.04, 0.055, 0.98), 0.0021)
        for line in (0.0, 0.25, 0.5, 0.75, 1.0):
            x = -0.135 + line * 0.270
            y = -0.135 + line * 0.215
            drawing.draw_batch(shader, 'LINES',
                [self.world(x, -0.135, 0.0025), self.world(x, 0.080, 0.0025)],
                (0.10, 0.18, 0.22, 1.0))
            drawing.draw_batch(shader, 'LINES',
                [self.world(-0.135, y, 0.0025), self.world(0.135, y, 0.0025)],
                (0.10, 0.18, 0.22, 1.0))
        try:
            segments = uv_tools.preview_segments(obj)
        except (ValueError, ReferenceError):
            segments = []
        points = []
        for ax, ay, bx, by in segments:
            points.extend((self.world(-0.135 + ax * 0.270, -0.135 + ay * 0.215, 0.0028),
                           self.world(-0.135 + bx * 0.270, -0.135 + by * 0.215, 0.0028)))
        if points:
            drawing.draw_batch(shader, 'LINES', points, (0.18, 0.92, 1.0, 1.0))

    drawing.Menu.draw = draw
    drawing.Menu._v060_material_uv_draw = True


def patch(Runtime):
    if getattr(Runtime, '_v060_patched', False):
        return
    _patch_menu_draw()
    original_command = Runtime.command

    def command(self, context, action):
        if action == 'MATERIAL_MENU':
            _ensure_idle(self)
            obj = _active(context)
            self.material_return_page = 'EDIT' if obj.mode == 'EDIT' else 'TOOLS'
            if obj.active_material is not None:
                material_uv.sync_settings(obj, self.settings)
            self.menu.page = 'MATERIAL_HOME'
            self.status = 'MATERIALS / TEXTURES / UV'
            return

        if action == 'COLOR_MENU':
            previous = self.menu.page
            result = original_command(self, context, action)
            if previous == 'MATERIAL_HOME':
                self.color_return_page = 'MATERIAL_HOME'
            return result

        if action == 'BACK' and _back(self, context):
            return

        if action == 'MAT_PROPS':
            _sync(self, context, create=True); self.menu.page = 'MATERIAL_PROPS'; self.status = 'MATERIAL PROPERTIES'; return
        if action == 'MAT_SLOTS':
            _active(context); self.menu.page = 'MATERIAL_SLOTS'; self.status = 'MATERIAL SLOTS'; return
        if action == 'MAT_TEXTURES':
            _active(context); self.menu.page = 'MATERIAL_TEXTURES'; self.status = 'TEXTURE IMAGES'; return
        if action == 'UV_MENU':
            _active(context); self.menu.page = 'UV'; self.status = 'UV MAPPING'; return
        if action == 'UV_TRANSFORM_MENU':
            _active(context); self.menu.page = 'UV_TRANSFORM'; self.status = 'UV TRANSFORM'; return
        if action == 'UV_PREVIEW':
            uv_tools.ensure_layer(_active(context)); self.menu.page = 'UV_PREVIEW'; self.status = 'UV PREVIEW'; return

        if action == 'MAT_NEW':
            _ensure_idle(self); material = material_uv.new_material(_active(context), self.settings.object_color)
            material_uv.sync_settings(context.view_layer.objects.active, self.settings)
            self.status = 'CREATED ' + material.name.upper(); return
        if action == 'MAT_DUP':
            _ensure_idle(self); material = material_uv.duplicate_material(_active(context))
            material_uv.sync_settings(context.view_layer.objects.active, self.settings)
            self.status = 'DUPLICATED ' + material.name.upper(); return
        if action == 'MAT_DELETE':
            _ensure_idle(self); name = material_uv.delete_material(_active(context)); self.status = 'DELETED ' + name.upper(); return
        if action == 'MAT_RENAME_AUTO':
            name = material_uv.auto_rename(_active(context)); self.status = 'RENAMED ' + name.upper(); return
        if action == 'MAT_PREVIEW':
            self.status = 'SHADING ' + material_uv.toggle_material_preview(context, self); return
        if action == 'MAT_SYNC':
            material_uv.sync_settings(_active(context), self.settings); self.status = 'MATERIAL VALUES READ'; return

        adjustments = {
            'MAT_METAL_DOWN': ('material_metallic', -0.1, 0.0, 1.0),
            'MAT_METAL_UP': ('material_metallic', 0.1, 0.0, 1.0),
            'MAT_ROUGH_DOWN': ('material_roughness', -0.1, 0.0, 1.0),
            'MAT_ROUGH_UP': ('material_roughness', 0.1, 0.0, 1.0),
            'MAT_ALPHA_DOWN': ('material_alpha', -0.1, 0.0, 1.0),
            'MAT_ALPHA_UP': ('material_alpha', 0.1, 0.0, 1.0),
            'MAT_EMIT_DOWN': ('material_emission', -0.25, 0.0, 100.0),
            'MAT_EMIT_UP': ('material_emission', 0.25, 0.0, 100.0),
        }
        if action in adjustments:
            _material_adjust(self, context, *adjustments[action]); return

        if action in {'SLOT_PREV','SLOT_NEXT'}:
            material_uv.cycle_slot(_active(context), -1 if action == 'SLOT_PREV' else 1)
            material_uv.sync_settings(context.view_layer.objects.active, self.settings)
            self.status = action.replace('_',' '); return
        if action == 'SLOT_ADD':
            material_uv.add_slot(_active(context), self.settings.object_color); self.status = 'MATERIAL SLOT ADDED'; return
        if action == 'SLOT_REMOVE':
            material_uv.remove_slot(_active(context)); self.status = 'MATERIAL SLOT REMOVED'; return
        if action == 'SLOT_ASSIGN':
            count = material_uv.assign_active_slot(_active(context)); self.status = 'ASSIGNED ' + str(count) + ' FACES'; return
        if action == 'SLOT_SELECT_FACES':
            count = material_uv.select_faces_with_active_material(_active(context)); self.status = 'SELECTED ' + str(count) + ' FACES'; return

        if action in {'IMG_PREV','IMG_NEXT'}:
            image = material_uv.select_texture(self.settings, -1 if action == 'IMG_PREV' else 1)
            self.status = 'IMAGE ' + image.name.upper(); return
        if action == 'IMG_APPLY':
            image = material_uv.selected_texture(self.settings)
            material_uv.apply_texture(_active(context), image, self.settings.object_color)
            self.status = 'TEXTURE ' + image.name.upper(); return
        if action == 'IMG_CLEAR':
            material_uv.clear_texture(_active(context), self.settings.object_color)
            self.settings.texture_name = ''; self.status = 'TEXTURE CLEARED'; return
        if action in {'IMG_CHECKER','IMG_DIRECTION','IMG_GRID'}:
            kind = {'IMG_CHECKER':'CHECKER','IMG_DIRECTION':'DIRECTION','IMG_GRID':'GRID'}[action]
            image = material_uv.diagnostic_image(kind)
            material_uv.apply_texture(_active(context), image, self.settings.object_color)
            self.settings.texture_name = image.name
            self.status = 'DIAGNOSTIC ' + kind; return

        uv_actions = {
            'UV_UNWRAP': lambda obj: uv_tools.unwrap(obj),
            'UV_SMART': lambda obj: uv_tools.smart_project(obj),
            'UV_CUBE': lambda obj: uv_tools.cube_project(obj),
            'UV_PLANAR': lambda obj: uv_tools.planar_project(obj),
            'UV_MARK_SEAM': lambda obj: uv_tools.mark_seams(obj, False),
            'UV_CLEAR_SEAM': lambda obj: uv_tools.mark_seams(obj, True),
            'UV_RESET': lambda obj: uv_tools.reset(obj),
            'UV_PACK': lambda obj: uv_tools.pack_islands(obj),
            'UV_U_DOWN': lambda obj: uv_tools.transform(obj, move=(-self.settings.uv_step, 0)),
            'UV_U_UP': lambda obj: uv_tools.transform(obj, move=(self.settings.uv_step, 0)),
            'UV_V_DOWN': lambda obj: uv_tools.transform(obj, move=(0, -self.settings.uv_step)),
            'UV_V_UP': lambda obj: uv_tools.transform(obj, move=(0, self.settings.uv_step)),
            'UV_ROT_DOWN': lambda obj: uv_tools.transform(obj, rotate=-15),
            'UV_ROT_UP': lambda obj: uv_tools.transform(obj, rotate=15),
            'UV_SCALE_DOWN': lambda obj: uv_tools.transform(obj, scale=0.9),
            'UV_SCALE_UP': lambda obj: uv_tools.transform(obj, scale=1.1),
        }
        if action in uv_actions:
            _ensure_idle(self)
            count = uv_actions[action](_active(context))
            self.status = action.replace('UV_', '').replace('_',' ') + ' / ' + str(count)
            return

        return original_command(self, context, action)

    Runtime.command = command
    Runtime._v060_patched = True
    v065.patch(Runtime)
