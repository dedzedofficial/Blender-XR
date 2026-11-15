# SPDX-License-Identifier: GPL-3.0-or-later
"""Creator-approved colour controls inside the existing native XR Materials menu.

All edits are explicit: previewing a swatch/HSV/HEX colour changes only the
scene's Mesh XR settings. LOCAL or SHARED is required to change a material.
Base Color links and unrelated shader nodes are never replaced.
"""
import colorsys
import math

import bpy

from . import drawing, materials, menus, mesh, v056, v065

_STUDIO = 'COLOR_STUDIO'
_HSV = 'COLOR_STUDIO_HSV'
_WHEEL = 'COLOR_STUDIO_WHEEL'
_HEX = 'COLOR_STUDIO_HEX'
_RGB = 'COLOR_STUDIO_RGB'
_SWATCHES = 'COLOR_STUDIO_SWATCHES'
_SLIDERS = ('STUDIO_HUE_SLIDER', 'STUDIO_SAT_SLIDER', 'STUDIO_VAL_SLIDER')
_ROWS = (('HUE', _SLIDERS[0], .117),
         ('SAT', _SLIDERS[1], .065),
         ('VALUE', _SLIDERS[2], .013))


def _active_material(context):
    if context.mode != 'OBJECT':
        raise ValueError('Edit material colour in Object Mode')
    obj = materials.editable_mesh_object(context.view_layer.objects.active)
    if obj.hide_select or not obj.visible_get(view_layer=context.view_layer):
        raise ValueError('Unlock and show the object before editing its material')
    if obj.override_library:
        raise ValueError('Library overrides cannot be changed by the XR colour editor')
    mat = obj.active_material
    if mat is None:
        raise ValueError('Select a mesh with an existing material; no material was created')
    if mat.library or mat.override_library:
        raise ValueError('Linked/overridden materials cannot be edited')
    if mat.use_nodes:
        tree = mat.node_tree
        principled = (next((node for node in tree.nodes if node.type == 'BSDF_PRINCIPLED'), None)
                      if tree else None)
        if principled is None:
            raise ValueError('Material lacks a Principled shader; no nodes were changed')
        base = principled.inputs.get('Base Color')
        if base is None:
            raise ValueError('Material has no Base Color input')
        if base.is_linked:
            raise ValueError('Base Color is texture-linked; its node links were preserved')
    return obj, mat


def _state(material):
    diffuse = tuple(material.diffuse_color)
    base = None
    alpha = None
    if material.use_nodes and material.node_tree:
        principled = next((n for n in material.node_tree.nodes
                          if n.type == 'BSDF_PRINCIPLED'), None)
        if principled:
            input_base = principled.inputs.get('Base Color')
            input_alpha = principled.inputs.get('Alpha')
            if input_base is not None:
                base = tuple(input_base.default_value)
            if input_alpha is not None:
                alpha = float(input_alpha.default_value)
    return diffuse, base, alpha


def _restore(material, snapshot):
    diffuse, base, alpha = snapshot
    material.diffuse_color = diffuse
    if base is not None or alpha is not None:
        principled = next((n for n in material.node_tree.nodes
                          if n.type == 'BSDF_PRINCIPLED'), None)
        if principled is None:
            raise ValueError('The shader changed outside XR colour history')
        if base is not None:
            principled.inputs['Base Color'].default_value = base
        if alpha is not None:
            principled.inputs['Alpha'].default_value = alpha


def _equal(first, second):
    if first is None or second is None:
        return first is None and second is None
    if isinstance(first, (float, int)):
        return abs(float(first) - float(second)) < 1e-5
    return len(first) == len(second) and all(_equal(x, y) for x, y in zip(first, second))


def _paint(material, color):
    color = materials.rgba(color)
    material.diffuse_color = color
    if material.use_nodes:
        principled = next(n for n in material.node_tree.nodes
                          if n.type == 'BSDF_PRINCIPLED')
        principled.inputs['Base Color'].default_value = color
        alpha = principled.inputs.get('Alpha')
        if alpha is not None and not alpha.is_linked:
            alpha.default_value = color[3]


def edit_active(context, color, scope='LOCAL'):
    """Apply to existing material; optionally make an explicit local copy.

    Returns one history entry (or None for no-op). Never changes the original
    material when LOCAL duplicates shared material users.
    """
    if scope not in {'LOCAL', 'SHARED'}:
        raise ValueError('Unknown material sharing scope')
    obj, original = _active_material(context)
    if obj.data.users > 1:
        raise ValueError('Make mesh data single-user before changing material slots')
    slot_index = int(obj.active_material_index)
    before = _state(original)
    paint = materials.rgba(color)
    if scope == 'SHARED' or original.users <= 1:
        try:
            _paint(original, paint)
        except Exception:
            _restore(original, before)
            raise
        after = _state(original)
        if _equal(before, after):
            return None
        return ('COLOR_EXISTING', obj.name, slot_index,
                original, original, before, after)
    copied = original.copy()
    try:
        obj.active_material = copied
        _paint(copied, paint)
    except Exception:
        obj.active_material = original
        if copied.users == 0:
            bpy.data.materials.remove(copied)
        raise
    return ('COLOR_EXISTING', obj.name, slot_index,
            original, copied, before, _state(copied))


def _patch_history():
    if getattr(mesh.History, '_xr_color_existing_patched', False):
        return
    old_step = mesh.History.step
    old_release = mesh.History.release

    def release(entry):
        if entry[0] != 'COLOR_EXISTING':
            return old_release(entry)
        new_mat = entry[4]
        if entry[3] != new_mat and new_mat is not None:
            try:
                if new_mat.users == 0 and bpy.data.materials.get(new_mat.name) == new_mat:
                    bpy.data.materials.remove(new_mat)
            except ReferenceError:
                pass

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] != 'COLOR_EXISTING':
            return old_step(self, backwards)
        entry = source[-1]
        _kind, obj_name, slot_index, original, edited, before, after = entry
        obj = bpy.data.objects.get(obj_name)
        if (bpy.context.mode != 'OBJECT' or obj is None or
                bpy.context.view_layer.objects.get(obj_name) != obj or
                obj.type != 'MESH' or obj.library or obj.override_library or
                obj.data.users != 1 or slot_index >= len(obj.material_slots)):
            raise ValueError('Object or slot changed outside XR colour history')
        expected_mat = edited if backwards else original
        if obj.material_slots[slot_index].material != expected_mat:
            raise ValueError('Material assignment changed outside XR colour history')
        if original == edited:
            expected_state = after if backwards else before
            if not _equal(_state(edited), expected_state):
                raise ValueError('Material values changed outside XR colour history')
            _restore(edited, before if backwards else after)
        else:
            if backwards and not _equal(_state(edited), after):
                raise ValueError('Local material changed outside XR colour history')
            obj.material_slots[slot_index].material = original if backwards else edited
        dest.append(source.pop())
        return True

    mesh.History.release = staticmethod(release)
    mesh.History.step = step
    mesh.History._xr_color_existing_patched = True


def _swatch(settings, index):
    return getattr(settings, 'color_swatch_' + str(index))


def _read_color(session, color):
    session.settings.object_color = materials.rgba(color)
    session.settings.color_hex = materials.to_hex(color)
    h, s, v = colorsys.rgb_to_hsv(*materials.rgba(color)[:3])
    previous = getattr(session, 'color_hsv', (h, s, v))
    if s < 1e-8:
        h = previous[0]
    if v < 1e-8:
        s = previous[1]
    session.color_hsv = [h, s, v]
    session.menu.color_hsv = tuple(session.color_hsv)


def _hsv_command(session, action):
    value = getattr(session.menu, 'slider_value', None)
    if value is None:
        return
    if not hasattr(session, 'color_hsv'):
        _read_color(session, session.settings.object_color)
    component = _SLIDERS.index(action)
    session.color_hsv[component] = min(1.0, max(0.0, float(value)))
    rgb = colorsys.hsv_to_rgb(*session.color_hsv)
    _read_color(session, rgb + (session.settings.object_color[3],))
    session.status = 'HSV ' + materials.to_hex(session.settings.object_color)


def wheel_hs(x, y):
    dx, dy = x - .025, y - .09
    radius = math.hypot(dx, dy)
    if radius > .07:
        return None
    return ((math.atan2(dy, dx) / (2 * math.pi)) % 1., radius / .07)


def _hex_page(session):
    page = getattr(session, '_xr_hex_page', 0) % 2
    chars = '0123456789ABCDEF'[page * 8:page * 8 + 8]
    menus.PAGES[_HEX] = tuple((c, 'STUDIO_HEX_CHAR_' + c) for c in chars) + (
        ('NEXT', 'STUDIO_HEX_NEXT'), ('DELETE', 'STUDIO_HEX_DELETE'),
        ('PREVIEW', 'STUDIO_HEX_ACCEPT'), ('CANCEL', 'STUDIO_HEX_CANCEL'))
    menus.TITLES[_HEX] = 'HEX / ' + session._xr_hex_buffer
    session.menu.page = _HEX
    session.status = 'ENTER SIX HEX DIGITS / PREVIEW DOES NOT APPLY'


def _patch_sliders():
    if getattr(drawing.Menu, '_xr_color_studio_sliders', False):
        return
    old_hit, old_draw = drawing.Menu.hit, drawing.Menu.draw

    def hit(self, origin, direction):
        action, position = old_hit(self, origin, direction)
        if self.page == _WHEEL and position is not None:
            local = (position - self.center) / self.scale
            hs = wheel_hs(local.dot(self.right), local.dot(self.up))
            if hs is not None:
                self.wheel_hs = hs
                return 'STUDIO_WHEEL_PICK', position
        if self.page != _HSV or position is None:
            return action, position
        local = (position - self.center) / self.scale
        x, y = local.dot(self.right), local.dot(self.up)
        if v056.SLIDER_X <= x <= v056.SLIDER_X + v056.SLIDER_W:
            for _label, new_action, row_y in _ROWS:
                if row_y <= y <= row_y + v056.SLIDER_H:
                    self.slider_value = min(1.0, max(0.0,
                        (x - v056.SLIDER_X) / v056.SLIDER_W))
                    return new_action, position
        return action, position

    def draw(self, shader, tool, hover, step, status, settings=None,
             selection='', select_mode='FACE'):
        old_draw(self, shader, tool, hover, step, status, settings, selection, select_mode)
        if self.page == _WHEEL and settings is not None and self.ready and self.visible:
            value = colorsys.rgb_to_hsv(*tuple(settings.object_color[:3]))[2]
            for ring in range(4):
                r0, r1 = ring * .0175, (ring + 1) * .0175
                for segment in range(48):
                    a, b = segment * math.tau / 48, (segment + 1) * math.tau / 48
                    points = [(r0, a), (r1, a), (r1, b), (r0, a), (r1, b), (r0, b)]
                    vertices = [self.world(.025 + r * math.cos(t), .09 + r * math.sin(t), .003) for r, t in points]
                    color = (*colorsys.hsv_to_rgb((segment + .5) / 48, (ring + .5) / 4, value), 1.)
                    drawing.draw_batch(shader, 'TRIS', vertices, color)
            return
        if self.page != _HSV or settings is None or not self.ready or not self.visible:
            return
        h, s, v = getattr(self, 'color_hsv',
                          colorsys.rgb_to_hsv(*tuple(settings.object_color[:3])))
        alpha = float(settings.object_color[3])
        v056._draw_rect(self, shader, -.108, .135, .280, .026,
                        (.015, .025, .04, .99), .0020)
        v056._draw_text(self, shader,
                        'HSV {} {} {}'.format(round(h * 360), round(s * 100),
                                             round(v * 100)), -.105, .153, .0022)
        v056._draw_slider(self, shader, 'HUE', .117, h,
                          lambda val: (*colorsys.hsv_to_rgb(val, 1, 1), alpha))
        v056._draw_slider(self, shader, 'SAT', .065, s,
                          lambda val: (*colorsys.hsv_to_rgb(h, val, v), alpha))
        v056._draw_slider(self, shader, 'VALUE', .013, v,
                          lambda val: (*colorsys.hsv_to_rgb(h, s, val), alpha))

    drawing.Menu.hit, drawing.Menu.draw = hit, draw
    drawing.Menu._xr_color_studio_sliders = True


class BXR_OT_color_hex_preview(bpy.types.Operator):
    bl_idname = 'blender_xr.color_hex_preview'
    bl_label = 'Use HEX Colour'
    bl_description = 'Preview HEX colour; use local/shared edit to change an existing material'
    bl_options = {'REGISTER'}

    def execute(self, context):
        settings = context.scene.blender_xr
        try:
            new = materials.from_hex(settings.color_hex, alpha=settings.object_color[3])
        except ValueError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        settings.object_color = new
        settings.color_hex = materials.to_hex(new)
        return {'FINISHED'}


CLASSES = (BXR_OT_color_hex_preview,)


def install_pages():
    original = menus.PAGES['MATERIAL_HOME']
    if any(action == 'COLOR_STUDIO_MENU' for _, action in original):
        return
    # 11 existing actions + exactly one contextual shortcut.
    if len(original) >= 12:
        raise ValueError('Material Home has no room for the colour studio')
    menus.PAGES['MATERIAL_HOME'] = original[:-1] + (
        ('EDIT COLOR', 'COLOR_STUDIO_MENU'), original[-1])
    menus.PAGES[_STUDIO] = (
        ('HSV', 'STUDIO_HSV'), ('READ MAT', 'STUDIO_READ'),
        ('WHEEL', 'STUDIO_WHEEL'), ('HEX INPUT', 'STUDIO_HEX_INPUT'), ('RGB', 'STUDIO_RGB'),
        ('PICK', 'STUDIO_PICK'), ('LOCAL EDIT', 'STUDIO_LOCAL'),
        ('SHARED EDIT', 'STUDIO_SHARED'), ('HEX', 'STUDIO_HEX_LOAD'),
        ('SWATCHES', 'STUDIO_SWATCHES'), ('HSL', 'COLOR_ADJUST_MENU'),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_WHEEL] = (
        *(('', 'PANEL') for _ in range(6)),
        ('DARKER', 'STUDIO_VALUE_DOWN'), ('BRIGHTER', 'STUDIO_VALUE_UP'),
        ('LOCAL EDIT', 'STUDIO_LOCAL'), ('SHARED EDIT', 'STUDIO_SHARED'),
        ('HSV', 'STUDIO_HSV'), ('BACK', 'BACK'),
    )
    menus.PAGES[_RGB] = tuple((channel + suffix, 'STUDIO_RGB_' + channel + '_' + direction)
        for channel in 'RGB' for suffix, direction in ((' -', 'DOWN'), (' +', 'UP'))) + (
        ('LOCAL EDIT', 'STUDIO_LOCAL'), ('SHARED EDIT', 'STUDIO_SHARED'), ('BACK', 'BACK'))
    menus.TITLES.update({_WHEEL: 'HSV WHEEL', _RGB: 'RGB COLOUR', _HEX: 'HEX INPUT'})
    menus.PAGES[_HEX] = (('CANCEL', 'STUDIO_HEX_CANCEL'),)
    menus.PAGES[_HSV] = (
        ('', 'PANEL'), ('', 'PANEL'), ('', 'PANEL'), ('', 'PANEL'),
        ('', 'PANEL'), ('', 'PANEL'),
        ('READ MAT', 'STUDIO_READ'), ('LOCAL EDIT', 'STUDIO_LOCAL'),
        ('SHARED EDIT', 'STUDIO_SHARED'), ('SWATCHES', 'STUDIO_SWATCHES'),
        ('HEX', 'STUDIO_HEX_LOAD'), ('BACK', 'BACK'),
    )
    menus.PAGES[_SWATCHES] = (
        tuple(('SAVE ' + str(i + 1), 'STUDIO_SAVE_' + str(i)) for i in range(4)) +
        tuple(('LOAD ' + str(i + 1), 'STUDIO_LOAD_' + str(i)) for i in range(4)) +
        (('BACK', 'BACK'),)
    )
    menus.TITLES.update({
        _STUDIO: 'NATIVE COLOUR EDIT', _HSV: 'HSV COLOUR',
        _SWATCHES: 'COLOUR SWATCHES',
    })
    v065.TOOLTIPS.update({
        'COLOR_STUDIO_MENU': ('Edit Existing Colour', 'Edit native material colours without replacing its nodes'),
        'STUDIO_LOCAL': ('Local Colour Edit', 'Duplicate a shared material before changing its colour'),
        'STUDIO_SHARED': ('Shared Colour Edit', 'Explicitly change the original material for all users'),
        'STUDIO_READ': ('Read Material', 'Preview the actual active material colour'),
        'STUDIO_HSV': ('HSV Sliders', 'Edit Hue, Saturation and Value by pointing at sliders'),
        'STUDIO_HEX_LOAD': ('Use HEX', 'Use the HEX value entered in Blender sidebar'),
        'STUDIO_SWATCHES': ('Swatches', 'Save and load four scene-persistent colours'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_color_studio_patched', False):
        return
    _patch_history()
    _patch_sliders()
    install_pages()
    old_command, old_tick = Runtime.command, Runtime.tick

    def command(self, context, action):
        if getattr(self, 'menu', None) is None:
            return old_command(self, context, action)
        if action == 'COLOR_STUDIO_MENU':
            self.menu.page = _STUDIO
            self.status = 'COLOUR PREVIEW / LOCAL OR SHARED'
            return
        if action == 'STUDIO_HEX_INPUT':
            self._xr_hex_buffer = ''
            self._xr_hex_page = 0
            _hex_page(self)
            return
        if self.menu.page == _HEX:
            if action.startswith('STUDIO_HEX_CHAR_'):
                char = action.removeprefix('STUDIO_HEX_CHAR_')
                if len(char) != 1 or char not in '0123456789ABCDEF':
                    raise ValueError('Invalid HEX digit')
                self._xr_hex_buffer = (self._xr_hex_buffer + char)[:6]
            elif action == 'STUDIO_HEX_DELETE':
                self._xr_hex_buffer = self._xr_hex_buffer[:-1]
            elif action == 'STUDIO_HEX_NEXT':
                self._xr_hex_page = 1 - self._xr_hex_page
            elif action == 'STUDIO_HEX_ACCEPT':
                color = materials.from_hex(self._xr_hex_buffer, alpha=self.settings.object_color[3])
                _read_color(self, color)
                self.menu.page = _STUDIO
                return
            elif action in {'STUDIO_HEX_CANCEL', 'BACK'}:
                self.menu.page = _STUDIO
                return
            else:
                return old_command(self, context, action)
            _hex_page(self)
            return
        if action in {'STUDIO_WHEEL', 'STUDIO_RGB'}:
            _read_color(self, self.settings.object_color)
            self.menu.page = _WHEEL if action == 'STUDIO_WHEEL' else _RGB
            return
        if action == 'STUDIO_WHEEL_PICK' and self.menu.page == _WHEEL:
            h, sat = self.menu.wheel_hs
            value = self.color_hsv[2]
            self.color_hsv = [h, sat, value]
            _read_color(self, (*colorsys.hsv_to_rgb(h, sat, value), self.settings.object_color[3]))
            return
        if action in {'STUDIO_VALUE_UP', 'STUDIO_VALUE_DOWN'} and self.menu.page == _WHEEL:
            h, sat, value = self.color_hsv
            value = min(1., max(0., value + (.05 if action.endswith('UP') else -.05)))
            _read_color(self, (*colorsys.hsv_to_rgb(h, sat, value), self.settings.object_color[3]))
            return
        if action.startswith('STUDIO_RGB_') and self.menu.page == _RGB:
            channel, direction = action.removeprefix('STUDIO_RGB_').split('_')
            color = list(self.settings.object_color)
            index = 'RGB'.index(channel)
            color[index] = min(1., max(0., color[index] + (.05 if direction == 'UP' else -.05)))
            _read_color(self, color)
            return
        if action == 'STUDIO_HSV':
            _read_color(self, self.settings.object_color)
            self.menu.page = _HSV
            return
        if action == 'STUDIO_SWATCHES':
            self._xr_swatch_parent = self.menu.page
            self.menu.page = _SWATCHES
            return
        if action == 'BACK':
            if self.menu.page == _SWATCHES:
                self.menu.page = getattr(self, '_xr_swatch_parent', _STUDIO)
                return
            if self.menu.page in {_HSV, _WHEEL, _RGB}:
                self.menu.page = _STUDIO
                return
            if self.menu.page == _STUDIO:
                self.menu.page = 'MATERIAL_HOME'
                return
        if action == 'COLOR_ADJUST_MENU' and self.menu.page == _STUDIO:
            self.color_return_page = _STUDIO
        if action in _SLIDERS:
            _hsv_command(self, action)
            return
        if action == 'STUDIO_READ':
            _obj, material = _active_material(context)
            _read_color(self, materials.material_color(material))
            self.status = 'READ / ' + material.name.upper()
            return
        if action == 'STUDIO_PICK':
            _read_color(self, materials.picked_color(context.view_layer.objects.active))
            self.status = 'PICKED COLOUR'
            return
        if action == 'STUDIO_HEX_LOAD':
            _read_color(self, materials.from_hex(
                self.settings.color_hex, alpha=self.settings.object_color[3]))
            self.status = 'HEX / ' + self.settings.color_hex.upper()
            return
        if action.startswith('STUDIO_SAVE_') or action.startswith('STUDIO_LOAD_'):
            index = int(action.rsplit('_', 1)[-1])
            if not 0 <= index < 4:
                raise ValueError('Unknown colour swatch')
            if action.startswith('STUDIO_SAVE_'):
                setattr(self.settings, 'color_swatch_' + str(index),
                        tuple(self.settings.object_color))
                self.status = 'SAVED SWATCH ' + str(index + 1)
            else:
                _read_color(self, _swatch(self.settings, index))
                self.status = 'LOADED SWATCH ' + str(index + 1)
            return
        if action in {'STUDIO_LOCAL', 'STUDIO_SHARED'}:
            # Gate the existing modal XR mutation system, do not create
            # an independent assignment or replacement workflow.
            if any(getattr(self, f, None) for f in
                   ('transaction', 'grab', 'air_grab', 'axis_move', '_xr_gesture',
                    '_weight_stroke', 'bone_drag')):
                raise ValueError('Finish the current XR edit before changing colour')
            scope = 'LOCAL' if action == 'STUDIO_LOCAL' else 'SHARED'
            entry = edit_active(context, self.settings.object_color, scope)
            if entry:
                self.history.push(entry)
                self.status = scope + ' COLOUR EDIT / ' + materials.to_hex(self.settings.object_color)
            else:
                self.status = 'MATERIAL COLOUR UNCHANGED'
            return
        return old_command(self, context, action)

    def tick(self, context):
        result = old_tick(self, context)
        if (self.menu.page == _WHEEL and getattr(self, 'trigger', None) and
                self.trigger.down and getattr(self, 'hover', None) == 'STUDIO_WHEEL_PICK' and
                not getattr(getattr(self, 'radial', None), 'active', False)):
            self.command(context, 'STUDIO_WHEEL_PICK')
        if (self.menu.page == _HSV and getattr(self, 'trigger', None) and
                self.trigger.down and getattr(self, 'hover', None) in _SLIDERS and
                getattr(self.menu, 'slider_value', None) is not None and
                not getattr(getattr(self, 'radial', None), 'active', False)):
            self.command(context, self.hover)
        return result

    Runtime.command = command
    Runtime.tick = tick
    Runtime._xr_color_studio_patched = True
