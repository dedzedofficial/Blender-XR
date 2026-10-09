# SPDX-License-Identifier: GPL-3.0-or-later
"""World-space axis handles picked and dragged by the dominant controller ray."""
from mathutils import Vector
from . import mesh

COLORS={'X':(1,.22,.18,1),'Y':(.2,1,.35,1),'Z':(.25,.55,1,1),'SIZE':(1,.8,.18,1)}


def parameter(origin, direction, anchor, axis):
    ray=direction.normalized();axis=axis.normalized();offset=origin-anchor
    dot=ray.dot(axis);denominator=1-dot*dot
    if denominator<0.002:
        return None
    ray_distance=(dot*axis.dot(offset)-ray.dot(offset))/denominator
    if ray_distance<0:
        return None
    along=(axis.dot(offset)-dot*ray.dot(offset))/denominator
    return along,ray_distance,(origin+ray*ray_distance-anchor-axis*along).length


class Handles:
    def __init__(self,anchor,axes,scale,viewer=None):
        self.anchor=Vector(anchor)
        self.axes=axes
        base=max(scale,1e-6)
        distance=(self.anchor-Vector(viewer)).length if viewer is not None else 0.0
        visual=max(base,min(base*8.0,distance*.35))
        self.visual_scale=visual
        self.length=visual*.30
        self.radius=visual*.04

    def pick(self,origin,direction):
        hits=[]
        for name,axis in self.axes:
            point=parameter(origin,direction,self.anchor,axis)
            if point and self.length*.14<=point[0]<=self.length*1.12 and point[2]<=self.radius:
                hits.append((point[1],name,axis))
        return min(hits,key=lambda hit:hit[0])[1:] if hits else None


def _edit_center_and_normal(obj):
    try:
        center=mesh.selected_center(obj)
    except ValueError:
        return None,None
    normal=mesh.selected_normal(obj)
    normal=obj.matrix_world.to_3x3()@normal
    return center,(normal.normalized() if normal.length>=1e-9 else None)


def make(context,tool,scale,viewer=None):
    if tool not in {'MOVE','SCALE','MOVE_FACE','SCALE_FACE','EXTRUDE','BEVEL','INSET'}:
        return None
    obj=context.view_layer.objects.active
    if not obj or obj.type!='MESH':
        return None
    if obj.mode=='OBJECT':
        if tool=='MOVE':
            axes=[(axis,Vector(vector)) for axis,vector in
                  (('X',(1,0,0)),('Y',(0,1,0)),('Z',(0,0,1)))]
        elif tool=='SCALE':
            axes=[('SIZE',Vector((1,1,1)).normalized())]
        else:
            return None
        return Handles(obj.matrix_world.translation,axes,scale,viewer)
    if obj.mode!='EDIT' or tool not in {'MOVE_FACE','SCALE_FACE','EXTRUDE','BEVEL','INSET'}:
        return None
    center,normal=_edit_center_and_normal(obj)
    if center is None:
        return None
    if tool in {'EXTRUDE','MOVE_FACE'}:
        axes=[(axis,Vector(vector)) for axis,vector in
              (('X',(1,0,0)),('Y',(0,1,0)),('Z',(0,0,1)))]
    else:
        if normal is None:
            return None
        axes=[('SIZE',normal)]
    return Handles(obj.matrix_world@center,axes,scale,viewer)
