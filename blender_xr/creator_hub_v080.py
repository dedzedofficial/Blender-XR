# SPDX-License-Identifier: GPL-3.0-or-later
"""Compact creator entry point for existing Mesh XR workflows.

Creator Hub groups *registered native operations* into one 12-cell XR menu.
It does not duplicate mesh, rigging or material editing implementations.
"""
from . import input_ownership_v080, menus, v065

_LINKS = frozenset({
    'NAV_MENU', 'FOCUS_MENU', 'LAYOUT_MENU', 'OBJECT_ADVANCED',
    'MODIFIER_MENU', 'RIG_MENU', 'ADD_MENU', 'MATERIAL_MENU', 'UV_MENU',
})


def install_page():
    # The top-level wrist/radial menu can display 12 cells. Keep the frequent
    # edit/undo/save/stop buttons; the old Travel page is available via Hub.
    old_actions = {action for _, action in menus.PAGES['TOOLS']}
    if not {'NAV_MENU', 'RIG_MENU'} <= old_actions:
        raise ValueError('Creator Hub needs the existing Travel and Rigging categories')
    # Legacy v0.6.5 intentionally has THIRTEEN top-level cells. Route the
    # existing Rigging action through Creator instead of hiding an offscreen
    # button or removing important Undo/Save/Stop tools.
    tools = tuple(
        ('', 'CREATOR_MENU') if action == 'NAV_MENU' else (label, action)
        for label, action in menus.PAGES['TOOLS'] if action != 'RIG_MENU'
    )
    if len(tools) != 12 or sum(action == 'CREATOR_MENU' for _, action in tools) != 1:
        raise ValueError('Creator Hub must fit the existing 12-button main menu')
    menus.PAGES['TOOLS'] = tools
    menus.PAGES['CREATOR'] = (
        ('TRAVEL', 'NAV_MENU'), ('FOCUS', 'FOCUS_MENU'),
        ('LAYOUT', 'LAYOUT_MENU'), ('OBJECT', 'OBJECT_ADVANCED'),
        ('MODIFIERS', 'MODIFIER_MENU'), ('RIGGING', 'RIG_MENU'),
        ('WEIGHTS', 'MODE_WEIGHT_PAINT'), ('SHAPES', 'ADD_MENU'),
        ('MATERIALS', 'MATERIAL_MENU'), ('UV', 'UV_MENU'),
        ('DELETE OBJ', 'DELETE_OBJECT'), ('BACK', 'BACK'),
    )
    menus.TITLES['CREATOR'] = 'CREATOR HUB'
    v065.TOOLTIPS['CREATOR_MENU'] = ('Creator Hub', 'Open the combined modelling, rigging, layout and scene tools')


def patch_runtime(Runtime):
    if getattr(Runtime, '_v080_creator_hub_patched', False):
        return
    install_page()
    original = Runtime.command

    def command(self, context, action):
        # Some Blender operators invoke command on a bare test/runtime proxy
        # before an XR menu exists. Preserve the old dispatch for those calls.
        menu = getattr(self, 'menu', None)
        if menu is None:
            return original(self, context, action)
        page = menu.page
        if action == 'CREATOR_MENU':
            if input_ownership_v080.is_editing(self):
                raise ValueError('Finish the current edit before opening Creator Hub')
            self.menu.page = 'CREATOR'
            self._creator_parent_page = None
            self.status = 'CREATOR HUB / ALL TOOLS IN ONE WORKSPACE'
            return
        if action == 'BACK':
            if page == 'CREATOR':
                self.menu.page = 'TOOLS'
                self._creator_parent_page = None
                return
            # Going back from a directly launched Hub page returns to Hub,
            # not to an unrelated legacy parent. Nested pages keep their
            # existing handlers (e.g. Layout -> Object Tools -> Creator).
            if page == getattr(self, '_creator_parent_page', None):
                self.menu.page = 'CREATOR'
                self._creator_parent_page = None
                return
        if page == 'CREATOR' and action in _LINKS:
            # Validate and dispatch through original mode-aware operator code.
            result = original(self, context, action)
            if self.menu.page not in {'CREATOR', 'TOOLS'}:
                self._creator_parent_page = self.menu.page
            return result
        return original(self, context, action)

    Runtime.command = command
    Runtime._v080_creator_hub_patched = True
