"""v0.5.6 selected-scale, edit undo, VR colors and version regression checks."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector
import blender_xr
from blender_xr import drawing, materials, mesh, runtime, version


def clear_selection(bm):
    for face in bm.faces:
        face.select_set(False)
    for edge in bm.edges:
        edge.select_set(False)
    for vert in bm.verts:
        vert.select_set(False)


blender_xr.register()
try:
    assert version.VERSION == (0, 5, 6)
    assert version.DISPLAY_VERSION == 'V0.5.6'
    assert getattr(drawing.Menu, '_v056_patched', False)
    assert 'COLOR_MENU' in {action for _label, action in drawing.BUTTONS}
    assert {'SCALE_EDIT', 'COLOR_MENU', 'UNDO'} <= {action for _label, action in drawing.EDIT_BUTTONS}
    assert 'REDO' in {action for _label, action in drawing.EDIT_MORE_BUTTONS}
    assert hasattr(drawing, 'MATERIAL_BUTTONS')

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_cube_add()
    obj=bpy.context.object

    session=runtime.Runtime.__new__(runtime.Runtime)
    session.transaction=None;session.grab=None;session.axis_move=None;session.air_grab=None
    session.history=mesh.History();session.tool='SELECT';session.select_mode='FACE';session.status=''
    session.settings=bpy.context.scene.blender_xr
    session.menu=NS(page='TOOLS')

    # Object-mode color menu can adjust, apply and pick the active material color.
    original=tuple(session.settings.object_color)
    session.command(bpy.context,'COLOR_MENU')
    assert session.menu.page=='MATERIALS' and session.color_return_page=='TOOLS'
    session.command(bpy.context,'COLOR_HUE_PLUS')
    assert tuple(session.settings.object_color)!=original
    session.command(bpy.context,'COLOR_WHITE')
    assert tuple(session.settings.object_color)==(1.0,1.0,1.0,1.0)
    session.command(bpy.context,'COLOR_APPLY')
    assert materials.colors_match(materials.material_color(obj.active_material),(1,1,1,1))
    materials.set_material_color(obj.active_material,(0.2,0.4,0.6,1.0))
    session.command(bpy.context,'COLOR_PICK')
    assert materials.colors_match(session.settings.object_color,(0.2,0.4,0.6,1.0))
    session.command(bpy.context,'BACK')
    assert session.menu.page=='TOOLS'

    # Edit SCALE means selected geometry only, not object scale / whole-object scale.
    bpy.ops.object.mode_set(mode='EDIT')
    mesh.set_selection_mode(bpy.context,'VERT')
    session.select_mode='VERT'
    bm=mesh.editable(obj);bm.verts.ensure_lookup_table();clear_selection(bm)
    bm.verts[0].select_set(True);bm.verts[1].select_set(True);mesh.update(obj)
    before=[v.co.copy() for v in mesh.editable(obj).verts]
    session.command(bpy.context,'SCALE_EDIT')
    assert session.tool=='SCALE_FACE'
    tx=mesh.Transaction(obj,session.tool,'VERT')
    tx.preview(0.5)
    after=[v.co.copy() for v in mesh.editable(obj).verts]
    assert any((after[i]-before[i]).length>1e-6 for i in (0,1))
    assert all((after[i]-before[i]).length<1e-6 for i in range(2,len(before)))
    tx.cancel()

    # VR colors in Edit Mode apply only to selected faces and PICK reads them back.
    mesh.set_selection_mode(bpy.context,'FACE')
    session.select_mode='FACE';session.tool='SELECT'
    bm=mesh.editable(obj);bm.faces.ensure_lookup_table();clear_selection(bm)
    bm.faces[0].select_set(True);mesh.update(obj)
    session.menu.page='EDIT'
    session.command(bpy.context,'COLOR_MENU')
    assert session.color_return_page=='EDIT'
    session.settings.object_color=(0.9,0.2,0.1,1.0)
    session.command(bpy.context,'COLOR_APPLY')
    bm=mesh.editable(obj);bm.faces.ensure_lookup_table()
    slot=bm.faces[0].material_index
    assert materials.colors_match(materials.material_color(obj.material_slots[slot].material),(0.9,0.2,0.1,1.0))
    session.settings.object_color=(0.0,0.0,0.0,1.0)
    session.command(bpy.context,'COLOR_PICK')
    assert materials.colors_match(session.settings.object_color,(0.9,0.2,0.1,1.0))
    session.command(bpy.context,'BACK')
    assert session.menu.page=='EDIT'

    print('PASS v0.5.6 selected edit scale, edit undo menu, VR colors and shared version')
finally:
    if bpy.context.object and bpy.context.object.mode=='EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')
    blender_xr.unregister()
