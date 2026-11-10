# SPDX-License-Identifier: GPL-3.0-or-later
"""Mesh XR v0.8.5 native image texture painting with controller ray-to-UV strokes.

Layers are generated Blender Images mixed over the existing Principled Base Color
without deleting existing texture links. Native generated image pixels are
changed by sparse brush dabs, with stroke-level XR-local undo/redo and rollback
on tracking loss. Paint stays editable/savable as Blender image data.
"""
from array import array
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector

from . import actions, input_ownership_v080, menus, mesh, native_curves_v080, v065

_PAGE = 'XR_TEXTURE_PAINT_085'
_RES_PAGE = 'XR_TEXTURE_RES_085'
_IMAGE = 'Mesh XR Paint Image'
_LAYER = 'Mesh XR Paint Overlay'
_TAG = '_meshxr_paint_layer'
_DEFAULT_SIZE = 512


def _mesh(context):
    if context.mode != 'OBJECT':
        raise ValueError('Use Object Mode to paint native images')
    obj = context.view_layer.objects.active
    if obj is None or obj.type != 'MESH' or obj.mode != 'OBJECT':
        raise ValueError('Select a mesh object to texture paint')
    if obj.library or obj.override_library or obj.data.library or obj.data.users != 1:
        raise ValueError('Texture Paint requires a local single-user mesh')
    if obj.hide_select or not obj.visible_get(view_layer=context.view_layer):
        raise ValueError('Unlock and show the mesh before painting')
    if obj.data.shape_keys or obj.modifiers:
        raise ValueError('Paint base mesh without shape keys/modifiers to keep UV hits exact')
    if obj.data.uv_layers.active is None or not obj.data.polygons:
        raise ValueError('Unwrap a native UV map before painting')
    return obj


def _material(context):
    obj = _mesh(context)
    material = obj.active_material
    if material is None:
        raise ValueError('Assign a material in Material Studio before painting')
    if (material.library or material.override_library or material.users != 1):
        raise ValueError('Duplicate shared or linked materials before painting')
    if not material.use_nodes or material.node_tree is None:
        raise ValueError('Use a native node material for texture painting')
    principled = next((n for n in material.node_tree.nodes
                       if n.type == 'BSDF_PRINCIPLED'), None)
    if principled is None:
        raise ValueError('The active material has no Principled shader')
    base = principled.inputs.get('Base Color')
    if base is None or len(base.links) > 1:
        raise ValueError('The material Base Color input is unsupported')
    return obj, material, principled, base


def _layers(material):
    return [(node, node.image) for node in material.node_tree.nodes
            if node.type == 'TEX_IMAGE' and node.get(_TAG)
            and node.image is not None]


def _selected(session, context):
    obj, mat, principled, base = _material(context)
    token = getattr(session, '_xr_paint_target', None)
    if not token or token[:3] != (obj.name, obj.as_pointer(), mat.as_pointer()):
        raise ValueError('Material/mesh changed; reopen Paint Studio')
    node = mat.node_tree.nodes.get(token[3])
    if node is None or node.type != 'TEX_IMAGE' or not node.get(_TAG):
        raise ValueError('Paint layer was removed; reopen the Paint Studio')
    image = node.image
    if image is None or image.source not in {'GENERATED', 'FILE'}:
        raise ValueError('Paint image changed; create a new native layer')
    if image.library or image.override_library or image.users != 1:
        raise ValueError('Paint image is linked/shared; create a new local layer')
    if image.channels != 4 or image.size[0] < 2 or image.size[1] < 2:
        raise ValueError('Paint image must be native RGBA')
    return obj, mat, node, image


def _new_image(size, name=_IMAGE):
    size = int(size)
    if size not in {256, 512, 1024}:
        raise ValueError('Use a 256, 512 or 1024 pixel editable paint layer')
    img = bpy.data.images.new(name, width=size, height=size,
                              alpha=True, float_buffer=True)
    img.alpha_mode = 'STRAIGHT'
    img.generated_color = (0., 0., 0., 0.)
    img.pixels.foreach_set(array('f', [0.0]) * (size * size * 4))
    img.update()
    return img


def _socket_name(socket):
    return (socket.identifier or socket.name)


def _make_nodes(mat, principled, image, old_link=None, original_color=None,
                label=_LAYER, image_label=_IMAGE, uvmap='', uv_label='Mesh XR Paint UV'):
    tree = mat.node_tree
    base = principled.inputs['Base Color']
    if base.links:
        raise ValueError('Base Color changed outside Paint Studio')
    mix = tree.nodes.new('ShaderNodeMixRGB')
    mix.name = label
    mix.label = 'Mesh XR Image Paint Layer'
    mix.blend_type = 'MIX'
    mix.inputs[0].default_value = 0.
    mix.inputs[1].default_value = tuple(original_color or base.default_value)
    mix.use_clamp = True
    tex = tree.nodes.new('ShaderNodeTexImage')
    tex.name = image_label
    tex.label = 'Mesh XR Editable Image'
    tex[_TAG] = True
    tex.image = image
    uv_node = tree.nodes.new('ShaderNodeUVMap')
    uv_node.name = uv_label
    uv_node.uv_map = uvmap
    tree.links.new(uv_node.outputs['UV'], tex.inputs['Vector'])
    mix.location = (principled.location.x - 240, principled.location.y - 220)
    tex.location = (mix.location.x - 280, mix.location.y)
    uv_node.location = (tex.location.x - 220, tex.location.y)
    if old_link is not None:
        source_node = tree.nodes.get(old_link[0])
        source_socket = (source_node.outputs.get(old_link[1])
                         if source_node else None)
        if source_socket is None:
            raise ValueError('Existing Base Color node link was removed')
        tree.links.new(source_socket, mix.inputs[1])
    tree.links.new(tex.outputs['Color'], mix.inputs[2])
    tree.links.new(tex.outputs['Alpha'], mix.inputs[0])
    tree.links.new(mix.outputs['Color'], base)
    return tex, mix


def _link_snapshot(base):
    if not base.links:
        return None
    source = base.links[0].from_socket
    return (base.links[0].from_node.name, _socket_name(source))


def _remove_layer(mat, bsdf_name, tex_name, mix_name, prior, base_color):
    tree = mat.node_tree
    bsdf = tree.nodes.get(bsdf_name)
    tex = tree.nodes.get(tex_name)
    mix = tree.nodes.get(mix_name)
    if (bsdf is None or bsdf.type != 'BSDF_PRINCIPLED' or
            tex is None or not tex.get(_TAG) or
            mix is None or mix.type != 'MIX_RGB'):
        raise ValueError('Paint layer node graph changed outside XR history')
    base = bsdf.inputs['Base Color']
    if not base.links or base.links[0].from_node != mix:
        raise ValueError('Paint layer is no longer the top Base Color layer')
    image = tex.image
    uv_node = (tex.inputs['Vector'].links[0].from_node
               if tex.inputs['Vector'].links else None)
    tree.nodes.remove(mix)
    tree.nodes.remove(tex)
    if uv_node is not None and uv_node.type == 'UVMAP' and uv_node.name.startswith('Mesh XR Paint UV'):
        tree.nodes.remove(uv_node)
    base.default_value = base_color
    if prior is not None:
        source = tree.nodes.get(prior[0])
        output = source.outputs.get(prior[1]) if source else None
        if output is None:
            raise ValueError('Original Base Color link was deleted')
        tree.links.new(output, base)
    if image is not None and image.users == 0:
        bpy.data.images.remove(image)


def _create_layer(session, context):
    obj, mat, bsdf, base = _material(context)
    size = int(getattr(session, '_xr_paint_resolution', _DEFAULT_SIZE))
    prior = _link_snapshot(base)
    base_color = tuple(base.default_value)
    image = _new_image(size)
    original_link = base.links[0] if base.links else None
    if original_link is not None:
        mat.node_tree.links.remove(original_link)
    try:
        tex, mix = _make_nodes(mat, bsdf, image, prior, base_color,
                               uvmap=obj.data.uv_layers.active.name)
    except Exception:
        if original_link is not None:
            source = mat.node_tree.nodes.get(prior[0])
            if source:
                mat.node_tree.links.new(source.outputs[prior[1]], base)
        if image.users == 0:
            bpy.data.images.remove(image)
        raise
    session._xr_paint_target = (obj.name, obj.as_pointer(), mat.as_pointer(), tex.name)
    session.history.push(('XR_PAINT_LAYER_085', mat, mat.name, bsdf.name,
                          tex.name, mix.name, prior, base_color,
                          image.name, size, obj.name,
                          obj.data.uv_layers.active.name,
                          tex.inputs['Vector'].links[0].from_node.name))
    session.status = 'PAINT LAYER CREATED / {} PX'.format(size)
    session.menu.page = _PAGE


def _open(session, context):
    obj, mat, _bsdf, _base = _material(context)
    existing = _layers(mat)
    session._xr_paint_target = ((obj.name, obj.as_pointer(), mat.as_pointer(),
                                 existing[-1][0].name) if existing else None)
    session._xr_paint_resolution = getattr(session, '_xr_paint_resolution', _DEFAULT_SIZE)
    session._xr_paint_radius = getattr(session, '_xr_paint_radius', 8)
    session._xr_paint_opacity = getattr(session, '_xr_paint_opacity', .8)
    session._xr_paint_mirror_u = getattr(session, '_xr_paint_mirror_u', False)
    session.menu.page = _PAGE
    session.status = ('PAINT / READY' if existing else 'PAINT / CREATE A LAYER FIRST')


def _cycle(session, context):
    obj, mat, _bsdf, _base = _material(context)
    layers = _layers(mat)
    if not layers:
        raise ValueError('Create a paint layer first')
    names = [node.name for node, _img in layers]
    old = getattr(session, '_xr_paint_target', (None, None, None, None))
    selected = names[(names.index(old[3]) + 1) % len(names)] if old[3] in names else names[0]
    session._xr_paint_target = (obj.name, obj.as_pointer(), mat.as_pointer(), selected)
    session.status = 'PAINT LAYER / ' + selected[:32]


def _pixel_data(image):
    total = int(image.size[0]) * int(image.size[1]) * 4
    result = array('f', [0.0]) * total
    image.pixels.foreach_get(result)
    return result


def _write_pixels(image, buf):
    image.pixels.foreach_set(buf)
    image.update()


def _uv_hit(context, obj, origin, direction):
    result = context.scene.ray_cast(context.evaluated_depsgraph_get(),
                                    Vector(origin), Vector(direction).normalized())
    if not result[0]:
        return None
    hit_obj = result[4].original if hasattr(result[4], 'original') else result[4]
    if hit_obj != obj:
        return None
    index = int(result[3])
    if not 0 <= index < len(obj.data.polygons):
        return None
    face = obj.data.polygons[index]
    if face.material_index != obj.active_material_index:
        return None
    loops = tuple(face.loop_indices)
    if len(loops) < 3:
        return None
    local = obj.matrix_world.inverted_safe() @ Vector(result[1])
    uv_layer = obj.data.uv_layers.active.data
    positions = [obj.data.vertices[obj.data.loops[i].vertex_index].co.copy()
                 for i in loops]
    uv_values = [uv_layer[i].uv.copy() for i in loops]
    # Triangulate the polygon fan without changing source geometry.
    for i in range(1, len(loops)-1):
        a, b, c = positions[0], positions[i], positions[i+1]
        e0, e1, v = b - a, c - a, local - a
        d00, d01, d11 = e0.dot(e0), e0.dot(e1), e1.dot(e1)
        denominator = d00*d11 - d01*d01
        if abs(denominator) < 1e-12:
            continue
        d20, d21 = v.dot(e0), v.dot(e1)
        beta = (d11*d20 - d01*d21) / denominator
        gamma = (d00*d21 - d01*d20) / denominator
        alpha = 1.0 - beta - gamma
        if min(alpha, beta, gamma) >= -0.0001:
            uv = uv_values[0] * alpha + uv_values[i] * beta + uv_values[i+1] * gamma
            if not (0. <= uv.x <= 1. and 0. <= uv.y <= 1.):
                return None  # Explicitly do not paint through tiled UVs.
            return uv.x, uv.y
    return None


class PaintStroke:
    def __init__(self, session, context, kind):
        obj, mat, node, image = _selected(session, context)
        self.object_name = obj.name
        self.object_ptr = obj.as_pointer()
        self.image_name = image.name
        self.image_ptr = image.as_pointer()
        self.image = image
        self.buf = _pixel_data(image)
        self.width, self.height = tuple(image.size)
        self.radius = max(1, min(64, int(session._xr_paint_radius)))
        self.opacity = max(.05, min(1.0, float(session._xr_paint_opacity)))
        self.color = tuple(float(v) for v in session.settings.object_color[:3])
        self.erase = kind == 'ERASE'
        self.mirror_u = bool(session._xr_paint_mirror_u)
        self.before = {}
        self.after = {}

    def dab(self, context, origin, direction):
        obj = context.view_layer.objects.get(self.object_name)
        if obj is None or obj.as_pointer() != self.object_ptr:
            raise ValueError('Paint mesh changed during the stroke')
        uv = _uv_hit(context, obj, origin, direction)
        if uv is None:
            return False
        coords = [(uv[0], uv[1])]
        if self.mirror_u:
            coords.append((1.0-uv[0], uv[1]))
        for u, v in coords:
            xcenter = min(self.width-1, max(0, round(u*(self.width-1))))
            ycenter = min(self.height-1, max(0, round(v*(self.height-1))))
            r = self.radius
            for y in range(max(0, ycenter-r), min(self.height, ycenter+r+1)):
                for x in range(max(0, xcenter-r), min(self.width, xcenter+r+1)):
                    distance = math.hypot(x-xcenter, y-ycenter)
                    if distance > r:
                        continue
                    alpha = self.opacity * max(.0, 1.0 - (distance / (r+0.001)) ** 2)
                    if alpha < .00001:
                        continue
                    idx = (y*self.width + x)*4
                    old = tuple(self.buf[idx:idx+4])
                    if idx not in self.before:
                        self.before[idx] = old
                    if self.erase:
                        new = old[:3] + (max(0., old[3]*(1.-alpha)),)
                    else:
                        new_alpha = min(1., old[3] + alpha*(1.-old[3]))
                        if new_alpha <= 0.:
                            rgb = self.color
                        else:
                            rgb = tuple((old[n]*old[3]*(1.-alpha) +
                                         self.color[n]*alpha) / new_alpha for n in range(3))
                        new = rgb + (new_alpha,)
                    self.buf[idx:idx+4] = array('f', new)
                    self.after[idx] = new
        if self.after:
            _write_pixels(self.image, self.buf)
            return True
        return False

    def cancel(self):
        for index, color in self.before.items():
            self.buf[index:index+4] = array('f', color)
        if self.before:
            _write_pixels(self.image, self.buf)

    def finish(self):
        changes = {index: (old, self.after.get(index, old))
                   for index, old in self.before.items()
                   if any(abs(a-b) > 1e-6 for a, b in zip(old, self.after.get(index, old)))}
        if not changes:
            return None
        return ('XR_PAINT_STROKE_085', self.image_name,
                self.image_ptr, changes)


def _arm(session, context, action):
    if input_ownership_v080.owner(session) not in {'IDLE', 'RADIAL'}:
        raise ValueError('Finish the active XR gesture before painting')
    kind = 'ERASE' if action == 'XR_PAINT_ERASE' else 'PAINT'
    stroke = PaintStroke(session, context, kind)
    session._xr_paint_pending = stroke
    session._xr_paint_ready = False
    session._xr_paint_started = False
    session._xr_paint_was_visible = bool(session.menu.visible)
    session.menu.visible = False
    radial = getattr(session, 'radial', None)
    if radial is not None and getattr(radial, 'active', False):
        radial.reset(require_release=True)
    session.status = 'TEXTURE / RELEASE, AIM, HOLD TRIGGER / OFFHAND CANCEL'


def _cancel(session, rollback=True):
    stroke = getattr(session, '_xr_paint_pending', None)
    if stroke is not None:
        if rollback:
            stroke.cancel()
        session._xr_paint_pending = None
        session.menu.visible = bool(getattr(session, '_xr_paint_was_visible', True))
        session._xr_paint_release_required = True


def _tick(session, context):
    try:
        pressed, cancel, origin, direction = native_curves_v080._input_sample(session, context)
    except (RuntimeError, TypeError, ValueError, IndexError, AttributeError) as exc:
        _cancel(session, True)
        session._xr_rearm_required = True
        session.status = 'PAINT INPUT LOST / RELEASE TO REARM'
        return
    if cancel:
        _cancel(session, True)
        session.status = 'PAINT STROKE CANCELLED'
        return
    if not pressed:
        if getattr(session, '_xr_paint_started', False):
            stroke = session._xr_paint_pending
            entry = stroke.finish()
            if entry:
                session.history.push(entry)
            _cancel(session, False)
            session.status = 'PAINT STROKE SAVED' if entry else 'PAINT STROKE UNCHANGED'
            return
        if getattr(session, '_xr_paint_pending', None) is not None:
            session._xr_paint_ready = True
        else:
            session._xr_paint_release_required = False
        if getattr(session, 'trigger', None):
            session.trigger.update(0.0)
        return
    stroke = getattr(session, '_xr_paint_pending', None)
    if stroke is not None and getattr(session, '_xr_paint_ready', False):
        try:
            stroke.dab(context, origin, direction)
            session._xr_paint_started = True
        except (ValueError, RuntimeError, ReferenceError) as exc:
            _cancel(session, True)
            session.status = 'PAINT CANCELLED / ' + str(exc).upper()[:38]


def _fill(session, context, empty=False):
    _obj, _mat, _node, image = _selected(session, context)
    before = _pixel_data(image)
    if empty:
        after = array('f', [0.0]) * len(before)
    else:
        r, g, b = (float(v) for v in session.settings.object_color[:3])
        after = array('f', (v for _ in range(len(before)//4)
                            for v in (r, g, b, 1.)))
    if after == before:
        session.status = 'PAINT IMAGE UNCHANGED'
        return
    _write_pixels(image, after)
    session.history.push(('XR_PAINT_IMAGE_085', image.name, image.as_pointer(),
                          before, after))
    session.status = 'PAINT IMAGE CLEARED' if empty else 'PAINT IMAGE FILLED'


def _save(session, context):
    _obj, _mat, _node, image = _selected(session, context)
    blend = bpy.data.filepath
    if not blend:
        raise ValueError('Save the .blend project before exporting a paint texture')
    folder = Path(blend).parent / 'textures'
    folder.mkdir(exist_ok=True)
    name = ''.join(ch if ch.isalnum() or ch in '-_' else '_'
                   for ch in image.name) + '.png'
    output = folder / name
    if output.exists():
        raise ValueError('Texture PNG already exists; rename image before exporting')
    image.filepath_raw = str(output)
    image.file_format = 'PNG'
    image.save()
    session.status = 'TEXTURE SAVED / ' + str(output)


def _apply_pixels(image, pairs, backwards):
    buf = _pixel_data(image)
    for idx, (before, after) in pairs.items():
        expected = after if backwards else before
        for n in range(4):
            if abs(buf[idx+n] - expected[n]) > 2e-5:
                raise ValueError('Paint pixels changed outside XR undo history')
    for idx, (before, after) in pairs.items():
        buf[idx:idx+4] = array('f', before if backwards else after)
    _write_pixels(image, buf)


def _history_patch():
    if getattr(mesh.History, '_xr_paint_085_history', False):
        return
    original_step, original_release = mesh.History.step, mesh.History.release

    def release(entry):
        if entry[0] in {'XR_PAINT_STROKE_085', 'XR_PAINT_IMAGE_085',
                        'XR_PAINT_LAYER_085'}:
            return
        return original_release(entry)

    def step(self, backwards=True):
        src, dest = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if not src or src[-1][0] not in {
                'XR_PAINT_STROKE_085', 'XR_PAINT_IMAGE_085', 'XR_PAINT_LAYER_085'}:
            return original_step(self, backwards)
        entry = src[-1]
        if bpy.context.mode != 'OBJECT':
            raise ValueError('Exit Edit Mode before texture Undo')
        if entry[0] in {'XR_PAINT_STROKE_085', 'XR_PAINT_IMAGE_085'}:
            image = bpy.data.images.get(entry[1])
            if image is None:
                raise ValueError('Native paint image was removed')
            if entry[0] == 'XR_PAINT_STROKE_085':
                _apply_pixels(image, entry[3], backwards)
            else:
                before, after = entry[3:5]
                current = _pixel_data(image)
                expected = after if backwards else before
                if current != expected:
                    raise ValueError('Paint image changed outside XR undo history')
                _write_pixels(image, before if backwards else after)
        else:
            (_tag, mat, matname, bsdf_name, tex_name, mix_name, prior,
             base_color, image_name, size, objname, uvmap, uv_label) = entry
            if bpy.data.materials.get(matname) != mat or mat.users != 1:
                raise ValueError('Material ownership changed outside XR history')
            tree = mat.node_tree
            if backwards:
                _remove_layer(mat, bsdf_name, tex_name, mix_name, prior, base_color)
            else:
                if tree.nodes.get(tex_name) or bpy.data.images.get(image_name):
                    raise ValueError('Paint layer name was reused outside XR history')
                bsdf = tree.nodes.get(bsdf_name)
                if bsdf is None:
                    raise ValueError('Material shader changed outside XR history')
                base = bsdf.inputs['Base Color']
                if base.links:
                    link = base.links[0]
                    if prior is None or (link.from_node.name, _socket_name(link.from_socket)) != prior:
                        raise ValueError('Prior Base Color input changed outside XR history')
                    tree.links.remove(link)
                image = _new_image(size, image_name)
                try:
                    _make_nodes(mat, bsdf, image, prior, base_color,
                                label=mix_name, image_label=tex_name,
                                uvmap=uvmap, uv_label=uv_label)
                except Exception:
                    if image.users == 0:
                        bpy.data.images.remove(image)
                    raise
        dest.append(src.pop())
        return True

    mesh.History.step = step
    mesh.History.release = staticmethod(release)
    mesh.History._xr_paint_085_history = True


def install_pages():
    # Existing Material Home currently has all twelve cells. Put Paint into
    # the Textures submenu rather than dropping its existing controls.
    current = tuple(menus.PAGES['MATERIAL_TEXTURES'])
    if not any(action == 'XR_PAINT_MENU' for _, action in current):
        menus.PAGES['MATERIAL_TEXTURES'] = current[:-1] + (
            ('PAINT IMAGE', 'XR_PAINT_MENU'), current[-1])
    menus.PAGES[_PAGE] = (
        ('NEW LAYER', 'XR_PAINT_NEW'),
        ('NEXT LAYER', 'XR_PAINT_NEXT'),
        ('PAINT', 'XR_PAINT_BRUSH'),
        ('ERASE', 'XR_PAINT_ERASE'),
        ('BRUSH -', 'XR_PAINT_RADIUS_DOWN'),
        ('BRUSH +', 'XR_PAINT_RADIUS_UP'),
        ('ALPHA -', 'XR_PAINT_OPACITY_DOWN'),
        ('ALPHA +', 'XR_PAINT_OPACITY_UP'),
        ('UV MIRROR', 'XR_PAINT_MIRROR_U'),
        ('FILL', 'XR_PAINT_FILL'),
        ('MORE', 'XR_PAINT_RES_MENU'),
        ('BACK', 'BACK'),
    )
    menus.PAGES[_RES_PAGE] = (
        ('256 PX', 'XR_PAINT_RES_256'),
        ('512 PX', 'XR_PAINT_RES_512'),
        ('1024 PX', 'XR_PAINT_RES_1024'),
        ('CLEAR', 'XR_PAINT_CLEAR'),
        ('SAVE PNG', 'XR_PAINT_SAVE'),
        ('BACK', 'BACK'),
    )
    menus.TITLES.update({_PAGE: 'VR TEXTURE PAINT', _RES_PAGE: 'PAINT IMAGE OPTIONS'})
    v065.TOOLTIPS.update({
        'XR_PAINT_MENU': ('VR Texture Paint', 'Edit native Blender image paint layers using controller UV rays'),
        'XR_PAINT_NEW': ('New Paint Layer', 'Create transparent image overlay without deleting existing texture links'),
        'XR_PAINT_BRUSH': ('Paint Surface', 'Release, aim, hold trigger to paint; offhand trigger cancels stroke'),
        'XR_PAINT_ERASE': ('Erase Paint', 'Reduce layer alpha without changing source texture'),
        'XR_PAINT_MIRROR_U': ('Mirror U Coordinates', 'Mirror paint within this UV map only, not across world geometry'),
        'XR_PAINT_SAVE': ('Export Texture PNG', 'Save active paint image as a PNG beside the .blend project'),
    })


def patch_runtime(Runtime):
    if getattr(Runtime, '_xr_paint_085_patched', False):
        return
    _history_patch()
    install_pages()
    previous_command, previous_tick, previous_cancel = (
        Runtime.command, Runtime.tick, Runtime.cancel_work)

    def cancel_work(self):
        _cancel(self, True)
        return previous_cancel(self)

    def tick(self, context):
        if (getattr(self, '_xr_paint_pending', None) is not None or
                getattr(self, '_xr_paint_release_required', False)):
            _tick(self, context)
            return
        return previous_tick(self, context)

    def command(self, context, action):
        menu = getattr(self, 'menu', None)
        if menu is None:
            return previous_command(self, context, action)
        if action == 'XR_PAINT_MENU':
            _open(self, context)
            return
        if menu.page in {_PAGE, _RES_PAGE}:
            if action == 'BACK':
                menu.page = ('MATERIAL_TEXTURES' if menu.page == _PAGE else _PAGE)
                return
            if action == 'XR_PAINT_RES_MENU':
                menu.page = _RES_PAGE
                return
            if action.startswith('XR_PAINT_RES_') and action != 'XR_PAINT_RES_MENU':
                self._xr_paint_resolution = int(action.rsplit('_', 1)[-1])
                self.status = 'NEW LAYER RESOLUTION / {}'.format(self._xr_paint_resolution)
                return
            if action == 'XR_PAINT_NEW':
                _create_layer(self, context)
                return
            if action == 'XR_PAINT_NEXT':
                _cycle(self, context)
                return
            if action in {'XR_PAINT_BRUSH', 'XR_PAINT_ERASE'}:
                _arm(self, context, action)
                return
            if action.startswith('XR_PAINT_RADIUS_'):
                step = 2 if action.endswith('UP') else -2
                self._xr_paint_radius = max(1, min(64, self._xr_paint_radius + step))
                self.status = 'BRUSH RADIUS / {} PX'.format(self._xr_paint_radius)
                return
            if action.startswith('XR_PAINT_OPACITY_'):
                delta = .1 if action.endswith('UP') else -.1
                self._xr_paint_opacity = max(.05, min(1., self._xr_paint_opacity + delta))
                self.status = 'PAINT OPACITY / {:.0f}%'.format(self._xr_paint_opacity*100)
                return
            if action == 'XR_PAINT_MIRROR_U':
                self._xr_paint_mirror_u = not self._xr_paint_mirror_u
                self.status = 'UV U-MIRROR / ' + ('ON' if self._xr_paint_mirror_u else 'OFF')
                return
            if action in {'XR_PAINT_FILL', 'XR_PAINT_CLEAR'}:
                _fill(self, context, empty=(action == 'XR_PAINT_CLEAR'))
                return
            if action == 'XR_PAINT_SAVE':
                _save(self, context)
                return
        return previous_command(self, context, action)

    Runtime.command = command
    Runtime.tick = tick
    Runtime.cancel_work = cancel_work
    Runtime._xr_paint_085_patched = True
