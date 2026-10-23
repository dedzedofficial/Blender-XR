# SPDX-License-Identifier: GPL-3.0-or-later
"""World-space menu drawn in XR, with no helper objects in the user's scene."""
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from . import materials, menus, version, icon_textures

# Official Blender UI artwork, rasterized to transparent PNGs by the asset build.
_ICON_BY_ACTION = {
    # Main object/edit workflows.
    'MODE_MENU': 'object_datamode', 'MODE': 'object_datamode',
    'MODE_OBJECT': 'object_data', 'MODE_EDIT': 'mesh_data',
    'SELECT': 'cursor', 'SELECT_VERT': 'mesh_data',
    'SELECT_EDGE': 'object_data', 'SELECT_FACE': 'mesh_cube',
    'MOVE': 'transform_move', 'MOVE_EDIT': 'transform_move',
    'SCALE': 'transform_scale', 'SCALE_EDIT': 'transform_scale',
    'ROTATE': 'transform_rotate', 'ADD_MENU': 'add',
    'ADD_CUBE': 'mesh_cube', 'ADD_SPHERE': 'mesh_uvsphere',
    'ADD_CYLINDER': 'mesh_cylinder', 'ADD_CONE': 'mesh_cone',
    'ADD_TORUS': 'mesh_torus', 'ADD_PLANE': 'mesh_plane',
    'DUPLICATE': 'duplicate', 'UNDO': 'undo', 'REDO': 'redo',
    'SAVE': 'save_as', 'STOP': 'cancel', 'BACK': 'undo',
    'LESS': 'transform_scale', 'MORE': 'transform_scale',
    'EDIT_MORE': 'properties', 'LOOP_CUT_MENU': 'mesh_data',
    'LOOP_CUT_LESS': 'transform_scale', 'LOOP_CUT_MORE': 'transform_scale',
    'LOOP_POS_LEFT': 'transform_move', 'LOOP_POS_RIGHT': 'transform_move',
    'LOOP_CUT_APPLY': 'checkmark',
    # Modeling / mesh diagnostics.
    'EXTRUDE': 'extrude_region', 'BEVEL': 'bevel', 'INSET': 'inset_faces',
    'DELETE_GEOM': 'delete', 'DELETE_OBJECT': 'delete',
    'MERGE': 'mesh_data', 'SUBDIVIDE': 'mesh_cube',
    'RECALC': 'mesh_data', 'FLIP_NORMALS': 'mesh_data',
    'RIG_AUDIT': 'mesh_data',
    # Armature and weights have dedicated Blender symbols, not a generic tool icon.
    'RIG_MENU': 'armature_data', 'RIG_CREATE': 'armature_data',
    'RIG_BIND': 'mod_armature', 'RIG_WEIGHT': 'mod_vertex_weight',
    'RIG_CLEAN': 'mod_vertex_weight', 'RIG_POSE': 'pose_hlt',
    # Materials, shader, image and texture operations.
    'MATERIAL_MENU': 'node_material', 'MATERIALS': 'node_material',
    'MAT_PROPS': 'properties', 'MAT_SLOTS': 'object_data',
    'MAT_TEXTURES': 'image_data', 'MAT_PREVIEW': 'image',
    'MAT_NEW': 'node_material', 'MAT_DUP': 'duplicate',
    'MAT_DELETE': 'delete', 'MAT_RENAME_AUTO': 'properties',
    'MAT_METAL_DOWN': 'node_material', 'MAT_METAL_UP': 'node_material',
    'MAT_ROUGH_DOWN': 'node_material', 'MAT_ROUGH_UP': 'node_material',
    'MAT_ALPHA_DOWN': 'node_material', 'MAT_ALPHA_UP': 'node_material',
    'MAT_EMIT_DOWN': 'node_material', 'MAT_EMIT_UP': 'node_material',
    'MAT_SYNC': 'node_material', 'SLOT_PREV': 'object_data',
    'SLOT_NEXT': 'object_data', 'SLOT_ADD': 'add',
    'SLOT_REMOVE': 'delete', 'SLOT_ASSIGN': 'object_data',
    'SLOT_SELECT_FACES': 'mesh_cube',
    'IMG_PREV': 'image_data', 'IMG_NEXT': 'image_data',
    'IMG_APPLY': 'checkmark', 'IMG_CLEAR': 'delete',
    'IMG_CHECKER': 'image', 'IMG_DIRECTION': 'image',
    'IMG_GRID': 'image', 'COLOR_MENU': 'node_material',
    'COLOR_ADJUST_MENU': 'brush_data', 'COLOR_PICK': 'brush_data',
    'COLOR_APPLY': 'checkmark', 'COLOR_PALETTE': 'brush_data',
    'COLOR_RED': 'brush_data', 'COLOR_ORANGE': 'brush_data',
    'COLOR_YELLOW': 'brush_data', 'COLOR_GREEN': 'brush_data',
    'COLOR_CYAN': 'brush_data', 'COLOR_BLUE': 'brush_data',
    'COLOR_PURPLE': 'brush_data', 'COLOR_PINK': 'brush_data',
    'COLOR_WHITE': 'brush_data', 'COLOR_BLACK': 'brush_data',
    'PANEL': None,
    # UV operations and transform controls.
    'UV_MENU': 'uv', 'UV_UNWRAP': 'uv', 'UV_SMART': 'uv',
    'UV_CUBE': 'uv', 'UV_PLANAR': 'uv', 'UV_MARK_SEAM': 'uv',
    'UV_CLEAR_SEAM': 'uv', 'UV_TRANSFORM_MENU': 'uv',
    'UV_PACK': 'uv', 'UV_RESET': 'uv', 'UV_PREVIEW': 'image',
    'UV_U_DOWN': 'transform_move', 'UV_U_UP': 'transform_move',
    'UV_V_DOWN': 'transform_move', 'UV_V_UP': 'transform_move',
    'UV_ROT_DOWN': 'transform_rotate', 'UV_ROT_UP': 'transform_rotate',
    'UV_SCALE_DOWN': 'transform_scale', 'UV_SCALE_UP': 'transform_scale',
    # View/travel and other utility actions.
    'NAV_MENU': 'view_camera', 'FLY_TOGGLE': 'view_camera',
    'TURBO': 'preferences', 'SLOWER': 'transform_scale',
    'FASTER': 'transform_scale', 'TURN_TOGGLE': 'transform_rotate',
    'RESET': 'view_camera',
    # Advanced object, geometry and modifier tools added in v0.7.1.
    'OBJECT_ADVANCED': 'object_data', 'GEOMETRY_ADVANCED': 'mesh_data',
    'OBJ_DUPLICATE': 'duplicate', 'OBJ_SNAP': 'transform_move',
    'OBJ_RESET_ROT': 'transform_rotate',
    'ROT_X_POS': 'transform_rotate', 'ROT_X_NEG': 'transform_rotate',
    'ROT_Y_POS': 'transform_rotate', 'ROT_Y_NEG': 'transform_rotate',
    'ROT_Z_POS': 'transform_rotate', 'ROT_Z_NEG': 'transform_rotate',
    'GEO_DISSOLVE_VERT': 'delete', 'GEO_DISSOLVE_EDGE': 'delete',
    'GEO_FILL': 'add', 'GEO_BRIDGE': 'mesh_data', 'GEO_RECALC': 'mesh_data',
    'MODIFIER_MENU': 'modifier',
    'MOD_MIRROR_X': 'modifier', 'MOD_MIRROR_Y': 'modifier',
    'MOD_MIRROR_Z': 'modifier', 'MOD_ARRAY': 'modifier',
    'MOD_SOLIDIFY': 'modifier', 'MOD_COUNT_UP': 'add',
    'MOD_COUNT_DOWN': 'delete', 'MOD_THICK_UP': 'transform_scale',
    'MOD_THICK_DOWN': 'transform_scale', 'MOD_TOGGLE': 'modifier',
    'MOD_REMOVE': 'delete',
}
_IMAGE_SHADER = None


def _draw_icon_texture(texture, corners):
    """Draw one transparent icon texture on a world-space quad."""
    global _IMAGE_SHADER
    if _IMAGE_SHADER is None:
        _IMAGE_SHADER = gpu.shader.from_builtin('IMAGE')
    batch = batch_for_shader(
        _IMAGE_SHADER, 'TRI_FAN',
        {'pos': corners, 'texCoord': ((0, 0), (1, 0), (1, 1), (0, 1))},
    )
    _IMAGE_SHADER.bind()
    _IMAGE_SHADER.uniform_sampler('image', texture)
    batch.draw(_IMAGE_SHADER)

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
    return (-0.207 + col * 0.211, 0.117 - row * 0.052, 0.198, 0.045)


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
        return menus.buttons(self.page)

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
        if not (-0.222 <= x <= 0.222 and -0.34 <= y <= 0.23):
            return None, None
        for i, (_, action) in enumerate(self.buttons):
            bx, by, w, h = button_rect(i)
            if bx <= x <= bx+w and by <= y <= by+h:
                return action, pos
        return 'PANEL', pos

    def draw(self, shader, tool, hover, step, status, settings=None, selection='', select_mode='FACE'):
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
        rect(-0.225,-0.34,0.45,0.57,(0.015,0.025,0.04,0.98))
        rect(-0.225,0.166,0.45,0.064,(0.025,0.13,0.17,1),0.0003)
        text('MESH XR / '+menus.title(self.page),-0.207,0.208,0.00275)
        if settings and self.page=='TRAVEL':
            summary=('FLY ' if settings.fly_mode else 'WALK ')+format(settings.move_speed,'.1f')+' / '+settings.turn_mode
        elif settings and self.page in {'MATERIALS','MATERIAL_ADJUST'}:
            color=tuple(float(v) for v in settings.object_color[:4])
            rect(-0.174,0.139,0.055,0.020,color,0.0005)
            summary=materials.color_summary(color)
        elif self.page in {'EDIT','EDIT_MORE'}:
            display_tool={'MOVE_FACE':'MOVE SELECTED','SCALE_FACE':'SCALE SELECTED'}.get(tool,tool.replace('_',' '))
            summary=select_mode+' / '+display_tool+' / '+format(step,'.3f')
        else:
            summary=tool.replace('_',' ')+' / STEP '+format(step,'.3f')
        text(summary,-0.108 if settings and self.page in {'MATERIALS','MATERIAL_ADJUST'} else -0.177,
             0.153,0.0024 if settings and self.page in {'MATERIALS','MATERIAL_ADJUST'} else 0.00265)
        mode_actions={'SELECT_VERT':'VERT','SELECT_EDGE':'EDGE','SELECT_FACE':'FACE'}
        tool_actions={'MOVE_FACE':'MOVE_EDIT','SCALE_FACE':'SCALE_EDIT'}
        for i,(label,action) in enumerate(self.buttons):
            bx,by,w,h=button_rect(i)
            color=materials.PRESET_COLORS.get(action,(0.06,0.12,0.18,1))
            selected = (action==tool or action==tool_actions.get(tool) or
                        mode_actions.get(action)==select_mode or (settings and (
                (action=='TURBO' and settings.fast_flight) or
                (action=='FLY_TOGGLE' and settings.fly_mode))))
            if selected:
                color=(0.025,0.35,0.35,1)
            if action==hover:
                color=(0.12,0.42,0.55,1)
            rect(bx,by,w,h,color,0.0005)
            icon_name = _ICON_BY_ACTION.get(action)
            icon_texture = icon_textures.texture_for(icon_name) if icon_name else None
            has_icon = icon_texture is not None
            if has_icon:
                ix, iy, iw, ih = bx + 0.006, by + 0.008, 0.029, 0.029
                corners = [self.world(ix, iy, 0.0015), self.world(ix+iw, iy, 0.0015),
                           self.world(ix+iw, iy+ih, 0.0015), self.world(ix, iy+ih, 0.0015)]
                _draw_icon_texture(icon_texture, corners)
            friendly = {
                'MODE_MENU':'MODE', 'MODE_OBJECT':'OBJECT', 'MODE_EDIT':'EDIT',
                'SELECT_VERT':'VERTEX', 'SELECT_EDGE':'EDGE', 'SELECT_FACE':'FACE',
                'MOVE_EDIT':'MOVE SEL', 'SCALE_EDIT':'SCALE SEL',
                'ADD_MENU':'SHAPES', 'MATERIAL_MENU':'MATERIALS', 'NAV_MENU':'TRAVEL',
                'RIG_MENU':'RIGGING', 'DELETE_OBJECT':'DELETE OBJ',
                'DELETE_GEOM':'DELETE GEO', 'LOOP_CUT_MENU':'LOOP CUT',
                'RIG_CREATE':'CREATE RIG', 'RIG_BIND':'BIND WEIGHTS',
                'RIG_WEIGHT':'WEIGHT PAINT', 'RIG_CLEAN':'CLEAN WEIGHTS',
                'RIG_POSE':'POSE TEST', 'RIG_AUDIT':'AUDIT MESH',
            }
            display_label = label or friendly.get(action, action.replace('_',' '))
            label_x = bx + (0.041 if has_icon else 0.009)
            label_width = 0.151 if has_icon else 0.177
            text(display_label,label_x,by+0.031,
                 min(0.0032,label_width/(max(len(display_label),1)*6)))
        text(('MESH '+selection)[:24],-0.207,-0.222,0.0023)
        text(status[:25],-0.207,-0.252,0.00225)
        hint = 'LEFT MOVE / RIGHT TURN' if self.page=='TRAVEL' else 'POINT + TRIGGER TO USE'
        text(hint,-0.207,-0.292,0.0021)
        text(version.DISPLAY_VERSION,-0.207,-0.322,0.0021)


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
                          runtime.settings,obj.name if obj else 'NONE',runtime.select_mode)
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
                if runtime.gizmo_hover and runtime.gizmo_hover[0]==name:
                    color=(1,1,1,1)
                sideways=axis.cross(Vector((0,0,1)))
                if sideways.length<.1:
                    sideways=axis.cross(Vector((0,1,0)))
                sideways.normalize()
                tail=tip-axis*handles.radius*2
                lines=[handles.anchor,tip,tip,tail+sideways*handles.radius,
                       tip,tail-sideways*handles.radius]
                draw_batch(shader,'LINES',lines,color)
                r=handles.radius*.80
                right=runtime.menu.right*r
                up=runtime.menu.up*r
                point=[tip-right-up,tip+right-up,tip+right+up,
                       tip-right-up,tip+right+up,tip-right+up]
                draw_batch(shader,'TRIS',point,color)
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
        obj=runtime.context.view_layer.objects.active
        if obj and obj.type=='MESH' and obj.mode=='EDIT':
            import bmesh
            bm=bmesh.from_edit_mesh(obj.data)
            points=[]
            if runtime.select_mode=='VERT':
                size=max(runtime.menu.scale*.012,0.005)
                for vert in bm.verts:
                    if vert.select and not vert.hide:
                        p=obj.matrix_world@vert.co
                        points.extend((p+Vector((-size,0,0)),p+Vector((size,0,0)),
                                       p+Vector((0,-size,0)),p+Vector((0,size,0)),
                                       p+Vector((0,0,-size)),p+Vector((0,0,size))))
            elif runtime.select_mode=='EDGE':
                for edge in bm.edges:
                    if edge.select and not edge.hide:
                        points.extend(obj.matrix_world@v.co for v in edge.verts)
            else:
                for face in bm.faces:
                    if face.select and not face.hide:
                        for edge in face.edges:
                            points.extend(obj.matrix_world@v.co for v in edge.verts)
            draw_batch(shader,'LINES',points,(1,0.6,0.08,1))
    finally:
        gpu.state.depth_test_set(old_depth)
        gpu.state.blend_set(old_blend)
