"""Run in background Blender: real mesh creation plus simulated XR modal input."""
import math
import sys
import time
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector, Quaternion, Euler
import blender_xr
from blender_xr import runtime, drawing, mesh, primitives

blender_xr.register()
try:
    # Shape creation must make new objects even when the old mesh is in Edit Mode.
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for kind in primitives.KINDS:
        before=len(bpy.data.objects)
        obj=primitives.add(bpy.context,kind,Vector((2,3,4)),.5)
        assert len(bpy.data.objects)==before+1 and obj.type=='MESH' and obj.mode=='OBJECT'
        assert len(obj.data.vertices)>0 and (obj.location-Vector((2,3,4))).length<1e-6
        obj_name,data_name=obj.name,obj.data.name
        history=mesh.History();history.push(mesh.creation_entry(obj))
        for _ in range(2):
            assert history.step(True) and bpy.data.objects.get(obj_name) is None
            assert history.step(False)
            restored=bpy.data.objects[obj_name]
            assert restored.data.name==data_name and restored.select_get()
            assert (restored.location-Vector((2,3,4))).length<1e-6
        history.clear()
        bpy.ops.object.mode_set(mode='EDIT')
    old=bpy.context.object;old_data=old.data;old_count=len(old_data.vertices)
    added=primitives.add(bpy.context,'CUBE',Vector(),1)
    assert added!=old and len(old_data.vertices)==old_count and old.mode=='OBJECT'
    print('PASS all six primitives, creation undo/redo, edit-mode isolation and history cleanup')

    session=runtime.Runtime.__new__(runtime.Runtime)
    session.menu=drawing.Menu();session.settings=bpy.context.scene.blender_xr
    session.pending_primitive=None;session.spawn_preview=None;session.history=mesh.History()
    session.command(bpy.context,'ADD_MENU');assert session.menu.page=='PRIMITIVES'
    session.command(bpy.context,'ADD_SPHERE');assert session.tool=='PLACE'
    empty=NS(scene=NS(ray_cast=lambda *a:(False,)),evaluated_depsgraph_get=lambda:None)
    location,size=session.placement(empty,Vector(),Vector((0,1,0)),2)
    assert (location-Vector((0,3,0))).length<1e-6 and size==1
    surface=NS(scene=NS(ray_cast=lambda *a:(True,Vector((0,0,0)),Vector((0,0,1)))),
               evaluated_depsgraph_get=lambda:None)
    location,size=session.placement(surface,Vector(),Vector((0,1,0)),1)
    assert (location-Vector((0,0,.25))).length<1e-6
    session.spawn_preview=(location,size);session.spawn(bpy.context)
    assert session.tool=='MOVE' and session.pending_primitive is None
    assert bpy.context.object.name.startswith('XR Sphere')
    assert session.history.step(True);assert session.history.step(False)
    session.history.clear()
    assert not any(obj.name.startswith('.BlenderXR_CreatedObject') for obj in bpy.data.objects)
    print('PASS picker, scaled placement preview, surface offset, spawn and no leftover templates')

    # Menu hit targets must match drawn buttons on both pages.
    menu=drawing.Menu();menu.position(Vector(),Vector((0,-1,.25)),1)
    for page in ('TOOLS','PRIMITIVES','TRAVEL'):
        menu.page=page
        for index,(_,action) in enumerate(menu.buttons):
            x,y,w,h=drawing.button_rect(index)
            target=menu.world(x+w/2,y+h/2)
            assert menu.hit(target+menu.normal,-menu.normal)[0]==action
    print('PASS primitive and main menu ray targets')

    original_bpy=runtime.bpy;original_read=runtime.actions.read
    try:
        runtime.bpy=NS(types=NS(XrSessionState=NS(is_running=lambda context:True)),context=None)
        rotation=Euler((math.pi/2,0,0)).to_quaternion()
        assert runtime.stick_delta(rotation,(0,.1),.05,1,1).length==0
        delta=runtime.stick_delta(rotation,(1,1),.1,1,1)
        assert abs(delta.length-.1)<1e-6 and abs(delta.z)<1e-6
        runtime.START_ERROR=''
        def make_session(dom):
            settings=bpy.context.scene.blender_xr
            settings.dominant_hand='LEFT' if dom==0 else 'RIGHT'
            settings.finger_touch=False;settings.input_source='CONTROLLERS'
            settings.grab_air=True
            positions=[Vector((-2,-2,1)),Vector((2,-2,1))]
            values={}
            state=NS(navigation_location=Vector(),viewer_pose_rotation=rotation,
                     viewer_pose_location=Vector((0,-3,1.7)),viewer_scale=1.0,
                     controller_aim_rotation_get=lambda c,h:rotation,
                     controller_grip_rotation_get=lambda c,h:rotation)
            state.controller_aim_location_get=lambda c,h:positions[h]+state.navigation_location
            state.controller_grip_location_get=state.controller_aim_location_get
            context=NS(window=None,area=NS(type='VIEW_3D',regions=[NS(type='WINDOW')]),
                       scene=bpy.context.scene,window_manager=NS(xr_session_state=state),
                       view_layer=bpy.context.view_layer,mode='OBJECT',selected_objects=[])
            session=runtime.Runtime(context);session.navigation_initialized=True
            session.object_hit=lambda *a:None
            runtime.actions.read=lambda c,name,h:values.get((name,h),(0,0))
            def tick():
                session.last_tick=time.monotonic()-.05
                session.tick(context)
            return session,state,values,positions,context,tick
        for dom in (0,1):
            session,state,values,positions,context,tick=make_session(dom)
            values[('stick',0)]=(0,1)
            tick();assert state.navigation_location.y>0
            assert abs(state.navigation_location.z)<1e-6
            values[('stick',0)]=(0,0)
            # Either hand can grip empty air; the user's selected mesh must not move.
            for hand in (0,1):
                state.navigation_location=Vector()
                values[('grab',hand)]=(1,0);tick()
                assert session.air_grab is not None and session.air_grab[0]==hand
                assert session.grab is None
                positions[hand].z+=.2
                tick();assert abs(state.navigation_location.z+.2)<1e-6
                previous=state.navigation_location.copy()
                tick();assert (state.navigation_location-previous).length<1e-6
                values[('grab',hand)]=(0,0);tick();assert session.air_grab is None
            session.history.clear()
        print('PASS left stick with either dominant hand, either-hand air grab, release and no feedback drift')

        # Object-directed grip must move a mesh, not the viewer.
        session,state,values,positions,context,tick=make_session(1)
        session.tool='MOVE';session.object_hit=lambda *a:(added,added.location)
        context.selected_objects=[]
        values[('grab',1)]=(1,0);tick()
        assert session.grab is not None and session.air_grab is None
        before=added.matrix_world.copy();positions[1].x+=.3;tick()
        assert abs(added.matrix_world.translation.x-before.translation.x-.3)<1e-6
        values[('grab',1)]=(0,0);tick()
        assert session.grab is None and state.navigation_location.length==0
        assert session.history.step(True)
        assert (added.matrix_world.translation-before.translation).length<1e-6
        session.history.clear()
        print('PASS mesh grip priority, object move and undo without viewer movement')

        # Reproduce screenshot: a TIMER Event with NO .timer attribute.
        session,state,values,positions,context,tick=make_session(1)
        session.tick=lambda c:events.append('tick')
        session.area=NS(type='VIEW_3D',tag_redraw=lambda:None)
        context.temp_override=lambda **kwargs:nullcontext()
        runtime.bpy.context=context
        session.last_tick=time.monotonic()-1
        events=[];runtime.CURRENT=session
        operator=NS(report=lambda *args:None)
        result=blender_xr.BXR_OT_session.modal(operator,context,NS(type='TIMER',value='NOTHING'))
        assert result=={'PASS_THROUGH'} and events==['tick']
        assert runtime.timer_due(NS(last_tick=10),10.01) is False
        assert runtime.timer_due(NS(last_tick=10),10.04) is True
        runtime.CURRENT=None
        print('PASS modal TIMER without event.timer, plus navigation rate limiting')
    finally:
        runtime.CURRENT=None
        runtime.bpy=original_bpy;runtime.actions.read=original_read
finally:
    blender_xr.unregister()
print('PASS v0.4.2 controls and primitives')
