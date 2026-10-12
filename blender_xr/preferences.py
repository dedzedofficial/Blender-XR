# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistent XR Mesh user preferences.

Scene properties remain the live session values for backwards compatibility;
these preferences simply remember the user's usual setup between Blender files.
"""
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty

FIELDS = (
    'dominant_hand','controller_family','input_source','finger_touch','bridge_port',
    'step','bevel_segments','move_speed','fly_mode','fast_flight','turn_mode',
    'turn_angle','turn_speed','grab_air','primitive_size','placement_distance',
    'show_statistics',
)
_RESTORED_SCENES = set()
_PENDING_SCENES = set()
_TIMER_SCHEDULED = False
_DRAW_WRITE_ERROR = 'Writing to ID classes in this context is not allowed'


class BXR_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    dominant_hand: EnumProperty(name='Dominant hand',items=[('RIGHT','Right',''),('LEFT','Left','')],default='RIGHT')
    controller_family: EnumProperty(name='Controller family',items=[('AUTO','Automatic',''),('META','Meta',''),('VALVE','Valve / SteamVR','')],default='AUTO')
    input_source: EnumProperty(name='Input',items=[('CONTROLLERS','Controllers',''),('STEAMVR_HANDS','Finger bridge','')],default='CONTROLLERS')
    finger_touch: BoolProperty(default=False)
    bridge_port: IntProperty(default=39540,min=1024,max=65535)
    step: FloatProperty(default=0.03,min=0.0001,max=10)
    bevel_segments: IntProperty(default=2,min=1,max=8)
    move_speed: FloatProperty(default=3.0,min=0.1,max=1000)
    fly_mode: BoolProperty(default=True)
    fast_flight: BoolProperty(default=False)
    turn_mode: EnumProperty(items=[('SNAP','Snap',''),('SMOOTH','Smooth','')],default='SNAP')
    turn_angle: FloatProperty(default=30,min=15,max=90)
    turn_speed: FloatProperty(default=90,min=15,max=180)
    grab_air: BoolProperty(default=True)
    primitive_size: FloatProperty(default=0.5,min=0.01,max=10)
    placement_distance: FloatProperty(default=1.5,min=0.1,max=10)
    show_statistics: BoolProperty(default=True)

    def draw(self, context):
        layout=self.layout
        layout.label(text='XR Mesh remembers controller, movement, modeling and UI settings automatically.')


def get(context=None):
    context = context or bpy.context
    addon = context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


def capture(settings, context=None):
    prefs = get(context)
    if not prefs:
        return
    for name in FIELDS:
        if hasattr(settings,name) and hasattr(prefs,name):
            setattr(prefs,name,getattr(settings,name))


def restore(settings, context=None):
    prefs = get(context)
    if not prefs:
        return False
    for name in FIELDS:
        if hasattr(settings,name) and hasattr(prefs,name):
            setattr(settings,name,getattr(prefs,name))
    return True


def _scene_key(scene):
    try:
        return int(scene.as_pointer())
    except ReferenceError:
        return None


def _draw_write_blocked(exc):
    return _DRAW_WRITE_ERROR in str(exc)


def _queue_restore(key):
    global _TIMER_SCHEDULED
    _PENDING_SCENES.add(key)
    if not _TIMER_SCHEDULED:
        _TIMER_SCHEDULED = True
        bpy.app.timers.register(_restore_pending, first_interval=0.0)


def _restore_pending():
    """Timer callback: restore saved values after Blender leaves UI draw context."""
    global _TIMER_SCHEDULED
    _TIMER_SCHEDULED = False
    if not _PENDING_SCENES:
        return None

    live_keys = set()
    for scene in tuple(bpy.data.scenes):
        key = _scene_key(scene)
        if key is None:
            continue
        live_keys.add(key)
        if key not in _PENDING_SCENES:
            continue
        if not hasattr(scene, 'blender_xr'):
            _PENDING_SCENES.discard(key)
            continue
        try:
            restored = restore(scene.blender_xr)
        except (AttributeError, RuntimeError) as exc:
            if not _draw_write_blocked(exc):
                raise
            restored = False
        if restored:
            _PENDING_SCENES.discard(key)
            _RESTORED_SCENES.add(key)

    _PENDING_SCENES.intersection_update(live_keys)
    if _PENDING_SCENES:
        _TIMER_SCHEDULED = True
        return 0.05
    return None


def ensure(settings, context=None):
    """Restore once per Scene; defer only when Blender forbids writes during UI drawing."""
    context = context or bpy.context
    scene = getattr(context, 'scene', None)
    if scene is None:
        return False
    key = _scene_key(scene)
    if key is None:
        return False
    if key in _RESTORED_SCENES:
        return True

    try:
        restored = restore(settings, context)
    except (AttributeError, RuntimeError) as exc:
        if not _draw_write_blocked(exc):
            raise
        _queue_restore(key)
        return False

    if restored:
        _PENDING_SCENES.discard(key)
        _RESTORED_SCENES.add(key)
        return True
    return False


def reset_restore_state():
    _RESTORED_SCENES.clear()
    _PENDING_SCENES.clear()
