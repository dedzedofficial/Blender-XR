# SPDX-License-Identifier: GPL-3.0-or-later
"""Hardware-independent thumbstick radial input state machine (v0.8)."""
import math

SECTORS = 8
ENTRY_THRESHOLD = 0.55
EXIT_THRESHOLD = 0.40
# Category actions use their existing Blender menu commands; no duplicate tools.
CATEGORIES = frozenset((
    'MODE_MENU', 'MATERIAL_MENU', 'ADD_MENU', 'RIG_MENU', 'NAV_MENU',
    'EDIT_MORE', 'PARENT_MENU', 'UV_MENU', 'UV_TRANSFORM_MENU',
    'COLOR_MENU', 'COLOR_ADJUST_MENU', 'MAT_PROPS', 'MAT_SLOTS',
    'MAT_TEXTURES', 'GEOMETRY_ADVANCED', 'OBJECT_ADVANCED',
    'MODIFIER_MENU', 'BONE_SELECT_MENU', 'BONE_EDIT_MENU',
    'BONE_SETTINGS_MENU', 'BONE_OPERATIONS_MENU', 'RIG_EDIT_MENU',
    'LOOP_CUT_MENU', 'COLOR_PALETTE',
))


def wedge(x, y, previous=None, entry=ENTRY_THRESHOLD, exit=EXIT_THRESHOLD):
    """0 is top; numbers advance clockwise; deadzone and boundary hysteresis."""
    x, y = float(x), float(y)
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    distance = math.hypot(x, y)
    if distance < (exit if previous is not None else entry):
        return None
    angle = math.atan2(x, y) % (2 * math.pi)
    step = 2 * math.pi / SECTORS
    result = int((angle + step / 2) // step) % SECTORS
    if previous is not None and result != previous:
        center = previous * step
        delta = abs((angle - center + math.pi) % (2 * math.pi) - math.pi)
        if delta < step / 2 + math.radians(9):
            return previous
    return result


def visible_actions(buttons, offset=0):
    """Eight maximum, last item cycles to the next chunk if needed."""
    valid = [(label, action) for label, action in buttons if action != 'PANEL']
    if len(valid) <= SECTORS:
        return valid
    pages = (len(valid) + 6) // 7
    offset = int(offset) % pages
    return valid[offset * 7:(offset + 1) * 7] + [
        ('MORE' if offset < pages - 1 else 'FIRST', 'RADIAL_NEXT')]


class RadialState:
    """Called once per controller snapshot, never from the draw callback."""

    def __init__(self):
        self.active = False
        self.selected = None
        self.page_offset = 0
        self.page_name = ''
        self._ready = True

    def reset(self):
        self.active = False
        self.selected = None
        self._ready = True

    def update(self, held, xy, buttons, page, submenus=CATEGORIES):
        """Return ('open'|'hover'|'navigate'|'select'|'close'|'next', action)."""
        if not held:
            if not self.active:
                self._ready = True
                return None
            selected = self.selected
            actions = visible_actions(buttons, self.page_offset)
            command = actions[selected][1] if selected is not None and selected < len(actions) else None
            self.reset()
            if command == 'RADIAL_NEXT':
                self.page_offset += 1
                return 'next', None
            return ('select', command) if command else ('close', None)
        if not self.active:
            if not self._ready:
                return None
            self.active = True
            self.selected = None
            self.page_offset = 0
            self.page_name = page
            return 'open', None
        if page != self.page_name:
            self.page_name = page
            self.page_offset = 0
            self.selected = None
        x, y = xy
        previous = self.selected
        selection = wedge(x, y, previous)
        actions = visible_actions(buttons, self.page_offset)
        if selection is not None and selection >= len(actions):
            selection = None
        if selection is None and previous is not None and previous < len(actions):
            command = actions[previous][1]
            self.selected = None
            if command == 'RADIAL_NEXT':
                self.page_offset += 1
                return 'next', None
            if command in submenus:
                return 'navigate', command
        if selection != self.selected:
            self.selected = selection
            return 'hover', actions[selection][1] if selection is not None else None
        return None
