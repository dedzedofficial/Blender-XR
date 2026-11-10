"""v0.7.1 advanced modeling and history regression tests."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import bmesh
from mathutils import Vector
import blender_xr
from blender_xr import drawing, material_uv, menus, mesh, runtime, uv_tools, v071, version

blender_xr.register()
history = mesh.History()
try:
    assert version.VERSION >= (0, 7, 1)
    # The desktop mirror toggle uses Blender's native XR viewport property when available.
    assert 'mirror_xr_session' in __import__('inspect').getsource(blender_xr.ui_v076._session)
    assert runtime.Runtime._v071_patched
    assert {'OBJECT_ADVANCED', 'GEOMETRY_ADVANCED', 'MODIFIER_MENU'} <= set(menus.PAGES)

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.object
    # One coherent creator menu exposes existing tools, without overflowing
    # the actual twelve-button headset/radial grid. Category Back returns Hub.
    from types import SimpleNamespace
    assert runtime.Runtime._v080_creator_hub_patched
    assert len(menus.PAGES['TOOLS']) == 12
    assert len(menus.PAGES['EDIT']) == 12
    assert len(menus.PAGES['EDIT_MORE']) == 12
    assert len(menus.PAGES['CREATOR']) == 12
    assert len(menus.PAGES['OBJECT_ADVANCED']) <= 12
    assert 'ROTATE_EDIT' in [action for _, action in menus.PAGES['EDIT_MORE']]
    assert 'MATERIAL_MENU' in [action for _, action in menus.PAGES['EDIT_MORE']]
    assert 'STEP_MENU' in [action for _, action in menus.PAGES['EDIT_MORE']]
    assert {'LESS', 'MORE'} <= {action for _, action in menus.PAGES['STEP_MENU']}
    assert 'RIG_MENU' not in [action for _, action in menus.PAGES['TOOLS']]
    assert 'RIG_MENU' in [action for _, action in menus.PAGES['CREATOR']]
    assert 'DELETE_OBJECT' in [action for _, action in menus.PAGES['CREATOR']]
    assert 'MODE_WEIGHT_PAINT' in [action for _, action in menus.PAGES['RIGGING']]
    assert 'UNDO' in [action for _, action in menus.PAGES['TOOLS']]
    assert [action for _, action in menus.PAGES['TOOLS']].count('CREATOR_MENU') == 1
    assert any(action == 'LAYOUT_MENU' for _, action in menus.PAGES['OBJECT_ADVANCED'])
    expected = {'NAV_MENU', 'FOCUS_MENU', 'LAYOUT_MENU', 'RIG_MENU',
                'SCENE_MENU', 'MATERIAL_MENU', 'UV_MENU',
                'OBJECT_ADVANCED', 'MODIFIER_MENU', 'ADD_MENU'}
    assert expected <= {action for _, action in menus.PAGES['CREATOR']}
    for page in ('TOOLS', 'CREATOR', 'OBJECT_ADVANCED'):
        for label, action in menus.PAGES[page]:
            icon = drawing._ICON_BY_ACTION.get(action)
            assert icon, (page, label, action)
            assert (Path(drawing.__file__).parent / 'icons' / (icon + '.png')).is_file()

    creator = runtime.Runtime.__new__(runtime.Runtime)
    creator.menu = drawing.Menu()
    creator.status = ''
    creator.tool = 'SELECT'
    creator.settings = bpy.context.scene.blender_xr
    creator.history = history
    creator.transaction = creator.grab = creator.axis_move = None
    creator.air_grab = creator.two_hand_scale = None
    for action, expected_page in (
        ('NAV_MENU', 'TRAVEL'), ('FOCUS_MENU', 'FOCUS_MENU'),
        ('RIG_MENU', 'RIGGING'), ('ADD_MENU', 'PRIMITIVES'),
        ('OBJECT_ADVANCED', 'OBJECT_ADVANCED'),
        ('LAYOUT_MENU', 'LAYOUT_MENU'), ('MODIFIER_MENU', 'MODIFIER_MENU'),
    ):
        creator.command(bpy.context, 'CREATOR_MENU')
        assert creator.menu.page == 'CREATOR'
        creator.command(bpy.context, action)
        assert creator.menu.page == expected_page, action
        creator.command(bpy.context, 'BACK')
        assert creator.menu.page == 'CREATOR', (action, creator.menu.page)
    creator.command(bpy.context, 'BACK')
    assert creator.menu.page == 'TOOLS'
    creator.command(bpy.context, 'CREATOR_MENU')
    creator._weight_stroke = object()
    try:
        creator.command(bpy.context, 'CREATOR_MENU')
    except ValueError:
        pass
    else:
        raise AssertionError('Creator Hub opened during an unfinished stroke')
    creator._weight_stroke = None
    creator.menu.page = 'TOOLS'

    obj.matrix_world.translation = Vector((0.27, 0.49, 0.13))
    history.push(v071.snap_to_grid(obj, 0.1))
    assert tuple(round(x, 3) for x in obj.matrix_world.translation) == (0.3, 0.5, 0.1)
    assert history.step(True)
    assert abs(obj.matrix_world.translation.x - 0.27) < 1e-6
    assert history.step(False)
    assert abs(obj.matrix_world.translation.x - 0.3) < 1e-6

    before = obj.matrix_world.copy()
    history.push(v071.rotate(obj, 'Z', 15))
    assert tuple(obj.matrix_world) != tuple(before)
    assert history.step(True)
    assert all((obj.matrix_world[i] - before[i]).length < 1e-5 for i in range(4))

    state0 = v071.modifier_state(obj)
    history.push(v071.modifier_action(obj, 'MOD_MIRROR_X'))
    assert any(m.type == 'MIRROR' for m in obj.modifiers)
    history.push(v071.modifier_action(obj, 'MOD_ARRAY'))
    history.push(v071.modifier_action(obj, 'MOD_COUNT_UP'))
    assert any(m.type == 'ARRAY' and m.count == 3 for m in obj.modifiers)
    assert history.step(True)
    assert any(m.type == 'ARRAY' and m.count == 2 for m in obj.modifiers)
    assert history.step(True)
    assert all(m.type != 'ARRAY' for m in obj.modifiers)
    assert history.step(True)
    assert v071.modifier_state(obj) == state0
    history.clear()

    history.push(v071.modifier_action(obj, 'MOD_SOLIDIFY'))
    clone = v071.duplicate_object(obj, 0.1)
    clone_name = clone[1]
    history.push(clone)
    assert bpy.data.objects.get(clone_name) is not None
    assert history.step(True)
    assert bpy.data.objects.get(clone_name) is None
    assert history.step(False)
    restored = bpy.data.objects.get(clone_name)
    assert restored is not None and any(m.type == 'SOLIDIFY' for m in restored.modifiers)
    history.clear()

    # Quick Layout aligns origins without touching geometry or modifier data.
    bpy.ops.mesh.primitive_cube_add(location=(3, 6, 0))
    layout_b = bpy.context.object
    bpy.ops.mesh.primitive_cube_add(location=(10, 8, 0))
    layout_c = bpy.context.object
    for selected in bpy.context.selected_objects:
        selected.select_set(False)
    for selected in (obj, layout_b, layout_c):
        selected.select_set(True)
    bpy.context.view_layer.objects.active = obj
    before_y = (layout_b.location.y, layout_c.location.y)
    history.push(v071.quick_layout(bpy.context, 'ALIGN', 'Y'))
    assert abs(layout_b.location.y - obj.location.y) < 1e-6
    assert abs(layout_c.location.y - obj.location.y) < 1e-6
    assert history.step(True)
    assert abs(layout_b.location.y - before_y[0]) < 1e-6
    assert abs(layout_c.location.y - before_y[1]) < 1e-6
    assert history.step(False)
    assert abs(layout_b.location.y - obj.location.y) < 1e-6
    history.clear()
    obj.location.x = 0.0
    layout_b.location.x = 3.0
    layout_c.location.x = 10.0
    history.push(v071.quick_layout(bpy.context, 'DISTRIBUTE', 'X'))
    assert abs(layout_b.location.x - 5.0) < 1e-6
    assert history.step(True)
    assert abs(layout_b.location.x - 3.0) < 1e-6
    assert history.step(False)
    assert abs(layout_b.location.x - 5.0) < 1e-6
    history.clear()
    layout_b.location.z = 2.0
    assert bpy.ops.blender_xr.quick_layout(operation='ALIGN', axis='Z') == {'FINISHED'}
    assert abs(layout_b.location.z - obj.location.z) < 1e-6
    assert {'LAYOUT_MENU'} <= set(menus.PAGES)
    assert any(action == 'LAYOUT_MENU' for _, action in menus.PAGES['OBJECT_ADVANCED'])
    for member in (layout_b, layout_c):
        bpy.data.objects.remove(member, do_unlink=True)
    for selected in bpy.context.selected_objects:
        selected.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Delete a unique material and ensure no invalid RNA reference is read.
    material_uv.new_material(obj, (0.5, 0.4, 0.3, 1.0), 'XR Delete Regression')
    assert material_uv.delete_material(obj) == 'XR Delete Regression'

    for selected in bpy.context.selected_objects:
        selected.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    mesh.set_selection_mode(bpy.context, 'VERT')
    bm = mesh.editable(obj)
    for v in bm.verts:
        v.select_set(True)
    mesh.update(obj)
    before = [v.co.copy() for v in mesh.editable(obj).verts]
    history.push(v071.rotate(obj, 'Y', 15))
    after = [v.co.copy() for v in mesh.editable(obj).verts]
    assert any((x-y).length > 1e-5 for x,y in zip(before, after))
    assert history.step(True)
    again = [v.co.copy() for v in mesh.editable(obj).verts]
    assert all((x-y).length < 1e-5 for x,y in zip(before, again))
    history.clear()

    bm = mesh.editable(obj)
    mesh.set_selection_mode(bpy.context, 'FACE')
    for face in bm.faces:
        face.select_set(True)
    mesh.update(obj)
    session = runtime.Runtime.__new__(runtime.Runtime)
    session.transaction = None; session.grab = None
    session.air_grab = None; session.axis_move = None
    session.history = history
    session.settings = bpy.context.scene.blender_xr
    session.menu = drawing.Menu()
    session.status = ''
    assert uv_tools.ensure_layer(obj)
    before = mesh.snapshot(obj)
    session.command(bpy.context, 'UV_U_UP')
    assert history.undo and history.undo[-1][0] == 'MESH'
    assert history.step(True)
    mesh.restore(obj, before)
    bpy.data.meshes.remove(before)
    history.clear()

    print('PASS v0.7.1 advanced modeling and history')
finally:
    history.clear()
    # A persistent reference to an edit BMesh can crash Blender 4.2 at exit
    # after mode switching. Drop the script's BMesh wrappers while still live.
    for _name in ('bm', 'v', 'face', 'edge'):
        globals().pop(_name, None)
    import gc
    gc.collect()
    if bpy.context.object and bpy.context.object.mode == 'EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')
    blender_xr.unregister()
