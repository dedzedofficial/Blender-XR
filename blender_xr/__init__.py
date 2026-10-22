# SPDX-License-Identifier: GPL-3.0-or-later
from .version import VERSION, VERSION_TEXT

bl_info = {
    'name': 'Mesh XR', 'author': 'Ded Zed', 'version': VERSION,
    'blender': (4,2,0), 'location': '3D View > Sidebar / View Menu > Mesh XR',
    'description': 'Free VR mesh modeling with a hand-mounted OpenXR menu',
    'category': '3D View',
}
import bpy
import textwrap
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty
from bpy.app.handlers import persistent
from . import material_uv, materials, mesh, preferences, project, runtime, statistics, status, v05, v052, v056, v060, v071, v075_features
v05.patch(runtime.Runtime)
v056.patch(runtime.Runtime)
v060.patch(runtime.Runtime)
v071.patch(runtime.Runtime)
# Keep the v0.6 desktop panels grouped with the renamed add-on without changing
# the stable blender_xr operator/property namespace or persisted material node names.
material_uv.BXR_PT_materials_v060.bl_category='Mesh XR'
material_uv.BXR_PT_uv_v060.bl_category='Mesh XR'
material_uv.BXR_OT_material_action.bl_label='Mesh XR Material Action'
material_uv.BXR_OT_uv_action.bl_label='Mesh XR UV Action'


def _persist_setting(self, context):
    preferences.capture(self, context)


class BXR_Settings(bpy.types.PropertyGroup):
    dominant_hand: EnumProperty(name='Dominant hand',items=[
        ('RIGHT','Right','Right edits, left holds the menu'),
        ('LEFT','Left','Left edits, right holds the menu')],default='RIGHT',update=_persist_setting)
    controller_family: EnumProperty(name='Controller family', items=[
        ('AUTO','Automatic','Touch, Index, Vive and simple controller bindings'),
        ('META','Meta','Touch-compatible controllers and simple fallback'),
        ('VALVE','Valve / SteamVR','Index, Touch-compatible, Vive and simple bindings')], default='AUTO',update=_persist_setting)
    input_source: EnumProperty(name='Input', items=[
        ('CONTROLLERS','Controllers','Use trigger and grip controls'),
        ('STEAMVR_HANDS','Finger bridge (experimental)','Requires external SteamVR skeletal bridge and tracked hand poses')], default='CONTROLLERS',update=_persist_setting)
    finger_touch: BoolProperty(name='Finger-touch shortcuts', default=False,
        description='Hold trigger-touch and thumbstick-touch for 0.7 seconds: other hand menu/cancel, dominant hand cancel',update=_persist_setting)
    bridge_port: IntProperty(name='Local bridge port', default=39540, min=1024, max=65535,update=_persist_setting)
    precision_mode: BoolProperty(name='Precision Snap',default=False,
        description='Quantize controller-driven geometry tool distances to the configured tool step')
    step: FloatProperty(name='Tool distance',default=0.03,min=0.0001,max=10,
                        description='Initial tool amount in local mesh units',update=_persist_setting)
    bevel_segments: IntProperty(name='Bevel segments',default=2,min=1,max=8,update=_persist_setting)
    move_speed: FloatProperty(name='Flight speed',default=3.0,min=0.1,max=1000,
        description='VR metres per second; adjust from the hand Travel menu',update=_persist_setting)
    fly_mode: BoolProperty(name='Fly in head direction', default=True,
        description='Left stick follows head pitch in flight; disable for level movement',update=_persist_setting)
    fast_flight: BoolProperty(name='Turbo flight', default=False,
        description='Multiply flight speed by four; also available by holding the left stick click',update=_persist_setting)
    turn_mode: EnumProperty(name='Turning', items=[('SNAP','Snap','One turn per stick deflection'),
        ('SMOOTH','Smooth','Continuous turning')], default='SNAP',update=_persist_setting)
    turn_angle: FloatProperty(name='Snap angle', default=30, min=15, max=90,update=_persist_setting)
    turn_speed: FloatProperty(name='Turn speed', default=90, min=15, max=180,update=_persist_setting)
    grab_air: BoolProperty(name='Grab empty space to move', default=True,
        description='Point into empty space and hold either grip; pull your hand to move the viewer',update=_persist_setting)
    primitive_size: FloatProperty(name='Shape size', default=0.5, min=0.01, max=10,
        description='Primitive size in physical VR metres, scaled to the scene',update=_persist_setting)
    placement_distance: FloatProperty(name='Placement distance', default=1.5, min=0.1, max=10,
        description='Distance in physical VR metres when pointing into empty space',update=_persist_setting)
    show_statistics: BoolProperty(name='Scene Statistics',default=True,update=_persist_setting)
    object_color: FloatVectorProperty(name='Material Color', subtype='COLOR_GAMMA', size=4,
        min=0.0, max=1.0, default=(0.18,0.55,0.95,1.0),
        description='Choose a color, then apply it to the active object or selected faces')
    material_metallic: FloatProperty(name='Metallic', default=0.0, min=0.0, max=1.0)
    material_roughness: FloatProperty(name='Roughness', default=0.5, min=0.0, max=1.0)
    material_alpha: FloatProperty(name='Alpha', default=1.0, min=0.0, max=1.0)
    material_emission: FloatProperty(name='Emission Strength', default=0.0, min=0.0, max=100.0)
    texture_name: bpy.props.StringProperty(name='Texture Image', default='')
    uv_step: FloatProperty(name='UV Move Step', default=0.05, min=0.001, max=1.0)
    status: bpy.props.StringProperty(default='Ready')
    save_path: bpy.props.StringProperty(name='Blend save path',subtype='FILE_PATH',default='',
        description='For an unsaved project; blank creates a timestamped file in Documents/BlenderXR')


class BXR_OT_session(bpy.types.Operator):
    bl_idname = 'blender_xr.session'
    bl_label = 'Start VR'
    bl_description = 'Start Mesh XR using the active OpenXR runtime'

    @classmethod
    def poll(cls,context):
        return context.area is not None and context.area.type=='VIEW_3D'

    def execute(self,context):
        if runtime.CURRENT:
            runtime.CURRENT.request_stop = True
            return {'FINISHED'}
        preferences.ensure(context.scene.blender_xr, context)
        preferences.capture(context.scene.blender_xr, context)
        if not bpy.app.build_options.xr_openxr:
            self.report({'ERROR'},'This Blender build has no OpenXR support')
            return {'CANCELLED'}
        if bpy.app.version[:3] == (5,0,1):
            self.report({'ERROR'},'Blender 5.0.1 has a known VR crash. Use another Blender version.')
            return {'CANCELLED'}
        if bpy.types.XrSessionState.is_running(context):
            self.report({'ERROR'},'Stop the existing VR session before starting Mesh XR')
            return {'CANCELLED'}
        if context.mode not in {'OBJECT','EDIT_MESH'}:
            self.report({'ERROR'},'Use object mode or mesh edit mode')
            return {'CANCELLED'}
        if len(context.objects_in_mode)>1:
            self.report({'ERROR'},'Mesh XR currently edits one mesh at a time')
            return {'CANCELLED'}
        runtime.START_ERROR = ''
        session = runtime.Runtime(context)
        runtime.CURRENT = session
        runtime.PENDING = True
        try:
            session.configure()
            result = bpy.ops.wm.xr_session_toggle('INVOKE_DEFAULT')
            if 'CANCELLED' in result:
                raise RuntimeError('OpenXR did not start; check your active runtime')
            if runtime.START_ERROR:
                raise RuntimeError(runtime.START_ERROR)
            session.timer=context.window_manager.event_timer_add(1/30,window=context.window)
            context.window_manager.modal_handler_add(self)
            context.scene.blender_xr.status='Connecting to OpenXR'
            return {'RUNNING_MODAL'}
        except Exception as exc:
            self.report({'ERROR'},str(exc))
            context.scene.blender_xr.status=str(exc)
            if bpy.types.XrSessionState.is_running(context):
                bpy.ops.wm.xr_session_toggle()
            session.cleanup(context)
            runtime.CURRENT=None
            return {'CANCELLED'}
        finally:
            runtime.PENDING=False

    def modal(self,context,event):
        session=runtime.CURRENT
        if session is None:
            return {'CANCELLED'}
        if event.type=='ESC' and event.value=='PRESS':
            session.request_stop=True
        if event.type=='TIMER' and runtime.timer_due(session):
            try:
                if session.area.type!='VIEW_3D':
                    session.request_stop=True
                if not session.request_stop:
                    with context.temp_override(window=session.window,area=session.area,region=session.region):
                        session.context=bpy.context
                        session.tick(bpy.context)
                session.settings.status=session.status
                session.area.tag_redraw()
            except ValueError as exc:
                session.cancel_work()
                session.status=str(exc).upper()
                session.settings.status=str(exc)
            except Exception as exc:
                session.error=str(exc)
                session.request_stop=True
        if session.request_stop:
            if bpy.types.XrSessionState.is_running(context):
                bpy.ops.wm.xr_session_toggle()
            session.cleanup(context)
            runtime.CURRENT=None
            session.settings.status=session.error or 'VR stopped'
            if session.error:
                self.report({'ERROR'},session.error)
            return {'FINISHED'}
        if session.transaction or session.grab or session.air_grab or session.axis_move:
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}


class BXR_OT_stop(bpy.types.Operator):
    bl_idname='blender_xr.stop'
    bl_label='Stop VR'
    def execute(self,context):
        if runtime.CURRENT:
            runtime.CURRENT.request_stop=True
        return {'FINISHED'}


class BXR_OT_save(bpy.types.Operator):
    bl_idname = 'blender_xr.save'
    bl_label = 'Save Blend'
    bl_description = 'Save the current project, or create a timestamped project if unsaved'

    @classmethod
    def poll(cls, context):
        session = runtime.CURRENT
        return not session or not (session.transaction or session.grab or session.air_grab or session.axis_move)

    def execute(self, context):
        try:
            if runtime.CURRENT:
                runtime.CURRENT.command(context,'SAVE')
                path = context.scene.blender_xr.save_path
            else:
                path = project.save(context)
                context.scene.blender_xr.status = 'Saved: ' + str(path)
            self.report({'INFO'},'Saved: ' + str(path))
            return {'FINISHED'}
        except ValueError as exc:
            self.report({'ERROR'},str(exc))
            context.scene.blender_xr.status = str(exc)
            return {'CANCELLED'}


class BXR_OT_tool(bpy.types.Operator):
    bl_idname='blender_xr.tool'
    bl_label='Apply Mesh XR Tool'
    bl_options={'REGISTER','UNDO'}
    tool: EnumProperty(items=[(t,t.title(),'') for t in ('EXTRUDE','BEVEL','INSET')])
    amount: FloatProperty(default=0.03)
    def execute(self,context):
        if runtime.CURRENT:
            self.report({'ERROR'},'Use the controller menu while VR is running')
            return {'CANCELLED'}
        try:
            mesh.apply_tool(context.active_object,self.tool,self.amount,
                            context.scene.blender_xr.bevel_segments)
            statistics.invalidate()
            return {'FINISHED'}
        except ValueError as exc:
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}


class BXR_OT_apply_color(bpy.types.Operator):
    bl_idname='blender_xr.apply_color'
    bl_label='Apply Material Color'
    bl_description='Apply the hue-wheel color to the active object or selected Edit Mode faces'
    bl_options={'REGISTER','UNDO'}

    def execute(self,context):
        try:
            obj=context.view_layer.objects.active
            settings=context.scene.blender_xr
            face_count=materials.selected_face_count(obj) if obj and obj.mode=='EDIT' else 0
            material=v052.apply_object_color(obj,settings.object_color)
            statistics.invalidate()
            if face_count:
                status.set_status(settings,status.material_assigned(material.name,face_count))
            else:
                status.set_status(settings,'Color applied: '+material.name)
            return {'FINISHED'}
        except ValueError as exc:
            self.report({'ERROR'},str(exc))
            status.set_status(context.scene.blender_xr,str(exc))
            return {'CANCELLED'}


class BXR_OT_shade(bpy.types.Operator):
    bl_idname='blender_xr.shade'
    bl_label='Shade Mesh XR Object'
    bl_description='Set all faces on the active mesh to smooth or flat shading'
    bl_options={'REGISTER','UNDO'}
    mode: EnumProperty(items=[('SMOOTH','Smooth','Shade faces smooth'),
                             ('FLAT','Flat','Shade faces flat')])

    def execute(self,context):
        try:
            count=v052.set_shading(context.view_layer.objects.active,self.mode=='SMOOTH')
            status.set_status(context.scene.blender_xr,('Smooth' if self.mode=='SMOOTH' else 'Flat')+' shading: '+str(count)+' faces')
            return {'FINISHED'}
        except ValueError as exc:
            self.report({'ERROR'},str(exc))
            status.set_status(context.scene.blender_xr,str(exc))
            return {'CANCELLED'}


class BXR_OT_bridge_command(bpy.types.Operator):
    bl_idname = 'blender_xr.bridge_command'
    bl_label = 'Copy Hand Bridge Command'
    def execute(self, context):
        import os
        import shlex
        import subprocess
        from pathlib import Path
        session = runtime.CURRENT
        if not session or not session.bridge:
            return {'CANCELLED'}
        arguments = [('py' if os.name == 'nt' else 'python3'),
                     str(Path(__file__).with_name('steamvr_hand_bridge.py')),
                     '--key', session.bridge.key, '--port', str(session.bridge.port)]
        context.window_manager.clipboard = (subprocess.list2cmdline(arguments)
                                           if os.name == 'nt' else shlex.join(arguments))
        self.report({'INFO'}, 'Paste into a terminal; the bundled OpenVR wheel will be used')
        return {'FINISHED'}


def draw_view_menu(self, context):
    """Keep a native Blender desktop launch entry available outside the sidebar."""
    active=runtime.CURRENT is not None
    self.layout.separator()
    self.layout.operator('blender_xr.stop' if active else 'blender_xr.session',
                         text='Stop Mesh XR' if active else 'Start Mesh XR',
                         icon='PAUSE' if active else 'PLAY')


class BXR_PT_panel(bpy.types.Panel):
    bl_label='Mesh XR v'+VERSION_TEXT
    bl_idname='BXR_PT_panel'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='Mesh XR'

    def draw(self,context):
        layout=self.layout
        settings=context.scene.blender_xr
        preferences.ensure(settings, context)
        active=runtime.CURRENT is not None

        session_box=layout.box()
        session_box.label(text='VR Session',icon='XRAY')
        hand=session_box.row(align=True)
        hand.enabled=not active
        hand.prop(settings,'dominant_hand',expand=True)
        session_box.label(text='Menu stays on the other hand',icon='HAND')
        session_box.operator('blender_xr.stop' if active else 'blender_xr.session',
                             text='Stop VR' if active else 'Start VR',
                             icon='PAUSE' if active else 'PLAY')
        for line in textwrap.wrap(settings.status,44):
            session_box.label(text=line,icon='INFO' if line==settings.status else 'NONE')

        # Blender exposes the active XR compositor mirror on each 3D View.
        # Keep this as a display-only toggle: it must never start/stop the XR session.
        view_box=layout.box()
        view_box.label(text='PC View Mode',icon='WINDOW')
        view_space=context.space_data
        if hasattr(view_space,'mirror_xr_session'):
            mirror_row=view_box.row(align=True)
            mirror_row.enabled=active and bpy.types.XrSessionState.is_running(context)
            mirror_row.prop(view_space,'mirror_xr_session',
                            text='Show VR View on PC',toggle=True,icon='XRAY')
            if active and bpy.types.XrSessionState.is_running(context):
                view_box.label(text='Off: normal desktop view  |  On: live headset mirror')
            else:
                view_box.label(text='Start VR to enable the live headset mirror',icon='INFO')
        else:
            view_box.label(text='This Blender build does not expose XR view mirroring',icon='ERROR')

        setup=layout.box()
        setup.label(text='Controller Setup',icon='SETTINGS')
        col=setup.column(align=True)
        col.enabled=not active
        col.prop(settings,'controller_family')
        col.prop(settings,'input_source')
        if settings.input_source=='CONTROLLERS':
            col.prop(settings,'finger_touch')
        else:
            col.prop(settings,'bridge_port')
            col.label(text='SteamVR skeletal input required')
            if active and runtime.CURRENT.bridge:
                setup.operator('blender_xr.bridge_command',text='Copy Hand Bridge Command',icon='COPYDOWN')

        modeling=layout.box()
        modeling.label(text='Modeling',icon='MESH_CUBE')
        grid=modeling.grid_flow(columns=2,align=True)
        grid.prop(settings,'step')
        grid.prop(settings,'precision_mode',text='Precision Snap',toggle=True,icon='SNAP_ON')
        grid.prop(settings,'bevel_segments')
        grid.prop(settings,'primitive_size')
        grid.prop(settings,'placement_distance')
        modeling.label(text='Vertex / edge / face editing',icon='MODIFIER')

        appearance=layout.box()
        appearance.label(text='Materials',icon='MATERIAL')
        active_obj=context.view_layer.objects.active
        material_name,slot,total=materials.active_material_summary(active_obj)
        if active_obj and active_obj.type=='MESH':
            if total:
                appearance.label(text='Material: '+material_name+'   Slot '+str(slot)+'/'+str(total))
            else:
                appearance.label(text='Material: None')
            if active_obj.mode=='EDIT':
                selected_faces=materials.selected_face_count(active_obj)
                appearance.label(text='Selected faces: '+str(selected_faces))
        appearance.prop(settings,'object_color',text='Color')
        appearance.label(text='Click the color swatch for the hue wheel')
        button_text='Assign to Selected Faces' if active_obj and active_obj.type=='MESH' and active_obj.mode=='EDIT' else 'Apply to Object'
        appearance.operator('blender_xr.apply_color',text=button_text,icon='COLOR')
        shade=appearance.row(align=True)
        smooth=shade.operator('blender_xr.shade',text='Shade Smooth',icon='SHADING_RENDERED')
        smooth.mode='SMOOTH'
        flat=shade.operator('blender_xr.shade',text='Shade Flat',icon='SHADING_SOLID')
        flat.mode='FLAT'
        appearance.label(text='Advanced material, texture and UV tools are in the panels below.')

        statistics_box=layout.box()
        statistics_box.prop(settings,'show_statistics',text='Scene Statistics',toggle=True,icon='INFO')
        if settings.show_statistics:
            stats=statistics.scene_stats(context)
            row=statistics_box.row(align=True)
            row.label(text='Objects: '+str(stats['objects']))
            row.label(text='Selected: '+str(stats['selected']))
            row=statistics_box.row(align=True)
            row.label(text='Meshes: '+str(stats['meshes']))
            row.label(text='Materials: '+str(stats['materials']))
            row=statistics_box.row(align=True)
            row.label(text='Verts: '+str(stats['vertices']))
            row.label(text='Edges: '+str(stats['edges']))
            row=statistics_box.row(align=True)
            row.label(text='Faces: '+str(stats['faces']))
            row.label(text='Triangles: '+str(stats['triangles']))
            if stats['active']:
                current=stats['active']
                statistics_box.separator()
                statistics_box.label(text='Active: '+current['name'],icon='OBJECT_DATA')
                statistics_box.label(text='V '+str(current['vertices'])+'  E '+str(current['edges'])+
                                          '  F '+str(current['faces'])+'  T '+str(current['triangles']))

        movement=layout.box()
        movement.label(text='Movement',icon='ORIENTATION_VIEW')
        movement.prop(settings,'move_speed')
        row=movement.row(align=True)
        row.prop(settings,'fly_mode',toggle=True)
        row.prop(settings,'fast_flight',toggle=True)
        movement.prop(settings,'turn_mode',expand=True)
        movement.prop(settings,'turn_angle' if settings.turn_mode=='SNAP' else 'turn_speed')
        movement.prop(settings,'grab_air')

        project_box=layout.box()
        project_box.label(text='Project',icon='FILE_BLEND')
        project_box.prop(settings,'save_path')
        project_box.operator('blender_xr.save',icon='FILE_TICK')

        help_box=layout.box()
        help_box.label(text='Quick Controls',icon='QUESTION')
        help_box.label(text='Trigger: select / use tool')
        help_box.label(text='Grip + trigger: add/remove selection')
        help_box.label(text='Grip: grab object or empty space')
        help_box.label(text='Left stick: move  |  Right stick: turn / height')
        help_box.label(text='Other trigger: menu / cancel')


@persistent
def load_pre(*_args):
    preferences.reset_restore_state()
    statistics.invalidate()
    if runtime.CURRENT:
        session=runtime.CURRENT
        if bpy.types.XrSessionState.is_running(bpy.context):
            bpy.ops.wm.xr_session_toggle()
        session.cleanup(bpy.context)
        runtime.CURRENT=None


CLASSES=(preferences.BXR_Preferences,BXR_Settings,BXR_OT_session,BXR_OT_stop,BXR_OT_save,BXR_OT_tool,
         BXR_OT_apply_color,BXR_OT_shade,BXR_OT_bridge_command,BXR_PT_panel) + material_uv.CLASSES + v075_features.CLASSES

def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.blender_xr=PointerProperty(type=BXR_Settings)
    bpy.types.VIEW3D_MT_view.append(draw_view_menu)
    bpy.app.handlers.xr_session_start_pre.append(runtime.session_pre)
    bpy.app.handlers.load_pre.append(load_pre)


def unregister():
    load_pre()
    try:
        bpy.types.VIEW3D_MT_view.remove(draw_view_menu)
    except (AttributeError, ValueError):
        pass
    for handlers,callback in [(bpy.app.handlers.xr_session_start_pre,runtime.session_pre),
                              (bpy.app.handlers.load_pre,load_pre)]:
        if callback in handlers:
            handlers.remove(callback)
    del bpy.types.Scene.blender_xr
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
