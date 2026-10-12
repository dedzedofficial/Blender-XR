"""v0.5.6 selected-scale, edit undo and HSL VR color regression checks."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector
import blender_xr
from blender_xr import drawing, materials, mesh, runtime, v056, version


def clear_selection(bm):
    for face in bm.faces:
        face.select_set(False)
    for edge in bm.edges:
        edge.select_set(False)
    for vert in bm.verts:
        vert.select_set(False)


blender_xr.register()
session=None
bm=None
tx=None
try:
    assert blender_xr.bl_info['version'] == version.VERSION
    assert version.VERSION >= (0, 5, 6)
    assert drawing.version.DISPLAY_VERSION == version.DISPLAY_VERSION
    assert 'MATERIAL_MENU' in {action for _label, action in drawing.BUTTONS}
    assert {'MOVE_EDIT', 'SCALE_EDIT', 'MATERIAL_MENU', 'UNDO'} <= {action for _label, action in drawing.EDIT_BUTTONS}
    assert 'REDO' in {action for _label, action in drawing.EDIT_MORE_BUTTONS}
    assert hasattr(drawing, 'MATERIAL_BUTTONS')
    assert hasattr(drawing, 'MATERIAL_ADJUST_BUTTONS')
    assert {'COLOR_RED','COLOR_ORANGE','COLOR_YELLOW','COLOR_GREEN','COLOR_CYAN',
            'COLOR_BLUE','COLOR_PURPLE','COLOR_PINK','COLOR_PICK','COLOR_APPLY'} <= {
                action for _label, action in drawing.MATERIAL_BUTTONS}
    assert set(v056.SLIDER_ACTIONS) == {
        'COLOR_HUE_SLIDER','COLOR_SAT_SLIDER','COLOR_LIGHT_SLIDER'}

    # HSL conversion covers the full range and keeps alpha.
    cyan=materials.color_from_hsl(0.5,1.0,0.5,0.75)
    assert materials.colors_match(cyan,(0.0,1.0,1.0,0.75))
    h,s,l=materials.color_hsl(cyan)
    assert abs(h-0.5)<1e-6 and abs(s-1.0)<1e-6 and abs(l-0.5)<1e-6

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_cube_add()
    obj=bpy.context.object

    session=runtime.Runtime.__new__(runtime.Runtime)
    session.transaction=None;session.grab=None;session.axis_move=None;session.air_grab=None
    session.history=mesh.History();session.tool='SELECT';session.select_mode='FACE';session.status=''
    session.settings=bpy.context.scene.blender_xr
    session.menu=drawing.Menu()

    # Real pointer hit on the full-width Hue slider gives a normalized value.
    session.menu.page='MATERIAL_ADJUST'
    session.menu.position(Vector((0,0,0)),Vector((0,-1,0.25)),1.0)
    target=session.menu.world(v056.SLIDER_X+v056.SLIDER_W*0.25,0.117+0.02)
    action,_point=session.menu.hit(target+session.menu.normal,-session.menu.normal)
    assert action=='COLOR_HUE_SLIDER'
    assert abs(session.menu.slider_value-0.25)<0.01

    # Legacy direct COLOR_MENU command remains valid for compatibility even
    # though the visible v0.6 top-level button now opens the Materials hub.
    session.menu.page='TOOLS'
    session.command(bpy.context,'COLOR_MENU')
    assert session.menu.page=='MATERIAL_ADJUST' and session.color_return_page=='TOOLS'
    session.menu.slider_value=0.5; session.command(bpy.context,'COLOR_HUE_SLIDER')
    session.menu.slider_value=1.0; session.command(bpy.context,'COLOR_SAT_SLIDER')
    session.menu.slider_value=0.5; session.command(bpy.context,'COLOR_LIGHT_SLIDER')
    assert materials.colors_match(session.settings.object_color,(0.0,1.0,1.0,1.0))
    assert materials.hsl_summary(session.color_hsl,is_hsl=True).startswith('H180 S100 L50')
    # White/black change lightness without destroying the chosen hue/saturation.
    session.command(bpy.context,'COLOR_WHITE')
    assert materials.colors_match(session.settings.object_color,(1,1,1,1))
    session.menu.slider_value=0.5; session.command(bpy.context,'COLOR_LIGHT_SLIDER')
    assert materials.colors_match(session.settings.object_color,(0.0,1.0,1.0,1.0))
    session.command(bpy.context,'COLOR_APPLY')
    assert materials.colors_match(materials.material_color(obj.active_material),(0.0,1.0,1.0,1.0))
    materials.set_material_color(obj.active_material,(0.2,0.4,0.6,1.0))
    session.command(bpy.context,'COLOR_PICK')
    assert materials.colors_match(session.settings.object_color,(0.2,0.4,0.6,1.0))
    session.command(bpy.context,'COLOR_PALETTE')
    assert session.menu.page=='MATERIALS'
    session.command(bpy.context,'BACK')
    assert session.menu.page=='MATERIAL_ADJUST'
    session.command(bpy.context,'BACK')
    assert session.menu.page=='TOOLS'

    # Edit SCALE means selected geometry only, not object scale / whole-object scale.
    bpy.ops.object.mode_set(mode='EDIT')
    mesh.set_selection_mode(bpy.context,'VERT')
    session.select_mode='VERT'
    bm=mesh.editable(obj);bm.verts.ensure_lookup_table();clear_selection(bm)
    bm.verts[0].select_set(True);bm.verts[1].select_set(True);mesh.update(obj)
    before=[v.co.copy() for v in mesh.editable(obj).verts]
    object_scale=tuple(obj.scale)
    session.command(bpy.context,'SCALE_EDIT')
    assert session.tool=='SCALE_FACE' and 'SELECTED' in session.status
    tx=mesh.Transaction(obj,session.tool,'VERT')
    tx.preview(0.5)
    after=[v.co.copy() for v in mesh.editable(obj).verts]
    assert any((after[i]-before[i]).length>1e-6 for i in (0,1))
    assert all((after[i]-before[i]).length<1e-6 for i in range(2,len(before)))
    assert tuple(obj.scale)==object_scale
    tx.cancel(); tx=None

    # Different faces can keep different colors; the latest assignment is independently undoable.
    mesh.set_selection_mode(bpy.context,'FACE')
    session.select_mode='FACE';session.tool='SELECT'
    bm=mesh.editable(obj);bm.faces.ensure_lookup_table();clear_selection(bm)
    face0,face1=bm.faces[0],bm.faces[1]
    face0.select_set(True);mesh.update(obj)
    old_slot0=mesh.editable(obj).faces[0].material_index
    session.menu.page='EDIT'
    session.command(bpy.context,'COLOR_MENU')
    assert session.menu.page=='MATERIAL_ADJUST' and session.color_return_page=='EDIT'
    snapshots_before={m.name for m in bpy.data.meshes if m.name.startswith('.BlenderXR_Snapshot')}
    session.command(bpy.context,'COLOR_RED')
    session.command(bpy.context,'COLOR_APPLY')
    bm=mesh.editable(obj);bm.faces.ensure_lookup_table()
    red_slot=bm.faces[0].material_index
    assert red_slot!=old_slot0
    assert materials.colors_match(materials.material_color(obj.material_slots[red_slot].material),
                                  materials.PRESET_COLORS['COLOR_RED'])

    clear_selection(bm);bm.faces[1].select_set(True);mesh.update(obj)
    old_slot1=mesh.editable(obj).faces[1].material_index
    session.command(bpy.context,'COLOR_BLUE')
    session.command(bpy.context,'COLOR_APPLY')
    bm=mesh.editable(obj);bm.faces.ensure_lookup_table()
    blue_slot=bm.faces[1].material_index
    assert blue_slot!=red_slot
    assert bm.faces[0].material_index==red_slot
    assert materials.colors_match(materials.material_color(obj.material_slots[blue_slot].material),
                                  materials.PRESET_COLORS['COLOR_BLUE'])
    assert session.history.undo[-1][0]=='FACE_MATERIAL'
    assert {m.name for m in bpy.data.meshes if m.name.startswith('.BlenderXR_Snapshot')}==snapshots_before

    # Re-applying an unchanged face color should not waste a history slot.
    history_count=len(session.history.undo)
    session.command(bpy.context,'COLOR_APPLY')
    assert len(session.history.undo)==history_count

    assert session.history.step(True)
    bm=mesh.editable(obj);bm.faces.ensure_lookup_table()
    assert bm.faces[1].material_index==old_slot1
    assert bm.faces[0].material_index==red_slot
    assert session.history.step(False)
    bm=mesh.editable(obj);bm.faces.ensure_lookup_table()
    assert bm.faces[1].material_index==blue_slot
    session.settings.object_color=(0.0,0.0,0.0,1.0)
    session.command(bpy.context,'COLOR_PICK')
    assert materials.colors_match(session.settings.object_color,
                                  materials.material_color(obj.material_slots[blue_slot].material))
    session.command(bpy.context,'BACK')
    assert session.menu.page=='EDIT'

    session.history.clear()
    assert {m.name for m in bpy.data.meshes if m.name.startswith('.BlenderXR_Snapshot')}==snapshots_before
    print('PASS v0.5.6 feature suite under XR Mesh '+version.DISPLAY_VERSION)
finally:
    # Release Python references to edit BMesh/RNA data before unregister removes
    # Scene.blender_xr. Blender 4.2 can crash at process shutdown if a test keeps
    # a stale PropertyGroup reference alive after its RNA property is unregistered.
    bm=None
    tx=None
    if session is not None:
        session.history.clear()
        session.settings=None
        session.menu=None
        session=None
    if bpy.context.object and bpy.context.object.mode=='EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')
    blender_xr.unregister()
