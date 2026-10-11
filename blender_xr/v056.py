# SPDX-License-Identifier: GPL-3.0-or-later
"""v0.5.6 VR edit-mode and color-menu fixes."""
import bpy
from . import materials, mesh, transforms


def _selected_face_material_state(obj):
    """Capture only selected-face material slots; no topology snapshots needed."""
    bm = mesh.editable(obj)
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    state = tuple((face.index, int(face.material_index))
                  for face in bm.faces if face.is_valid and face.select and not face.hide)
    if not state:
        raise ValueError('Select one or more faces first')
    return state


def _restore_face_material_state(obj, state):
    bm = mesh.editable(obj)
    bm.faces.ensure_lookup_table()
    for face_index, material_index in state:
        if face_index < 0 or face_index >= len(bm.faces):
            raise ValueError('Mesh topology changed; undo geometry changes before color history')
        face = bm.faces[face_index]
        if not face.is_valid:
            raise ValueError('Mesh topology changed; undo geometry changes before color history')
        face.material_index = int(material_index)
    mesh.update(obj)


def _patch_material_history():
    """Extend VR-local history with lightweight face-material-only entries."""
    if getattr(mesh.History, '_v056_material_history', False):
        return
    original_release = mesh.History.release
    original_step = mesh.History.step

    def release(entry):
        if entry[0] == 'FACE_MATERIAL':
            return
        return original_release(entry)

    def step(self, backwards=True):
        source, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not source or source[-1][0] != 'FACE_MATERIAL':
            return original_step(self, backwards)
        entry = source[-1]
        obj = bpy.data.objects.get(entry[1])
        if obj is None:
            raise ValueError('The edited object was removed; restart VR to clear history')
        if obj.type != 'MESH' or obj.data.name != entry[2]:
            raise ValueError('The mesh changed outside VR; restart VR')
        if obj.mode != 'EDIT':
            raise ValueError('Switch to edit mode before undoing face colors')
        _restore_face_material_state(obj, entry[3] if backwards else entry[4])
        dest.append(source.pop())
        return True

    mesh.History.release = staticmethod(release)
    mesh.History.step = step
    mesh.History._v056_material_history = True


def patch(Runtime):
    """Patch the already-v0.5-aware Runtime with v0.5.6 controller UX."""
    if getattr(Runtime, '_v056_patched', False):
        return
    _patch_material_history()
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
                before = _selected_face_material_state(obj)
                _material, count, _slot = materials.assign_color_to_selected_faces(
                    obj, self.settings.object_color)
                after = _selected_face_material_state(obj)
                self.history.push(('FACE_MATERIAL', obj.name, obj.data.name, before, after))
                self.status = 'COLOR APPLIED TO ' + str(count) + ' FACE' + ('' if count == 1 else 'S')
            else:
                material = materials.apply_object_color(obj, self.settings.object_color)
                self.status = 'COLOR APPLIED / ' + material.name.upper()
            return

        return original_command(self, context, action)

    Runtime.command = command
    Runtime._v056_patched = True
