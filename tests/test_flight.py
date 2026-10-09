"""Blender regression checks for 3D flight, turning, ray switching and travel UI."""
import math
import sys
import time
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import bmesh
from mathutils import Vector, Quaternion, Euler
import blender_xr
from blender_xr import runtime, primitives, drawing

blender_xr.register()
try:
    pitched=Euler((math.pi/4,0,0)).to_quaternion()
    delta=runtime.flight_delta(pitched,(0,1),0,.1,10,1,True)
    assert delta.z < -.6 and delta.length > .99  # look down and fly forward
    level=runtime.flight_delta(pitched,(0,1),0,.1,10,1,False)
    assert abs(level.z)<1e-6 and abs(level.length-1)<1e-6
    lift=runtime.flight_delta(pitched,(0,0),1,.1,10,1,True)
    assert (lift-Vector((0,0,1))).length<1e-6
    capped=runtime.flight_delta(pitched,(1,1),1,.1,10,1,True)
    assert capped.length<=1.00001
    assert runtime.flight_delta(pitched,(0,.1),.1,.1,10,1).length==0
    turn=runtime.Turning()
    assert turn.angle(.8,.1,'SNAP',30,90)==-30
    assert turn.angle(.8,.1,'SNAP',30,90)==0
    assert turn.angle(0,.1,'SNAP',30,90)==0
    assert turn.angle(-.8,.1,'SNAP',30,90)==30
    assert turn.angle(1,.1,'SMOOTH',30,90)==-9
    base=Vector((10,20,30));raw=Vector((.2,.4,1.6))
    old_rotation=Quaternion(Vector((0,0,1)),.4)
    offset=Vector((3,4,5))
    viewer=base+offset+old_rotation@raw
    state=NS(navigation_location=offset,navigation_rotation=old_rotation,viewer_pose_location=viewer)
    runtime.turn_view(state,-30,base)
    new_viewer=base+state.navigation_location+state.navigation_rotation@raw
    assert (new_viewer-viewer).length<1e-5
    print('PASS full 3D flight, vertical input, speed cap, snap rearming, smooth turning and head pivot')

    settings=bpy.context.scene.blender_xr
    area=NS(type='VIEW_3D',regions=[NS(type='WINDOW')])
    positions=[Vector((-5,-5,1)),Vector((5,-5,1))]
    rotation=Euler((math.pi/2,0,0)).to_quaternion()
    def make_session(dom):
        settings.dominant_hand='LEFT' if dom==0 else 'RIGHT'
        settings.finger_touch=False;settings.input_source='CONTROLLERS'
        settings.move_speed=10;settings.fly_mode=True;settings.fast_flight=False
        settings.turn_mode='SNAP'
        state=NS(navigation_location=Vector(),navigation_rotation=Quaternion(),
                 viewer_pose_location=Vector((0,0,1.6)),viewer_pose_rotation=rotation,viewer_scale=1,
                 controller_aim_location_get=lambda c,h:positions[h],
                 controller_grip_location_get=lambda c,h:positions[h],
                 controller_aim_rotation_get=lambda c,h:rotation,
                 controller_grip_rotation_get=lambda c,h:rotation)
        context=NS(window=None,area=area,scene=bpy.context.scene,
                   window_manager=NS(xr_session_state=state),view_layer=bpy.context.view_layer,
                   mode='OBJECT',selected_objects=[])
        session=runtime.Runtime(context);session.navigation_initialized=True
        session.object_hit=lambda *a:None
        values={}
        def tick():
            session.last_tick=time.monotonic()-.05;session.tick(context)
        return session,state,values,tick
    original_bpy,original_read=runtime.bpy,runtime.actions.read
    try:
        runtime.bpy=NS(types=NS(XrSessionState=NS(is_running=lambda c:True)))
        for dom in (0,1):
            session,state,values,tick=make_session(dom)
            runtime.actions.read=lambda c,n,h:values.get((n,h),(0,0))
            values[('stick',0)]=(0,1);tick();normal=state.navigation_location.y
            state.navigation_location=Vector();values[('boost',0)]=(1,0);tick()
            assert state.navigation_location.y>normal*3.8
            values.clear();state.navigation_location=Vector()
            values[('stick',1)]=(.9,1);tick()
            assert state.navigation_location.z>0
            assert state.navigation_rotation.angle>.4
            first=state.navigation_rotation.copy();tick()
            assert state.navigation_rotation.rotation_difference(first).angle<1e-6
            values[('stick',1)]=(0,0);tick()
            values[('stick',1)]=(.9,0);tick()
            assert state.navigation_rotation.angle>first.angle
            session.command(None,'NAV_MENU');assert session.menu.page=='TRAVEL'
            session.command(None,'FASTER');assert settings.move_speed==20
            session.command(None,'SLOWER');assert settings.move_speed==10
            session.command(None,'TURBO');assert settings.fast_flight
            session.command(None,'TURN_TOGGLE');assert settings.turn_mode=='SMOOTH'
            session.history.clear()
        print('PASS actual tick left flight/boost and right turn/lift with either dominant hand, plus Travel buttons')
    finally:
        runtime.bpy=original_bpy;runtime.actions.read=original_read

    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    a=primitives.add(bpy.context,'CUBE',Vector((-2,0,0)),1)
    b=primitives.add(bpy.context,'CUBE',Vector((2,0,0)),1)
    b.select_set(False);a.select_set(True);bpy.context.view_layer.objects.active=a
    bpy.ops.object.mode_set(mode='EDIT');bpy.context.tool_settings.mesh_select_mode=(False,False,True)
    bpy.context.view_layer.update()
    session=runtime.Runtime.__new__(runtime.Runtime)
    session.transaction=session.grab=session.air_grab=None;session.tool='SELECT'
    session.select(bpy.context,Vector((2,0,3)),Vector((0,0,-1)))
    assert bpy.context.active_object==b and b.mode=='EDIT' and a.mode=='OBJECT'
    assert sum(f.select for f in bmesh.from_edit_mesh(b.data).faces)==1
    session.select(bpy.context,Vector((-2,0,3)),Vector((0,0,-1)))
    assert bpy.context.active_object==a and a.mode=='EDIT' and b.mode=='OBJECT'
    b.shape_key_add(name='Basis')
    try:session.select(bpy.context,Vector((2,0,3)),Vector((0,0,-1)))
    except ValueError:pass
    else:raise AssertionError('Refused target switched into edit mode')
    assert bpy.context.active_object==a and a.mode=='EDIT'
    session.transaction=NS()
    try:session.select(bpy.context,Vector((2,0,3)),Vector((0,0,-1)))
    except ValueError:pass
    else:raise AssertionError('Switched meshes during live preview')
    session.transaction=None;session.tool='MOVE'
    session.select(bpy.context,Vector((2,0,3)),Vector((0,0,-1)))
    assert bpy.context.active_object==b and b.mode=='OBJECT' and a.mode=='OBJECT'
    print('PASS real scene ray switching, preserved edit mode, face selection, refused target and live-operation guards')
finally:
    runtime.CURRENT=None
    if bpy.context.object and bpy.context.object.mode=='EDIT':bpy.ops.object.mode_set(mode='OBJECT')
    blender_xr.unregister()
print('PASS v0.4.2 flight, menu and mesh switching')
