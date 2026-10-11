# SPDX-License-Identifier: GPL-3.0-or-later
"""v0.5.6 VR edit-mode, color-menu and version-display fixes."""
from . import drawing, materials, mesh, transforms, version


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


def _text(menu, shader, label, x, y, pixel=0.0024, color=(0.88, 0.95, 1, 1)):
    points = []
    for i, char in enumerate(label.upper()):
        for row, line in enumerate(drawing.FONT.get(char, drawing.FONT[' '])):
            for col, value in enumerate(line):
                if value != '1':
                    continue
                for px, py in drawing.rectangle_points(
                        x + i * 6 * pixel + col * pixel,
                        y - row * pixel, pixel * 0.86, pixel * 0.86):
                    points.append(menu.world(px, py, 0.0018))
    if points:
        drawing.draw_batch(shader, 'TRIS', points, color)


def _rect(menu, shader, x, y, w, h, color, depth=0.0016):
    drawing.draw_batch(shader, 'TRIS',
        [menu.world(px, py, depth) for px, py in drawing.rectangle_points(x, y, w, h)],
        color)


def patch_draw():
    if getattr(drawing.Menu, '_v056_patched', False):
        return
    original_draw = drawing.Menu.draw

    def draw(self, shader, tool, hover, step, status, settings=None,
             selection='', select_mode='FACE'):
        original_draw(self, shader, tool, hover, step, status, settings, selection, select_mode)
        if not self.ready or not self.visible:
            return
        # Cover the old duplicated footer and always show the shared version source.
        _rect(self, shader, -0.181, -0.286, 0.112, 0.022, (0.015, 0.025, 0.04, 1))
        _text(self, shader, version.DISPLAY_VERSION, -0.174, -0.274, 0.0021)
        if settings is not None and self.page in {'MATERIALS', 'MATERIAL_ADJUST'}:
            # Replace the generic tool summary with a live swatch and RGB readout.
            _rect(self, shader, -0.184, 0.137, 0.368, 0.026, (0.015, 0.025, 0.04, 1))
            color = tuple(float(v) for v in settings.object_color[:4])
            _rect(self, shader, -0.174, 0.141, 0.058, 0.018, color)
            _text(self, shader, materials.color_summary(color), -0.105, 0.155, 0.00215)

    drawing.Menu.draw = draw
    drawing.Menu._v056_patched = True


def patch(Runtime):
    """Patch the already-v0.5-aware Runtime with v0.5.6 controller UX."""
    if getattr(Runtime, '_v056_patched', False):
        return
    original_command = Runtime.command

    def command(self, context, action):
        # Public edit actions are mode-neutral. Internally retain the proven
        # v0.5 transaction names so old tests and third-party calls keep working.
        if action == 'MOVE_EDIT':
            original_command(self, context, 'MOVE_FACE')
            self.status = 'MOVE SELECTED READY'
            return
        if action == 'SCALE_EDIT':
            original_command(self, context, 'SCALE_FACE')
            self.status = 'SCALE SELECTED READY'
            return

        if action == 'COLOR_MENU':
            transforms.ensure_idle(self)
            obj = context.view_layer.objects.active
            self.color_return_page = 'EDIT' if obj and obj.mode == 'EDIT' else 'TOOLS'
            self.menu.page = 'MATERIALS'
            self.status = 'CHOOSE / PICK / APPLY COLOR'
            return
        if action == 'COLOR_ADJUST_MENU':
            self.menu.page = 'MATERIAL_ADJUST'
            self.status = 'ADJUST CURRENT COLOR'
            return
        if action == 'COLOR_PALETTE':
            self.menu.page = 'MATERIALS'
            self.status = 'CHOOSE / PICK / APPLY COLOR'
            return
        if action == 'BACK' and self.menu.page in {'MATERIALS', 'MATERIAL_ADJUST'}:
            if self.menu.page == 'MATERIAL_ADJUST':
                self.menu.page = 'MATERIALS'
                self.status = 'COLOR PALETTE'
            else:
                self.menu.page = getattr(self, 'color_return_page', 'TOOLS')
                self.status = 'COLOR MENU CLOSED'
            return

        if action in PRESET_COLORS:
            self.settings.object_color = PRESET_COLORS[action]
            self.status = 'COLOR ' + action.removeprefix('COLOR_')
            return

        adjustments = {
            'COLOR_HUE_MINUS': (-1.0 / 24.0, 0.0, 0.0),
            'COLOR_HUE_PLUS': (1.0 / 24.0, 0.0, 0.0),
            'COLOR_SAT_MINUS': (0.0, -0.1, 0.0),
            'COLOR_SAT_PLUS': (0.0, 0.1, 0.0),
            'COLOR_VALUE_MINUS': (0.0, 0.0, -0.1),
            'COLOR_VALUE_PLUS': (0.0, 0.0, 0.1),
        }
        if action in adjustments:
            hue, saturation, value = adjustments[action]
            self.settings.object_color = materials.adjust_hsv(
                self.settings.object_color, hue, saturation, value)
            self.status = 'COLOR ' + materials.color_summary(self.settings.object_color)
            return
        if action == 'COLOR_WHITE':
            self.settings.object_color = (1.0, 1.0, 1.0, 1.0)
            self.status = 'COLOR WHITE'
            return
        if action == 'COLOR_BLACK':
            self.settings.object_color = (0.0, 0.0, 0.0, 1.0)
            self.status = 'COLOR BLACK'
            return
        if action == 'COLOR_PICK':
            obj = context.view_layer.objects.active
            self.settings.object_color = materials.picked_color(obj)
            self.status = 'PICKED ' + materials.color_summary(self.settings.object_color)
            return
        if action == 'COLOR_APPLY':
            transforms.ensure_idle(self)
            obj = context.view_layer.objects.active
            if obj and obj.mode == 'EDIT':
                if getattr(self, 'select_mode', 'FACE') != 'FACE':
                    raise ValueError('Switch to FACE selection before applying a face color')
                before = mesh.snapshot(obj)
                try:
                    material, count, _slot = materials.assign_color_to_selected_faces(
                        obj, self.settings.object_color)
                    after = mesh.snapshot(obj)
                except Exception:
                    mesh.restore(obj, before)
                    import bpy
                    bpy.data.meshes.remove(before)
                    raise
                self.history.push(('MESH', obj.name, obj.data.name, before, after))
                self.status = 'COLOR APPLIED TO ' + str(count) + ' FACE' + ('' if count == 1 else 'S')
            else:
                material = materials.apply_object_color(obj, self.settings.object_color)
                self.status = 'COLOR APPLIED / ' + material.name.upper()
            return

        return original_command(self, context, action)

    Runtime.command = command
    Runtime._v056_patched = True
    patch_draw()
