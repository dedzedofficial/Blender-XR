# SPDX-License-Identifier: GPL-3.0-or-later
"""Central VR menu definitions.

Keeping page definitions outside drawing.py makes future Materials, UV and
rigging pages easier to add without mixing UI structure with GPU drawing code.
"""

PAGES = {
    'TOOLS': (
        ('SELECT','SELECT'), ('MOVE','MOVE'),
        ('SCALE','SCALE'), ('EDIT MODE','MODE'),
        ('SHAPES','ADD_MENU'), ('COLORS','COLOR_MENU'),
        ('TRAVEL','NAV_MENU'), ('UNDO','UNDO'),
        ('REDO','REDO'), ('SAVE','SAVE'),
        ('STOP','STOP'),
    ),
    'EDIT': (
        ('VERT','SELECT_VERT'), ('EDGE','SELECT_EDGE'),
        ('FACE','SELECT_FACE'), ('SELECT','SELECT'),
        ('MOVE SEL','MOVE_EDIT'), ('SCALE SEL','SCALE_EDIT'),
        ('EXTRUDE','EXTRUDE'), ('BEVEL','BEVEL'),
        ('COLORS','COLOR_MENU'), ('UNDO','UNDO'),
        ('MORE','EDIT_MORE'), ('OBJECT','MODE'),
    ),
    'EDIT_MORE': (
        ('INSET','INSET'), ('DELETE','DELETE_GEOM'),
        ('MERGE','MERGE'), ('SUBDIVIDE','SUBDIVIDE'),
        ('DUPLICATE','DUPLICATE'), ('RECALC','RECALC'),
        ('FLIP NORMAL','FLIP_NORMALS'), ('REDO','REDO'),
        ('STEP -','LESS'), ('STEP +','MORE'),
        ('BACK','BACK'),
    ),
    'MATERIALS': (
        ('RED','COLOR_RED'), ('ORANGE','COLOR_ORANGE'),
        ('YELLOW','COLOR_YELLOW'), ('GREEN','COLOR_GREEN'),
        ('CYAN','COLOR_CYAN'), ('BLUE','COLOR_BLUE'),
        ('PURPLE','COLOR_PURPLE'), ('PINK','COLOR_PINK'),
        ('PICK','COLOR_PICK'), ('APPLY','COLOR_APPLY'),
        ('ADJUST','COLOR_ADJUST_MENU'), ('BACK','BACK'),
    ),
    'MATERIAL_ADJUST': (
        ('HUE -','COLOR_HUE_MINUS'), ('HUE +','COLOR_HUE_PLUS'),
        ('SAT -','COLOR_SAT_MINUS'), ('SAT +','COLOR_SAT_PLUS'),
        ('DARKER','COLOR_VALUE_MINUS'), ('BRIGHTER','COLOR_VALUE_PLUS'),
        ('WHITE','COLOR_WHITE'), ('BLACK','COLOR_BLACK'),
        ('PICK','COLOR_PICK'), ('APPLY','COLOR_APPLY'),
        ('COLORS','COLOR_PALETTE'), ('BACK','BACK'),
    ),
    'PRIMITIVES': tuple((kind, 'ADD_' + kind) for kind in
                        ('CUBE','SPHERE','CYLINDER','CONE','TORUS','PLANE')) + (
        ('TOOLS','BACK'),
    ),
    'TRAVEL': (
        ('FLY/WALK','FLY_TOGGLE'), ('TURBO','TURBO'),
        ('SLOWER','SLOWER'), ('FASTER','FASTER'),
        ('SNAP/SMOOTH','TURN_TOGGLE'), ('RESET VIEW','RESET'),
        ('TOOLS','BACK'),
    ),
}

TITLES = {
    'TOOLS': 'TOOLS',
    'EDIT': 'EDIT',
    'EDIT_MORE': 'MORE EDIT',
    'MATERIALS': 'COLORS',
    'MATERIAL_ADJUST': 'COLOR ADJUST',
    'PRIMITIVES': 'SHAPES',
    'TRAVEL': 'TRAVEL',
}


def buttons(page):
    return PAGES.get(page, PAGES['TOOLS'])


def title(page):
    return TITLES.get(page, 'TOOLS')
