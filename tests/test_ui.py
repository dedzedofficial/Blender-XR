"""Run with Blender --background --factory-startup --python tests/test_ui.py."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import blender_xr
from blender_xr import material_uv, preferences, runtime, version


class FakeLayout:
    def __init__(self):
        self.calls=[]

    def separator(self):
        self.calls.append(('separator',))

    def operator(self,identifier,text='',icon='NONE'):
        self.calls.append(('operator',identifier,text,icon))
        return NS()


def run():
    assert version.VERSION >= (0,6,4)
    assert blender_xr.bl_info['name']=='Mesh XR'
    assert blender_xr.bl_info['version']==version.VERSION
    assert blender_xr.BXR_PT_panel.bl_label=='Blender XR v'+version.VERSION_TEXT
    assert blender_xr.BXR_PT_panel.bl_category=='Blender XR'
    assert material_uv.BXR_PT_materials_v060.bl_category=='Blender XR'
    assert material_uv.BXR_PT_uv_v060.bl_category=='Blender XR'
    assert material_uv.BXR_OT_material_action.bl_label=='Mesh XR Material Action'
    assert material_uv.BXR_OT_uv_action.bl_label=='Mesh XR UV Action'
    assert getattr(runtime.Runtime,'_v056_patched',False), 'v0.5.6 runtime layer was not activated'
    assert getattr(runtime.Runtime,'_v060_patched',False), 'v0.6 material/UV runtime layer was not activated'
    assert hasattr(bpy.types,'VIEW3D_MT_view')

    blender_xr.register()
    assert hasattr(bpy.types.Scene,'blender_xr')
    assert hasattr(bpy.ops.blender_xr,'session')
    assert hasattr(bpy.ops.blender_xr,'material_action')
    assert hasattr(bpy.ops.blender_xr,'uv_action')

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

    # Blender 5.2 forbids writing Scene properties while a Panel.draw callback
    # is running. ensure() must swallow only that specific restriction and
    # finish the restore later through the timer callback.
    settings=bpy.context.scene.blender_xr
    key=int(bpy.context.scene.as_pointer())
    original_restore=preferences.restore
    preferences.reset_restore_state()
    try:
        def blocked(_settings,context=None):
            raise AttributeError(preferences._DRAW_WRITE_ERROR+': Scene')
        preferences.restore=blocked
        assert preferences.ensure(settings,bpy.context) is False
        assert key in preferences._PENDING_SCENES
        assert key not in preferences._RESTORED_SCENES

        preferences.restore=lambda _settings,context=None: True
        assert preferences._restore_pending() is None
        assert key not in preferences._PENDING_SCENES
        assert key in preferences._RESTORED_SCENES

        preferences.reset_restore_state()
        preferences.restore=lambda _settings,context=None: (_ for _ in ()).throw(AttributeError('unexpected restore error'))
        try:
            preferences.ensure(settings,bpy.context)
        except AttributeError as exc:
            assert 'unexpected restore error' in str(exc)
        else:
            raise AssertionError('Unexpected preference restore errors were hidden')
    finally:
        preferences.restore=original_restore
        preferences.reset_restore_state()

    blender_xr.unregister()
    assert not hasattr(bpy.types.Scene,'blender_xr')
    print('PASS Mesh XR '+version.DISPLAY_VERSION+' native launch UI, v0.6 runtime and deferred preference restore')


run()
