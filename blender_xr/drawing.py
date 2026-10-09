# SPDX-License-Identifier: GPL-3.0-or-later
"""World-space menu drawn in XR, with no helper objects in the user's scene."""
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

BUTTONS = (
    ('SELECT', 'SELECT'), ('MODE', 'MODE'),
    ('EXTRUDE', 'EXTRUDE'), ('BEVEL', 'BEVEL'),
    ('INSET', 'INSET'), ('MOVE', 'MOVE'),
    ('UNDO', 'UNDO'), ('REDO', 'REDO'),
    ('LESS', 'LESS'), ('MORE', 'MORE'),
    ('RESET VIEW', 'RESET'), ('STOP VR', 'STOP'),
    ('ADD SHAPES', 'ADD_MENU'), ('', 'PANEL'),
)
PRIMITIVE_BUTTONS = tuple((kind, 'ADD_' + kind) for kind in
                         ('CUBE','SPHERE','CYLINDER','CONE','TORUS','PLANE')) + (
    ('BACK', 'BACK'), ('STOP VR', 'STOP'))
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
        return PRIMITIVE_BUTTONS if self.page == 'PRIMITIVES' else BUTTONS

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
        if not (-0.19 <= x <= 0.19 and -0.27 <= y <= 0.23):
            return None, None
        for i, (_, action) in enumerate(self.buttons):
            bx, by, w, h = button_rect(i)
            if bx <= x <= bx+w and by <= y <= by+h:
                return action, pos
        return 'PANEL', pos

    def draw(self, shader, tool, hover, step, status):
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
        rect(-0.19,-0.27,0.38,0.50,(0.025,0.04,0.06,0.97))
        text('BLENDER XR 0.4.1',-0.17,0.205,0.0032)
        text('STEP '+format(step,'.4f'),-0.17,0.177,0.0026)
        for i,(label,action) in enumerate(self.buttons):
            bx,by,w,h=button_rect(i)
            color=(0.06,0.12,0.18,1)
            if action==tool: color=(0.04,0.41,0.43,1)
            if action==hover: color=(0.12,0.42,0.55,1)
            rect(bx,by,w,h,color,0.0005)
            text(label,bx+0.009,by+0.027,0.00245)
        text(status[:24],-0.17,-0.246,0.0023)


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
        runtime.menu.draw(shader,runtime.tool,runtime.hover,runtime.settings.step,runtime.status)
        origin,direction=runtime.ray
        end=runtime.pointer if runtime.pointer is not None else origin+direction*2*runtime.menu.scale
        draw_batch(shader,'LINES',[origin,end],(0.12,0.85,1,1))
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
