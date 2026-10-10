# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistent Blender XR user preferences.

Scene properties remain the live session values for backwards compatibility;
these preferences simply remember the user's usual setup between Blender files.
"""
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty

FIELDS = (
    'dominant_hand','controller_family','input_source','finger_touch','bridge_port',
    'step','bevel_segments','move_speed','fly_mode','fast_flight','turn_mode',
    'turn_angle','turn_speed','grab_air','primitive_size','placement_distance',
)


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

    def draw(self, context):
        layout=self.layout
        layout.label(text='Blender XR remembers the main controller, movement and modeling settings automatically.')


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
        return
    for name in FIELDS:
        if hasattr(settings,name) and hasattr(prefs,name):
            setattr(settings,name,getattr(prefs,name))
