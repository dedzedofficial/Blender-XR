"""Blender integration tests for collection-aware reversible XR focus."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy

import blender_xr
from blender_xr import drawing, focus_v080, menus, runtime


def _expect_refusal(callback, phrase):
    try:
        callback()
    except ValueError as exc:
        assert phrase.lower() in str(exc).lower(), str(exc)
    else:
        raise AssertionError("Unsafe focus target was accepted")


def _new_mesh(name, collection):
    data = bpy.data.meshes.new(name + " Mesh")
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    return obj


def _new_armature(name, collection):
    data = bpy.data.armatures.new(name + " Data")
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    return obj


def _find_layer_collection(layer, collection):
    if layer.collection == collection:
        return layer
    for child in layer.children:
        found = _find_layer_collection(child, collection)
        if found is not None:
            return found
    return None


def _select(context, objects, active=None):
    view_layer = context.view_layer
    for obj in view_layer.objects:
        obj.select_set(False, view_layer=view_layer)
    for obj in objects:
        obj.select_set(True, view_layer=view_layer)
    view_layer.objects.active = active


def run():
    blender_xr.register()
    context = bpy.context
    state = focus_v080.FocusState()
    created_objects = []
    created_collections = []
    try:
        # Keep the test isolated from the factory-startup cube/camera/light.
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)

        scene = context.scene
        root = scene.collection
        group = bpy.data.collections.new("XR Focus Collection Test")
        nested = bpy.data.collections.new("XR Focus Nested Test")
        outside_group = bpy.data.collections.new("XR Focus Outside Test")
        root.children.link(group)
        group.children.link(nested)
        root.children.link(outside_group)
        created_collections.extend((group, nested, outside_group))

        group_item = _new_mesh("XR Focus Group Item", group)
        nested_mesh = _new_mesh("XR Focus Nested Mesh", nested)
        prehidden_member = _new_mesh("XR Focus Prehidden Member", nested)
        outside_item = _new_mesh("XR Focus Outside Item", outside_group)
        outside_prehidden = _new_mesh("XR Focus Outside Prehidden", outside_group)
        armature = _new_armature("XR Focus Deform Rig", outside_group)
        deleted_during_focus = _new_mesh("XR Focus Deleted During Focus", outside_group)
        created_objects.extend((
            group_item, nested_mesh, prehidden_member, outside_item,
            outside_prehidden, armature, deleted_during_focus,
        ))
        modifier = nested_mesh.modifiers.new("XR Focus Deform", "ARMATURE")
        modifier.object = armature
        context.view_layer.update()

        prehidden_member.hide_set(True, view_layer=context.view_layer)
        outside_prehidden.hide_set(True, view_layer=context.view_layer)
        group_layer = _find_layer_collection(context.view_layer.layer_collection, group)
        assert group_layer is not None
        context.view_layer.active_layer_collection = group_layer

        # Collection isolation includes nested members and a deforming rig,
        # but never unhides objects that were hidden before the operation.
        _select(context, (group_item, nested_mesh), active=nested_mesh)
        assert state.isolate_collection(context)
        assert not group_item.hide_get(view_layer=context.view_layer)
        assert not nested_mesh.hide_get(view_layer=context.view_layer)
        assert not armature.hide_get(view_layer=context.view_layer)
        assert prehidden_member.hide_get(view_layer=context.view_layer)
        assert outside_item.hide_get(view_layer=context.view_layer)
        assert outside_prehidden.hide_get(view_layer=context.view_layer)
        assert deleted_during_focus.hide_get(view_layer=context.view_layer)

        # Selection changes made while focused do not leak after Restore:
        # the original multi-selection and active object are reinstated.
        _select(context, (armature,), active=armature)
        state.restore_isolation()
        assert not outside_item.hide_get(view_layer=context.view_layer)
        assert outside_prehidden.hide_get(view_layer=context.view_layer)
        assert prehidden_member.hide_get(view_layer=context.view_layer)
        assert group_item.select_get(view_layer=context.view_layer)
        assert nested_mesh.select_get(view_layer=context.view_layer)
        assert not armature.select_get(view_layer=context.view_layer)
        assert context.view_layer.objects.active == nested_mesh

        # Selection isolation still keeps the mesh/armature pair together.
        _select(context, (nested_mesh,), active=nested_mesh)
        assert state.isolate(context)
        assert not nested_mesh.hide_get(view_layer=context.view_layer)
        assert not armature.hide_get(view_layer=context.view_layer)
        assert group_item.hide_get(view_layer=context.view_layer)
        # Repeating Isolate is a safe toggle-off and restores exact selection.
        assert state.isolate(context) is False
        assert not group_item.hide_get(view_layer=context.view_layer)
        assert nested_mesh.select_get(view_layer=context.view_layer)
        assert context.view_layer.objects.active == nested_mesh

        # Deleted scene objects are skipped, never recreated during restore.
        assert state.isolate_collection(context)
        bpy.data.objects.remove(deleted_during_focus, do_unlink=True)
        state.restore_isolation()
        assert bpy.data.objects.get(deleted_during_focus.name) is None

        # The master scene collection is intentionally rejected as a no-op.
        context.view_layer.active_layer_collection = context.view_layer.layer_collection
        _expect_refusal(
            lambda: state.isolate_collection(context),
            "child collection",
        )

        # Verify the headset menu routes the new action through the same state.
        assert ("ISOLATE COLLECTION", "FOCUS_COLLECTION") in menus.PAGES["FOCUS_MENU"]
        assert len(menus.PAGES["FOCUS_MENU"]) <= 12
        context.view_layer.active_layer_collection = group_layer
        _select(context, (group_item,), active=group_item)
        session = runtime.Runtime.__new__(runtime.Runtime)
        session.menu = drawing.Menu()
        session.menu.page = "FOCUS_MENU"
        session.focus_state = focus_v080.FocusState()
        session._weight_stroke = None
        session.status = ""
        session.command(context, "FOCUS_COLLECTION")
        assert session.focus_state.hidden is not None
        assert outside_item.hide_get(view_layer=context.view_layer)
        session.command(context, "FOCUS_RESTORE")
        assert session.focus_state.hidden is None
        assert not outside_item.hide_get(view_layer=context.view_layer)
        assert group_item.select_get(view_layer=context.view_layer)
        assert context.view_layer.objects.active == group_item

        print("PASS collection-aware XR focus, nested contents, rig pairing, visibility and selection restore")
    finally:
        state.restore()
        for obj in reversed(created_objects):
            try:
                if bpy.data.objects.get(obj.name) == obj:
                    bpy.data.objects.remove(obj, do_unlink=True)
            except (ReferenceError, RuntimeError):
                pass
        for collection in reversed(created_collections):
            try:
                if bpy.data.collections.get(collection.name) == collection:
                    bpy.data.collections.remove(collection)
            except (ReferenceError, RuntimeError):
                pass
        blender_xr.unregister()


run()
