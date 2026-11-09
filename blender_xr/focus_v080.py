# SPDX-License-Identifier: GPL-3.0-or-later
"""VR creator focus: reversible isolation, X-Ray and a read-only scene pulse.

All temporary visibility is restored when the XR session closes, including a
failed or interrupted session. Geometry, materials and rendering are untouched.
"""
import bpy
from . import menus, armature_v076


def focus_targets(context):
    selection = {o for o in context.selected_objects if o.visible_get()}
    if not selection:
        raise ValueError('Select an object before isolating the scene')
    # Keep each mesh and the armature that deforms it visible together.
    for obj in tuple(selection):
        if obj.type == 'MESH':
            if obj.parent is not None and obj.parent.type == 'ARMATURE':
                selection.add(obj.parent)
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object is not None:
                    selection.add(mod.object)
        elif obj.type == 'ARMATURE':
            for other in context.view_layer.objects:
                if other.type == 'MESH' and (
                    other.parent == obj or any(
                        m.type == 'ARMATURE' and m.object == obj
                        for m in other.modifiers)):
                    selection.add(other)
    return selection


def scene_pulse(context):
    objects = tuple(context.view_layer.objects)
    selection = sum(o.select_get() for o in objects)
    meshes = [o for o in objects if o.type == 'MESH']
    triangles = sum(sum(max(0, len(face.vertices) - 2)
                        for face in o.data.polygons) for o in meshes)
    return 'SCENE / {} OBJECTS / {} SELECTED / {} MESHES / {} TRIS'.format(
        len(objects), selection, len(meshes), triangles)


class FocusState:
    def __init__(self):
        self.hidden = None
        self.view_layer = None
        self.shading = None
        self.xray_before = None
        self.armatures_before = None
        self.select_through = False

    def isolate(self, context):
        if self.hidden is not None:
            self.restore_isolation()
            return False
        keep = focus_targets(context)
        view_layer = context.view_layer
        snapshot = [(obj, obj.hide_get(view_layer=view_layer))
                    for obj in view_layer.objects]
        try:
            for obj, hidden in snapshot:
                if obj not in keep and not hidden:
                    obj.hide_set(True, view_layer=view_layer)
        except (RuntimeError, ReferenceError, TypeError, ValueError):
            for obj, hidden in snapshot:
                try:
                    obj.hide_set(hidden, view_layer=view_layer)
                except (RuntimeError, ReferenceError, TypeError, ValueError):
                    pass
            raise
        self.hidden = snapshot
        self.view_layer = view_layer
        return True

    def restore_isolation(self):
        if self.hidden is None:
            return
        snapshot, view_layer = self.hidden, self.view_layer
        self.hidden = None
        self.view_layer = None
        for obj, hidden in snapshot:
            try:
                # Deleted objects are never recreated merely to restore a view.
                if bpy.data.objects.get(obj.name) == obj:
                    obj.hide_set(hidden, view_layer=view_layer)
            except (RuntimeError, ReferenceError, TypeError, ValueError):
                pass

    def toggle_xray(self, context):
        area = context.area
        if area is None or area.type != 'VIEW_3D':
            raise ValueError('X-Ray requires an active Blender 3D View')
        shading = area.spaces.active.shading
        if self.shading is None:
            self.shading = shading
            self.xray_before = bool(shading.show_xray)
            self.armatures_before = [
                (obj, obj.show_in_front)
                for obj in context.view_layer.objects if obj.type == 'ARMATURE']
            shading.show_xray = True
            for obj, _prior in self.armatures_before:
                obj.show_in_front = True
            return True
        self.restore_xray()
        return False

    def restore_xray(self):
        if self.shading is None:
            return
        try:
            self.shading.show_xray = self.xray_before
        except (ReferenceError, AttributeError, RuntimeError):
            pass
        for obj, value in self.armatures_before or ():
            try:
                if bpy.data.objects.get(obj.name) == obj:
                    obj.show_in_front = value
            except (ReferenceError, RuntimeError):
                pass
        self.shading = None
        self.xray_before = None
        self.armatures_before = None
        self.select_through = False

    def restore(self):
        self.restore_isolation()
        self.restore_xray()
        self.select_through = False


def install_menu():
    menus.PAGES['TRAVEL'] = tuple(
        list(menus.PAGES['TRAVEL'][:-1])
        + [('FOCUS', 'FOCUS_MENU'), ('TOOLS', 'BACK')])
    menus.PAGES['FOCUS_MENU'] = (
        ('ISOLATE', 'FOCUS_ISOLATE'), ('RESTORE', 'FOCUS_RESTORE'),
        ('X-RAY', 'FOCUS_XRAY'), ('PICK BONE', 'FOCUS_PICK'),
        ('SCENE PULSE', 'FOCUS_STATS'), ('BACK', 'BACK'))
    menus.TITLES['FOCUS_MENU'] = 'SCENE FOCUS / X-RAY'


def patch_runtime(Runtime):
    if getattr(Runtime, '_v080_scene_focus', False):
        return
    install_menu()
    old_init = Runtime.__init__
    old_command = Runtime.command
    old_cleanup = Runtime.cleanup
    old_object_hit = Runtime.object_hit

    def init(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        self.focus_state = FocusState()

    def command(self, context, action):
        if action == 'FOCUS_MENU':
            if any((self.transaction, self.grab, self.axis_move, self.air_grab,
                    getattr(self, '_xr_gesture', None),
                    getattr(self, '_weight_stroke', None))):
                raise ValueError('Finish the active edit before opening Focus')
            self.menu.page = 'FOCUS_MENU'
            self.status = 'FOCUS / REVEAL, X-RAY, PICK, SCENE PULSE'
            return
        if action == 'BACK' and self.menu.page == 'FOCUS_MENU':
            self.menu.page = 'TRAVEL'
            return
        if action in {'FOCUS_ISOLATE', 'FOCUS_RESTORE', 'FOCUS_XRAY',
                      'FOCUS_PICK', 'FOCUS_STATS'}:
            state = getattr(self, 'focus_state', None)
            if state is None:
                state = self.focus_state = FocusState()
            if action == 'FOCUS_STATS':
                self.status = scene_pulse(context)
                return
            if getattr(self, '_weight_stroke', None) is not None:
                raise ValueError('Release the brush before changing visibility')
            if action == 'FOCUS_ISOLATE':
                enabled = state.isolate(context)
                self.status = 'FOCUS ON / SELECTED RIG AND MESH' if enabled else 'FOCUS OFF / SCENE RESTORED'
            elif action == 'FOCUS_RESTORE':
                state.restore()
                self.status = 'FOCUS / ORIGINAL VISIBILITY RESTORED'
            elif action == 'FOCUS_XRAY':
                enabled = state.toggle_xray(context)
                self.status = 'X-RAY ON / ARMS IN FRONT' if enabled else 'X-RAY OFF / VIEW RESTORED'
            else:
                if state.shading is None and not state.select_through:
                    raise ValueError('Enable X-Ray before pick-through')
                state.select_through = not state.select_through
                self.status = ('BONE PICK-THROUGH ON' if state.select_through
                               else 'BONE PICK-THROUGH OFF')
            return
        return old_command(self, context, action)

    def object_hit(self, context, origin, direction):
        state = getattr(self, 'focus_state', None)
        if state is not None and state.select_through:
            obj = context.view_layer.objects.active
            if obj is not None and obj.type == 'ARMATURE' and obj.mode in {'POSE', 'EDIT'}:
                bone = armature_v076.ray_pick_bone(
                    context, origin, direction, only_active=True)
                if bone:
                    return bone[2], bone[4]
        return old_object_hit(self, context, origin, direction)

    def cleanup(self, context):
        try:
            state = getattr(self, 'focus_state', None)
            if state is not None:
                state.restore()
        finally:
            return old_cleanup(self, context)

    Runtime.__init__ = init
    Runtime.command = command
    Runtime.object_hit = object_hit
    Runtime.cleanup = cleanup
    Runtime._v080_scene_focus = True
