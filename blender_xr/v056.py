# SPDX-License-Identifier: GPL-3.0-or-later
"""v0.5.6 VR edit-mode and color-menu fixes."""
from . import materials, mesh, transforms


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

        if action in materials.PRESET_COLORS:
            self.settings.object_color = materials.PRESET_COLORS[action]
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
                    _material, count, _slot = materials.assign_color_to_selected_faces(
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
