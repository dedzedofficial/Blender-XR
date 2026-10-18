"""v0.6.5 icon UI, mode selector, Loop Cut and object-delete regression checks."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import bmesh
import blender_xr
from blender_xr import drawing, menus, mesh, runtime, v065, version


blender_xr.register()
session=None
try:
    assert version.VERSION >= (0,6,5)
    assert blender_xr.bl_info['version'] == version.VERSION
    assert runtime.Runtime._v065_patched
    assert drawing.Menu._v065_icons
    assert drawing._v065_loop_preview
    assert mesh.History._v065_delete_history

    print('v065: menus', flush=True)
    # Core pages are icon-first and include the new Blender-style mode control.
    assert menus.PAGES['TOOLS'][0][1] == 'MODE_MENU'
    assert menus.PAGES['EDIT'][0][1] == 'MODE_MENU'
    assert all(label == '' for label,_action in menus.PAGES['TOOLS'])
    assert all(label == '' for label,_action in menus.PAGES['EDIT'])
    edit_actions={action for _label,action in menus.PAGES['EDIT']}
    assert {'INSET','BEVEL','EXTRUDE','LOOP_CUT_MENU','SELECT_VERT','SELECT_EDGE','SELECT_FACE'} <= edit_actions
    assert {'MODE_OBJECT','MODE_EDIT'} <= {action for _label,action in menus.PAGES['MODE_SELECT']}
    assert {'LOOP_CUT_LESS','LOOP_CUT_MORE','LOOP_POS_LEFT','LOOP_POS_RIGHT','LOOP_CUT_APPLY'} <= {
        action for _label,action in menus.PAGES['LOOP_CUT']}
    assert v065.TOOLTIP_DELAY == 0.5
    assert 'DELETE_OBJECT' in v065.TOOLTIPS and 'LOOP_CUT_MENU' in v065.TOOLTIPS

    print('v065: create cube', flush=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_cube_add()
    obj=bpy.context.object

    session=runtime.Runtime.__new__(runtime.Runtime)
    session.transaction=None; session.grab=None; session.axis_move=None; session.air_grab=None
    session.history=mesh.History(); session.tool='SELECT'; session.select_mode='FACE'; session.status=''
    session.settings=bpy.context.scene.blender_xr; session.menu=drawing.Menu()
    session.loop_cuts=1; session.loop_position=0.5; session.loop_preview=None

    # Explicit mode actions behave like a dropdown choice rather than a blind toggle.
    session.command(bpy.context,'MODE_MENU')
    assert session.menu.page == 'MODE_SELECT'
    session.command(bpy.context,'MODE_EDIT')
    assert obj.mode == 'EDIT' and session.menu.page == 'EDIT'
    session.command(bpy.context,'MODE_EDIT')
    assert obj.mode == 'EDIT'

    print('v065: mode switch complete', flush=True)
    # Pick a cube edge and verify the continuous quad ring can be found and cut.
    mesh.set_selection_mode(bpy.context,'EDGE'); session.select_mode='EDGE'
    bm=mesh.editable(obj); bm.edges.ensure_lookup_table()
    for edge in bm.edges: edge.select_set(False)
    bm.edges[0].select_set(True); mesh.update(obj)
    ring=v065._ring_edges(obj)
    assert len(ring) >= 4
    preview=v065.loop_preview(obj)
    assert len(preview) == len(ring)
    before_edges=len(mesh.editable(obj).edges)
    print('v065: beginning loop subdivision', flush=True)
    entry=v065.loop_cut(obj,1,0.5)
    print('v065: loop subdivision complete', flush=True)
    after_edges=len(mesh.editable(obj).edges)
    assert after_edges > before_edges
    print('v065: loop history', flush=True)
    session.history.push(entry)
    assert session.history.step(True)
    assert len(mesh.editable(obj).edges) == before_edges
    assert session.history.step(False)
    assert len(mesh.editable(obj).edges) == after_edges

    print('v065: history complete; inset next', flush=True)
    # Inset remains directly available and transaction-safe in Face mode.
    session.history.clear()
    mesh.set_selection_mode(bpy.context,'FACE'); session.select_mode='FACE'
    bm=mesh.editable(obj)
    for face in bm.faces: face.select_set(False)
    bm.faces.ensure_lookup_table(); bm.faces[0].select_set(True); mesh.update(obj)
    tx=mesh.Transaction(obj,'INSET','FACE')
    before_faces=len(mesh.editable(obj).faces)
    tx.preview(0.1)
    assert len(mesh.editable(obj).faces) > before_faces
    tx.cancel()
    assert len(mesh.editable(obj).faces) == before_faces

    print('v065: inset complete; deletion next', flush=True)
    # Object deletion is a separate Object Mode history entry and is undo/redo safe.
    bpy.ops.object.mode_set(mode='OBJECT')
    session.menu.page='TOOLS'; session.select_mode='FACE'; session.history.clear()
    name=obj.name
    print('v065: delete start', flush=True)
    session.command(bpy.context,'DELETE_OBJECT')
    print('v065: delete complete', flush=True)
    assert bpy.data.objects.get(name) is None
    assert session.history.undo[-1][0] == 'DELETE_OBJECT'
    print('v065: undo object delete', flush=True)
    assert session.history.step(True)
    print('v065: undo object delete complete', flush=True)
    restored=bpy.data.objects.get(name)
    assert restored is not None
    print('v065: redo object delete', flush=True)
    assert session.history.step(False)
    print('v065: redo object delete complete', flush=True)
    assert bpy.data.objects.get(name) is None

    print('PASS v0.6.5 modeling and icon UI suite under Mesh XR '+version.DISPLAY_VERSION, flush=True)
finally:
    print('v065: finally begins', flush=True)
    if session is not None:
        print('v065: history cleanup begins', flush=True)
        try: session.history.clear()
        except Exception: pass
        print('v065: history cleanup completed', flush=True)
        print('v065: release session attributes', flush=True)
        session.settings=None; session.menu=None; session=None
    if bpy.context.object and bpy.context.object.mode=='EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')
    print('v065: unregister begins', flush=True)
    blender_xr.unregister()
    print('v065: unregister completed', flush=True)
    # Blender 4.2 can crash on process teardown when module-global references
    # retain BMesh or RNA wrappers for objects/edges already removed above.
    # Release these test-only wrappers while Blender's Python runtime is alive.
    for _name in ('obj', 'restored', 'bm', 'edge', 'face', 'ring',
                  'entry', 'tx', 'preview', 'selected'):
        globals().pop(_name, None)
    import gc
    gc.collect()
    print('v065: stale test references collected', flush=True)
