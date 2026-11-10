"""Blender integration tests for native, hand-mounted XR scene hierarchy."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import blender_xr
from blender_xr import drawing, menus, mesh, runtime, scene_hierarchy_v080


def _choose(session, kind, name, context):
    index = session._xr_hierarchy_rows.index((kind, name))
    session.command(context, 'HIER_ROW_' + str(index))


def _expect_refusal(command, phrase):
    try:
        command()
    except ValueError as exc:
        assert phrase.lower() in str(exc).lower(), str(exc)
    else:
        raise AssertionError('Unsafe hierarchy operation was accepted')


def run():
    blender_xr.register()
    history = mesh.History()
    try:
        context = bpy.context
        assert runtime.Runtime._xr_hierarchy_patched
        assert len(menus.PAGES['CREATOR']) == 12
        assert 'SCENE_MENU' in [action for _, action in menus.PAGES['CREATOR']]
        assert 'MODE_WEIGHT_PAINT' in [action for _, action in menus.PAGES['RIGGING']]

        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        scene = context.scene
        root = scene.collection
        group = bpy.data.collections.new('XR Hierarchy Group')
        child = bpy.data.collections.new('XR Nested')
        root.children.link(group)
        group.children.link(child)
        first = bpy.data.objects.new('XR Scene A', bpy.data.meshes.new('XR A Mesh'))
        second = bpy.data.objects.new('XR Scene B', bpy.data.meshes.new('XR B Mesh'))
        group.objects.link(first)
        group.objects.link(second)
        nested = bpy.data.objects.new('XR Nested Item', bpy.data.meshes.new('XR N Mesh'))
        child.objects.link(nested)
        context.view_layer.update()
        original_mesh = first.data

        session = runtime.Runtime.__new__(runtime.Runtime)
        session.menu = drawing.Menu()
        session.history = history
        session.tool = 'SELECT'
        session.status = ''
        session.settings = scene.blender_xr
        session._xr_rearm_required = False

        session.command(context, 'SCENE_MENU')
        assert session.menu.page == 'SCENE_HIERARCHY'
        assert ('COLLECTION', group.name) in session._xr_hierarchy_rows
        _choose(session, 'COLLECTION', group.name, context)
        assert ('COLLECTION', child.name) in session._xr_hierarchy_rows
        assert ('OBJECT', first.name) in session._xr_hierarchy_rows
        _choose(session, 'OBJECT', first.name, context)
        assert session.menu.page == 'SCENE_HIERARCHY_ITEM'
        session.command(context, 'HIER_SELECT')
        assert context.view_layer.objects.active == first
        assert first.select_get(view_layer=context.view_layer)

        session.command(context, 'HIER_BACK')
        _choose(session, 'OBJECT', second.name, context)
        session.command(context, 'HIER_MULTI')
        assert first.select_get() and second.select_get()
        session.command(context, 'HIER_MULTI')
        assert first.select_get() and not second.select_get()

        session.command(context, 'HIER_BACK')
        _choose(session, 'OBJECT', first.name, context)
        session.command(context, 'HIER_VISIBILITY')
        assert first.hide_get(view_layer=context.view_layer)
        assert first.data == original_mesh
        assert history.undo[-1][0] == 'SCENE_VISIBILITY'
        _expect_refusal(lambda: session.command(context, 'HIER_SELECT'), 'hidden')
        assert history.step(True)  # Undo visibility
        assert not first.hide_get(view_layer=context.view_layer)
        assert history.step(False)  # Redo visibility
        assert first.hide_get(view_layer=context.view_layer)
        # An external edit must not be silently overwritten by VR history.
        first.hide_set(False, view_layer=context.view_layer)
        _expect_refusal(lambda: history.step(True), 'outside XR history')
        first.hide_set(True, view_layer=context.view_layer)
        assert history.step(True)
        assert not first.hide_get(view_layer=context.view_layer)

        session.command(context, 'HIER_LOCK')
        assert first.hide_select
        assert history.undo[-1][0] == 'SCENE_SELECT_LOCK'
        _expect_refusal(lambda: session.command(context, 'HIER_MULTI'), 'locked')
        assert history.step(True)
        assert not first.hide_select
        assert history.step(False)
        assert first.hide_select
        assert history.step(True)
        assert not first.hide_select

        # Nested collection navigation and return path.
        session.command(context, 'HIER_BACK')
        _choose(session, 'COLLECTION', child.name, context)
        assert ('OBJECT', nested.name) in session._xr_hierarchy_rows
        session.command(context, 'HIER_UP')
        assert ('OBJECT', first.name) in session._xr_hierarchy_rows

        # Invalidate a cached row when an object is renamed externally.
        cached_name = second.name
        second.name = 'XR Scene Z'
        _expect_refusal(lambda: _choose(session, 'OBJECT', cached_name, context),
                        'scene changed')
        assert ('OBJECT', second.name) in session._xr_hierarchy_rows

        # 7-row pages keep the hand grid bounded; native objects remain reachable.
        extras = []
        for i in range(10):
            obj = bpy.data.objects.new('XR Test Prop %02d' % i,
                                       bpy.data.meshes.new('XR Prop Mesh %02d' % i))
            group.objects.link(obj)
            extras.append(obj)
        context.view_layer.update()
        session.command(context, 'HIER_REFRESH')
        assert len(menus.PAGES['SCENE_HIERARCHY']) <= 12
        session.command(context, 'HIER_NEXT')
        assert session._xr_hierarchy_page == 1
        assert len(menus.PAGES['SCENE_HIERARCHY']) <= 12
        session.command(context, 'HIER_PREV')
        assert session._xr_hierarchy_page == 0

        session.command(context, 'HIER_BACK')  # group -> scene root
        session.command(context, 'HIER_BACK')  # scene root -> Creator
        assert session.menu.page == 'CREATOR'
        assert first.data == original_mesh
        assert first.type == 'MESH' and not first.hide_select
        print('PASS XR scene hierarchy, nested navigation, multi-select, visibility, locks and history')
    finally:
        history.clear()
        blender_xr.unregister()


run()
