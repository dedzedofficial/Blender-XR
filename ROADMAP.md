# Blender XR roadmap

Free Blender VR tools by Ded Zed. Versions describe scoped goals, not promises of complete Blender parity. There is no paid feature tier planned.

## v0.3.0: initial basic editing

Implemented:

- Installable Blender 5+ extension with GPL-3.0-or-later source.
- Left/right dominant-hand choice before starting VR.
- Tool menu attached to the non-dominant controller.
- Dominant-controller pointing, object selection, and face selection.
- Extrude, bevel, and inset with controller-driven distance previews.
- Move and rotate an unparented object using the dominant grip.
- Add/remove selected faces by gripping while selecting in face mode.
- Cancel a live operation with the other trigger.
- VR-local undo/redo for the latest 20 tool/move operations.
- Viewer movement with the non-dominant thumbstick and reset view.
- GitHub release check, checksum-verified download, installation rollback, and restart prompt.
- Automated geometry, cancellation, history, packaging, and updater tests.

Release gate still requiring real hardware:

- Quest 3 with Air Link and Meta OpenXR.
- Quest 3 with SteamVR as the OpenXR runtime.
- Quest 3 with Virtual Desktop and VDXR, plus its SteamVR route.
- Stereo menu readability, controller ordering, ray direction, and button feedback.
- Windows installation/update/restart tests.

v0.3 is an initial development release. Headless mesh tests do not establish headset compatibility.

## v0.4.0: Meta/Valve targets and optional fingers

Implemented:

- Automatic, Meta and Valve/SteamVR controller binding presets.
- Documented Quest, Rift, Index and conditional Steam Frame compatibility targets.
- Opt-in controller finger-touch hold for menu/cancel.
- Experimental external SteamVR skeletal bridge: pinch selection/tool use and finger-curl object grab.
- Loopback-only session-key protocol, bounded packet processing, input freshness and release-before-arming checks.
- Tracking loss cancels unfinished work; estimated skeletal data cannot drive finger tools.
- Automated profile, skeletal sample, gesture, malformed packet, replay and reconnection tests.

Pending physical release validation: every headset/runtime combination above, controller touch behavior, skeletal measurements and background SteamVR input. Native OpenXR hand joints are not exposed through Blender's current Python API. Native Air Link hand tracking and native Steam Frame controller extensions need upstream integration or a different backend.

## v0.4.1: fixing update

- Fixed the missing Event.timer access that interrupted the VR modal loop.
- Left thumbstick locomotion independent of dominant-hand choice, with deadzone and speed limiting.
- Either-hand grab-air translation, with object-grip priority and no navigation feedback drift.
- Hand-menu primitive picker and placement preview: cube, sphere, cylinder, cone, torus and plane.
- Primitive creation in object mode, with VR-local undo/redo and snapshot cleanup.
- Regression tests reproduce timer events without the missing attribute and simulate both handedness settings.

## v0.4.2: flight and mesh switching

- Unbounded scene flight: left stick moves, right stick turns and changes altitude.
- Default 3 m/s flight, 4x turbo, held left-stick click boost, Travel speed controls and configurable snap/smooth turning.
- Head-pivot rotation with a nonzero starting 3D cursor.
- Tools, Shapes and Travel menu pages with larger labels, selected mesh name and ray-target bounds.
- Ray switching between meshes while face editing, with validation before leaving the current mesh.
- Regression tests for flight, turning, pivot preservation, both dominant-hand settings and real scene ray switching.

## v0.4.3: startup fix, saving and Blender 4.2+

- Fixed unsupported BOOLEAN XR action types; trigger touch, thumb touch and boost use FLOAT state values.
- Test every action type against Blender's real RNA enum, even without an XR session.
- Save Blend in the hand menu and desktop sidebar, current-file saves, timestamped first saves and an optional first-save path.
- Saved projects exclude private VR mesh history; saving retains live-session undo data in memory.
- Minimum Blender 4.2.0 with automated 4.2.0, 4.5.0, 5.0.0 and 5.2.2 coverage.

## v0.4.x: follow-up after headset testing

- Fix reported runtime/profile issues first; publish actual hardware results.
- Improve gesture thresholds from measured headset behavior.
- Adjustable menu position/size, axis snapping and improved diagnostics.
- Test native Blender undo integration before replacing local history.

## v0.4.4: easier building and public updates

- [x] Ray-picked XYZ movement and extrusion handles.
- [x] Bevel/inset thickness drag handles.
- [x] Delete selected faces with undo/redo.
- [x] Separate Edit Tools menu.
- [x] One public updater button without authentication.
- [x] Verified current release replaces older downloads.
- [x] Face selection and direct face movement/scaling workflows.
- [x] Whole-object scaling support.
- [x] Distance-aware transform handles for easier VR targeting.
- [x] Cleaner VR menus with duplicate options removed.
- [ ] Quest and Valve headset usability testing for ray dragging and menu placement.

# Future roadmap

| Version | Main goal | Ideal features |
| --- | --- | --- |
| **v0.5** | **Complete mesh modeling** | Vertex, edge and face selection; switch selection modes in VR; multi-select; move, rotate and scale selected geometry; extrude vertices, edges and faces; inset; bevel vertices and edges; loop cut; subdivide; merge vertices; dissolve geometry; delete vertices, edges and faces; duplicate geometry; bridge edge loops; fill faces and holes; separate selected geometry; join meshes; flip and recalculate normals; Shade Smooth / Flat; Global / Local / Normal transform orientation; improved XYZ gizmos. |
| **v0.6** | **Materials + UV mapping** | Create and delete materials; material slots; assign materials to selected faces; Base Color, Metallic, Roughness, Alpha and Emission controls; texture image selection; UV unwrap; Smart UV Project; cube and planar projection; move, rotate and scale UVs; reset UVs; simple VR UV preview; material preview mode. |
| **v0.7** | **Object transforms + modifiers** | Direct numeric Position X/Y/Z, Rotation X/Y/Z and Scale X/Y/Z; uniform scale; reset and apply transforms; copy/paste transforms; VR transform gizmos; set object origin; Origin to Geometry; Geometry to Origin; snap object to cursor; duplicate and linked duplicate; improved object snapping; Mirror modifier with X/Y/Z, Clipping, Merge and Mirror Object; Array modifier with Count, Relative/Constant Offset, X/Y/Z direction and Object Offset; Solidify modifier; apply/remove modifiers; visibility toggle; reorder supported modifiers. |
| **v0.8** | **Rigging + armatures** | Add armatures and bones; select bones in VR; move, rotate and scale bones; extrude bones; bone parenting; bone naming; mirror bones; Pose Mode; Rest/Pose switching; parent mesh to armature; automatic weights; basic IK; Copy Rotation / Location constraints; armature display controls. |
| **v0.9** | **Weight painting + character tools** | Weight Paint mode; add/remove weights; brush size and strength; bone/vertex-group selection; create, delete and rename vertex groups; assign selected vertices; normalize, mirror and smooth weights; automatic cleanup; visual weight heatmap; test deformation while painting; shape keys/blendshapes; create, rename and delete shape keys; adjust shape-key values. |
| **v1.0** | **Stable complete XR modeling workflow** | Polish all earlier systems; reliable Object/Edit/Pose/Weight/UV/Material switching; unified Undo/Redo; grid, vertex, edge and face snapping; pivot controls; collection and hierarchy controls; common modifier management; better object duplication; transform presets; customizable VR menu; large-scene performance improvements; clearer error feedback; controller accessibility options; full tutorials and documentation; broad Blender-version and OpenXR compatibility testing. |

## v0.7 transform workflow target

v0.7 should translate the most useful parts of Blender's Object Properties and basic Modifier workflow into VR without turning the menu into a desktop UI clone.

### Transform

- Location: X / Y / Z
- Rotation: X / Y / Z
- Scale: X / Y / Z
- Uniform scale
- Reset Location / Rotation / Scale
- Apply Location / Rotation / Scale
- Copy and paste transforms
- Global/local transform handling

### Mirror

- X / Y / Z axes
- Clipping
- Merge
- Mirror Object
- Apply
- Remove

### Array

- Count
- X / Y / Z direction
- Relative Offset
- Constant Offset
- Object Offset
- Apply
- Remove

### Solidify

- Thickness
- Offset
- Even Thickness where supported
- Apply
- Remove

## Beyond v1.0

The following are intentionally outside the initial 1.0 target so the core VR modeling workflow can become stable first:

- Sculpting.
- Full Shader Node editing.
- Geometry Nodes editing.
- Grease Pencil workflows.
- Animation graph editing.
- Video editing and compositing.
- Cloth, fluid and other advanced simulation workflows.
- Advanced retopology systems.

These may be explored in later 1.x releases after the core XR modeling, material, UV, rigging and character workflows are stable.