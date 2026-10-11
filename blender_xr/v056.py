# SPDX-License-Identifier: GPL-3.0-or-later
"""v0.5.6 VR edit-mode and color-menu fixes."""
import bpy
import bmesh
from . import drawing, materials, mesh, statistics, transforms


SLIDER_ACTIONS = ('COLOR_HUE_SLIDER', 'COLOR_SAT_SLIDER', 'COLOR_LIGHT_SLIDER')
SLIDER_ROWS = (
    ('HUE', 'COLOR_HUE_SLIDER', 0.117),
    ('SAT', 'COLOR_SAT_SLIDER', 0.065),
    ('LIGHT', 'COLOR_LIGHT_SLIDER', 0.013),
)
SLIDER_X = -0.088
SLIDER_W = 0.262
SLIDER_H = 0.043


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
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    statistics.invalidate()


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


def _draw_text(menu, shader, label, x, y, pixel=0.0023):
    points = []
    for i, char in enumerate(label.upper()):
        for row, line in enumerate(drawing.FONT.get(char, drawing.FONT[' '])):
            for col, value in enumerate(line):
                if value != '1':
                    continue
                for px, py in drawing.rectangle_points(
                        x + i * 6 * pixel + col * pixel,
                        y - row * pixel, pixel * 0.86, pixel * 0.86):
                    points.append(menu.world(px, py, 0.0021))
    if points:
        drawing.draw_batch(shader, 'TRIS', points, (0.88, 0.95, 1, 1))


def _draw_rect(menu, shader, x, y, w, h, color, depth=0.0019):
    drawing.draw_batch(shader, 'TRIS',
        [menu.world(px, py, depth) for px, py in drawing.rectangle_points(x, y, w, h)], color)


def _draw_slider(menu, shader, label, y, value, color_at):
    _draw_text(menu, shader, label, -0.174, y + 0.030, 0.0022)
    track_y = y + 0.010
    track_h = 0.022
    segments = 32
    for index in range(segments):
        x0 = SLIDER_X + SLIDER_W * index / segments
        x1 = SLIDER_X + SLIDER_W * (index + 1) / segments
        _draw_rect(menu, shader, x0, track_y, x1 - x0 + 0.0004, track_h,
                   color_at((index + 0.5) / segments), 0.0020)
    marker_x = SLIDER_X + SLIDER_W * max(0.0, min(1.0, float(value)))
    _draw_rect(menu, shader, marker_x - 0.0022, y + 0.005, 0.0044, 0.032,
               (1, 1, 1, 1), 0.0024)


def _patch_menu_sliders():
    """Overlay real pointer sliders on the reserved HSL menu rows."""
    if getattr(drawing.Menu, '_v056_hsl_sliders', False):
        return
    original_hit = drawing.Menu.hit
    original_draw = drawing.Menu.draw

    def hit(self, origin, direction):
        action, pos = original_hit(self, origin, direction)
        self.slider_value = None
        if self.page != 'MATERIAL_ADJUST' or pos is None:
            return action, pos
        local = (pos - self.center) / self.scale
        x, y = local.dot(self.right), local.dot(self.up)
        if SLIDER_X <= x <= SLIDER_X + SLIDER_W:
            for _label, slider_action, row_y in SLIDER_ROWS:
                if row_y <= y <= row_y + SLIDER_H:
                    self.slider_value = max(0.0, min(1.0, (x - SLIDER_X) / SLIDER_W))
                    return slider_action, pos
        return action, pos

    def draw(self, shader, tool, hover, step, status, settings=None, selection='', select_mode='FACE'):
        original_draw(self, shader, tool, hover, step, status, settings, selection, select_mode)
        if self.page != 'MATERIAL_ADJUST' or settings is None or not self.ready or not self.visible:
            return
        hsl = tuple(getattr(self, 'color_hsl', materials.color_hsl(settings.object_color)))
        hue, saturation, lightness = hsl
        alpha = float(settings.object_color[3])
        # Cover the RGB summary from the generic renderer with the useful HSL values.
        _draw_rect(self, shader, -0.108, 0.135, 0.280, 0.026, (0.015, 0.025, 0.04, 0.99), 0.0020)
        _draw_text(self, shader, materials.hsl_summary(hsl, is_hsl=True), -0.105, 0.153, 0.00225)
        _draw_slider(self, shader, 'HUE', 0.117, hue,
                     lambda value: materials.color_from_hsl(value, 1.0, 0.5, alpha))
        _draw_slider(self, shader, 'SAT', 0.065, saturation,
                     lambda value: materials.color_from_hsl(hue, value, lightness, alpha))
        _draw_slider(self, shader, 'LIGHT', 0.013, lightness,
                     lambda value: materials.color_from_hsl(hue, saturation, value, alpha))

    drawing.Menu.hit = hit
    drawing.Menu.draw = draw
    drawing.Menu._v056_hsl_sliders = True


def _sync_hsl(session, color=None, preserve_gray_hue=False):
    color = tuple(color if color is not None else session.settings.object_color)
    hue, saturation, lightness = materials.color_hsl(color)
    old = getattr(session, 'color_hsl', None)
    if preserve_gray_hue and saturation < 1e-7 and old is not None:
        hue = old[0]
    session.color_hsl = [hue, saturation, lightness]
    session.menu.color_hsl = tuple(session.color_hsl)
    return session.color_hsl


def _apply_hsl(session):
    h, s, l = session.color_hsl
    alpha = float(session.settings.object_color[3])
    session.settings.object_color = materials.color_from_hsl(h, s, l, alpha)
    session.menu.color_hsl = tuple(session.color_hsl)


def patch(Runtime):
    """Patch the already-v0.5-aware Runtime with v0.5.6 controller UX."""
    if getattr(Runtime, '_v056_patched', False):
        return
    _patch_material_history()
    _patch_menu_sliders()
    original_command = Runtime.command
    original_tick = Runtime.tick

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
            _sync_hsl(self)
            self.menu.page = 'MATERIAL_ADJUST'
            self.status = 'HSL COLOR / PICK / APPLY'
            return
        if action == 'COLOR_ADJUST_MENU':
            _sync_hsl(self)
            self.menu.page = 'MATERIAL_ADJUST'
            self.status = 'DRAG HUE / SAT / LIGHT'
            return
        if action == 'COLOR_PALETTE':
            self.menu.page = 'MATERIALS'
            self.status = 'OPTIONAL COLOR PRESETS'
            return
        if action == 'BACK' and self.menu.page in {'MATERIALS', 'MATERIAL_ADJUST'}:
            if self.menu.page == 'MATERIALS':
                self.menu.page = 'MATERIAL_ADJUST'
                self.status = 'HSL COLOR'
            else:
                self.menu.page = getattr(self, 'color_return_page', 'TOOLS')
                self.status = 'COLOR MENU CLOSED'
            return

        if action in materials.PRESET_COLORS:
            self.settings.object_color = materials.PRESET_COLORS[action]
            _sync_hsl(self)
            self.status = 'COLOR ' + action.removeprefix('COLOR_')
            return

        if action in SLIDER_ACTIONS:
            value = getattr(self.menu, 'slider_value', None)
            if value is None:
                return
            if not hasattr(self, 'color_hsl'):
                _sync_hsl(self)
            component = {
                'COLOR_HUE_SLIDER': 0,
                'COLOR_SAT_SLIDER': 1,
                'COLOR_LIGHT_SLIDER': 2,
            }[action]
            self.color_hsl[component] = max(0.0, min(1.0, float(value)))
            _apply_hsl(self)
            self.status = materials.hsl_summary(self.color_hsl, is_hsl=True)
            return
        if action == 'COLOR_WHITE':
            if not hasattr(self, 'color_hsl'):
                _sync_hsl(self)
            self.color_hsl[2] = 1.0
            _apply_hsl(self)
            self.status = 'LIGHTNESS 100'
            return
        if action == 'COLOR_BLACK':
            if not hasattr(self, 'color_hsl'):
                _sync_hsl(self)
            self.color_hsl[2] = 0.0
            _apply_hsl(self)
            self.status = 'LIGHTNESS 0'
            return
        if action == 'COLOR_PICK':
            obj = context.view_layer.objects.active
            self.settings.object_color = materials.picked_color(obj)
            _sync_hsl(self, preserve_gray_hue=True)
            self.status = 'PICKED ' + materials.hsl_summary(self.color_hsl, is_hsl=True)
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
                if before != after:
                    self.history.push(('FACE_MATERIAL', obj.name, obj.data.name, before, after))
                    self.status = 'COLOR APPLIED TO ' + str(count) + ' FACE' + ('' if count == 1 else 'S')
                else:
                    self.status = 'SELECTED FACE COLOR UNCHANGED'
            else:
                material = materials.apply_object_color(obj, self.settings.object_color)
                self.status = 'COLOR APPLIED / ' + material.name.upper()
            statistics.invalidate()
            return

        return original_command(self, context, action)

    def tick(self, context):
        result = original_tick(self, context)
        # Runtime's normal press path sets the slider immediately. Re-running it
        # while trigger remains held turns that same track into a continuous drag.
        if (getattr(self, 'trigger', None) and self.trigger.down and
                getattr(self, 'hover', None) in SLIDER_ACTIONS and
                getattr(self.menu, 'slider_value', None) is not None):
            command(self, context, self.hover)
        return result

    Runtime.command = command
    Runtime.tick = tick
    Runtime._v056_patched = True
