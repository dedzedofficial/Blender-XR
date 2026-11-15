"""Real Blender checks for the 0.8.5 authoring completion and data preservation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Vector
import blender_xr
from blender_xr import drawing, menus, mesh, runtime
from blender_xr import native_modifiers_v080 as mods, native_lighting_v080 as lights
from blender_xr import color_studio_v080 as colors, join_split_v085 as parts


def refusal(call):
    try:
        call()
    except ValueError:
        return
    raise AssertionError('Unsafe operation was accepted')


def select(ctx, objects, active):
    for obj in tuple(ctx.selected_objects):
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    ctx.view_layer.objects.active = active


def run():
    blender_xr.register()
    ctx = bpy.context
    session = runtime.Runtime.__new__(runtime.Runtime)
    session.menu = drawing.Menu()
    session.history = mesh.History()
    session.settings = ctx.scene.blender_xr
    session.status = ''
    session.tool = 'SELECT'
    session.transaction = session.grab = session.air_grab = session.axis_move = None
    session._xr_gesture = session._weight_stroke = session.bone_drag = None
    try:
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        bpy.ops.mesh.primitive_cube_add()
        obj = ctx.object
        curve_data = bpy.data.curves.new('Path', 'CURVE')
        curve_data.dimensions = '3D'
        spline = curve_data.splines.new('POLY')
        spline.points.add(1)
        spline.points[0].co = (0, 0, 0, 1)
        spline.points[1].co = (3, 0, 0, 1)
        curve = bpy.data.objects.new('Curve target', curve_data)
        ctx.scene.collection.objects.link(curve)
        select(ctx, [obj, curve], obj)
        session.menu.page = 'MODIFIER_MENU'
        session.command(ctx, 'MOD_CURVE_EDIT_MENU')
        session.command(ctx, 'XR_CURVE_NEW')
        modifier = obj.modifiers[-1]
        session.command(ctx, 'XR_CURVE_TARGET')
        assert modifier.object == curve
        session.command(ctx, 'XR_CURVE_AXIS_NEG_Y')
        assert modifier.deform_axis == 'NEG_Y'
        assert session.history.step(True)
        assert modifier.deform_axis == 'POS_X'
        assert session.history.step(False)
        assert modifier.deform_axis == 'NEG_Y'
        session.command(ctx, 'XR_CURVE_TARGET_CLEAR')
        assert modifier.object is None
        assert session.history.step(True)
        assert modifier.object == curve
        select(ctx, [obj], obj)
        refusal(lambda: session.command(ctx, 'XR_CURVE_TARGET'))
        obj.modifiers.clear()
        session.history.clear()

        # Wrist colour entry changes preview only until explicit material apply.
        session.menu.page = 'COLOR_STUDIO'
        original_materials = len(obj.data.materials)
        session.command(ctx, 'STUDIO_HEX_INPUT')
        for char in '3366CC':
            session.command(ctx, 'STUDIO_HEX_CHAR_' + char)
        session.command(ctx, 'STUDIO_HEX_ACCEPT')
        assert all(abs(a-b) < 1e-5 for a,b in zip(session.settings.object_color[:3], (.2,.4,.8)))
        assert len(obj.data.materials) == original_materials
        before = tuple(session.settings.object_color)
        session.command(ctx, 'STUDIO_HEX_INPUT')
        session.command(ctx, 'STUDIO_HEX_CHAR_A')
        refusal(lambda: session.command(ctx, 'STUDIO_HEX_ACCEPT'))
        session.command(ctx, 'STUDIO_HEX_CANCEL')
        assert tuple(session.settings.object_color) == before
        assert colors.wheel_hs(.5,.5) is None
        assert colors.wheel_hs(.025,.09)[1] == 0
        session.command(ctx, 'STUDIO_WHEEL')
        session.menu.visible = session.menu.ready = True
        session.menu.center = Vector((0, 0, 0))
        session.menu.right = Vector((1, 0, 0))
        session.menu.up = Vector((0, 1, 0))
        session.menu.normal = Vector((0, 0, 1))
        session.menu.scale = 1.
        hit, _ = session.menu.hit(Vector((.025,.09,1.)), Vector((0,0,-1)))
        assert hit == 'STUDIO_WHEEL_PICK'
        # The lower edge of the wheel must never overlap the brightness buttons.
        hit, _ = session.menu.hit(Vector((.025,-.01,1.)), Vector((0,0,-1)))
        assert hit == 'STUDIO_VALUE_UP'
        session.menu.wheel_hs = (.5, 1.)
        session.command(ctx, 'STUDIO_WHEEL_PICK')
        assert session.settings.object_color[0] < 1e-5
        session.command(ctx, 'STUDIO_RGB')
        session.command(ctx, 'STUDIO_RGB_R_UP')
        assert abs(session.settings.object_color[0] - .05) < 1e-5

        session.command(ctx, 'STUDIO_HSV')
        session.color_hsv = [.7, 0., .5]
        session.menu.slider_value = .8
        session.command(ctx, 'STUDIO_HUE_SLIDER')
        assert abs(session.color_hsv[0] - .8) < 1e-6

        # Hue selected while black must survive raising brightness.
        colors._read_color(session, (0., 0., 0., 1.))
        session.command(ctx, 'STUDIO_WHEEL')
        session.menu.wheel_hs = (.5, 1.)
        session.command(ctx, 'STUDIO_WHEEL_PICK')
        session.command(ctx, 'STUDIO_VALUE_UP')
        assert session.settings.object_color[0] < 1e-6
        assert abs(session.settings.object_color[1] - .05) < 1e-6

        # Native lights: temperature is reversible; flicker is explicit native keys.
        light = bpy.data.lights.new('Test Light', 'POINT')
        lamp = bpy.data.objects.new('Lamp', light)
        ctx.scene.collection.objects.link(lamp)
        select(ctx, [lamp], lamp)
        session.command(ctx, 'XR_LIGHT_MENU')
        session.command(ctx, 'XR_LIGHT_OPEN_ACTIVE')
        session.command(ctx, 'XR_LIGHT_COLOR_MENU')
        session.command(ctx, 'XR_LIGHT_KELVIN_2700')
        warm = tuple(light.color)
        assert warm[0] > warm[2]
        assert session.history.step(True)
        assert tuple(light.color) == (1.,1.,1.)
        assert session.history.step(False)
        assert tuple(light.color) == warm
        session.command(ctx, 'BACK')
        session.command(ctx, 'XR_LIGHT_PRESET_MENU')
        light.energy = 100.
        session.command(ctx, 'XR_LIGHT_FLICKER')
        action = light.animation_data.action
        assert action is not None
        assert len(lights._action_signature(action)[0][2]) == 7
        ctx.scene.frame_set(10)
        assert abs(light.energy - 40.) < 1e-4
        refusal(lambda: session.command(ctx, 'XR_LIGHT_FLICKER'))
        assert session.history.step(True)
        assert light.animation_data.action is None and light.energy == 100.
        assert session.history.step(False)
        assert light.animation_data.action == action
        assert session.history.step(True)
        session.history.clear()

        # Separate selected vertices preserves originals; redo retains group names/weights.
        select(ctx, [obj], obj)
        group = obj.vertex_groups.new(name='PreservedWeight')
        group.add(list(range(len(obj.data.vertices))), .7, 'REPLACE')
        group.lock_weight = True
        for vertex in obj.data.vertices:
            vertex.select = vertex.co.z > 0
        for edge in obj.data.edges:
            edge.select = all(obj.data.vertices[i].select for i in edge.vertices)
        for face in obj.data.polygons:
            face.select = all(obj.data.vertices[i].select for i in face.vertices)
        session.command(ctx, 'XR_JOIN_MENU')
        session.command(ctx, 'XR_JOIN_SELECTED')
        assert obj.hide_get()
        outputs = list(ctx.selected_objects)
        assert len(outputs) == 2
        assert sum(len(part.data.vertices) for part in outputs) >= 8
        assert session.history.step(True)
        assert not obj.hide_get()
        assert session.history.step(False)
        for output in ctx.selected_objects:
            assert output.vertex_groups['PreservedWeight'].lock_weight
            assert abs(output.vertex_groups['PreservedWeight'].weight(0) - .7) < 1e-5
        assert session.history.step(True)
        select(ctx, [obj], obj)
        session.command(ctx, 'XR_JOIN_EXTRACT')
        assert not obj.hide_get()
        extracted = ctx.view_layer.objects.active
        assert extracted != obj and len(extracted.data.vertices) == 4
        assert len(obj.data.vertices) == 8
        assert session.history.step(True)
        for vertex in obj.data.vertices:
            vertex.select = True
        select(ctx, [obj], obj)
        refusal(lambda: session.command(ctx, 'XR_JOIN_SELECTED'))
        assert len(obj.data.vertices) == 8 and not obj.hide_get()
        for name, page in menus.PAGES.items():
            assert len(page) <= 12, (name, len(page))
        print('PASS v0.8.5 Curve modifier, wrist colour entry, temperature, flicker, extraction and weighted redo')
    finally:
        session.history.clear()
        blender_xr.unregister()


if __name__ == '__main__':
    run()
