"""v0.6 material management, textures, UV tools and headset routing checks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import bmesh
import blender_xr
from blender_xr import material_uv, materials, menus, mesh, runtime, uv_tools, version


def select_all_faces(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    for face in bm.faces:
        face.select_set(True)
    for edge in bm.edges:
        edge.select_set(True)
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)


blender_xr.register()
session = None
try:
    assert version.VERSION >= (0, 6, 0)
    assert blender_xr.bl_info['version'] == version.VERSION
    assert getattr(runtime.Runtime, '_v060_patched', False)
    assert ('MATERIALS', 'MATERIAL_MENU') in menus.PAGES['TOOLS']
    assert ('MATERIALS', 'MATERIAL_MENU') in menus.PAGES['EDIT']
    assert {'MATERIAL_HOME','MATERIAL_PROPS','MATERIAL_SLOTS','MATERIAL_TEXTURES',
            'UV','UV_TRANSFORM','UV_PREVIEW'} <= set(menus.PAGES)

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.object
    settings = bpy.context.scene.blender_xr

    first = material_uv.new_material(obj, settings.object_color, 'Primary')
    assert obj.active_material == first
    settings.material_metallic = 0.7
    settings.material_roughness = 0.2
    settings.material_alpha = 0.6
    settings.material_emission = 1.5
    material_uv.apply_settings(obj, settings)
    values = material_uv.parameters(first)
    assert abs(values['metallic'] - 0.7) < 1e-6
    assert abs(values['roughness'] - 0.2) < 1e-6
    assert abs(values['alpha'] - 0.6) < 1e-6
    assert abs(values['emission'] - 1.5) < 1e-6

    duplicate = material_uv.duplicate_material(obj)
    assert duplicate != first and len(obj.material_slots) == 2
    assert material_uv.rename_material(obj, 'Detail') == 'Detail'
    material_uv.add_slot(obj)
    assert len(obj.material_slots) == 3
    material_uv.cycle_slot(obj, -1)
    material_uv.remove_slot(obj)
    assert len(obj.material_slots) == 2

    checker = material_uv.diagnostic_image('CHECKER', size=64)
    direction = material_uv.diagnostic_image('DIRECTION', size=64)
    grid = material_uv.diagnostic_image('GRID', size=64)
    assert all(image.size[0] == 64 and image.size[1] == 64 for image in (checker, direction, grid))
    material_uv.apply_texture(obj, checker, settings.object_color)
    assert material_uv.current_texture(obj.active_material) == checker
    settings.texture_name = checker.name
    material_uv.clear_texture(obj, settings.object_color)
    assert material_uv.current_texture(obj.active_material) is None

    # A second distinct slot lets assignment/select-by-slot be validated.
    material_uv.new_material(obj, (0.8, 0.1, 0.2, 1.0), 'Face Detail')
    target_slot = obj.active_material_index
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.context.tool_settings.mesh_select_mode = (False, False, True)
    select_all_faces(obj)
    assigned = material_uv.assign_active_slot(obj)
    assert assigned == 6
    bm = bmesh.from_edit_mesh(obj.data)
    assert all(face.material_index == target_slot for face in bm.faces)
    assert material_uv.select_faces_with_active_material(obj) == 6

    assert uv_tools.ensure_layer(obj)
    assert uv_tools.planar_project(obj) == 6
    assert uv_tools.preview_segments(obj)
    before = [tuple(loop[uv].uv) for face in bm.faces for loop in face.loops
              for uv in [bm.loops.layers.uv.active]]
    uv_tools.transform(obj, move=(0.05, -0.03), rotate=15, scale=0.95)
    bm = bmesh.from_edit_mesh(obj.data); uv = bm.loops.layers.uv.active
    after = [tuple(loop[uv].uv) for face in bm.faces for loop in face.loops]
    assert before != after
    assert uv_tools.mark_seams(obj, False) > 0
    bm = bmesh.from_edit_mesh(obj.data)
    assert any(edge.seam for edge in bm.edges)
    assert uv_tools.mark_seams(obj, True) > 0
    bm = bmesh.from_edit_mesh(obj.data)
    assert not any(edge.seam for edge in bm.edges)
    assert uv_tools.smart_project(obj) == 6
    assert uv_tools.cube_project(obj) == 6
    assert uv_tools.unwrap(obj) == 6
    assert uv_tools.pack_islands(obj) >= 1
    assert uv_tools.reset(obj) == 6

    # Exercise headset page routing without starting an OpenXR session.
    session = runtime.Runtime.__new__(runtime.Runtime)
    session.transaction = None; session.grab = None; session.axis_move = None; session.air_grab = None
    session.settings = settings; session.menu = blender_xr.runtime.drawing.Menu(); session.status = ''
    session.material_return_page = 'EDIT'
    session.command(bpy.context, 'MATERIAL_MENU')
    assert session.menu.page == 'MATERIAL_HOME'
    session.command(bpy.context, 'MAT_PROPS')
    assert session.menu.page == 'MATERIAL_PROPS'
    session.command(bpy.context, 'BACK')
    assert session.menu.page == 'MATERIAL_HOME'
    session.command(bpy.context, 'UV_MENU')
    assert session.menu.page == 'UV'
    session.command(bpy.context, 'UV_TRANSFORM_MENU')
    assert session.menu.page == 'UV_TRANSFORM'
    session.command(bpy.context, 'BACK')
    assert session.menu.page == 'UV'
    session.command(bpy.context, 'UV_PREVIEW')
    assert session.menu.page == 'UV_PREVIEW'
    session.command(bpy.context, 'BACK')
    assert session.menu.page == 'UV'
    session.command(bpy.context, 'BACK')
    assert session.menu.page == 'MATERIAL_HOME'
    session.command(bpy.context, 'BACK')
    assert session.menu.page == 'EDIT'

    print('PASS v0.6 materials, slots, textures, UV mapping, UV transforms and VR routing')
finally:
    session = None
    if bpy.context.object and bpy.context.object.mode == 'EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')
    blender_xr.unregister()
