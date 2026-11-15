"""Integration: hand-mounted search filters loaded native Blender objects."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import blender_xr
from blender_xr import drawing, menus, mesh, runtime

def run():
    blender_xr.register()
    history = mesh.History()
    try:
        ctx = bpy.context
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        group = bpy.data.collections.new('XR Search Nested')
        ctx.scene.collection.children.link(group)
        target = bpy.data.objects.new('Lantern Prop', bpy.data.meshes.new('Search Target Mesh'))
        group.objects.link(target)
        other = bpy.data.objects.new('Camera Rig', bpy.data.meshes.new('Search Other Mesh'))
        ctx.scene.collection.objects.link(other)
        ctx.view_layer.update()
        session = runtime.Runtime.__new__(runtime.Runtime)
        session.menu = drawing.Menu()
        session.history = history
        session.status = ''
        session.settings = ctx.scene.blender_xr
        session.tool = 'SELECT'
        session._xr_rearm_required = False
        session.command(ctx, 'SCENE_MENU')
        session.command(ctx, 'HIER_SEARCH')
        assert session.menu.page == 'SCENE_HIERARCHY_SEARCH'
        # Type "LAN" on the 9-character wrist keyboard.
        for char in 'LAN':
            index = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ '.index(char)
            session._xr_hierarchy_search_page = index // 9
            session.command(ctx, 'HIER_CHAR_' + str(index))
        assert session._xr_hierarchy_query == 'LAN'
        assert len(menus.PAGES['SCENE_HIERARCHY_SEARCH']) <= 12
        session.command(ctx, 'HIER_SEARCH_DONE')
        assert session._xr_hierarchy_rows == (('OBJECT', target.name),)
        session.command(ctx, 'HIER_ROW_0')
        session.command(ctx, 'HIER_SELECT')
        assert ctx.view_layer.objects.active == target
        session.command(ctx, 'HIER_BACK')
        # A rename invalidates the cached result instead of selecting another object.
        target.name = 'Renamed Prop'
        try:
            session.command(ctx, 'HIER_ROW_0')
        except ValueError as exc:
            assert 'changed' in str(exc)
        else:
            raise AssertionError('Stale search row was accepted')
        assert not session._xr_hierarchy_rows
        session.command(ctx, 'HIER_SEARCH')
        session.command(ctx, 'HIER_SEARCH_DELETE')
        assert session._xr_hierarchy_query == 'LA'
        session.command(ctx, 'HIER_SEARCH_DONE')
        assert not session._xr_hierarchy_rows
        session.command(ctx, 'HIER_BACK')
        assert session._xr_hierarchy_query == ''
        assert session.menu.page == 'SCENE_HIERARCHY'
        assert ('COLLECTION', group.name) in session._xr_hierarchy_rows
        assert target.data.name == 'Search Target Mesh'
        print('PASS native XR hierarchy wrist search, nested matching, stale row guard, clear')
    finally:
        history.clear()
        blender_xr.unregister()

run()
