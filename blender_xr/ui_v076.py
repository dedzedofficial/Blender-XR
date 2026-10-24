# SPDX-License-Identifier: GPL-3.0-or-later
"""Compact native-Blender icon-led sidebar for the 0.7.6 test build.

Keep existing operators and XR controls: this module only organises their UI.
Blender owns the icon assets, localization and the hover tooltips.
"""
import textwrap

import bpy

from . import materials, preferences, runtime, statistics


UI_SECTION_ITEMS = [
    ('SESSION', 'Session', 'Headset connection and controller setup', 'PLAY', 0),
    ('MODEL', 'Model', 'Geometry, precision, audit and rigging tools', 'MESH_CUBE', 1),
    ('MATERIAL', 'Material', 'Materials, color and shading', 'MATERIAL', 2),
    ('UV', 'UV', 'Unwrap and edit UV coordinates', 'UV', 3),
    ('TRAVEL', 'Travel', 'Movement and turning', 'ORIENTATION_VIEW', 4),
    ('PROJECT', 'Project', 'Save files and inspect scene statistics', 'FILE_BLEND', 5),
    ('HELP', 'Help', 'Controller controls and useful Blender tools', 'QUESTION', 6),
]
_SECTION_META = {key: (label, icon) for key, label, _description, icon, _number in UI_SECTION_ITEMS}


def _operator(row, identifier, label, icon, **properties):
    """Buttons always retain a descriptive tooltip via their operator."""
    button = row.operator(identifier, text=label, icon=icon)
    for name, value in properties.items():
        setattr(button, name, value)
    return button


def _header(layout, title, icon):
    row = layout.row(align=True)
    row.label(text=title, icon=icon)
    return row


def _session(layout, context, settings, active):
    _header(layout, 'Headset', 'XRAY')
    col = layout.column(align=True)
    col.enabled = not active
    col.prop(settings, 'dominant_hand', text='Hand', icon='HAND')
    col.prop(settings, 'controller_family', text='Controller', icon='PREFERENCES')
    col.prop(settings, 'input_source', text='Input', icon='EVENT_S')
    if settings.input_source == 'STEAMVR_HANDS':
        col.prop(settings, 'bridge_port', text='Bridge port', icon='CONSOLE')
        if active and getattr(runtime.CURRENT, 'bridge', None):
            _operator(layout, 'blender_xr.bridge_command', 'Copy bridge command', 'COPYDOWN')
    else:
        col.prop(settings, 'finger_touch', text='Finger shortcuts', toggle=True, icon='HAND')

    _header(layout, 'PC View Mode', 'WINDOW')
    view_space = context.space_data
    if hasattr(view_space, 'mirror_xr_session'):
        row = layout.row(align=True)
        row.enabled = active and bpy.types.XrSessionState.is_running(context)
        row.prop(view_space, 'mirror_xr_session',
                 text='Show VR View on PC', icon='XRAY', toggle=True)
        if not row.enabled:
            layout.label(text='Requires an active XR session', icon='INFO')
    else:
        layout.label(text='XR mirror unavailable in this Blender build', icon='ERROR')


def _model(layout, context, settings):
    _header(layout, 'Precision', 'MODIFIER')
    col = layout.column(align=True)
    col.prop(settings, 'step', text='Tool step', icon='TRANSFORM_MOVE')
    row = col.row(align=True)
    row.prop(settings, 'precision_mode', text='Snap', icon='SNAP_ON', toggle=True)
    row.prop(settings, 'haptic_feedback', text='Haptics', icon='FORCE_HARMONIC', toggle=True)
    col.prop(settings, 'bevel_segments', text='Bevel', icon='MOD_BEVEL')
    row = col.row(align=True)
    row.prop(settings, 'primitive_size', text='Shape', icon='MESH_CUBE')
    row.prop(settings, 'placement_distance', text='Distance', icon='ORIENTATION_VIEW')

    layout.separator()
    _header(layout, 'Asset audit', 'CHECKMARK')
    layout.prop(settings, 'triangle_budget', text='Triangle budget', icon='MESH_DATA')
    obj = context.view_layer.objects.active
    row = layout.row(align=True)
    row.enabled = bool(obj and obj.type == 'MESH' and obj.mode == 'OBJECT')
    _operator(row, 'blender_xr.asset_audit', 'Audit mesh', 'VIEWZOOM')

    layout.separator()
    _header(layout, 'Rigging', 'ARMATURE_DATA')
    col = layout.column(align=True)
    _operator(col, 'blender_xr.create_basic_rig', 'Create starter rig', 'ARMATURE_DATA')
    _operator(col, 'blender_xr.bind_auto_weights', 'Automatic weights', 'CONSTRAINT_BONE')
    _operator(col, 'blender_xr.weight_cleanup', 'Clean weights', 'GROUP_VERTEX')
    row = col.row(align=True)
    _operator(row, 'blender_xr.weight_paint', 'Paint', 'WPAINT_HLT')
    _operator(row, 'blender_xr.pose_test', 'Pose', 'POSE_HLT')


def _material(layout, context, settings):
    obj = context.view_layer.objects.active
    name, slot, total = materials.active_material_summary(obj)
    _header(layout, 'Materials', 'MATERIAL')
    if obj is not None and obj.type == 'MESH':
        layout.label(text=f'{name}  ({slot}/{total})', icon='MATERIAL')
    else:
        layout.label(text='Select a mesh', icon='INFO')
    layout.prop(settings, 'object_color', text='Color', icon='COLOR')
    is_mesh = bool(obj and obj.type == 'MESH')
    row = layout.row(align=True)
    row.enabled = is_mesh
    _operator(row, 'blender_xr.apply_color',
              'Assign faces' if is_mesh and obj.mode == 'EDIT' else 'Apply color', 'COLOR')
    row = layout.row(align=True)
    row.enabled = is_mesh
    _operator(row, 'blender_xr.shade', 'Smooth', 'SHADING_RENDERED', mode='SMOOTH')
    _operator(row, 'blender_xr.shade', 'Flat', 'SHADING_SOLID', mode='FLAT')
    row = layout.row(align=True)
    row.enabled = is_mesh
    _operator(row, 'blender_xr.material_action', 'New', 'ADD', action='NEW')
    _operator(row, 'blender_xr.material_action', 'Duplicate', 'DUPLICATE', action='DUPLICATE')
    layout.label(text='More tools in Materials + Textures below', icon='INFO')


def _uv(layout, context, settings):
    obj = context.view_layer.objects.active
    _header(layout, 'UV Mapping', 'UV')
    if not obj or obj.type != 'MESH' or obj.mode != 'EDIT':
        layout.label(text='Select a mesh in Edit Mode', icon='INFO')
        return
    col = layout.column(align=True)
    row = col.row(align=True)
    _operator(row, 'blender_xr.uv_action', 'Unwrap', 'UV', action='UNWRAP')
    _operator(row, 'blender_xr.uv_action', 'Smart', 'MODIFIER', action='SMART')
    row = col.row(align=True)
    _operator(row, 'blender_xr.uv_action', 'Cube', 'MESH_CUBE', action='CUBE')
    _operator(row, 'blender_xr.uv_action', 'Planar', 'MESH_PLANE', action='PLANAR')
    row = col.row(align=True)
    _operator(row, 'blender_xr.uv_action', 'Mark', 'ADD', action='MARK')
    _operator(row, 'blender_xr.uv_action', 'Clear', 'X', action='CLEAR')
    _operator(col, 'blender_xr.uv_action', 'Pack islands', 'UV', action='PACK')
    layout.prop(settings, 'uv_step', text='UV step', icon='UV')
    layout.label(text='More tools in UV Mapping below', icon='INFO')


def _travel(layout, context, settings):
    _header(layout, 'Movement', 'ORIENTATION_VIEW')
    col = layout.column(align=True)
    col.prop(settings, 'move_speed', text='Speed', icon='ORIENTATION_VIEW')
    row = col.row(align=True)
    row.prop(settings, 'fly_mode', text='Fly', toggle=True, icon='ORIENTATION_VIEW')
    row.prop(settings, 'fast_flight', text='Turbo', toggle=True, icon='FORWARD')
    col.prop(settings, 'turn_mode', text='Turning', expand=True, icon='TRANSFORM_ROTATE')
    col.prop(settings, 'turn_angle' if settings.turn_mode == 'SNAP' else 'turn_speed', icon='TRANSFORM_ROTATE')
    col.prop(settings, 'grab_air', text='Grab empty space', toggle=True, icon='HAND')


def _project(layout, context, settings):
    _header(layout, 'Project', 'FILE_BLEND')
    layout.prop(settings, 'save_path', text='File', icon='FILE_BLEND')
    _operator(layout, 'blender_xr.save', 'Save .blend', 'FILE_TICK')
    layout.separator()
    layout.prop(settings, 'show_statistics', text='Statistics', icon='INFO', toggle=True)
    if not settings.show_statistics:
        return
    info = statistics.scene_stats(context)
    for label, key, icon in (
        ('Objects', 'objects', 'OBJECT_DATA'),
        ('Selected', 'selected', 'RESTRICT_SELECT_OFF'),
        ('Meshes', 'meshes', 'MESH_DATA'),
        ('Materials', 'materials', 'MATERIAL'),
        ('Vertices', 'vertices', 'VERTEXSEL'),
        ('Edges', 'edges', 'EDGESEL'),
        ('Faces', 'faces', 'FACESEL'),
        ('Triangles', 'triangles', 'MOD_TRIANGULATE'),
    ):
        row = layout.row(align=True)
        row.label(text=label, icon=icon)
        row.label(text=str(info[key]))
    obj = info.get('active')
    if obj:
        layout.label(text=obj['name'], icon='OBJECT_DATA')


def _help(layout):
    _header(layout, 'Controller guide', 'QUESTION')
    for label, icon in (
        ('Trigger: select / use tool', 'RESTRICT_SELECT_OFF'),
        ('Grip + trigger: multi-select', 'ADD'),
        ('Grip: grab object / move viewer', 'ORIENTATION_VIEW'),
        ('Left stick: move', 'TRANSFORM_MOVE'),
        ('Right stick: turn / height', 'TRANSFORM_ROTATE'),
        ('Other trigger: menu / cancel', 'CANCEL'),
    ):
        layout.label(text=label, icon=icon)
    _operator(layout, 'wm.search_menu', 'Search Blender tools', 'VIEWZOOM')


_DRAW = {
    'SESSION': _session,
    'MODEL': _model,
    'MATERIAL': _material,
    'UV': _uv,
    'TRAVEL': _travel,
    'PROJECT': _project,
    'HELP': _help,
}


def draw_panel(panel, context):
    """Draw one compact workspace at a time rather than a stacked mega-panel."""
    layout = panel.layout
    settings = context.scene.blender_xr
    preferences.ensure(settings, context)
    active = runtime.CURRENT is not None

    row = layout.row(align=True)
    row.scale_y = 1.3
    _operator(row, 'blender_xr.stop' if active else 'blender_xr.session',
              'Stop VR' if active else 'Start VR', 'PAUSE' if active else 'PLAY')
    for line in textwrap.wrap(settings.status or 'Ready', width=38)[:2]:
        layout.label(text=line, icon='INFO')

    # The enum uses Blender's own icons; icon_only keeps the sidebar compact.
    # Full labels and translated tooltips remain on hover.
    row = layout.row(align=True)
    row.prop(settings, 'ui_section', text='', expand=True, icon_only=True)
    label, icon = _SECTION_META.get(settings.ui_section, _SECTION_META['SESSION'])
    box = layout.box()
    if settings.ui_section == 'SESSION':
        _session(box, context, settings, active)
    elif settings.ui_section == 'HELP':
        _help(box)
    else:
        _DRAW.get(settings.ui_section, _session)(box, context, settings)
