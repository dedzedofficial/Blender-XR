# SPDX-License-Identifier: GPL-3.0-or-later
"""Compact native-Blender icon-led sidebar for the 0.7.6 test build.

Keep existing operators and XR controls: this module only organises their UI.
Blender owns the icon assets, localization and the hover tooltips.
"""
import textwrap

import bpy

from . import materials, preferences, runtime, statistics, platform_support, quality_v080, recovery_v080


UI_SECTION_ITEMS = [
    ('SESSION', 'Session', 'Headset connection and controller setup', 'PLAY', 0),
    ('MODEL', 'Model', 'Geometry, precision, audit and rigging tools', 'MESH_CUBE', 1),
    ('MATERIAL', 'Material', 'Materials, color and shading', 'MATERIAL', 2),
    ('UV', 'UV', 'Unwrap and edit UV coordinates', 'UV', 3),
    ('TRAVEL', 'Travel', 'Movement and turning', 'ORIENTATION_VIEW', 4),
    ('PROJECT', 'Project', 'Save files and inspect scene statistics', 'FILE_BLEND', 5),
    ('HELP', 'Help', 'Controller controls and useful Blender tools', 'QUESTION', 6),
]


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
    col.prop(settings, 'menu_style', text='Menu', icon='EVENT_M')
    col.prop(settings, 'hand_display', text='Hands', icon='HAND')
    if settings.hand_display == 'HANDS':
        col.prop(settings, 'hand_scale', text='Hand size', icon='ARROW_LEFTRIGHT')
        col.prop(settings, 'hand_offset_x', text='Hand offset X', icon='EMPTY_ARROWS')
        col.prop(settings, 'hand_offset_y', text='Hand offset Y', icon='EMPTY_ARROWS')
        col.prop(settings, 'hand_offset_z', text='Hand offset Z', icon='EMPTY_ARROWS')
        _operator(col, 'blender_xr.reset_hand_calibration', 'Reset hand alignment', 'LOOP_BACK')
    if settings.input_source == 'STEAMVR_HANDS':
        col.prop(settings, 'bridge_port', text='Bridge port', icon='CONSOLE')
        if active and getattr(runtime.CURRENT, 'bridge', None):
            _operator(layout, 'blender_xr.bridge_command', 'Copy bridge command', 'COPYDOWN')
    else:
        col.prop(settings, 'finger_touch', text='Finger shortcuts', toggle=True, icon='HAND')

    capabilities = platform_support.current_info(bpy)
    _header(layout, 'Platform', 'DESKTOP')
    layout.label(text='Desktop: ' + (capabilities['tag'] or 'unsupported'),
                 icon='CHECKMARK' if capabilities['desktop'] else 'ERROR')
    if not capabilities['vr']:
        layout.label(text='VR unavailable on this build', icon='INFO')
    elif capabilities['tag'].startswith('macos'):
        layout.label(text='VR experimental / needs OpenXR runtime', icon='INFO')
    else:
        layout.label(text='VR requires an active OpenXR runtime', icon='INFO')

    layout.prop(settings, 'show_diagnostics', text='Controller diagnostics', icon='INFO', toggle=True)
    if settings.show_diagnostics:
        session = runtime.CURRENT
        if session:
            layout.label(text='Dominant: ' + settings.dominant_hand, icon='HAND')
            layout.label(text='Input: ' + settings.input_source, icon='EVENT_S')
            layout.label(text='Menu: ' + ('active' if getattr(
                getattr(session, 'radial', None), 'active', False) else 'idle'), icon='EVENT_M')
            bridge = getattr(session, 'bridge', None)
            if bridge:
                layout.label(text='Fingers: ' + str(getattr(bridge, 'tracking_levels', []))[:40], icon='HAND')
        else:
            layout.label(text='VR not running', icon='INFO')
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
    col.prop(settings, 'step', text='Tool step', icon='EMPTY_ARROWS')
    col.prop(settings, 'fine_grab_enabled', text='Precision Grab', icon='SNAP_ON')
    if settings.fine_grab_enabled:
        col.prop(settings, 'fine_grab_factor', text='Fine sensitivity', icon='SNAP_ON')
    row = col.row(align=True)
    row.prop(settings, 'precision_mode', text='Snap', icon='SNAP_ON', toggle=True)
    row.prop(settings, 'haptic_feedback', text='Haptics', icon='FORCE_HARMONIC', toggle=True)
    col.prop(settings, 'bevel_segments', text='Bevel', icon='MOD_BEVEL')
    row = col.row(align=True)
    row.prop(settings, 'primitive_size', text='Shape', icon='MESH_CUBE')
    row.prop(settings, 'placement_distance', text='Distance', icon='ORIENTATION_VIEW')

    if context.mode == 'EDIT_MESH':
        _header(layout, 'Exact Numeric Mesh Move', 'TRANSFORM_MOVE')
        move_row = layout.row(align=True)
        move_row.enabled = runtime.CURRENT is None
        for axis in 'XYZ':
            move_row.operator('blender_xr.numeric_mesh_move',
                              text='Move ' + axis, icon='TRANSFORM_MOVE').axis = axis
        _header(layout, 'Select Similar', 'RESTRICT_SELECT_OFF')
        obj = context.view_layer.objects.active
        if obj and obj.type == 'MESH':
            mode = ('VERT' if context.tool_settings.mesh_select_mode[0]
                    else 'EDGE' if context.tool_settings.mesh_select_mode[1]
                    else 'FACE')
            similar = {
                'VERT': (('Valence', 'XR_SIM_VERT_VALENCE'),),
                'EDGE': (('Length', 'XR_SIM_EDGE_LENGTH'),
                         ('Seam', 'XR_SIM_EDGE_SEAM'),
                         ('Sharp', 'XR_SIM_EDGE_SHARP')),
                'FACE': (('Area', 'XR_SIM_FACE_AREA'),
                         ('Normal', 'XR_SIM_FACE_NORMAL'),
                         ('Sides', 'XR_SIM_FACE_SIDES')),
            }
            if mode == 'EDGE':
                flags_row = layout.row(align=True)
                flags_row.enabled = runtime.CURRENT is None
                for label, action in (('Seam', 'XR_EDGE_MARK_SEAM'),
                                      ('Unseam', 'XR_EDGE_CLEAR_SEAM'),
                                      ('Sharp', 'XR_EDGE_MARK_SHARP'),
                                      ('Smooth', 'XR_EDGE_CLEAR_SHARP')):
                    flags_row.operator('blender_xr.edge_flags', text=label,
                                       icon='EDGESEL').action = action
            similar_row = layout.row(align=True)
            similar_row.enabled = runtime.CURRENT is None
            for label, action in similar[mode]:
                similar_row.operator('blender_xr.select_similar', text=label,
                                     icon='RESTRICT_SELECT_OFF').operation = action

    if context.mode == 'EDIT_MESH':
        weld_row = layout.row(align=True)
        weld_row.enabled = runtime.CURRENT is None
        weld_row.operator('blender_xr.preview_weld',
                          text='Preview Duplicate-Vertex Weld',
                          icon='AUTOMERGE_ON')
        audit_row = layout.row(align=True)
        audit_row.enabled = runtime.CURRENT is None
        audit_row.operator('blender_xr.topology_audit',
                           text='Quad Topology Report', icon='MESH_DATA')
        pair_row = layout.row(align=True)
        pair_row.enabled = runtime.CURRENT is None
        pair_row.operator('blender_xr.quad_pair',
                          text='Preview Triangle Pair to Quad', icon='MESH_DATA')
        fill_row = layout.row(align=True)
        fill_row.enabled = runtime.CURRENT is None
        fill_row.operator('blender_xr.quad_hole',
                          text='Preview Four-Edge Quad Fill', icon='MESH_DATA')
        bridge_row = layout.row(align=True)
        bridge_row.enabled = runtime.CURRENT is None
        bridge_row.operator('blender_xr.bridge_quads',
                            text='Preview Quad Loop Bridge', icon='MESH_DATA')
        audit_row.operator('blender_xr.topology_select',
                           text='Select Non-Quads',
                           icon='RESTRICT_SELECT_OFF').action = 'XR_TOPO_SELECT_NONQUADS'
        mirror_row = layout.row(align=True)
        mirror_row.enabled = runtime.CURRENT is None
        mirror_row.operator('blender_xr.mesh_symmetry_audit',
                            text='Symmetry Audit (Local X)', icon='MOD_MIRROR')
        uv_row = layout.row(align=True)
        uv_row.enabled = runtime.CURRENT is None
        uv_row.operator('blender_xr.uv_island_inspect',
                        text='UV Island Report', icon='UV')
        uv_row.operator('blender_xr.uv_island_select',
                        text='Select Active Island', icon='UV').action = (
                            'XR_UV_ISLAND_SELECT_ACTIVE')

    layout.separator()
    _header(layout, 'Quick Layout (Object Mode)', 'EMPTY_ARROWS')
    row = layout.row(align=True)
    row.enabled = context.mode == 'OBJECT' and len(context.selected_objects) >= 2
    for axis in 'XYZ':
        _operator(row, 'blender_xr.quick_layout', 'Align ' + axis, 'EMPTY_ARROWS',
                  operation='ALIGN', axis=axis)
    row = layout.row(align=True)
    row.enabled = context.mode == 'OBJECT' and len(context.selected_objects) >= 3
    for axis in 'XYZ':
        _operator(row, 'blender_xr.quick_layout', 'Space ' + axis, 'EMPTY_ARROWS',
                  operation='DISTRIBUTE', axis=axis)

    layout.separator()
    _header(layout, 'Scene Timeline', 'TIME')
    layout.label(text='Frame {} / {}..{}'.format(context.scene.frame_current,
                  context.scene.frame_start, context.scene.frame_end), icon='TIME')
    timeline_row = layout.row(align=True)
    timeline_row.enabled = runtime.CURRENT is None
    timeline_row.operator('blender_xr.timeline_step', text='-1',
                          icon='BACK').action = 'XR_TIME_PREV'
    timeline_row.operator('blender_xr.timeline_step', text='+1',
                          icon='FORWARD').action = 'XR_TIME_NEXT'
    range_row = layout.row(align=True)
    range_row.enabled = runtime.CURRENT is None
    range_row.operator('blender_xr.timeline_range', text='Start Here',
                       icon='BACK').action = 'XR_TIME_SET_START'
    range_row.operator('blender_xr.timeline_range', text='End Here',
                       icon='FORWARD').action = 'XR_TIME_SET_END'
    play_row = layout.row(align=True)
    play_row.enabled = runtime.CURRENT is None
    play_row.operator('blender_xr.timeline_playback', text='Play / Pause',
                      icon='PLAY').action = 'XR_TIME_PLAY_PAUSE'
    play_row.operator('blender_xr.timeline_playback', text='Reverse',
                      icon='PLAY_REVERSE').action = 'XR_TIME_REVERSE'
    marker_row = layout.row(align=True)
    marker_row.enabled = runtime.CURRENT is None
    marker_row.operator('blender_xr.timeline_marker', text='Add Marker',
                        icon='ADD').action = 'XR_MARKER_ADD'
    marker_row.operator('blender_xr.timeline_marker', text='Remove XR',
                        icon='REMOVE').action = 'XR_MARKER_REMOVE'
    animated_obj = context.view_layer.objects.active
    if animated_obj and (animated_obj.mode == 'OBJECT' or
                         (animated_obj.type == 'ARMATURE' and animated_obj.mode == 'POSE')):
        _header(layout, 'Transform Animation', 'ACTION')
        anim_row = layout.row(align=True)
        anim_row.enabled = runtime.CURRENT is None
        for axis in 'XYZ':
            anim_row.operator('blender_xr.transform_keyframe',
                              text='Loc ' + axis, icon='KEY_HLT').channel = (
                                  'XR_ANIM_KEY_LOC_' + axis)
        rot_row = layout.row(align=True)
        rot_row.enabled = runtime.CURRENT is None
        for axis in 'XYZ':
            rot_row.operator('blender_xr.transform_keyframe',
                             text='Rot ' + axis, icon='KEY_HLT').channel = (
                                 'XR_ANIM_KEY_ROT_' + axis)
        scale_row = layout.row(align=True)
        scale_row.enabled = runtime.CURRENT is None
        for axis in 'XYZ':
            scale_row.operator('blender_xr.transform_keyframe',
                               text='Scale ' + axis, icon='KEY_HLT').channel = (
                                   'XR_ANIM_KEY_SCALE_' + axis)

    layout.separator()
    _header(layout, 'Shape Keys', 'SHAPEKEY_DATA')
    shape_obj = context.view_layer.objects.active
    shape_data = (shape_obj.data.shape_keys if shape_obj and
                  shape_obj.type == 'MESH' else None)
    if shape_obj and shape_obj.type == 'MESH':
        structure_row = layout.row(align=True)
        structure_row.enabled = (context.mode == 'OBJECT' and runtime.CURRENT is None)
        if shape_data is None:
            structure_row.operator('blender_xr.shape_key_create', text='New Basis',
                                   icon='ADD').action = 'XR_SHAPE_CREATE_BASIS'
        else:
            structure_row.operator('blender_xr.shape_key_create', text='Add Key',
                                   icon='ADD').action = 'XR_SHAPE_CREATE_KEY'
            if len(shape_data.key_blocks) > 1:
                structure_row.operator('blender_xr.shape_key_create', text='Duplicate',
                                       icon='DUPLICATE').action = 'XR_SHAPE_DUPLICATE'
    if shape_data and len(shape_data.key_blocks) > 1:
        layout.prop(shape_obj, 'active_shape_key_index', text='Active key')
        shape_row = layout.row(align=True)
        shape_row.enabled = context.mode == 'OBJECT' and runtime.CURRENT is None
        shape_row.operator('blender_xr.shape_key_value', text='Value -',
                           icon='REMOVE').action = 'XR_SHAPE_VALUE_DOWN'
        shape_row.operator('blender_xr.shape_key_value', text='Value +',
                           icon='ADD').action = 'XR_SHAPE_VALUE_UP'
        shape_row.operator('blender_xr.shape_key_value', text='Mute',
                           icon='HIDE_ON').action = 'XR_SHAPE_MUTE'
        deform_row = layout.row(align=True)
        deform_row.enabled = shape_row.enabled
        deform_row.operator('blender_xr.shape_deform', text='Reset',
                            icon='LOOP_BACK').action = 'XR_SHAPE_RESET'
        deform_row.operator('blender_xr.shape_deform', text='-X to +X',
                            icon='MOD_MIRROR').action = 'XR_SHAPE_MIRROR_NEG_POS'
        deform_row.operator('blender_xr.shape_deform', text='+X to -X',
                            icon='MOD_MIRROR').action = 'XR_SHAPE_MIRROR_POS_NEG'
        shape_keyframe_row = layout.row(align=True)
        shape_keyframe_row.enabled = shape_row.enabled
        shape_keyframe_row.operator('blender_xr.shape_keyframe', text='Key Current',
                                    icon='KEY_HLT').action = 'XR_SHAPE_KEY_CURRENT'
        shape_keyframe_row.operator('blender_xr.shape_keyframe', text='Key 0',
                                    icon='DECORATE_KEYFRAME').action = 'XR_SHAPE_KEY_0'
        shape_keyframe_row.operator('blender_xr.shape_keyframe', text='Key 1',
                                    icon='DECORATE_KEYFRAME').action = 'XR_SHAPE_KEY_1'
    else:
        layout.label(text='No editable non-Basis key on active mesh', icon='INFO')

    layout.separator()
    _header(layout, 'Asset audit', 'CHECKMARK')
    layout.prop(settings, 'triangle_budget', text='Triangle budget', icon='MESH_DATA')
    obj = context.view_layer.objects.active
    row = layout.row(align=True)
    row.enabled = bool(obj and obj.type == 'MESH' and obj.mode == 'OBJECT')
    _operator(row, 'blender_xr.asset_audit', 'Audit mesh', 'VIEWZOOM')
    _operator(layout, 'blender_xr.export_check', 'Pre-Export Check', 'CHECKMARK')
    _operator(layout, 'blender_xr.measure', 'Measure Selection', 'ORIENTATION_VIEW')
    layout.separator()
    _header(layout, 'Quick Inspector', 'OBJECT_DATA')
    quality_v080.draw_inspector(layout, context)

    layout.separator()
    _header(layout, 'Rigging', 'ARMATURE_DATA')
    col = layout.column(align=True)
    row = col.row(align=True)
    _operator(row, 'blender_xr.create_basic_rig', 'New', 'ARMATURE_DATA')
    col.label(text='Use Select to pick meshes, rigs or bones in VR', icon='RESTRICT_SELECT_OFF')
    if obj and obj.type == 'ARMATURE':
        pose_view_row = col.row(align=True)
        pose_view_row.enabled = runtime.CURRENT is None
        pose_view_row.prop(obj.data, 'pose_position', text='Display')
        if obj.mode == 'OBJECT':
            _operator(col, 'blender_xr.edit_bones', 'Edit Armature', 'EDITMODE_HLT')
        if obj.mode in {'OBJECT', 'EDIT'}:
            _operator(col, 'blender_xr.add_bone', 'Add Bone', 'BONE_DATA')
        if obj.mode == 'EDIT':
            _operator(col, 'blender_xr.finish_bones', 'Finish Bones', 'CHECKMARK')
    col.label(text='Parent to Armature (Blender Ctrl+P)', icon='CONSTRAINT_BONE')
    row = col.row(align=True)
    _operator(row, 'blender_xr.parent_paired', 'Auto Weights', 'CONSTRAINT_BONE', parent_type='ARMATURE_AUTO')
    _operator(row, 'blender_xr.parent_paired', 'Empty Groups', 'GROUP_VERTEX', parent_type='ARMATURE_NAME')
    row = col.row(align=True)
    _operator(row, 'blender_xr.parent_paired', 'Envelopes', 'MOD_ARMATURE', parent_type='ARMATURE_ENVELOPE')
    _operator(row, 'blender_xr.parent_paired', 'Deform Only', 'ARMATURE_DATA', parent_type='ARMATURE')
    row = col.row(align=True)
    _operator(row, 'blender_xr.parent_paired', 'Object Parent', 'OBJECT_DATA', parent_type='OBJECT')
    _operator(row, 'blender_xr.clear_mesh_parent', 'Clear Parent', 'X')
    _operator(col, 'blender_xr.weight_cleanup', 'Clean Weights', 'GROUP_VERTEX')
    row = col.row(align=True)
    _operator(row, 'blender_xr.weight_mode', 'Weight Paint Mode', 'WPAINT_HLT', enabled=True)
    if obj and obj.mode == 'WEIGHT_PAINT':
        _operator(row, 'blender_xr.weight_mode', 'Object Mode', 'OBJECT_DATA', enabled=False)
    if obj and obj.type == 'MESH' and obj.vertex_groups:
        col.label(text='Vertex group: ' + (obj.vertex_groups.active.name
                  if obj.vertex_groups.active else '(none)'), icon='GROUP_VERTEX')
        row = col.row(align=True)
        _operator(row, 'blender_xr.select_weight_group', 'Prev Group', 'TRIA_LEFT', direction=-1)
        _operator(row, 'blender_xr.select_weight_group', 'Next Group', 'TRIA_RIGHT', direction=1)
        col.prop(settings, 'weight_brush_strength', text='Brush strength', icon='BRUSH_DATA')
        col.prop(settings, 'weight_brush_radius', text='Brush size', icon='BRUSH_DATA')
        col.prop(settings, 'weight_erase', text='Erase', icon='X')
        col.prop(settings, 'weight_mirror_tolerance', text='X match tolerance', icon='MOD_MIRROR')
        mirror_row = col.row(align=True)
        mirror_row.enabled = (obj.mode == 'WEIGHT_PAINT' and runtime.CURRENT is None)
        mirror_row.operator('blender_xr.weight_mirror_x', text='-X to +X',
                            icon='MOD_MIRROR').direction = 'NEG_POS'
        mirror_row.operator('blender_xr.weight_mirror_x', text='+X to -X',
                            icon='MOD_MIRROR').direction = 'POS_NEG'
        weight_row = col.row(align=True)
        weight_row.enabled = mirror_row.enabled
        weight_row.operator('blender_xr.weight_balance', text='Normalize',
                            icon='GROUP_VERTEX').operation = 'NORMALIZE'
        weight_row.operator('blender_xr.weight_balance', text='Limit 4',
                            icon='GROUP_VERTEX').operation = 'LIMIT_FOUR'
        # Mirror only the active VR session's sample/target state. This is
        # diagnostic UI, not a second editor or a saved Blender datablock.
        session = runtime.CURRENT
        if session and obj.mode == 'WEIGHT_PAINT' and obj.vertex_groups.active:
            group = obj.vertex_groups.active
            try:
                scope = (obj.name, obj.as_pointer(), obj.data.name,
                         obj.data.as_pointer(), group.name, group.as_pointer())
                if getattr(session, '_xr_weight_target_scope', None) == scope:
                    value = getattr(session, '_xr_weight_target', None)
                    if value is not None:
                        label = ('Paint Exact' if getattr(session, 'tool', '') == 'WEIGHT_EXACT'
                                 else 'Brush target')
                        col.label(text='{}: {:.4f}'.format(label, value),
                                  icon='GROUP_VERTEX')
                sampled = getattr(session, '_xr_weight_probe', None)
                if sampled and sampled[0] == scope:
                    col.label(text='Sample: V{} / {:.4f}'.format(
                        sampled[1], 0.0 if sampled[3] is None else sampled[3]),
                        icon='EYEDROPPER')
            except (ReferenceError, RuntimeError):
                pass

    if obj and obj.type == 'ARMATURE' and obj.mode == 'OBJECT':
        _operator(col, 'blender_xr.pose_test', 'Pose', 'POSE_HLT')
    col.label(text='Point at rig bones to select in VR', icon='INFO')
    col.label(text='Edit Mode tools appear below', icon='ARMATURE_DATA')



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
    col.prop(settings, 'turn_mode', text='Turning', expand=True, icon='FILE_REFRESH')
    col.prop(settings, 'turn_angle' if settings.turn_mode == 'SNAP' else 'turn_speed', icon='FILE_REFRESH')
    col.prop(settings, 'grab_air', text='Grab empty space', toggle=True, icon='HAND')


def _project(layout, context, settings):
    _header(layout, 'Project', 'FILE_BLEND')
    layout.prop(settings, 'save_path', text='File', icon='FILE_BLEND')
    _operator(layout, 'blender_xr.save', 'Save .blend', 'FILE_TICK')
    layout.separator()
    _header(layout, 'Safe Recovery', 'FILE_BACKUP')
    recovery_v080.draw(layout, settings)
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
        ('Left stick: move', 'EMPTY_ARROWS'),
        ('Right stick: turn / height', 'FILE_REFRESH'),
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
    box = layout.box()
    if settings.ui_section == 'SESSION':
        _session(box, context, settings, active)
    elif settings.ui_section == 'HELP':
        _help(box)
    else:
        _DRAW.get(settings.ui_section, _session)(box, context, settings)
