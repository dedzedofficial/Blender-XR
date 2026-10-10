# SPDX-License-Identifier: GPL-3.0-or-later
"""Central VR menu definitions.

Keeping page definitions outside drawing.py makes future Materials, UV and
rigging pages easier to add without mixing UI structure with GPU drawing code.
"""

PAGES = {
    'TOOLS': (
        ('SELECT','SELECT'), ('MOVE','MOVE'),
        ('SCALE','SCALE'), ('EDIT MODE','MODE'),
        ('SHAPES','ADD_MENU'), ('TRAVEL','NAV_MENU'),
        ('UNDO','UNDO'), ('REDO','REDO'),
        ('SAVE','SAVE'), ('STOP','STOP'),
    ),
    'EDIT': (
        ('VERT','SELECT_VERT'), ('EDGE','SELECT_EDGE'),
        ('FACE','SELECT_FACE'), ('SELECT','SELECT'),
        ('MOVE','MOVE_FACE'), ('SCALE','SCALE_FACE'),
        ('EXTRUDE','EXTRUDE'), ('BEVEL','BEVEL'),
        ('MORE','EDIT_MORE'), ('OBJECT','MODE'),
    ),
    'EDIT_MORE': (
        ('INSET','INSET'), ('DELETE','DELETE_GEOM'),
        ('MERGE','MERGE'), ('SUBDIVIDE','SUBDIVIDE'),
        ('DUPLICATE','DUPLICATE'), ('RECALC','RECALC'),
        ('FLIP NORMAL','FLIP_NORMALS'), ('STEP -','LESS'),
        ('STEP +','MORE'), ('BACK','BACK'),
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
    'PRIMITIVES': 'SHAPES',
    'TRAVEL': 'TRAVEL',
}


def buttons(page):
    return PAGES.get(page, PAGES['TOOLS'])


def title(page):
    return TITLES.get(page, 'TOOLS')
