# SPDX-License-Identifier: GPL-3.0-or-later
"""World-space menu drawn in XR, with no helper objects in the user's scene."""
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

# Keep each action in one logical place. Edit-mode face tools live together,
# while global project/history actions stay on the main tools page.
BUTTONS = (
    ('SELECT OBJECT','SELECT'), ('MOVE OBJECT','MOVE'),
    ('SCALE OBJECT','SCALE'), ('FACE MODE','MODE'),
    ('SHAPES','ADD_MENU'), ('TRAVEL','NAV_MENU'),
    ('UNDO','UNDO'), ('REDO','REDO'),
    ('SAVE BLEND','SAVE'), ('STOP VR','STOP'),
)
EDIT_BUTTONS = (
    ('SELECT FACE','SELECT'), ('MOVE FACE','MOVE_FACE'),
    ('SCALE FACE','SCALE_FACE'), ('EXTRUDE','EXTRUDE'),
    ('BEVEL','BEVEL'), ('INSET','INSET'),
    ('DEL FACES','DELETE_FACES'), ('STEP -','LESS'),
    ('STEP +','MORE'), ('OBJECT MODE','MODE'),
)
PRIMITIVE_BUTTONS = tuple((kind, 'ADD_' + kind) for kind in
                         ('CUBE','SPHERE','CYLINDER','CONE','TORUS','PLANE')) + (
    ('TOOLS','BACK'),)
TRAVEL_BUTTONS = (
    ('FLY/WALK','FLY_TOGGLE'), ('TURBO','TURBO'),
    ('SLOWER','SLOWER'), ('FASTER','FASTER'),
    ('SNAP/SMOOTH','TURN_TOGGLE'), ('RESET VIEW','RESET'),
    ('TOOLS','BACK'),
)
# Original compact 5x7 bitmap font. GPU triangles work in both stereo eyes.
FONT = {
'A':['01110','10001','10001','11111','10001','10001','10001'],
'B':['11110','10001','10001','11110','10001','10001','11110'],
'C':['01111','10000','10000','10000','10000','10000','01111'],
'D':['11110','10001','10001','10001','10001','10001','11110'],
'E':['11111','10000','10000','11110','10000','10000','11111'],
'F':['11111','10000','10000','11110','10000','10000','10000'],
'G':['01111','10000','10000','10111','10001','10001','01111'],
'H':['10001','10001','10001','11111','10001','10001','10001'],
'I':['11111','00100','00100','00100','00100','00100','11111'],
'J':['00111','00010','00010','00010','10010','10010','01100'],
'K':['10001','10010','10100','11000','10100','10010','10001'],
'L':['10000','10000','10000','10000','10000','10000','11111'],
'M':['10001','11011','10101','10101','10001','10001','10001'],
'N':['10001','11001','10101','10011','10001','10001','10001'],
'O':['01110','10001','10001','10001','10001','10001','01110'],
'P':['11110','10001','10001','11110','10000','10000','10000'],
'Q':['01110','10001','10001','10001','10101','10010','01101'],
'R':['11110','10001','10001','11110','10100','10010','10001'],
'S':['01111','10000','10000','01110','00001','00001','11110'],
'T':['11111','00100','00100','00100','00100','00100','00100'],
'U':['10001','10001','10001','10001','10001','10001','01110'],
'V':['10001','10001','10001','10001','10001','01010','00100'],
'W':['10001','10001','10001','10101','10101','10101','01010'],
'X':['10001','10001','01010','00100','01010','10001','10001'],
'Y':['10001','10001','01010','00100','00100','00100','00100'],
'Z':['11111','00001','00010','00100','01000','10000','11111'],
'0':['01110','10001','10011','10101','11001','10001','01110'],
'1':['00100','01100','00100','00100','00100','00100','01110'],
'2':['01110','10001','00001','00010','00100','01000','11111'],
'3':['11110','00001','00001','01110','00001','00001','11110'],
'4':['00010','00110','01010','10010','11111','00010','00010'],
'5':['11111','10000','10000','11110','00001','00001','11110'],
'6':['01110','10000','10000','11110','10001','10001','01110'],
'7':['11111','00001','00010','00100','01000','01000','01000'],
'8':['01110','10001','10001','01110','10001','10001','01110'],
'9':['01110','10001','10001','01111','00001','00001','01110'],
'.':['00000','00000','00000','00000','00000','00100','00100'],
'-':['00000','00000','00000','11111','00000','00000','00000'],
':':['00000','00100','00100','00000','00100','00100','00000'],
'/':['00001','00001','00010','00100','01000','10000','10000'],
'+':['00000','00100','00100','11111','00100','00100','00000'],
' ':['00000']*7,
}


def rectangle_points(x, y, w, h):
    return [(x,y),(x+w,y),(x+w,y+h),(x,y),(x+w,y+h),(x,y+h)]


def button_rect(index):
    col, row = index % 2, index // 2
    return (-0.174 + col * 0.177, 0.117 - row * 0.052, 0.168, 0.043)


class Menu:
    def __init__(self):
        self.center = Vector()
        self.right = Vector((1, 0, 0))
        self.up = Vector((0, 0, 1))
        self.normal = Vector((0, -1, 0))
        self.scale = 1.0
        self.visible = True
        self.ready = False
        self.page = 'TOOLS'

    @property
    def buttons(self):
        return {'PRIMITIVES':PRIMITIVE_BUTTONS,'TRAVEL':TRAVEL_BUTTONS,'EDIT':EDIT_BUTTONS}.get(self.page,BUTTONS)

    def position(self, hand, viewer, scale):
        self.scale = max(scale, 1e-6)
        self.center = hand + Vector((0, 0, 0.25)) * self.scale
        normal = viewer - self.center
        if normal.length < 1e-6:
            self.ready = False
            return
        self.normal = normal.normalized()
        right = Vector((0, 0, 1)).cross(self.normal)
        if right.length < 1e-6:
            right = Vector((1, 0, 0))
        self.right = right.normalized()
        self.up = self.normal.cross(self.right).normalized()
        self.ready = True

    def world(self, x, y, depth=0):
        return self.center + (self.right*x + self.up*y + self.normal*depth)*self.scale

    def hit(self, origin, direction):
        if not self.visible or not self.ready:
            return None, None
        denom = direction.dot(self.normal)
        if abs(denom) < 1e-7:
            return None, None
        t = (self.center-origin).dot(self.normal)/denom
        if t <= 0:
            return None, None
        pos = origin + direction*t
        local = (pos-self.center)/self.scale
        x, y = local.dot(self.right), local.dot(self.up)
        if not (-0.19 <= x <= 0.19 and -0.29 <= y <= 0.23):
            return None, None
        for i, (_, action) in enumerate(self.buttons):
            bx, by, w, h = button_rect(i)
            if bx <= x <= bx+w and by <= y <= by+h:
                return action, pos
        return 'PANEL', pos

    def draw(self, shader, tool, hover, step, status, settings=None, selection=''):
        if not self.ready or not self.visible:
            return
        def rect(x,y,w,h,color,depth=0):
            draw_batch(shader, 'TRIS', [self.world(px,py,depth)
                       for px,py in rectangle_points(x,y,w,h)], color)
        def text(label,x,y,pixel=0.0030):
            points=[]
            for i,char in enumerate(label.upper()):
                for row,line in enumerate(FONT.get(char,FONT[' '])):
                    for col,value in enumerate(line):
                        if value == '1':
                            for px,py in rectangle_points(x+i*6*pixel+col*pixel,
                                                         y-row*pixel,pixel*0.86,pixel*0.86):
                                points.append(self.world(px,py,0.0015))
            if points:
                draw_batch(shader,'TRIS',points,(0.88,0.95,1,1))
        rect(-0.195,-0.29,0.39,0.52,(0.015,0.025,0.04,0.97))
        rect(-0.195,0.166,0.39,0.064,(0.025,0.13,0.17,1),0.0003)
        title = {'PRIMITIVES':'SHAPES','TRAVEL':'TRAVEL','EDIT':'FACE TOOLS'}.get(self.page,'TOOLS')
        text('BLENDER XR / '+title,-0.177,0.208,0.00275)
        summary = ('FLY ' if settings.fly_mode else 'WALK ') + format(settings.move_speed,'.1f') + ' / '+settings.turn_mode if settings and self.page=='TRAVEL' else tool.replace('_',' ')+' / STEP '+format(step,'.3f')
        text(summary,-0.177,0.153,0.00265)
        for i,(label,action) in enumerate(self.buttons):
            bx,by,w,h=button_rect(i)
            color=(0.06,0.12,0.18,1)
            selected = action==tool or (settings and (
                (action=='TURBO' and settings.fast_flight) or
                (action=='FLY_TOGGLE' and settings.fly_mode)))
            if selected: color=(0.025,0.35,0.35,1)
            if action==hover: color=(0.12,0.42,0.55,1)
            rect(bx,by,w,h,color,0.0005)
            text(label,bx+0.009,by+0.030,min(0.0032,0.15/(max(len(label),1)*6)))
        text(('MESH '+selection)[:24],-0.174,-0.19,0.0023)
        text(status[:25],-0.174,-0.214,0.00225)
        hint = 'LEFT MOVE / RIGHT TURN' if self.page=='TRAVEL' else 'POINT + TRIGGER TO USE'
        text(hint,-0.174,-0.246,0.0021)
        text('V0.4.4',-0.174,-0.274,0.0021)


def draw_batch(shader, kind, points, color):
    if not points:
        return
    shader.bind()
    shader.uniform_float('color', color)
    batch_for_shader(shader,kind,{'pos':points}).draw(shader)


def draw(runtime):
    if not runtime.active or runtime.ray is None:
        return
    shader=gpu.shader.from_builtin('UNIFORM_COLOR')
    old_depth=gpu.state.depth_test_get()
    old_blend=gpu.state.blend_get()
    try:
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('NONE')
        obj=runtime.context.view_layer.objects.active
        runtime.menu.draw(shader,runtime.tool,runtime.hover,runtime.settings.step,runtime.status,
                          runtime.settings,obj.name if obj else 'NONE')
        origin,direction=runtime.ray
        end=runtime.pointer if runtime.pointer is not None else origin+direction*2*runtime.menu.scale
        draw_batch(shader,'LINES',[origin,end],(0.3,1,0.6,1) if runtime.target else (0.12,0.85,1,1))
        if runtime.target:
            target=runtime.target
            corners=[target.matrix_world @ Vector(p) for p in target.bound_box]
            pairs=((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),
                   (0,4),(1,5),(2,6),(3,7))
            draw_batch(shader,'LINES',[corners[k] for pair in pairs for k in pair],(0.3,1,0.6,1))
        if runtime.gizmo is not None:
            from . import gizmo
            handles=runtime.gizmo
            for name,axis in handles.axes:
                tip=handles.anchor+axis*handles.length
                color=gizmo.COLORS[name]
                if runtime.gizmo_hover and runtime.gizmo_hover[0]==name:color=(1,1,1,1)
                sideways=axis.cross(Vector((0,0,1)))
                if sideways.length<.1:sideways=axis.cross(Vector((0,1,0)))
                sideways.normalize()
                tail=tip-axis*handles.radius*2
                lines=[handles.anchor,tip,tip,tail+sideways*handles.radius,
                       tip,tail-sideways*handles.radius]
                draw_batch(shader,'LINES',lines,color)
                # A billboard tip is much easier to see and hit at a distance.
                r=handles.radius*.80
                right=runtime.menu.right*r
                up=runtime.menu.up*r
                point=[tip-right-up,tip+right-up,tip+right+up,
                       tip-right-up,tip+right+up,tip-right+up]
                draw_batch(shader,'TRIS',point,color)
                # Billboard axis labels using the existing stereo-safe bitmap font.
                points=[];pixel=handles.length*.012
                origin_label=tip+runtime.menu.up*handles.radius
                for i,char in enumerate(name):
                    for row,line in enumerate(FONT.get(char,FONT[' '])):
                        for col,value in enumerate(line):
                            if value=='1':
                                for x,y in rectangle_points(i*6*pixel+col*pixel,-row*pixel,pixel*.86,pixel*.86):
                                    points.append(origin_label+runtime.menu.right*x+runtime.menu.up*y)
                draw_batch(shader,'TRIS',points,color)
        if runtime.spawn_preview is not None:
            center, size = runtime.spawn_preview
            corners = [center + Vector((x,y,z))*size/2
                       for x in (-1,1) for y in (-1,1) for z in (-1,1)]
            pairs = [(i,j) for i in range(8) for j in range(i+1,8)
                     if (i ^ j) in (1,2,4)]
            draw_batch(shader,'LINES',[corners[k] for pair in pairs for k in pair],(0.3,1,0.55,1))
        # Explicit VR face feedback, independent of desktop edit overlays.
        obj=runtime.context.view_layer.objects.active
        if obj and obj.type=='MESH' and obj.mode=='EDIT':
            import bmesh
            points=[]
            for face in bmesh.from_edit_mesh(obj.data).faces:
                if face.select and not face.hide:
                    for edge in face.edges:
                        points.extend(obj.matrix_world@v.co for v in edge.verts)
            draw_batch(shader,'LINES',points,(1,0.6,0.08,1))
    finally:
        gpu.state.depth_test_set(old_depth)
        gpu.state.blend_set(old_blend)
