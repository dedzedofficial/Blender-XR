"""v0.8.5 native object-parenting and Empty assembly integration."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy

import blender_xr
from blender_xr import assembly_v085 as assembly, drawing, menus, mesh, runtime


def selected(context, *objects, active=None):
    for obj in tuple(context.selected_objects):
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    context.view_layer.objects.active = active or objects[0]


def near(a, b):
    return (a - b).length < 1e-5


def refused(action, msg):
    try:
        action()
    except ValueError as exc:
        assert msg.lower() in str(exc).lower(), str(exc)
    else:
        raise AssertionError('Expected refusal: ' + msg)


def run():
    blender_xr.register()
    h = mesh.History()
    session = None
    try:
        ctx = bpy.context
        assert runtime.Runtime._xr_assembly_085_patched
        assert len(menus.PAGES['XR_ASSEMBLY_085']) <= 12
        assert 'XR_ASSEMBLY_MENU' in {a for _, a in menus.PAGES['SCENE_HIERARCHY_ITEM']}
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)

        bpy.ops.mesh.primitive_cube_add(location=(2., 0., 1.))
        parent = ctx.object
        bpy.ops.mesh.primitive_cube_add(location=(4., 1., 2.))
        child1 = ctx.object
        bpy.ops.mesh.primitive_ico_sphere_add(location=(6., 2., 1.))
        child2 = ctx.object
        for obj in (parent, child1, child2):
            obj.name = 'XR_' + obj.name
        meshes = tuple((obj.data, len(obj.data.vertices)) for obj in (parent, child1, child2))
        original1, original2 = child1.matrix_world.copy(), child2.matrix_world.copy()

        session = runtime.Runtime.__new__(runtime.Runtime)
        session.menu = drawing.Menu()
        session.history = h
        session.status = ''
        session.settings = ctx.scene.blender_xr
        session._xr_hierarchy_object = parent.name
        session._xr_hierarchy_path = []
        session._xr_hierarchy_page = 0
        session._xr_hierarchy_rows = ()
        session.transaction = session.grab = session.air_grab = session.axis_move = None
        session._xr_gesture = session._weight_stroke = session.bone_drag = None
        selected(ctx, parent, child1, child2, active=parent)

        session.command(ctx, 'XR_ASSEMBLY_MENU')
        assert session.menu.page == 'XR_ASSEMBLY_085'
        session.command(ctx, 'XR_ASSEMBLY_PARENT')
        assert child1.parent == parent and child2.parent == parent
        assert near(child1.matrix_world.translation, original1.translation)
        assert near(child2.matrix_world.translation, original2.translation)
        assert h.undo[-1][0] == 'XR_ASSEMBLY_PARENT'
        assert h.step(True)
        assert child1.parent is None and child2.parent is None
        assert near(child1.matrix_world.translation, original1.translation)
        assert h.step(False)
        assert child1.parent == parent and child2.parent == parent
        assert near(child1.matrix_world.translation, original1.translation)
        # Parenting establishes transform hierarchy while remaining separate geometry.
        parent.location.x += 2
        ctx.view_layer.update()
        assert abs(child1.matrix_world.translation.x - (original1.translation.x + 2)) < 1e-4
        parent.location.x -= 2
        ctx.view_layer.update()
        assert abs(child1.matrix_world.translation.x - original1.translation.x) < 1e-4

        selected(ctx, child1, child2, active=child1)
        session.command(ctx, 'XR_ASSEMBLY_CLEAR')
        assert child1.parent is None and child2.parent is None
        assert near(child1.matrix_world.translation, original1.translation)
        assert h.step(True)
        assert child1.parent == parent and child2.parent == parent
        assert h.step(False)
        assert child1.parent is None and child2.parent is None

        selected(ctx, child1, child2, active=child1)
        session.command(ctx, 'XR_ASSEMBLY_EMPTY')
        empty = ctx.view_layer.objects.active
        assert empty.type == 'EMPTY'
        assert child1.parent == empty and child2.parent == empty
        empty_name = empty.name
        loc1, loc2 = child1.matrix_world.translation.copy(), child2.matrix_world.translation.copy()
        assert h.step(True)
        assert bpy.data.objects.get(empty_name) is None
        assert child1.parent is None and child2.parent is None
        assert near(child1.matrix_world.translation, loc1)
        assert h.step(False)
        recreated = bpy.data.objects.get(empty_name)
        assert recreated is not None and recreated.type == 'EMPTY'
        assert child1.parent == recreated and child2.parent == recreated

        selected(ctx, child1, recreated, active=child1)
        refused(lambda: session.command(ctx, 'XR_ASSEMBLY_PARENT'), 'cycle')
        assert child1.parent == recreated

        selected(ctx, child1, active=child1)
        session.command(ctx, 'XR_ASSEMBLY_PARENT_SELECT')
        assert ctx.view_layer.objects.active == recreated
        assert recreated.select_get()

        session.command(ctx, 'XR_ASSEMBLY_CHILDREN_SELECT')
        assert child1.select_get() and child2.select_get()

        selected(ctx, parent, active=parent)
        session.command(ctx, 'XR_ASSEMBLY_EMPTY_ONLY')
        empty_only = ctx.view_layer.objects.active
        assert empty_only.type == 'EMPTY' and len(empty_only.children) == 0
        only_name = empty_only.name
        assert h.step(True)
        assert bpy.data.objects.get(only_name) is None
        assert h.step(False)
        assert bpy.data.objects.get(only_name) is not None

        selected(ctx, child1, active=child1)
        child1.hide_select = True
        refused(lambda: session.command(ctx, 'XR_ASSEMBLY_CLEAR'), 'unlock')
        child1.hide_select = False
        selected(ctx, child1, active=child1)

        # External parenting changes must be detected before undo.
        h.clear()
        session.command(ctx, 'XR_ASSEMBLY_CLEAR')
        child1.location.z += 2
        ctx.view_layer.update()
        refused(lambda: h.step(True), 'outside XR history')

        assert all(obj.data == data and len(obj.data.vertices) == count
                   for obj, (data, count) in zip((parent, child1, child2), meshes))
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'xr-parenting.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(path), copy=True)
            with bpy.data.libraries.load(str(path)) as (lib, loaded):
                loaded.objects = [parent.name, child1.name, child2.name,
                                  recreated.name]
            names = {obj.name: obj for obj in loaded.objects}
            assert names[child2.name].parent is not None
            assert names[child2.name].parent.name.startswith(recreated.name)
        print('PASS v0.8.5 native parenting/Empty, lock guards, history and persistence')
    finally:
        h.clear()
        if session is not None:
            session.menu = None
            session.settings = None
        blender_xr.unregister()


run()
