# SPDX-License-Identifier: GPL-3.0-or-later
"""Low-overhead scene statistics for the Blender XR sidebar."""
import time

_CACHE = {'key': None, 'value': None, 'time': 0.0}


def invalidate():
    _CACHE['key'] = None
    _CACHE['value'] = None
    _CACHE['time'] = 0.0


def _visible_objects(context):
    visible = []
    for obj in context.view_layer.objects:
        try:
            shown = obj.visible_get(view_layer=context.view_layer)
        except TypeError:
            shown = obj.visible_get()
        if shown:
            visible.append(obj)
    return visible


def _cache_key(context, visible):
    active = context.view_layer.objects.active
    mesh_signature = []
    for obj in visible:
        if obj.type == 'MESH':
            data = obj.data
            mesh_signature.append((
                obj.name_full, len(data.vertices), len(data.edges), len(data.polygons),
                tuple(slot.material.name_full if slot.material else None for slot in obj.material_slots),
            ))
    return (
        tuple((obj.name_full, obj.type) for obj in visible),
        tuple(mesh_signature),
        tuple(obj.name_full for obj in visible if obj.select_get()),
        active.name_full if active else None,
    )


def scene_stats(context, max_age=0.35):
    visible = _visible_objects(context)
    now = time.monotonic()
    key = _cache_key(context, visible)
    if _CACHE['key'] == key and _CACHE['value'] is not None and now - _CACHE['time'] <= max_age:
        return _CACHE['value']

    meshes = [obj for obj in visible if obj.type == 'MESH']
    vertices = edges = faces = triangles = 0
    material_names = set()
    active = context.view_layer.objects.active
    active_stats = None
    for obj in meshes:
        data = obj.data
        vertex_count, edge_count, face_count = len(data.vertices), len(data.edges), len(data.polygons)
        triangle_count = sum(max(0, len(poly.vertices) - 2) for poly in data.polygons)
        vertices += vertex_count
        edges += edge_count
        faces += face_count
        triangles += triangle_count
        if obj == active:
            active_stats = {
                'name': obj.name,
                'vertices': vertex_count,
                'edges': edge_count,
                'faces': face_count,
                'triangles': triangle_count,
            }
        for slot in obj.material_slots:
            if slot.material:
                material_names.add(slot.material.name_full)

    result = {
        'objects': len(visible),
        'selected': sum(1 for obj in visible if obj.select_get()),
        'meshes': len(meshes),
        'vertices': vertices,
        'edges': edges,
        'faces': faces,
        'triangles': triangles,
        'materials': len(material_names),
        'active': active_stats,
    }
    _CACHE.update(key=key, value=result, time=now)
    return result
