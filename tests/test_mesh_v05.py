"""v0.5 vertex/edge/face selection and edit-operation regression checks."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy,bmesh
from mathutils import Vector
import blender_xr
from blender_xr import mesh,runtime,drawing,gizmo

blender_xr.register()
try:
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_cube_add()
    obj=bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')

    for mode,tuple_mode in [('VERT',(True,False,False)),('EDGE',(False,True,False)),('FACE',(False,False,True))]:
        mesh.set_selection_mode(bpy.context,mode)
        assert tuple(bpy.context.tool_settings.mesh_select_mode)==tuple_mode
        assert mesh.selection_mode(bpy.context)==mode

    mesh.set_selection_mode(bpy.context,'VERT')
    bm=mesh.editable(obj);bm.verts.ensure_lookup_table()
    for v in bm.verts:v.select_set(False)
    bm.verts[0].select_set(True);mesh.update(obj)
    before=mesh.selected_center(obj,'VERT').copy()
    tx=mesh.Transaction(obj,'MOVE_FACE','VERT');tx.preview(.25,axis=Vector((1,0,0)))
    after=mesh.selected_center(obj,'VERT')
    assert (after-before-Vector((.25,0,0))).length<1e-5
    tx.cancel()

    bm=mesh.editable(obj);bm.verts.ensure_lookup_table()
    for v in bm.verts:v.select_set(False)
    bm.verts[0].select_set(True);bm.verts[1].select_set(True);mesh.update(obj)
    count=len(bm.verts)
    hist=mesh.History();hist.push(mesh.merge_selected(obj))
    assert len(mesh.editable(obj).verts)==count-1
    assert hist.step() and len(mesh.editable(obj).verts)==count
    hist.clear()

    mesh.set_selection_mode(bpy.context,'EDGE')
    bm=mesh.editable(obj);bm.edges.ensure_lookup_table()
    for e in bm.edges:e.select_set(False)
    bm.edges[0].select_set(True);mesh.update(obj)
    edge_count=len(bm.edges)
    hist=mesh.History();hist.push(mesh.subdivide_selected(obj))
    assert len(mesh.editable(obj).edges)>edge_count
    assert hist.step() and len(mesh.editable(obj).edges)==edge_count
    hist.clear()

    mesh.set_selection_mode(bpy.context,'FACE')
    mesh.select_face(obj,0)
    face_count=len(mesh.editable(obj).faces)
    hist=mesh.History();hist.push(mesh.duplicate_selected(obj))
    assert len(mesh.editable(obj).faces)>face_count
    assert hist.step() and len(mesh.editable(obj).faces)==face_count
    hist.clear()

    session=runtime.Runtime.__new__(runtime.Runtime)
    session.transaction=None;session.grab=None;session.axis_move=None;session.air_grab=None
    session.history=mesh.History();session.tool='SELECT';session.select_mode='FACE';session.status=''
    session.command(bpy.context,'SELECT_VERT')
    assert session.select_mode=='VERT' and mesh.selection_mode()=='VERT'
    session.command(bpy.context,'SELECT_EDGE')
    assert session.select_mode=='EDGE' and mesh.selection_mode()=='EDGE'
    session.command(bpy.context,'SELECT_FACE')
    assert session.select_mode=='FACE' and mesh.selection_mode()=='FACE'

    assert {'SELECT_VERT','SELECT_EDGE','SELECT_FACE'} <= {a for _,a in drawing.EDIT_BUTTONS}
    assert {'MERGE','SUBDIVIDE','DUPLICATE','RECALC','FLIP_NORMALS','DELETE_GEOM'} <= {a for _,a in drawing.EDIT_MORE_BUTTONS}
    mesh.select_face(obj,0)
    assert {n for n,_ in gizmo.make(bpy.context,'MOVE_FACE',1).axes}=={'X','Y','Z'}
    print('PASS v0.5 vertex edge face modes, move, merge, subdivide, duplicate and menus')
finally:
    if bpy.context.object and bpy.context.object.mode=='EDIT':bpy.ops.object.mode_set(mode='OBJECT')
    blender_xr.unregister()
