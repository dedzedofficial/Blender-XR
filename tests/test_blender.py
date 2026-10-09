"""Run with Blender --background --factory-startup --python tests/test_blender.py."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import bmesh
from mathutils import Vector
import blender_xr
from blender_xr import mesh, actions, drawing, runtime


def cube():
    if bpy.context.object and bpy.context.object.mode!='OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_cube_add()
    obj=bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.context.tool_settings.mesh_select_mode=(False,False,True)
    bm=bmesh.from_edit_mesh(obj.data)
    for f in bm.faces:f.select_set(False)
    for e in bm.edges:e.select_set(False)
    for v in bm.verts:v.select_set(False)
    top=max(bm.faces,key=lambda f:f.calc_center_median().z)
    top.select_set(True)
    bm.select_flush_mode()
    mesh.update(obj)
    return obj


def geometry(obj):
    bm=bmesh.from_edit_mesh(obj.data)
    return len(bm.verts),len(bm.edges),len(bm.faces)


def test_mesh(tool):
    obj=cube()
    before=geometry(obj)
    tx=mesh.Transaction(obj,tool)
    tx.preview(0.15)
    first=geometry(obj)
    assert first!=before,(tool,first,before)
    tx.preview(0.2)
    assert geometry(obj)==first,('Preview accumulated topology',tool)
    assert all(v.co.length<5 for v in bmesh.from_edit_mesh(obj.data).verts)
    bm=bmesh.from_edit_mesh(obj.data)
    assert all(e.is_manifold for e in bm.edges),('Non-manifold result',tool)
    history=mesh.History()
    history.push(tx.finish())
    assert history.step(True)
    assert geometry(obj)==before
    assert history.step(False)
    assert geometry(obj)==first
    history.clear()
    tx=mesh.Transaction(obj,tool)
    tx.preview(0.1)
    tx.cancel()
    assert geometry(obj)==first
    assert not [m for m in bpy.data.meshes if m.name.startswith('.BlenderXR_Snapshot')]
    print('PASS mesh',tool,first)


def run():
    blender_xr.register()
    assert bpy.context.scene.blender_xr.dominant_hand=='RIGHT'
    for tool in ['EXTRUDE','BEVEL','INSET']:test_mesh(tool)
    obj=cube()
    bm=bmesh.from_edit_mesh(obj.data)
    for face in bm.faces:
        if face.normal.x>0.9:face.select_set(True)
    mesh.apply_tool(obj,'EXTRUDE',0.1)
    assert all(e.is_manifold for e in bm.edges), 'Multi-face extrusion left internal wires'
    obj=cube()
    bm=bmesh.from_edit_mesh(obj.data)
    uv=bm.loops.layers.uv.new('UV_Test')
    for face in bm.faces:
        for loop in face.loops:loop[uv].uv=(0.25,0.75)
    tx=mesh.Transaction(obj,'INSET');tx.preview(0.1);tx.cancel()
    bm=bmesh.from_edit_mesh(obj.data)
    uv=bm.loops.layers.uv.get('UV_Test')
    assert uv is not None
    assert all((loop[uv].uv-Vector((0.25,0.75))).length<1e-6 for face in bm.faces for loop in face.loops)
    print('PASS multi-face extrusion and UV preservation on cancel')
    obj=cube()
    hit=mesh.face_hit(obj,Vector((0,0,3)),Vector((0,0,-1)))
    bm=bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    assert hit and bm.faces[hit[0]].normal.z>0.9
    mesh.select_face(obj,hit[0])
    assert sum(f.select for f in bmesh.from_edit_mesh(obj.data).faces)==1
    mesh.select_face(obj,hit[0],True)
    assert sum(f.select for f in bmesh.from_edit_mesh(obj.data).faces)==0
    try:mesh.Transaction(obj,'EXTRUDE')
    except ValueError:pass
    else:raise AssertionError('Empty selection allowed')
    bm.faces[hit[0]].select_set(True)
    bpy.ops.blender_xr.tool(tool='INSET',amount=0.1)
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.shape_key_add(name='Basis')
    bpy.ops.object.mode_set(mode='EDIT')
    try:mesh.editable(obj)
    except ValueError:pass
    else:raise AssertionError('Shape keys allowed')
    bpy.ops.object.mode_set(mode='OBJECT')
    obj=cube()
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.data=bpy.data.meshes.new('shared')
    other=obj.copy();bpy.context.collection.objects.link(other)
    try:mesh.editable(obj)
    except ValueError:pass
    else:raise AssertionError('Shared mesh allowed')
    button=runtime.Button()
    assert button.update(0.7)==(True,False)
    assert button.update(0.5)==(False,False)
    assert button.update(0.2)==(False,True)
    menu=drawing.Menu();menu.position(Vector((0,0,0)),Vector((0,-1,0.25)),1)
    for i,(_,action) in enumerate(drawing.BUTTONS):
        x,y,w,h=drawing.button_rect(i)
        target=menu.world(x+w/2,y+h/2)
        assert menu.hit(target+menu.normal,-menu.normal)[0]==action
    menu.visible=False
    assert menu.hit(Vector((0,-1,0)),Vector((0,1,0)))[0] is None
    print('PASS face selection, guards, button hysteresis, all menu targets')
    # Exercise the actual modal input-loss branch, not just the packet receiver.
    from types import SimpleNamespace as NS
    import time
    session=runtime.Runtime.__new__(runtime.Runtime)
    session.last_tick=time.monotonic();session.started=session.last_tick
    session.navigation_initialized=True;session.dom=1;session.off=0
    session.transaction=NS(cancel=lambda:events.append('cancel'),
                           finish=lambda:events.append('COMMIT'))
    session.grab=None;session.trigger=runtime.Button();session.trigger.down=True
    session.off_trigger=runtime.Button();session.grip=runtime.Button()
    session.menu=drawing.Menu();session.bridge=NS(read=lambda:None)
    session.object_hit=lambda *args:None
    events=[]
    state=NS(controller_aim_rotation_get=lambda c,h:(1,0,0,0),
             controller_grip_rotation_get=lambda c,h:(1,0,0,0),
             controller_aim_location_get=lambda c,h:(0,0,0),
             controller_grip_location_get=lambda c,h:(0,0,0),
             viewer_pose_location=(0,-1,0.25),viewer_scale=1)
    fake_context=NS(window_manager=NS(xr_session_state=state))
    original_bpy=runtime.bpy
    try:
        runtime.bpy=NS(types=NS(XrSessionState=NS(is_running=lambda c:True)))
        session.tick(fake_context)
    finally:
        runtime.bpy=original_bpy
    assert events==['cancel'] and session.transaction is None
    assert not session.trigger.down
    assert 'WAITING' in session.status
    print('PASS actual runtime cancels preview on finger input loss without committing')
    # RNA map construction does not require a connected headset.
    state=bpy.context.window_manager.xr_session_state
    if state is not None:
        amap=actions.build_map(state)
        assert len(amap.actionmap_items)==6
        assert [u.path for u in amap.actionmap_items['aim_pose'].user_paths]==list(actions.HANDS)
        for item in amap.actionmap_items:
            for binding in item.bindings:
                assert len(binding.component_paths)==len(item.user_paths)==2
        print('PASS OpenXR action-map construction on Blender',bpy.app.version_string)
    else:
        print('SKIP action-map construction: background Blender has no XR session state')
    blender_xr.unregister()
    assert not hasattr(bpy.types.Scene,'blender_xr')
    blender_xr.register();blender_xr.unregister()
    print('PASS register / unregister / reload')

run()
