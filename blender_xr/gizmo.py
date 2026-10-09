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
    def __init__(self,anchor,axes,scale):
        self.anchor=Vector(anchor)
        self.axes=axes
        self.length=max(scale,1e-6)*.30
        self.radius=max(scale,1e-6)*.025

    def pick(self,origin,direction):
        hits=[]
        for name,axis in self.axes:
            point=parameter(origin,direction,self.anchor,axis)
            if point and self.length*.16<=point[0]<=self.length*1.1 and point[2]<=self.radius:
                hits.append((point[1],name,axis))
        return min(hits,key=lambda hit:hit[0])[1:] if hits else None


def make(context,tool,scale):
    if tool not in {'MOVE','EXTRUDE','BEVEL','INSET'}:return None
    obj=context.view_layer.objects.active
    if not obj or obj.type!='MESH':return None
    if tool=='MOVE' and obj.mode=='OBJECT':
        return Handles(obj.matrix_world.translation,
                       [(axis,Vector(vector)) for axis,vector in
                        (('X',(1,0,0)),('Y',(0,1,0)),('Z',(0,0,1)))],scale)
    if tool not in {'EXTRUDE','BEVEL','INSET'} or obj.mode!='EDIT':return None
    bm=mesh.editable(obj)
    faces=[face for face in bm.faces if face.select and not face.hide]
    if not faces:return None
    weight=sum(face.calc_area() for face in faces)
    if weight<=1e-9:return None
    center=sum((face.calc_center_median()*face.calc_area() for face in faces),Vector())/weight
    if tool=='EXTRUDE':
        axes=[(axis,Vector(vector)) for axis,vector in
              (('X',(1,0,0)),('Y',(0,1,0)),('Z',(0,0,1)))]
    else:
        normal=sum((face.normal*face.calc_area() for face in faces),Vector())
        normal=obj.matrix_world.to_3x3()@normal
        if normal.length<1e-9:return None
        axes=[('SIZE',normal.normalized())]
    return Handles(obj.matrix_world@center,axes,scale)
