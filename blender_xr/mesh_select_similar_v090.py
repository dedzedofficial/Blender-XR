# SPDX-License-Identifier: GPL-3.0-or-later
"""Native BMesh Select Similar for headset precision modelling.

Matches visible edit geometry against one or more selected reference elements:
vertex valence, edge length/seam/sharpness and face area/normal/sides.
The mesh is not modified. All selection changes use the existing guarded
XR_MESH_SELECTION_086 history via selection_quicksets_v090.restore_indices.
"""
import math

from . import (input_ownership_v080, menus, mesh_selection_tools_v086,
               selection, selection_quicksets_v090, v065)

_PAGE = 'XR_SELECT_SIMILAR_090'
_DIAGNOSTICS = 'XR_SELECT_DIAGNOSTICS_090'
_PARENT = mesh_selection_tools_v086._PAGE
_MATCH = {
    'XR_SIM_VERT_VALENCE': ('VERT', 'VALENCE'),
    'XR_SIM_EDGE_LENGTH': ('EDGE', 'LENGTH'),
    'XR_SIM_EDGE_SEAM': ('EDGE', 'SEAM'),
    'XR_SIM_EDGE_SHARP': ('EDGE', 'SHARP'),
    'XR_SIM_FACE_AREA': ('FACE', 'AREA'),
    'XR_SIM_FACE_NORMAL': ('FACE', 'NORMAL'),
    'XR_SIM_FACE_SIDES': ('FACE', 'SIDES'),
}
_TOLERANCES = {
    'XR_SIM_FINE': 0.01,
    'XR_SIM_MEDIUM': 0.05,
    'XR_SIM_BROAD': 0.15,
}
_DIAGNOSTIC_ACTIONS = frozenset({
    'XR_SEL_NONMANIFOLD', 'XR_SEL_LOOSE', 'XR_SEL_SHARP',
})
_MAX_VISIBLE = 150000
_MAX_REFERENCES = 64


def _feature(item, mode, kind):
    if kind == 'VALENCE':
        return sum(1 for edge in item.link_edges if edge.is_valid)
    if kind == 'LENGTH':
        value = float(item.calc_length())
    elif kind == 'SEAM':
        return bool(item.seam)
    elif kind == 'SHARP':
        return not bool(item.smooth)
    elif kind == 'AREA':
        value = float(item.calc_area())
    elif kind == 'NORMAL':
        normal = tuple(float(v) for v in item.normal)
        magnitude = math.sqrt(sum(v * v for v in normal))
        if not math.isfinite(magnitude) or magnitude <= 1e-10:
            return None
        return tuple(v / magnitude for v in normal)
    elif kind == 'SIDES':
        return len(item.verts)
    else:
        raise ValueError('Unsupported Select Similar feature')
    if not math.isfinite(value) or value < 0:
        return None
    return value


def _matches(candidate, references, kind, tolerance):
    if candidate is None:
        return False
    if kind == 'NORMAL':
        dot_limit = math.cos(math.radians(tolerance * 100.0))
        return any(sum(a * b for a, b in zip(candidate, ref)) >= dot_limit
                   for ref in references)
    if kind in {'LENGTH', 'AREA'}:
        # A relative tolerance works for both tiny and metre-scale assets;
        # an absolute floor only absorbs floating point precision noise.
        return any(abs(candidate - ref) <= max(1e-8, max(candidate, ref) * tolerance)
                   for ref in references)
    return candidate in references


def _targets(context, kind, tolerance):
    obj = mesh_selection_tools_v086._editable(context)
    mode = selection.mode(context)
    bm, items = mesh_selection_tools_v086._current(obj, mode)
    visible = tuple(item for item in items if item.is_valid and not item.hide)
    if len(visible) > _MAX_VISIBLE:
        raise ValueError('Select Similar handles up to 150,000 visible elements')
    seeds = tuple(item for item in visible if item.select)
    if not seeds:
        raise ValueError('Select at least one visible reference element first')
    if len(seeds) > _MAX_REFERENCES:
        raise ValueError('Select at most 64 similar-reference elements at once')
    references = tuple(_feature(item, mode, kind) for item in seeds)
    if any(value is None for value in references):
        raise ValueError('Reference element has degenerate or invalid geometry')
    # Preserve selection even when seed geometry is degenerate or large by
    # planning in read-only memory before passing indexes to the shared
    # guarded selection transaction.
    return mode, tuple(item.index for item in visible
                       if _matches(_feature(item, mode, kind),
                                   references, kind, tolerance))


def _apply(session, context, action):
    if action not in _MATCH:
        raise ValueError('Unknown native Select Similar command')
    if input_ownership_v080.is_editing(session):
        raise ValueError('Release XR controllers before selecting similar geometry')
    if getattr(session, 'history', None) is None:
        raise ValueError('XR Undo history is required for Select Similar')
    mode = selection.mode(context)
    required_mode, kind = _MATCH[action]
    if mode != required_mode:
        raise ValueError('Choose {} Select mode for {}'.format(required_mode, kind))
    tolerance = float(getattr(session, '_xr_similar_tolerance', 0.05))
    if not math.isfinite(tolerance) or tolerance not in _TOLERANCES.values():
        raise ValueError('Select a supported similarity threshold')
    current_mode, target_indices = _targets(context, kind, tolerance)
    additive = bool(getattr(session, '_xr_similar_add', False))
    count, changed = selection_quicksets_v090.restore_indices(
        session, context, target_indices, additive)
    session.status = 'SIMILAR {} / {} {} / {} / {}'.format(
        kind, count, current_mode,
        'ADD' if additive else 'REPLACE',
        'XR UNDO READY' if changed else 'UNCHANGED')
    return changed


def install_pages():
    existing = tuple(menus.PAGES[_PARENT])
    if not existing or existing[-1][1] != 'BACK':
        raise ValueError('Existing Mesh Selection menu is unavailable')
    if any(action in {'XR_SEL_SIMILAR_MENU', 'XR_SEL_DIAGNOSTICS_MENU'}
           for _label, action in existing):
        raise ValueError('Select Similar menus have already been installed')
    # Existing Selection page was full at twelve buttons. Group its three
    # diagnostics into their own page; leave their original actions intact.
    cleaned = tuple((label, action) for label, action in existing[:-1]
                    if action not in _DIAGNOSTIC_ACTIONS)
    if len(cleaned) != len(existing) - 4:
        raise ValueError('Native selection diagnostic actions were rearranged')
    replacement = cleaned + (
        ('SIMILAR', 'XR_SEL_SIMILAR_MENU'),
        ('DIAGNOSTICS', 'XR_SEL_DIAGNOSTICS_MENU'),
        existing[-1],
    )
    if len(replacement) > 12:
        raise ValueError('Select Similar would overflow the wrist menu')
    menus.PAGES[_PARENT] = replacement
    menus.PAGES[_DIAGNOSTICS] = (
        ('NON-MANIFOLD', 'XR_SEL_NONMANIFOLD'),
        ('LOOSE', 'XR_SEL_LOOSE'),
        ('SHARP', 'XR_SEL_SHARP'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_DIAGNOSTICS] = 'MESH DIAGNOSTICS'
    menus.PAGES[_PAGE] = (
        ('VERT VALENCE', 'XR_SIM_VERT_VALENCE'),
        ('EDGE LENGTH', 'XR_SIM_EDGE_LENGTH'),
        ('EDGE SEAM', 'XR_SIM_EDGE_SEAM'),
        ('EDGE SHARP', 'XR_SIM_EDGE_SHARP'),
        ('FACE AREA', 'XR_SIM_FACE_AREA'),
        ('FACE NORMAL', 'XR_SIM_FACE_NORMAL'),
        ('FACE SIDES', 'XR_SIM_FACE_SIDES'),
        ('FINE', 'XR_SIM_FINE'),
        ('MEDIUM', 'XR_SIM_MEDIUM'),
        ('BROAD', 'XR_SIM_BROAD'),
        ('ADD/REPLACE', 'XR_SIM_MODE'),
        ('BACK', 'BACK'),
    )
    menus.TITLES[_PAGE] = 'SELECT SIMILAR'
    v065.TOOLTIPS.update({
        'XR_SEL_SIMILAR_MENU': ('Select Similar Geometry',
            'Match native mesh geometry by vertex, edge or face properties'),
        'XR_SEL_DIAGNOSTICS_MENU': ('Mesh Selection Diagnostics',
            'Original non-manifold, loose and sharp selection tools'),
        'XR_SIM_VERT_VALENCE': ('Similar Vertex Valence',
            'Find visible vertices with the same number of connected edges'),
        'XR_SIM_EDGE_LENGTH': ('Similar Edge Length',
            'Find visible edges whose native lengths match the selected edges'),
        'XR_SIM_EDGE_SEAM': ('Similar UV Seam State',
            'Find edges with the selected Blender seam flag'),
        'XR_SIM_EDGE_SHARP': ('Similar Edge Sharp State',
            'Find edges with the selected native smooth/sharp setting'),
        'XR_SIM_FACE_AREA': ('Similar Face Area',
            'Find face areas within the chosen relative tolerance'),
        'XR_SIM_FACE_NORMAL': ('Similar Face Normals',
            'Match local face normals with a 1, 5 or 15 degree threshold'),
        'XR_SIM_FACE_SIDES': ('Similar Face Side Count',
            'Find triangles, quads or ngons with the same side count'),
        'XR_SIM_FINE': ('Fine Similarity',
            'One percent for size, one degree for face normals'),
        'XR_SIM_MEDIUM': ('Medium Similarity',
            'Five percent for size, five degrees for face normals'),
        'XR_SIM_BROAD': ('Broad Similarity',
            'Fifteen percent for size, fifteen degrees for face normals'),
        'XR_SIM_MODE': ('Add or Replace Similar Selection',
            'Change recall mode without modifying native Blender geometry'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_select_similar_090_patched', False):
        return
    install_pages()
    previous_command = Runtime.command

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous_command(self, context, action)
        page = menu.page
        if page == _PARENT and action in {
                'XR_SEL_SIMILAR_MENU', 'XR_SEL_DIAGNOSTICS_MENU'}:
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release controller edit before mesh selection')
            mesh_selection_tools_v086._editable(context)
            menu.page = (_PAGE if action == 'XR_SEL_SIMILAR_MENU'
                         else _DIAGNOSTICS)
            self.status = 'MESH / SELECT SIMILAR' if menu.page == _PAGE else (
                'MESH / NON-MANIFOLD, LOOSE, SHARP')
            return
        if page == _DIAGNOSTICS:
            if action == 'BACK':
                menu.page = _PARENT
                return
            if action in _DIAGNOSTIC_ACTIONS:
                return mesh_selection_tools_v086._apply(self, context, action)
            raise ValueError('Use a diagnostic selection or Back')
        if page == _PAGE:
            if action == 'BACK':
                menu.page = _PARENT
                return
            if input_ownership_v080.is_editing(self):
                raise ValueError('Release XR gesture before Select Similar')
            if action in _TOLERANCES:
                self._xr_similar_tolerance = _TOLERANCES[action]
                self.status = 'SIMILAR TOLERANCE / {}% / {} DEGREES'.format(
                    int(_TOLERANCES[action] * 100),
                    int(_TOLERANCES[action] * 100))
                return
            if action == 'XR_SIM_MODE':
                self._xr_similar_add = not bool(getattr(self, '_xr_similar_add', False))
                self.status = ('SIMILAR SELECTION / ' +
                               ('ADD' if self._xr_similar_add else 'REPLACE'))
                return
            if action in _MATCH:
                return _apply(self, context, action)
            raise ValueError('Choose Similar geometry or a threshold')
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime._xr_select_similar_090_patched = True
