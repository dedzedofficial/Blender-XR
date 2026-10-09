"""Run in background Blender: real project save, snapshot omission and failure recovery."""
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
import bmesh
import blender_xr
from blender_xr import mesh, project, runtime, drawing

blender_xr.register()
try:
    assert bpy.app.version >= (4,2,0)
    with tempfile.TemporaryDirectory() as folder:
        directory=Path(folder)
        generated=project.choose_path('',directory=directory)
        assert generated.parent==directory and generated.suffix=='.blend'
        generated.write_bytes(b'KEEP')
        assert project.choose_path('',directory=directory)!=generated
        try:project.choose_path('',str(generated))
        except ValueError:pass
        else:raise AssertionError('Existing first-save target accepted')
        assert generated.read_bytes()==b'KEEP'
        try:project.choose_path('','relative.blend')
        except ValueError:pass
        else:raise AssertionError('Unsaved relative path accepted')
        requested=directory/'scene.blend'
        assert project.choose_path('',str(directory/'scene'))==requested
        bpy.context.scene.blender_xr.save_path=str(requested)
        obj=bpy.context.active_object
        history=mesh.History();history.push(mesh.creation_entry(obj))
        template_data=history.undo[0][3]
        template_data.use_fake_user=True
        bpy.ops.object.mode_set(mode='EDIT')
        bm=bmesh.from_edit_mesh(obj.data)
        for f in bm.faces:f.select_set(False)
        max(bm.faces,key=lambda f:f.normal.z).select_set(True)
        del bm
        bpy.context.tool_settings.mesh_select_mode=(False,False,True)
        tx=mesh.Transaction(obj,'EXTRUDE');tx.preview(.2);history.push(tx.finish())
        expected=len(bmesh.from_edit_mesh(obj.data).verts)
        saved=project.save(bpy.context,history)
        assert saved==requested and requested.is_file() and bpy.data.filepath==str(requested)
        assert history.undo[0][3]==template_data and template_data.use_fake_user
        assert len(history.undo)==2 and len(bmesh.from_edit_mesh(obj.data).verts)==expected
        # Inspect a copy to avoid Blender's refusal to load the currently open file.
        inspection=directory/'inspection.blend';shutil.copyfile(saved,inspection)
        with bpy.data.libraries.load(str(inspection)) as (source,target):
            assert not any(name.startswith('.BlenderXR') for name in source.objects)
            assert not any(name.startswith('.BlenderXR') for name in source.meshes)
            assert template_data.name not in source.meshes
            assert source.objects and obj.data.name in source.meshes
            target.meshes=[obj.data.name]
        loaded=target.meshes[0]
        assert len(loaded.vertices)==expected
        bpy.data.meshes.remove(loaded)
        assert history.step(True) and len(bmesh.from_edit_mesh(obj.data).verts)==8
        assert history.step(False) and len(bmesh.from_edit_mesh(obj.data).verts)==expected
        # Current filepath wins, so repeat Save updates the same project.
        bpy.context.scene.blender_xr.save_path=str(directory/'other.blend')
        assert project.save(bpy.context,history)==requested
        assert not (directory/'other.blend').exists()
        before=bpy.context.scene.blender_xr.save_path
        original_bpy=project.bpy
        def fail(**kwargs):raise RuntimeError('simulated disk write failure')
        try:
            project.bpy=NS(data=NS(filepath=str(requested)),ops=NS(wm=NS(save_as_mainfile=fail)))
            try:project.save(bpy.context,history)
            except ValueError as exc:assert 'Save failed' in str(exc)
            else:raise AssertionError('Failed save reported success')
        finally:project.bpy=original_bpy
        assert bpy.context.scene.blender_xr.save_path==before
        assert history.undo[0][3]==template_data and template_data.use_fake_user
        assert len(history.undo)==2
        session=runtime.Runtime.__new__(runtime.Runtime)
        session.transaction=NS();session.grab=session.air_grab=None
        try:session.command(bpy.context,'SAVE')
        except ValueError:pass
        else:raise AssertionError('Live preview allowed Save')
        assert any(action=='SAVE' for _,action in drawing.BUTTONS)
        assert any(action=='SAVE' for _,action in drawing.TRAVEL_BUTTONS)
        history.clear()
        bpy.ops.object.mode_set(mode='OBJECT')
        print('PASS real project save, edit geometry, snapshot omission, undo retention, collision guards and failure recovery')
finally:
    blender_xr.unregister()
