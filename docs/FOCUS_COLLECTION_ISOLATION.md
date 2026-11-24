# Mesh XR collection-aware Focus

Mesh XR's **Travel → Focus** page provides two reversible isolation targets:

- **Isolate** keeps the currently selected objects visible, including a mesh's
  parent/Armature-modifier rig and a rig's paired deforming meshes.
- **Isolate Collection** keeps every object in the active Outliner collection,
  including nested child collections. It also keeps associated deforming
  armatures and meshes visible when they are outside that collection.

Before hiding anything, Focus records the current view layer's per-object
viewport hide flags, the selected objects and the active object. **Restore**
(or pressing the same isolation action again) restores those original flags
and reinstates the original selection and active object. Objects that were
already hidden remain hidden. Objects deleted or removed from the view layer
while Focus is active are skipped rather than recreated.

Collection isolation uses the active collection in Blender's Outliner. Select
a child collection before choosing **Isolate Collection**; the master Scene
Collection is rejected because it would not isolate anything. A collection
with no objects in the active view layer, or one that already contains every
visible object, is also rejected with a status message.

This is viewport-only visibility handling. It does not edit mesh geometry,
materials, UVs, rig weights, object transforms or render visibility. X-Ray is
still a separate toggle and can be restored independently.

## Current safety boundary

The Focus snapshot lives in the active Mesh XR session. Restore it before
saving or closing a project. A Blender crash, or saving a file while temporary
isolation is active and then reopening that saved file, is not yet covered by
persistent load-time recovery. That is a separate follow-up; this change does
not claim to solve it. Real controller ergonomics and Quest 3 acceptance still
require creator testing.

## Regression test

Run from the repository root with a supported Blender executable:

```sh
blender --background --factory-startup --python-exit-code 1 --python tests/test_focus_collection_v090.py
```

The integration test covers nested collections, deforming armature pairing,
pre-hidden objects, exact selection restoration, repeated-toggle restoration,
deleted-object handling, master-collection refusal and headset menu dispatch.
