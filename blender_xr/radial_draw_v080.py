# SPDX-License-Identifier: GPL-3.0-or-later
"""XR radial-menu drawing only; input decisions live in radial_logic_v080."""
import math
from . import drawing
from .radial_logic_v080 import visible_actions


def _letters(menu, shader, label, x, y, size=.0021):
    vertices = []
    for index, ch in enumerate(label.upper()[:11]):
        for row, bits in enumerate(drawing.FONT.get(ch, drawing.FONT[' '])):
            for col, bit in enumerate(bits):
                if bit == '1':
                    for px, py in drawing.rectangle_points(
                            x + index * 6 * size + col * size,
                            y - row * size, size * .83, size * .83):
                        vertices.append(menu.world(px, py, .002))
    if vertices:
        drawing.draw_batch(shader, 'TRIS', vertices, (.92, .96, 1, 1))


def draw(runtime, shader):
    """Draw at the non-dominant controller, without any Blender scene objects."""
    radial = getattr(runtime, 'radial', None)
    menu = runtime.menu
    if radial is None or not radial.active or not menu.ready:
        return
    buttons = visible_actions(menu.buttons, radial.page_offset)
    step = 2 * math.pi / 8
    inner, outer = .061, .217
    for index in range(8):
        picked = index == radial.selected and index < len(buttons)
        usable = index < len(buttons)
        color = ((.08, .49, .55, .97) if picked else
                 (.065, .14, .20, .94) if usable else (.035, .06, .08, .74))
        vertices = []
        for k in range(12):
            a0 = (index - .5 + k / 12) * step
            a1 = (index - .5 + (k + 1) / 12) * step
            def polar(a, r):
                return menu.world(math.sin(a) * r, math.cos(a) * r, .001)
            p0, p1 = polar(a0, inner), polar(a0, outer)
            p2, p3 = polar(a1, outer), polar(a1, inner)
            vertices.extend((p0, p1, p2, p0, p2, p3))
        drawing.draw_batch(shader, 'TRIS', vertices, color)
        if usable:
            label, action = buttons[index]
            caption = label or action.replace('_', ' ')
            caption = caption[:11]
            a = index * step
            x = math.sin(a) * .139 - .0037 * len(caption)
            y = math.cos(a) * .139 + .004
            _letters(menu, shader, caption, x, y, .00155)
    # Central target/mode indication: short enough to fit the inner hole.
    _letters(menu, shader, 'MESH XR', -.032, .009, .0015)
    _letters(menu, shader, 'RADIAL', -.028, -.013, .0016)
