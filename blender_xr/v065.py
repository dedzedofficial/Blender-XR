# SPDX-License-Identifier: GPL-3.0-or-later
"""v0.6.5 icon-first modeling UI, hover help, loop cut and object delete."""
import time
import bpy
import bmesh
import gpu
from mathutils import Vector
from . import drawing, menus, mesh

CORE_PAGES = {'TOOLS', 'EDIT', 'EDIT_MORE', 'MODE_SELECT', 'LOOP_CUT'}
TOOLTIP_DELAY = 0.5

TOOLTIPS = {
    'MODE_MENU': ('Mode', 'Switch Object / Edit Mode'),
    'MODE_OBJECT': ('Object Mode', 'Work with complete objects'),
    'MODE_EDIT': ('Edit Mode', 'Edit vertices, edges and faces'),
    'SELECT': ('Select', 'Point at geometry and press trigger'),
    'SELECT_VERT': ('Vertex Select', 'Select individual vertices'),
    'SELECT_EDGE': ('Edge Select', 'Select individual edges'),
    'SELECT_FACE': ('Face Select', 'Select individual faces'),
    'MOVE': ('Move', 'Move the selected object'),
    'MOVE_EDIT': ('Move Selection', 'Move selected mesh geometry'),
    'SCALE': ('Scale', 'Scale the selected object'),
    'SCALE_EDIT': ('Scale Selection', 'Scale selected mesh geometry'),
    'EXTRUDE': ('Extrude', 'Extrude selected mesh geometry'),
    'INSET': ('Inset Faces', 'Inset selected faces'),
    'BEVEL': ('Bevel', 'Bevel selected geometry'),
    'LOOP_CUT_MENU': ('Loop Cut', 'Cut through a connected quad edge ring'),
    'LOOP_CUT_LESS': ('Fewer Cuts', 'Reduce the loop cut count'),
    'LOOP_CUT_MORE': ('More Cuts', 'Increase the loop cut count'),
    'LOOP_POS_LEFT': ('Move Cut Left', 'Move a single cut toward one side'),
    'LOOP_POS_RIGHT': ('Move Cut Right', 'Move a single cut toward the other side'),
    'LOOP_CUT_APPLY': ('Apply Loop Cut', 'Create the previewed loop cut'),
    'DELETE_GEOM': ('Delete Geometry', 'Delete selected vertices, edges or faces'),
    'DELETE_OBJECT': ('Delete Object', 'Delete the active object; Undo restores it'),
    'MERGE': ('Merge', 'Merge selected vertices'),
    'SUBDIVIDE': ('Subdivide', 'Subdivide selected geometry'),
    'DUPLICATE': ('Duplicate', 'Duplicate selected geometry'),
    'RECALC': ('Recalculate Normals', 'Recalculate selected face normals'),
    'FLIP_NORMALS': ('Flip Normals', 'Flip selected face normals'),
    'ADD_MENU': ('Add Object', 'Open primitive creation tools'),
    'MATERIAL_MENU': ('Materials', 'Open materials, textures and UV tools'),
    'NAV_MENU': ('Travel', 'Open movement and turning controls'),
    'UNDO': ('Undo', 'Undo the last Mesh XR action'),
    'REDO': ('Redo', 'Redo the last undone Mesh XR action'),
    'SAVE': ('Save', 'Save the current Blend file'),
    'STOP': ('Stop VR', 'Stop the Mesh XR session'),
    'BACK': ('Back', 'Return to the previous menu'),
    'LESS': ('Smaller Step', 'Reduce modeling step size'),
    'MORE': ('Larger Step', 'Increase modeling step size'),
}


def _install_pages():
    # Empty labels make icons the primary UI language. Hover tooltips provide text help.
    menus.PAGES['TOOLS'] = (
        ('', 'MODE_MENU'), ('', 'SELECT'),
        ('', 'MOVE'), ('', 'SCALE'),
        ('', 'ADD_MENU'), ('', 'MATERIAL_MENU'),
        ('', 'NAV_MENU'), ('', 'UNDO'),
        ('', 'REDO'), ('', 'SAVE'),
        ('', 'DELETE_OBJECT'), ('', 'STOP'),
    )
    menus.PAGES['EDIT'] = (
        ('', 'MODE_MENU'), ('', 'SELECT'),
        ('', 'SELECT_VERT'), ('', 'SELECT_EDGE'),
        ('', 'SELECT_FACE'), ('', 'MOVE_EDIT'),
        ('', 'SCALE_EDIT'), ('', 'EXTRUDE'),
        ('', 'INSET'), ('', 'BEVEL'),
        ('', 'LOOP_CUT_MENU'), ('', 'EDIT_MORE'),
    )
    menus.PAGES['EDIT_MORE'] = (
        ('', 'DELETE_GEOM'), ('', 'MERGE'),
        ('', 'SUBDIVIDE'), ('', 'DUPLICATE'),
        ('', 'RECALC'), ('', 'FLIP_NORMALS'),
        ('', 'MATERIAL_MENU'), ('', 'UNDO'),
        ('', 'REDO'), ('', 'LESS'),
        ('', 'MORE'), ('', 'BACK'),
    )
    menus.PAGES['MODE_SELECT'] = (
        ('', 'MODE_OBJECT'), ('', 'MODE_EDIT'),
        ('', 'BACK'),
    )
    menus.PAGES['LOOP_CUT'] = (
        ('', 'LOOP_CUT_LESS'), ('', 'LOOP_CUT_MORE'),
        ('', 'LOOP_POS_LEFT'), ('', 'LOOP_POS_RIGHT'),
        ('', 'LOOP_CUT_APPLY'), ('', 'BACK'),
    )
    menus.TITLES['MODE_SELECT'] = 'MODE'
    menus.TITLES['LOOP_CUT'] = 'LOOP CUT'


def _line_icon(action, x, y, w, h):
    """Return simple 2D line pairs for familiar Blender-style pictograms."""
    cx, cy = x + w * .5, y + h * .5
    sx, sy = w * .28, h * .28
    p = []
    def line(a, b):
        p.extend((a, b))
    def box(scale=1.0):
        dx, dy = sx * scale, sy * scale
        a=(cx-dx,cy-dy); b=(cx+dx,cy-dy); c=(cx+dx,cy+dy); d=(cx-dx,cy+dy)
        line(a,b);line(b,c);line(c,d);line(d,a)
    if action in {'MODE_MENU','MODE_OBJECT'}:
        box(.82)
        line((cx+sx*.3,cy+sy*.9),(cx+sx*.75,cy+sy*.45))
        line((cx+sx*.75,cy+sy*.45),(cx+sx*.3,cy+sy*.1))
    elif action == 'MODE_EDIT':
        box(.82); line((cx-sx*.8,cy-sy*.8),(cx+sx*.8,cy+sy*.8))
    elif action in {'SELECT','SELECT_VERT'}:
        line((cx-sx*.7,cy+sy*.8),(cx+sx*.55,cy-sy*.2)); line((cx+sx*.55,cy-sy*.2),(cx,cy-sy*.15))
        line((cx,cy-sy*.15),(cx+sx*.25,cy-sy*.8))
    elif action == 'SELECT_EDGE':
        line((cx-sx,cy-sy*.65),(cx+sx,cy+sy*.65))
    elif action == 'SELECT_FACE':
        box(.72)
    elif action in {'MOVE','MOVE_EDIT'}:
        line((cx-sx,cy),(cx+sx,cy)); line((cx+sx,cy),(cx+sx*.55,cy+sy*.35)); line((cx+sx,cy),(cx+sx*.55,cy-sy*.35))
        line((cx,cy-sy),(cx,cy+sy)); line((cx,cy+sy),(cx-sx*.28,cy+sy*.55)); line((cx,cy+sy),(cx+sx*.28,cy+sy*.55))
    elif action in {'SCALE','SCALE_EDIT'}:
        box(.65); line((cx+sx*.2,cy+sy*.2),(cx+sx,cy+sy)); line((cx+sx,cy+sy),(cx+sx*.45,cy+sy)); line((cx+sx,cy+sy),(cx+sx,cy+sy*.45))
    elif action == 'EXTRUDE':
        box(.55); line((cx-sx*.55,cy+sy*.55),(cx-sx*.9,cy+sy*.9)); line((cx+sx*.55,cy+sy*.55),(cx+sx*.9,cy+sy*.9))
        line((cx-sx*.9,cy+sy*.9),(cx+sx*.9,cy+sy*.9))
    elif action == 'INSET':
        box(.9); box(.48)
    elif action == 'BEVEL':
        line((cx-sx,cy-sy),(cx+sx*.45,cy-sy)); line((cx+sx*.45,cy-sy),(cx+sx,cy-sy*.25)); line((cx+sx,cy-sy*.25),(cx+sx,cy+sy))
    elif action in {'LOOP_CUT_MENU','LOOP_CUT_APPLY'}:
        box(.9); line((cx,cy-sy*.9),(cx,cy+sy*.9)); line((cx-sx*.9,cy),(cx+sx*.9,cy))
    elif action in {'LOOP_CUT_LESS','LESS'}:
        line((cx-sx,cy),(cx+sx,cy))
    elif action in {'LOOP_CUT_MORE','MORE'}:
        line((cx-sx,cy),(cx+sx,cy)); line((cx,cy-sy),(cx,cy+sy))
    elif action == 'LOOP_POS_LEFT':
        line((cx+sx*.8,cy),(cx-sx*.8,cy)); line((cx-sx*.8,cy),(cx-sx*.25,cy+sy*.55)); line((cx-sx*.8,cy),(cx-sx*.25,cy-sy*.55))
    elif action == 'LOOP_POS_RIGHT':
        line((cx-sx*.8,cy),(cx+sx*.8,cy)); line((cx+sx*.8,cy),(cx+sx*.25,cy+sy*.55)); line((cx+sx*.8,cy),(cx+sx*.25,cy-sy*.55))
    elif action in {'DELETE_GEOM','DELETE_OBJECT'}:
        box(.55); line((cx-sx*.7,cy+sy*.7),(cx+sx*.7,cy+sy*.7)); line((cx-sx*.35,cy+sy),(cx+sx*.35,cy+sy))
    elif action == 'DUPLICATE':
        box(.62); cx2=cx-sx*.35; cy2=cy+sy*.35
        dx,dy=sx*.62,sy*.62; line((cx2-dx,cy2-dy),(cx2+dx,cy2-dy)); line((cx2-dx,cy2-dy),(cx2-dx,cy2+dy))
    elif action == 'MERGE':
        line((cx-sx,cy+sy),(cx,cy)); line((cx-sx,cy-sy),(cx,cy)); line((cx+sx,cy),(cx,cy))
    elif action == 'SUBDIVIDE':
        box(.9); line((cx,cy-sy*.9),(cx,cy+sy*.9)); line((cx-sx*.9,cy),(cx+sx*.9,cy))
    elif action in {'UNDO','REDO'}:
        direction = -1 if action == 'UNDO' else 1
        line((cx+direction*sx*.8,cy+sy*.55),(cx-direction*sx*.45,cy+sy*.55)); line((cx-direction*sx*.45,cy+sy*.55),(cx-direction*sx*.9,cy))
        line((cx-direction*sx*.9,cy),(cx-direction*sx*.45,cy-sy*.55))
    elif action == 'SAVE':
        box(.8); line((cx-sx*.45,cy+sy*.8),(cx+sx*.45,cy+sy*.8)); box(.25)
    elif action == 'STOP':
        box(.62)
    elif action == 'BACK':
        line((cx+sx*.8,cy),(cx-sx*.8,cy)); line((cx-sx*.8,cy),(cx-sx*.2,cy+sy*.6)); line((cx-sx*.8,cy),(cx-sx*.2,cy-sy*.6))
    elif action == 'OBJECT_ADVANCED':
        box(.82); line((cx-sx*.65,cy),(cx+sx*.65,cy)); line((cx,cy-sy*.65),(cx,cy+sy*.65))
    elif action == 'ADD_MENU':
        line((cx-sx,cy),(cx+sx,cy)); line((cx,cy-sy),(cx,cy+sy)); box(.35)
    elif action == 'MATERIAL_MENU':
        # diamond/sphere-like material mark
        line((cx,cy+sy),(cx+sx,cy)); line((cx+sx,cy),(cx,cy-sy)); line((cx,cy-sy),(cx-sx,cy)); line((cx-sx,cy),(cx,cy+sy))
    elif action == 'NAV_MENU':
        line((cx,cy+sy),(cx+sx*.55,cy-sy)); line((cx,cy+sy),(cx-sx*.55,cy-sy)); line((cx,cy+sy),(cx,cy-sy*.2))
    elif action in {'RECALC','FLIP_NORMALS'}:
        box(.65); line((cx,cy),(cx,cy+sy)); line((cx,cy+sy),(cx-sx*.3,cy+sy*.55)); line((cx,cy+sy),(cx+sx*.3,cy+sy*.55))
    else:
        box(.65)
    return p


def _draw_text(menu, shader, label, x, y, pixel=0.0021):
    points=[]
    for i,char in enumerate(label.upper()):
        for row,line in enumerate(drawing.FONT.get(char,drawing.FONT[' '])):
            for col,value in enumerate(line):
                if value=='1':
                    for px,py in drawing.rectangle_points(x+i*6*pixel+col*pixel,
                                                           y-row*pixel,pixel*.86,pixel*.86):
                        points.append(menu.world(px,py,0.0032))
    if points:
        drawing.draw_batch(shader,'TRIS',points,(0.94,0.98,1,1))


def _patch_menu_draw():
    if getattr(drawing.Menu, '_v065_icons', False):
        return
    original_draw = drawing.Menu.draw

    def draw(self, shader, tool, hover, step, status, settings=None, selection='', select_mode='FACE'):
        original_draw(self, shader, tool, hover, step, status, settings, selection, select_mode)
        if self.page not in CORE_PAGES or not self.ready or not self.visible:
            return
        mode_actions={'SELECT_VERT':'VERT','SELECT_EDGE':'EDGE','SELECT_FACE':'FACE'}
        tool_alias={'MOVE_FACE':'MOVE_EDIT','SCALE_FACE':'SCALE_EDIT'}
        for i,(_label,action) in enumerate(self.buttons):
            bx,by,w,h=drawing.button_rect(i)
            active=(action==tool or action==tool_alias.get(tool) or mode_actions.get(action)==select_mode)
            if action=='MODE_OBJECT':
                obj=bpy.context.view_layer.objects.active; active=bool(obj and obj.mode=='OBJECT')
            elif action=='MODE_EDIT':
                obj=bpy.context.view_layer.objects.active; active=bool(obj and obj.mode=='EDIT')
            color=(0.025,0.35,0.35,1) if active else (0.06,0.12,0.18,1)
            if action==hover: color=(0.12,0.42,0.55,1)
            drawing.draw_batch(shader,'TRIS',[self.world(px,py,0.0025) for px,py in drawing.rectangle_points(bx,by,w,h)],color)
            lines=_line_icon(action,bx,by,w,h)
            if lines:
                drawing.draw_batch(shader,'LINES',[self.world(px,py,0.0030) for px,py in lines],(0.88,0.95,1,1))
        tip=getattr(self,'tooltip_action',None)
        if tip and tip==hover and tip in TOOLTIPS:
            title,desc=TOOLTIPS[tip]
            try:
                index=next(i for i,(_l,a) in enumerate(self.buttons) if a==tip)
            except StopIteration:
                return
            bx,by,w,h=drawing.button_rect(index)
            # A dedicated strip above the panel prevents the tooltip from
            # covering controls, selection readouts or the controller ray.
            ty=0.247
            tw=0.37
            drawing.draw_batch(shader,'TRIS',[self.world(px,py,0.0045) for px,py in drawing.rectangle_points(-0.185,ty,tw,0.050)],(0.01,0.02,0.03,0.99))
            _draw_text(self,shader,title,-0.177,ty+0.037,0.0020)
            _draw_text(self,shader,desc[:39],-0.177,ty+0.017,0.0015)
    drawing.Menu.draw=draw
    drawing.Menu._v065_icons=True


def _ring_edges(obj):
    bm=mesh.editable(obj)
    selected=[e for e in bm.edges if e.is_valid and e.select and not e.hide]
    if len(selected) != 1:
        raise ValueError('Select exactly one edge for Loop Cut')
    start=selected[0]
    ring={start}
    queue=[start]
    while queue:
        edge=queue.pop()
        for face in edge.link_faces:
            if not face.is_valid or face.hide:
                continue
            if len(face.edges) != 4:
                raise ValueError('Loop Cut requires a continuous quad-only edge ring')
            opposite=[candidate for candidate in face.edges
                      if candidate.is_valid and candidate != edge and
                      not any(v in edge.verts for v in candidate.verts)]
            if len(opposite)!=1:
                continue
            candidate=opposite[0]
            if candidate not in ring:
                ring.add(candidate); queue.append(candidate)
    if len(ring)<2:
        raise ValueError('Loop Cut requires a continuous quad edge ring')
    return sorted(ring, key=lambda edge: edge.index)


def loop_preview(obj):
    edges=_ring_edges(obj)
    return [(obj.matrix_world@edge.verts[0].co.copy(),obj.matrix_world@edge.verts[1].co.copy())
            for edge in edges if edge.is_valid]


def loop_cut(obj,cuts=1,position=0.5):
    cuts=max(1,min(16,int(cuts)))
    position=max(0.05,min(0.95,float(position)))
    bm=mesh.editable(obj)
    edges=_ring_edges(obj)
    def operation():
        kwargs=dict(edges=edges,cuts=cuts,use_grid_fill=False)
        if cuts==1:
            kwargs['edge_percents']={edge:position for edge in edges if edge.is_valid}
        result=bmesh.ops.subdivide_edges(bm,**kwargs)
        for edge in bm.edges:
            if edge.is_valid: edge.select_set(False)
        for item in result.get('geom_inner',[]):
            if isinstance(item,bmesh.types.BMEdge) and item.is_valid:
                item.select_set(True)
    return mesh._snapshot_operation(obj,operation)


def _patch_delete_history():
    if getattr(mesh.History,'_v065_delete_history',False):
        return
    old_release=mesh.History.release
    old_step=mesh.History.step
    def release(entry):
        if entry[0]!='DELETE_OBJECT':
            return old_release(entry)
        template=entry[3]
        try:
            data=template.data
            if template.name in bpy.data.objects: bpy.data.objects.remove(template,do_unlink=True)
            if data and data.users==0 and data.name in bpy.data.meshes: bpy.data.meshes.remove(data)
        except ReferenceError:
            pass
    def step(self,backwards=True):
        source,dest=(self.undo,self.redo) if backwards else (self.redo,self.undo)
        if not source or source[-1][0]!='DELETE_OBJECT':
            return old_step(self,backwards)
        entry=source[-1]; name,data_name,template,collections=entry[1],entry[2],entry[3],entry[4]
        obj=bpy.data.objects.get(name)
        if backwards:
            if obj is not None: raise ValueError('Object name is already in use; restart VR')
            if bpy.context.mode!='OBJECT': raise ValueError('Switch to Object Mode before restoring an object')
            valid=[c for c in collections if c and c.name in bpy.data.collections]
            if not valid: raise ValueError('The original collection was removed')
            restored=template.copy(); restored.data=template.data.copy(); restored.name=name; restored.data.name=data_name
            for collection in valid: collection.objects.link(restored)
            for selected in bpy.context.selected_objects: selected.select_set(False)
            restored.select_set(True); bpy.context.view_layer.objects.active=restored
        else:
            if obj is None: raise ValueError('The restored object was removed outside Mesh XR')
            if obj.mode!='OBJECT': raise ValueError('Switch to Object Mode before deleting the object again')
            data=obj.data; bpy.data.objects.remove(obj,do_unlink=True)
            if data and data.users==0 and data.name in bpy.data.meshes: bpy.data.meshes.remove(data)
        dest.append(source.pop()); return True
    mesh.History.release=staticmethod(release)
    mesh.History.step=step
    mesh.History._v065_delete_history=True


def delete_object_entry(obj):
    if not obj or obj.type!='MESH': raise ValueError('Select a mesh object first')
    if obj.mode!='OBJECT': raise ValueError('Switch to Object Mode before deleting an object')
    if obj.library or obj.data.library: raise ValueError('Linked library objects cannot be deleted by Mesh XR')
    collections=tuple(obj.users_collection)
    template=obj.copy(); template.data=obj.data.copy()
    name,data_name=obj.name,obj.data.name
    data=obj.data
    bpy.data.objects.remove(obj,do_unlink=True)
    if data.users==0: bpy.data.meshes.remove(data)
    return ('DELETE_OBJECT',name,data_name,template,collections)


def _patch_world_draw():
    if getattr(drawing,'_v065_loop_preview',False): return
    original=drawing.draw
    def draw(runtime):
        original(runtime)
        preview=getattr(runtime,'loop_preview',None)
        if not runtime.active or not preview: return
        shader=gpu.shader.from_builtin('UNIFORM_COLOR')
        points=[]
        for a,b in preview: points.extend((a,b))
        drawing.draw_batch(shader,'LINES',points,(1.0,0.72,0.08,1.0))
    drawing.draw=draw
    drawing._v065_loop_preview=True


def patch(Runtime):
    if getattr(Runtime,'_v065_patched',False): return
    _install_pages(); _patch_menu_draw(); _patch_delete_history(); _patch_world_draw()
    original_init=Runtime.__init__
    original_tick=Runtime.tick
    original_command=Runtime.command

    def init(self,*args,**kwargs):
        original_init(self,*args,**kwargs)
        self.hover_started=0.0; self.hover_previous=None
        self.loop_cuts=1; self.loop_position=0.5; self.loop_preview=None

    def command(self,context,action):
        if action=='MODE_MENU':
            self.menu.page='MODE_SELECT'; self.status='CHOOSE MODE'; return
        if action in {'MODE_OBJECT','MODE_EDIT'}:
            obj=context.view_layer.objects.active
            if not obj or obj.type!='MESH': raise ValueError('Select a mesh object')
            want_edit=action=='MODE_EDIT'
            if want_edit and obj.mode!='EDIT': original_command(self,context,'MODE')
            elif not want_edit and obj.mode!='OBJECT': original_command(self,context,'MODE')
            self.menu.page='EDIT' if want_edit else 'TOOLS'
            self.status='EDIT MODE' if want_edit else 'OBJECT MODE'; return
        if action=='EDIT_MORE':
            self.menu.page='EDIT_MORE'; self.status='MORE EDIT TOOLS'; return
        if action=='DELETE_OBJECT':
            if self.transaction or self.grab or self.air_grab or self.axis_move: raise ValueError('Finish or cancel the current operation first')
            entry=delete_object_entry(context.view_layer.objects.active); self.history.push(entry)
            self.target=None; self.status='OBJECT DELETED / UNDO TO RESTORE'; return
        if action=='LOOP_CUT_MENU':
            obj=context.view_layer.objects.active
            if not obj or obj.mode!='EDIT': raise ValueError('Enter Edit Mode for Loop Cut')
            if getattr(self,'select_mode','FACE')!='EDGE': raise ValueError('Switch to Edge Select and select one edge')
            self.loop_preview=loop_preview(obj); self.menu.page='LOOP_CUT'
            self.status='LOOP CUTS {} / POS {}%'.format(self.loop_cuts,round(self.loop_position*100)); return
        if action in {'LOOP_CUT_LESS','LOOP_CUT_MORE','LOOP_POS_LEFT','LOOP_POS_RIGHT'}:
            if action=='LOOP_CUT_LESS': self.loop_cuts=max(1,self.loop_cuts-1)
            elif action=='LOOP_CUT_MORE': self.loop_cuts=min(16,self.loop_cuts+1)
            elif action=='LOOP_POS_LEFT': self.loop_position=max(.05,self.loop_position-.05)
            else: self.loop_position=min(.95,self.loop_position+.05)
            self.status='LOOP CUTS {} / POS {}%'.format(self.loop_cuts,round(self.loop_position*100)); return
        if action=='LOOP_CUT_APPLY':
            obj=context.view_layer.objects.active
            self.history.push(loop_cut(obj,self.loop_cuts,self.loop_position))
            self.loop_preview=None; self.menu.page='EDIT'; self.status='LOOP CUT APPLIED'; return
        if action=='BACK' and self.menu.page in {'MODE_SELECT','LOOP_CUT'}:
            self.loop_preview=None
            obj=context.view_layer.objects.active
            self.menu.page='EDIT' if obj and obj.mode=='EDIT' else 'TOOLS'; self.status='BACK'; return
        result=original_command(self,context,action)
        return result

    def tick(self,context):
        result=original_tick(self,context)
        now=time.monotonic(); hover=getattr(self,'hover',None)
        if hover!=getattr(self,'hover_previous',None):
            self.hover_previous=hover; self.hover_started=now; self.menu.tooltip_action=None
        elif hover and now-self.hover_started>=TOOLTIP_DELAY:
            self.menu.tooltip_action=hover
        else:
            self.menu.tooltip_action=None
        return result

    Runtime.__init__=init; Runtime.command=command; Runtime.tick=tick
    Runtime._v065_patched=True