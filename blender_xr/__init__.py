# SPDX-License-Identifier: GPL-3.0-or-later
bl_info = {
    'name': 'Blender XR', 'author': 'Ded Zed', 'version': (0,3,0),
    'blender': (5,0,0), 'location': '3D View > Sidebar > Blender XR',
    'description': 'Free basic VR mesh editing with a hand-mounted menu',
    'category': '3D View',
}
import bpy
import textwrap
from bpy.props import EnumProperty, FloatProperty, IntProperty, PointerProperty
from bpy.app.handlers import persistent
from . import runtime, mesh, updater


class BXR_Settings(bpy.types.PropertyGroup):
    dominant_hand: EnumProperty(name='Dominant hand',items=[
        ('RIGHT','Right','Right edits, left holds the menu'),
        ('LEFT','Left','Left edits, right holds the menu')],default='RIGHT')
    step: FloatProperty(name='Tool distance',default=0.03,min=0.0001,max=10,
                        description='Initial tool amount in local mesh units')
    bevel_segments: IntProperty(name='Bevel segments',default=2,min=1,max=8)
    move_speed: FloatProperty(name='Navigation speed',default=1.0,min=0.1,max=5)
    status: bpy.props.StringProperty(default='Ready')


class BXR_OT_session(bpy.types.Operator):
    bl_idname = 'blender_xr.session'
    bl_label = 'Start VR'
    bl_description = 'Start Blender XR using the active OpenXR runtime'

    @classmethod
    def poll(cls,context):
        return context.area is not None and context.area.type=='VIEW_3D'

    def execute(self,context):
        if runtime.CURRENT:
            runtime.CURRENT.request_stop = True
            return {'FINISHED'}
        if context.window_manager.blender_xr_update.restart_required:
            self.report({'ERROR'},'Restart Blender to finish the installed update')
            return {'CANCELLED'}
        if not bpy.app.build_options.xr_openxr:
            self.report({'ERROR'},'This Blender build has no OpenXR support')
            return {'CANCELLED'}
        if bpy.app.version[:3] == (5,0,1):
            self.report({'ERROR'},'Blender 5.0.1 has a known VR crash. Use another Blender version.')
            return {'CANCELLED'}
        if bpy.types.XrSessionState.is_running(context):
            self.report({'ERROR'},'Stop the existing VR session before starting Blender XR')
            return {'CANCELLED'}
        if context.mode not in {'OBJECT','EDIT_MESH'}:
            self.report({'ERROR'},'Use object mode or mesh edit mode')
            return {'CANCELLED'}
        if len(context.objects_in_mode)>1:
            self.report({'ERROR'},'v0.3 supports editing one mesh at a time')
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
        if event.type=='TIMER' and event.timer==session.timer:
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
        # Avoid desktop topology edits/native undo invalidating a live preview.
        if session.transaction or session.grab:
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}


class BXR_OT_stop(bpy.types.Operator):
    bl_idname='blender_xr.stop'
    bl_label='Stop VR'
    def execute(self,context):
        if runtime.CURRENT:
            runtime.CURRENT.request_stop=True
        return {'FINISHED'}


class BXR_OT_tool(bpy.types.Operator):
    bl_idname='blender_xr.tool'
    bl_label='Apply Blender XR Tool'
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
            return {'FINISHED'}
        except ValueError as exc:
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}


class BXR_PT_panel(bpy.types.Panel):
    bl_label='Blender XR v0.3'
    bl_idname='BXR_PT_panel'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='Blender XR'
    def draw(self,context):
        layout=self.layout
        settings=context.scene.blender_xr
        active=runtime.CURRENT is not None
        row=layout.row()
        row.enabled=not active
        row.prop(settings,'dominant_hand',expand=True)
        layout.label(text='Menu on the other hand',icon='HAND')
        col=layout.column()
        col.enabled=not active
        col.prop(settings,'step')
        col.prop(settings,'bevel_segments')
        col.prop(settings,'move_speed')
        layout.operator('blender_xr.stop' if active else 'blender_xr.session',
                        text='Stop VR' if active else 'Start VR',icon='HIDE_OFF')
        for line in textwrap.wrap(settings.status,44):
            layout.label(text=line)
        box=layout.box()
        box.label(text='Point + trigger: select / use tool')
        box.label(text='Grip in MOVE: move / rotate object')
        box.label(text='Other trigger: menu / cancel')
        box.label(text='Other stick: move around')
        box.label(text='ESC: stop VR')
        updates=layout.box()
        updates.label(text='GitHub Updates',icon='FILE_REFRESH')
        update_settings=context.window_manager.blender_xr_update
        updates.prop(update_settings,'token')
        row=updates.row(align=True)
        row.enabled=not active and not update_settings.restart_required
        row.operator('blender_xr.update',text='Check').mode='CHECK'
        row.operator('blender_xr.update',text='Download & Install').mode='INSTALL'
        for line in textwrap.wrap(update_settings.status,44):
            updates.label(text=line)
        if update_settings.restart_required:
            updates.label(text='Restart Blender',icon='INFO')


@persistent
def load_pre(*_args):
    if runtime.CURRENT:
        session=runtime.CURRENT
        if bpy.types.XrSessionState.is_running(bpy.context):
            bpy.ops.wm.xr_session_toggle()
        session.cleanup(bpy.context)
        runtime.CURRENT=None


CLASSES=(BXR_Settings,BXR_OT_session,BXR_OT_stop,BXR_OT_tool,BXR_PT_panel)

def register():
    updater.register()
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.blender_xr=PointerProperty(type=BXR_Settings)
    bpy.app.handlers.xr_session_start_pre.append(runtime.session_pre)
    bpy.app.handlers.load_pre.append(load_pre)


def unregister():
    load_pre()
    updater.unregister()
    for handlers,callback in [(bpy.app.handlers.xr_session_start_pre,runtime.session_pre),
                              (bpy.app.handlers.load_pre,load_pre)]:
        if callback in handlers:
            handlers.remove(callback)
    del bpy.types.Scene.blender_xr
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
