# SPDX-License-Identifier: GPL-3.0-or-later
"""UV mapping helpers used by XR Mesh v0.6.

The helpers deliberately work from Edit Mesh/BMesh data so the same operations
can be called from the headset menu and the normal Blender sidebar. Blender's
native unwrap operators are preferred where they are context-safe; deterministic
fallbacks keep the workflow usable in restricted/background contexts.
"""
import math
import bpy
import bmesh
from mathutils import Vector


def editable(obj, require_edit=True):
    if not obj or obj.type != 'MESH':
        raise ValueError('Select a mesh object first')
    if obj.library or obj.data.library:
        raise ValueError('Use a local mesh object')
    if require_edit and obj.mode != 'EDIT':
        raise ValueError('Enter Edit Mode for UV tools')
    return obj


def _edit(obj):
    obj = editable(obj, True)
    bm = bmesh.from_edit_mesh(obj.data)
    uv = bm.loops.layers.uv.verify()
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    return bm, uv


def _selected_faces(bm):
    faces = [face for face in bm.faces if face.is_valid and face.select and not face.hide]
    if not faces:
        raise ValueError('Select one or more faces first')
    return faces


def _update(obj):
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    obj.data.update()


def ensure_layer(obj):
    bm, _uv = _edit(obj)
    _update(obj)
    layer = obj.data.uv_layers.active
    if layer:
        return layer.name
    return 'UVMap'


def _native_uv(op, **kwargs):
    """Try a native Blender UV operator without making it a hard dependency."""
    try:
        result = op(**kwargs)
    except (RuntimeError, TypeError, AttributeError):
        return False
    return bool(result and 'FINISHED' in result)


def _project_axes(normal):
    normal = Vector(normal)
    values = [abs(normal.x), abs(normal.y), abs(normal.z)]
    axis = values.index(max(values))
    return ((1, 2) if axis == 0 else (0, 2) if axis == 1 else (0, 1))


def _normalize_points(points, margin=0.02):
    if not points:
        return []
    min_x = min(point.x for point in points)
    max_x = max(point.x for point in points)
    min_y = min(point.y for point in points)
    max_y = max(point.y for point in points)
    span_x = max(max_x - min_x, 1e-8)
    span_y = max(max_y - min_y, 1e-8)
    usable = max(0.0, 1.0 - margin * 2.0)
    return [Vector((margin + (point.x - min_x) / span_x * usable,
                    margin + (point.y - min_y) / span_y * usable)) for point in points]


def planar_project(obj):
    bm, uv = _edit(obj)
    faces = _selected_faces(bm)
    normal = Vector()
    for face in faces:
        normal += face.normal
    axes = _project_axes(normal if normal.length > 1e-8 else Vector((0, 0, 1)))
    loops = [loop for face in faces for loop in face.loops]
    points = [Vector((loop.vert.co[axes[0]], loop.vert.co[axes[1]])) for loop in loops]
    for loop, point in zip(loops, _normalize_points(points)):
        loop[uv].uv = point
    _update(obj)
    return len(faces)


def _fallback_face_grid(obj, cube=False):
    bm, uv = _edit(obj)
    faces = _selected_faces(bm)
    columns = max(1, math.ceil(math.sqrt(len(faces))))
    rows = max(1, math.ceil(len(faces) / columns))
    for index, face in enumerate(faces):
        axes = _project_axes(face.normal) if cube else (0, 1)
        raw = [Vector((loop.vert.co[axes[0]], loop.vert.co[axes[1]])) for loop in face.loops]
        normalized = _normalize_points(raw, 0.08)
        col = index % columns
        row = index // columns
        for loop, point in zip(face.loops, normalized):
            loop[uv].uv = Vector(((col + point.x) / columns,
                                  (row + point.y) / rows))
    _update(obj)
    return len(faces)


def unwrap(obj):
    bm, _uv = _edit(obj)
    faces = _selected_faces(bm)
    if _native_uv(bpy.ops.uv.unwrap, method='ANGLE_BASED', margin=0.001):
        _update(obj)
        return len(faces)
    return planar_project(obj)


def smart_project(obj):
    bm, _uv = _edit(obj)
    faces = _selected_faces(bm)
    if _native_uv(bpy.ops.uv.smart_project, angle_limit=math.radians(66.0), island_margin=0.02):
        _update(obj)
        return len(faces)
    return _fallback_face_grid(obj, cube=True)


def cube_project(obj):
    bm, _uv = _edit(obj)
    faces = _selected_faces(bm)
    if _native_uv(bpy.ops.uv.cube_project):
        _update(obj)
        return len(faces)
    return _fallback_face_grid(obj, cube=True)


def mark_seams(obj, clear=False):
    bm, _uv = _edit(obj)
    edges = [edge for edge in bm.edges if edge.is_valid and edge.select and not edge.hide]
    if not edges:
        # Face selection normally implies its boundary edges, but keep this
        # useful even if selection flushing was disabled by another tool.
        faces = _selected_faces(bm)
        edges = list({edge for face in faces for edge in face.edges})
    for edge in edges:
        edge.seam = not clear
    _update(obj)
    return len(edges)


def _selected_loops(obj):
    bm, uv = _edit(obj)
    faces = _selected_faces(bm)
    return bm, uv, faces, [loop for face in faces for loop in face.loops]


def transform(obj, move=(0.0, 0.0), rotate=0.0, scale=1.0):
    bm, uv, faces, loops = _selected_loops(obj)
    if not loops:
        raise ValueError('Select one or more faces first')
    # UV coordinates are 2D vectors. An explicit 2D accumulator avoids
    # Blender-version-dependent Vector() defaults (which are 3D in 4.x/5.x).
    center = sum((Vector(loop[uv].uv) for loop in loops), Vector((0.0, 0.0))) / len(loops)
    angle = math.radians(float(rotate))
    cosine, sine = math.cos(angle), math.sin(angle)
    offset = Vector((float(move[0]), float(move[1])))
    factor = max(1e-4, float(scale))
    for loop in loops:
        value = (Vector(loop[uv].uv) - center) * factor
        value = Vector((value.x * cosine - value.y * sine,
                        value.x * sine + value.y * cosine))
        loop[uv].uv = center + value + offset
    _update(obj)
    return len(faces)


def reset(obj):
    bm, uv = _edit(obj)
    faces = _selected_faces(bm)
    for face in faces:
        count = max(1, len(face.loops))
        for index, loop in enumerate(face.loops):
            angle = math.tau * index / count + math.pi * 0.25
            loop[uv].uv = Vector((0.5 + math.cos(angle) * 0.46,
                                  0.5 + math.sin(angle) * 0.46))
    _update(obj)
    return len(faces)


def _face_islands(faces):
    selected = set(faces)
    islands = []
    while selected:
        seed = selected.pop()
        island = {seed}
        stack = [seed]
        while stack:
            face = stack.pop()
            for edge in face.edges:
                if edge.seam:
                    continue
                for linked in edge.link_faces:
                    if linked in selected:
                        selected.remove(linked)
                        island.add(linked)
                        stack.append(linked)
        islands.append(tuple(island))
    return islands


def pack_islands(obj, margin=0.04):
    """Pack selected seam-delimited islands into a deterministic square grid."""
    bm, uv = _edit(obj)
    faces = _selected_faces(bm)
    islands = _face_islands(faces)
    columns = max(1, math.ceil(math.sqrt(len(islands))))
    rows = max(1, math.ceil(len(islands) / columns))
    margin = max(0.0, min(0.2, float(margin)))
    for index, island in enumerate(islands):
        loops = [loop for face in island for loop in face.loops]
        points = [Vector(loop[uv].uv) for loop in loops]
        normalized = _normalize_points(points, margin)
        col = index % columns
        row = index // columns
        for loop, point in zip(loops, normalized):
            loop[uv].uv = Vector(((col + point.x) / columns,
                                  (row + point.y) / rows))
    _update(obj)
    return len(islands)


def preview_segments(obj, limit=320):
    """Return normalized UV line segments for the simple headset preview."""
    if not obj or obj.type != 'MESH':
        return []
    segments = []
    points = []
    if obj.mode == 'EDIT':
        bm, uv = _edit(obj)
        faces = [face for face in bm.faces if face.is_valid and not face.hide and face.select]
        if not faces:
            faces = [face for face in bm.faces if face.is_valid and not face.hide]
        for face in faces:
            loops = list(face.loops)
            for index, loop in enumerate(loops):
                a = Vector(loop[uv].uv)
                b = Vector(loops[(index + 1) % len(loops)][uv].uv)
                segments.append((a, b)); points.extend((a, b))
                if len(segments) >= limit:
                    break
            if len(segments) >= limit:
                break
    else:
        layer = obj.data.uv_layers.active
        if not layer:
            return []
        for polygon in obj.data.polygons:
            indices = list(polygon.loop_indices)
            for index, loop_index in enumerate(indices):
                next_index = indices[(index + 1) % len(indices)]
                a = Vector(layer.data[loop_index].uv)
                b = Vector(layer.data[next_index].uv)
                segments.append((a, b)); points.extend((a, b))
                if len(segments) >= limit:
                    break
            if len(segments) >= limit:
                break
    if not points:
        return []
    min_x = min(point.x for point in points); max_x = max(point.x for point in points)
    min_y = min(point.y for point in points); max_y = max(point.y for point in points)
    span_x = max(max_x - min_x, 1e-8); span_y = max(max_y - min_y, 1e-8)
    return [((a.x - min_x) / span_x, (a.y - min_y) / span_y,
             (b.x - min_x) / span_x, (b.y - min_y) / span_y) for a, b in segments]


def summary(obj):
    if not obj or obj.type != 'MESH':
        return 'NO MESH'
    layer = obj.data.uv_layers.active
    name = layer.name if layer else 'NO UV'
    if obj.mode != 'EDIT':
        return name.upper()
    bm = bmesh.from_edit_mesh(obj.data)
    count = sum(1 for face in bm.faces if face.select and not face.hide)
    return (name + ' / F' + str(count)).upper()
