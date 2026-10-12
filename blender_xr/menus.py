# SPDX-License-Identifier: GPL-3.0-or-later
"""Central VR menu definitions.

Keeping page definitions outside drawing.py makes Materials, UV, transform and
future rigging pages easy to extend without mixing UI structure into rendering.
"""

PAGES = {
    'TOOLS': (
        ('SELECT','SELECT'), ('MOVE','MOVE'),
        ('SCALE','SCALE'), ('EDIT MODE','MODE'),
        ('SHAPES','ADD_MENU'), ('MATERIALS','MATERIAL_MENU'),
        ('TRAVEL','NAV_MENU'), ('UNDO','UNDO'),
        ('REDO','REDO'), ('SAVE','SAVE'),
        ('STOP','STOP'),
    ),
    'EDIT': (
        ('VERT','SELECT_VERT'), ('EDGE','SELECT_EDGE'),
        ('FACE','SELECT_FACE'), ('SELECT','SELECT'),
        ('MOVE SEL','MOVE_EDIT'), ('SCALE SEL','SCALE_EDIT'),
        ('EXTRUDE','EXTRUDE'), ('BEVEL','BEVEL'),
        ('MATERIALS','MATERIAL_MENU'), ('UNDO','UNDO'),
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
    'MATERIAL_HOME': (
        ('BASE COLOR','COLOR_MENU'), ('PROPERTIES','MAT_PROPS'),
        ('SLOTS','MAT_SLOTS'), ('TEXTURES','MAT_TEXTURES'),
        ('UV TOOLS','UV_MENU'), ('PREVIEW','MAT_PREVIEW'),
        ('NEW MAT','MAT_NEW'), ('DUP MAT','MAT_DUP'),
        ('DELETE MAT','MAT_DELETE'), ('AUTO NAME','MAT_RENAME_AUTO'),
        ('BACK','BACK'),
    ),
    'MATERIAL_PROPS': (
        ('METAL -','MAT_METAL_DOWN'), ('METAL +','MAT_METAL_UP'),
        ('ROUGH -','MAT_ROUGH_DOWN'), ('ROUGH +','MAT_ROUGH_UP'),
        ('ALPHA -','MAT_ALPHA_DOWN'), ('ALPHA +','MAT_ALPHA_UP'),
        ('EMIT -','MAT_EMIT_DOWN'), ('EMIT +','MAT_EMIT_UP'),
        ('READ MAT','MAT_SYNC'), ('BACK','BACK'),
    ),
    'MATERIAL_SLOTS': (
        ('PREV SLOT','SLOT_PREV'), ('NEXT SLOT','SLOT_NEXT'),
        ('ADD SLOT','SLOT_ADD'), ('REMOVE SLOT','SLOT_REMOVE'),
        ('ASSIGN FACES','SLOT_ASSIGN'), ('SELECT FACES','SLOT_SELECT_FACES'),
        ('NEW MAT','MAT_NEW'), ('DUP MAT','MAT_DUP'),
        ('BACK','BACK'),
    ),
    'MATERIAL_TEXTURES': (
        ('PREV IMG','IMG_PREV'), ('NEXT IMG','IMG_NEXT'),
        ('APPLY IMG','IMG_APPLY'), ('CLEAR TEX','IMG_CLEAR'),
        ('CHECKER','IMG_CHECKER'), ('DIRECTION','IMG_DIRECTION'),
        ('COLOR GRID','IMG_GRID'), ('BACK','BACK'),
    ),
    'MATERIALS': (
        ('RED','COLOR_RED'), ('ORANGE','COLOR_ORANGE'),
        ('YELLOW','COLOR_YELLOW'), ('GREEN','COLOR_GREEN'),
        ('CYAN','COLOR_CYAN'), ('BLUE','COLOR_BLUE'),
        ('PURPLE','COLOR_PURPLE'), ('PINK','COLOR_PINK'),
        ('HSL','COLOR_ADJUST_MENU'), ('PICK','COLOR_PICK'),
        ('APPLY','COLOR_APPLY'), ('BACK','BACK'),
    ),
    # The first three rows are reserved for the full-width H/S/L slider overlay.
    'MATERIAL_ADJUST': (
        ('','PANEL'), ('','PANEL'),
        ('','PANEL'), ('','PANEL'),
        ('','PANEL'), ('','PANEL'),
        ('PICK','COLOR_PICK'), ('APPLY','COLOR_APPLY'),
        ('WHITE','COLOR_WHITE'), ('BLACK','COLOR_BLACK'),
        ('PRESETS','COLOR_PALETTE'), ('BACK','BACK'),
    ),
    'UV': (
        ('UNWRAP','UV_UNWRAP'), ('SMART','UV_SMART'),
        ('CUBE','UV_CUBE'), ('PLANAR','UV_PLANAR'),
        ('MARK SEAM','UV_MARK_SEAM'), ('CLEAR SEAM','UV_CLEAR_SEAM'),
        ('TRANSFORM','UV_TRANSFORM_MENU'), ('PACK','UV_PACK'),
        ('RESET UV','UV_RESET'), ('PREVIEW','UV_PREVIEW'),
        ('BACK','BACK'),
    ),
    'UV_TRANSFORM': (
        ('U -','UV_U_DOWN'), ('U +','UV_U_UP'),
        ('V -','UV_V_DOWN'), ('V +','UV_V_UP'),
        ('ROT -15','UV_ROT_DOWN'), ('ROT +15','UV_ROT_UP'),
        ('SCALE -','UV_SCALE_DOWN'), ('SCALE +','UV_SCALE_UP'),
        ('PACK','UV_PACK'), ('RESET','UV_RESET'),
        ('BACK','BACK'),
    ),
    'UV_PREVIEW': (
        ('PACK','UV_PACK'), ('RESET','UV_RESET'),
        ('BACK','BACK'),
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
    'MATERIAL_HOME': 'MATERIALS',
    'MATERIAL_PROPS': 'MATERIAL PROPS',
    'MATERIAL_SLOTS': 'MATERIAL SLOTS',
    'MATERIAL_TEXTURES': 'TEXTURES',
    'MATERIALS': 'COLOR PRESETS',
    'MATERIAL_ADJUST': 'HSL COLOR',
    'UV': 'UV MAPPING',
    'UV_TRANSFORM': 'UV TRANSFORM',
    'UV_PREVIEW': 'UV PREVIEW',
    'PRIMITIVES': 'SHAPES',
    'TRAVEL': 'TRAVEL',
}


def buttons(page):
    return PAGES.get(page, PAGES['TOOLS'])


def title(page):
    return TITLES.get(page, 'TOOLS')
