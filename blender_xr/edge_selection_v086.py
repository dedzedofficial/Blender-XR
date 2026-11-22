# SPDX-License-Identifier: GPL-3.0-or-later
"""Conservative, topology-aware edge flow selection for the XR mesh editor.

An edge loop continues straight through regular, four-valence quad vertices.
An edge ring crosses the opposite edge of successive visible quad faces.
Boundary, seam and sharp chains continue while the path is unambiguous.

Poles, non-manifold junctions, hidden edges/faces and ambiguous branches are
deliberate stopping points. No mesh mutation or Blender operator context is
used by these pure BMesh traversal helpers.
"""


def _visible_edge(edge):
    return edge.is_valid and not edge.hide and all(
        v.is_valid and not v.hide for v in edge.verts)


def _visible_face(face):
    return (face.is_valid and not face.hide and
            all(v.is_valid and not v.hide for v in face.verts) and
            all(_visible_edge(edge) for edge in face.edges))


def _regular_successor(edge, vertex):
    """Across a regular quad vertex, choose the *unique* opposite edge.

    At a regular quad interior vertex all four incident faces are visible,
    and the opposite edge is the one sharing no face with the incoming edge.
    This avoids walking through a pole, triangle junction or hidden geometry.
    """
    if not _visible_edge(edge) or vertex not in edge.verts:
        return None
    edges = tuple(e for e in vertex.link_edges if _visible_edge(e))
    faces = tuple(f for f in vertex.link_faces if _visible_face(f))
    if len(edges) != 4 or len(faces) != 4 or any(len(f.verts) != 4 for f in faces):
        return None
    if not edge.is_manifold:
        return None
    incoming_faces = frozenset(face for face in edge.link_faces if _visible_face(face))
    candidates = [other for other in edges
                  if other != edge and other.is_manifold and
                  not incoming_faces.intersection(other.link_faces)]
    return candidates[0] if len(candidates) == 1 else None


def _walk_loop(seed):
    """Return a contiguous non-branching edge loop in both directions."""
    found = {seed}
    for endpoint in seed.verts:
        previous, vertex = seed, endpoint
        while True:
            next_edge = _regular_successor(previous, vertex)
            if next_edge is None or next_edge in found:
                break
            found.add(next_edge)
            vertex = next_edge.other_vert(vertex)
            previous = next_edge
    return found


def _ring_successors(edge):
    """Find quad-opposite edges across both sides of one selected edge."""
    if not _visible_edge(edge) or not edge.is_manifold:
        return ()
    output = []
    for face in edge.link_faces:
        if not _visible_face(face) or len(face.verts) != 4:
            continue
        opposites = [other for other in face.edges
                     if other != edge and _visible_edge(other) and
                     not any(vertex in edge.verts for vertex in other.verts)]
        if len(opposites) == 1:
            output.append(opposites[0])
    return tuple(output)


def _walk_ring(seed):
    found = {seed}
    pending = [seed]
    while pending:
        for edge in _ring_successors(pending.pop()):
            if edge not in found:
                found.add(edge)
                pending.append(edge)
    return found


def _qualifies(edge, kind):
    if not _visible_edge(edge):
        return False
    if kind == 'BOUNDARY':
        return edge.is_boundary and any(_visible_face(face) for face in edge.link_faces)
    if kind == 'SEAM':
        return bool(edge.seam)
    if kind == 'SHARP':
        return not edge.smooth
    return False


def _walk_chain(seed, kind):
    """Follow edge markings without silently forking across branch points."""
    found = {seed}
    for endpoint in seed.verts:
        previous, vertex = seed, endpoint
        while True:
            candidates = [edge for edge in vertex.link_edges
                          if edge != previous and edge not in found and
                          _qualifies(edge, kind)]
            # Only a single continuation is a well-defined chain. Branching
            # topology should be selected deliberately via Select Linked.
            if len(candidates) != 1:
                break
            edge = candidates[0]
            found.add(edge)
            vertex = edge.other_vert(vertex)
            previous = edge
    return found


def select_flow(bm, operation):
    """Return selected edge indices plus all traversed edges.

    The caller handles undo history and BMesh selection state. Never
    mutate the input BMEdge.select flags here.
    """
    if operation not in {'EDGE_LOOP', 'EDGE_RING',
                         'BOUNDARY_CHAIN', 'SEAM_CHAIN', 'SHARP_CHAIN'}:
        raise ValueError('Unknown edge flow selection')
    bm.edges.ensure_lookup_table()
    bm.edges.index_update()
    seeds = [edge for edge in bm.edges if edge.select and _visible_edge(edge)]
    if not seeds:
        raise ValueError('Select one or more edges before choosing a flow')
    result = set(seeds)
    for seed in seeds:
        if operation == 'EDGE_LOOP':
            result.update(_walk_loop(seed))
        elif operation == 'EDGE_RING':
            result.update(_walk_ring(seed))
        else:
            kind = operation.removesuffix('_CHAIN')
            if not _qualifies(seed, kind):
                raise ValueError('Selected edges must have the matching {} property'.format(
                    kind.lower()))
            result.update(_walk_chain(seed, kind))
    return tuple(sorted(edge.index for edge in result))
