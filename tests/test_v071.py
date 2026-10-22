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
    assert 'mirror_xr_session' in __import__('inspect').getsource(blender_xr.BXR_PT_panel.draw)
    assert runtime.Runtime._v071_patched
    assert {'OBJECT_ADVANCED', 'GEOMETRY_ADVANCED', 'MODIFIER_MENU'} <= set(menus.PAGES)

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.object
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
