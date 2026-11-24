"""Blender-background regressions for native XR edge-chain spacing.

Run with:
    blender --background --factory-startup --python-exit-code 1 \
        --python tests/test_mesh_edge_chain_spacing_v090.py

These tests exercise the real edit BMesh, preview fingerprint, bounded world-space
plan, native topology preservation, confirmation and stale-preview rejection.
"""
import math
import sys
import unittest
from pathlib import Path

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender_xr import mesh_edge_chain_spacing_v090 as spacing
from blender_xr import selection


class EdgeChainSpacingTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.object.mode_set(mode='OBJECT') if bpy.context.object and bpy.context.object.mode != 'OBJECT' else None
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        mesh_data = bpy.data.meshes.new('ChainTestMesh')
        mesh_data.from_pydata(
            [(0, 0, 0), (1, 1, 0), (3, 1, 0), (4, 0, 0)],
            [(0, 1), (1, 2), (2, 3)], [])
        mesh_data.update()
        self.obj = bpy.data.objects.new('ChainTestObject', mesh_data)
        bpy.context.collection.objects.link(self.obj)
        self.obj.select_set(True)
        bpy.context.view_layer.objects.active = self.obj
        bpy.ops.object.mode_set(mode='EDIT')
        selection.set_mode(bpy.context, 'EDGE')
        self._select_all_edges()

    def tearDown(self):
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        for mesh_data in tuple(bpy.data.meshes):
            if mesh_data.users == 0:
                bpy.data.meshes.remove(mesh_data)

    def _select_all_edges(self):
        bm = bmesh.from_edit_mesh(self.obj.data)
        for face in bm.faces:
            face.select_set(False)
        for edge in bm.edges:
            edge.select_set(False)
        for vert in bm.verts:
            vert.select_set(False)
        for edge in bm.edges:
            edge.select_set(True)
        bm.select_mode = {'EDGE'}
        bm.select_flush_mode()
        bmesh.update_edit_mesh(self.obj.data, loop_triangles=False, destructive=False)
        bpy.context.tool_settings.mesh_select_mode = (False, True, False)

    def _edge_coordinates(self):
        bm = bmesh.from_edit_mesh(self.obj.data)
        bm.verts.ensure_lookup_table()
        return tuple(tuple(float(c) for c in v.co) for v in bm.verts)

    def test_preview_is_bounded_and_commit_preserves_native_topology(self):
        bm = bmesh.from_edit_mesh(self.obj.data)
        counts = (len(bm.verts), len(bm.edges), len(bm.faces))
        original = self._edge_coordinates()
        proposal = spacing.plan(bpy.context, 'XR_CHAIN_SPACING_MEDIUM')
        self.assertEqual(proposal['chain_verts'], 4)
        self.assertEqual(proposal['chain_edges'], 3)
        self.assertEqual(len(proposal['changes']), 2)
        self.assertLessEqual(
            proposal['max_world_move'],
            min((Vector(original[i + 1]) - Vector(original[i])).length
                for i in range(3)) * 0.10 + 1e-7)
        changed = spacing.commit(bpy.context, proposal)
        self.assertEqual(changed, 2)
        after = self._edge_coordinates()
        self.assertEqual(after[0], original[0])
        self.assertEqual(after[-1], original[-1])
        bm = bmesh.from_edit_mesh(self.obj.data)
        self.assertEqual((len(bm.verts), len(bm.edges), len(bm.faces)), counts)
        self.assertTrue(all(
            (bm.verts[i].co - bm.verts[i + 1].co).length > 1e-8
            for i in range(3)))

    def test_world_space_handles_rotation_and_nonuniform_scale(self):
        self.obj.matrix_world = (
            Matrix.Translation(Vector((2.0, -3.0, 1.0))) @
            Euler((0.3, -0.6, 0.8)).to_matrix().to_4x4() @
            Matrix.Diagonal((2.0, 0.5, 1.5, 1.0)))
        proposal = spacing.plan(bpy.context, 'XR_CHAIN_SPACING_GENTLE')
        self.assertTrue(math.isfinite(proposal['max_world_move']))
        self.assertGreater(proposal['max_world_move'], 0.0)
        before = self._edge_coordinates()
        spacing.commit(bpy.context, proposal)
        after = self._edge_coordinates()
        self.assertEqual(after[0], before[0])
        self.assertEqual(after[-1], before[-1])

    def test_changed_geometry_invalidates_preview_without_overwriting_it(self):
        proposal = spacing.plan(bpy.context, 'XR_CHAIN_SPACING_MEDIUM')
        bm = bmesh.from_edit_mesh(self.obj.data)
        bm.verts.ensure_lookup_table()
        bm.verts[1].co.x += 0.025
        bmesh.update_edit_mesh(self.obj.data, loop_triangles=False, destructive=False)
        changed = self._edge_coordinates()
        with self.assertRaises(ValueError):
            spacing.commit(bpy.context, proposal)
        self.assertEqual(self._edge_coordinates(), changed)

    def test_disconnected_selection_is_rejected(self):
        bm = bmesh.from_edit_mesh(self.obj.data)
        for edge in bm.edges:
            edge.select_set(False)
        bm.edges.ensure_lookup_table()
        bm.edges[0].select_set(True)
        bm.edges[2].select_set(True)
        bm.select_mode = {'EDGE'}
        bm.select_flush_mode()
        bmesh.update_edit_mesh(self.obj.data, loop_triangles=False, destructive=False)
        with self.assertRaises(ValueError):
            spacing.plan(bpy.context)

    def test_closed_loop_and_branch_are_rejected(self):
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.data.objects.remove(self.obj, do_unlink=True)
        mesh_data = bpy.data.meshes.new('InvalidChainMesh')
        mesh_data.from_pydata(
            [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (2, 0, 0)],
            [(0, 1), (1, 2), (2, 3), (3, 0), (1, 4)], [])
        self.obj = bpy.data.objects.new('InvalidChainObject', mesh_data)
        bpy.context.collection.objects.link(self.obj)
        self.obj.select_set(True)
        bpy.context.view_layer.objects.active = self.obj
        bpy.ops.object.mode_set(mode='EDIT')
        selection.set_mode(bpy.context, 'EDGE')
        bm = bmesh.from_edit_mesh(self.obj.data)
        for edge in bm.edges:
            edge.select_set(True)
        bm.select_mode = {'EDGE'}
        bm.select_flush_mode()
        bmesh.update_edit_mesh(self.obj.data, loop_triangles=False, destructive=False)
        bpy.context.tool_settings.mesh_select_mode = (False, True, False)
        with self.assertRaises(ValueError):
            spacing.plan(bpy.context)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EdgeChainSpacingTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print('PASS native edge-chain spacing Blender regressions')
