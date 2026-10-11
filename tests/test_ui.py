"""Run with Blender --background --factory-startup --python tests/test_ui.py."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import blender_xr
from blender_xr import runtime


class FakeLayout:
    def __init__(self):
        self.calls=[]

    def separator(self):
        self.calls.append(('separator',))

    def operator(self,identifier,text='',icon='NONE'):
        self.calls.append(('operator',identifier,text,icon))
        return NS()


def run():
    assert blender_xr.bl_info['version']==(0,5,5)
    assert blender_xr.BXR_PT_panel.bl_label=='Blender XR v0.5.5'
    assert hasattr(bpy.types,'VIEW3D_MT_view')

    blender_xr.register()
    assert hasattr(bpy.types.Scene,'blender_xr')
    assert hasattr(bpy.ops.blender_xr,'session')

    layout=FakeLayout()
    blender_xr.draw_view_menu(NS(layout=layout),bpy.context)
    assert ('operator','blender_xr.session','Start Blender XR','PLAY') in layout.calls

    previous=runtime.CURRENT
    try:
        runtime.CURRENT=NS()
        layout=FakeLayout()
        blender_xr.draw_view_menu(NS(layout=layout),bpy.context)
        assert ('operator','blender_xr.stop','Stop Blender XR','PAUSE') in layout.calls
    finally:
        runtime.CURRENT=previous

    blender_xr.unregister()
    assert not hasattr(bpy.types.Scene,'blender_xr')
    print('PASS v0.5.5 native Blender launch UI')


run()
