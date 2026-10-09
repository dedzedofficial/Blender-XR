"""Ray-picked XYZ transforms and face deletion regression checks."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy,bmesh
from mathutils import Vector
import blender_xr
from blender_xr import gizmo,mesh,runtime
blender_xr.register()
try:
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_cube_add()
    obj=bpy.context.object
    handles=gizmo.make(bpy.context,'MOVE',1)
    assert {name for name,axis in handles.axes}=={'X','Y','Z'}
    for name,axis in handles.axes:
        other=Vector((0,0,1)) if name!='Z' else Vector((0,1,0))
        origin=handles.anchor+axis*.2+other*2
        direction=-other
        assert handles.pick(origin,direction)[0]==name
        first=gizmo.parameter(origin,direction,handles.anchor,axis)
        last=gizmo.parameter(origin+axis*.5,direction,handles.anchor,axis)
        assert abs(last[0]-first[0]-.5)<1e-6
        session=runtime.Runtime.__new__(runtime.Runtime)
        session.tool='MOVE';session.gizmo=handles;session.axis_move=None;session.axis_drag=None
        session.transaction=None;session.grab=None;session.air_grab=None
        session.begin_axis(bpy.context,origin,direction,(name,axis))
        assert session.axis_drag[5]==name
        obj.matrix_world.translation+=axis*.5
        session.cancel_work()
        assert obj.matrix_world.translation.length<1e-6
    assert gizmo.parameter(Vector((0,0,2)),Vector((0,0,-1)),Vector(),Vector((0,0,1))) is None
    bpy.ops.object.mode_set(mode='EDIT');bpy.context.tool_settings.mesh_select_mode=(False,False,True)
    mesh.select_face(obj,0)
    assert {name for name,axis in gizmo.make(bpy.context,'EXTRUDE',1).axes}=={'X','Y','Z'}
    for axis in (Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))):
        before=mesh.snapshot(obj)
        tx=mesh.Transaction(obj,'EXTRUDE');tx.preview(.5,axis=axis)
        bm=mesh.editable(obj)
        center=sum((f.calc_center_median() for f in bm.faces if f.select),Vector())
        del bm
        mesh.restore(obj,before)
        bm=mesh.editable(obj)
        baseline=sum((f.calc_center_median() for f in bm.faces if f.select),Vector())
        del bm
        assert (center-baseline-axis*.5).length<1e-5
        tx.cancel();bpy.data.meshes.remove(before)
    history=mesh.History()
    history.push(mesh.delete_selected(obj))
    assert len(mesh.editable(obj).faces)==5
    assert history.step() and len(mesh.editable(obj).faces)==6
    assert history.step(False) and len(mesh.editable(obj).faces)==5
    history.clear()
    for face in mesh.editable(obj).faces:face.select_set(False)
    try:mesh.delete_selected(obj)
    except ValueError:pass
    else:raise AssertionError('Empty face selection allowed')
    print('PASS XYZ ray handles, axis movement cancellation, XYZ extrusion, parallel rays and delete faces undo/redo')
finally:
    if bpy.context.object and bpy.context.object.mode=='EDIT':bpy.ops.object.mode_set(mode='OBJECT')
    blender_xr.unregister()
