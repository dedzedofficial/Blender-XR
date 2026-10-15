# Mesh XR v0.6.5 — Icon UI Guide

Mesh XR v0.6.5 changes the main VR modeling interface to an icon-first layout. The goal is to make common tools recognizable without relying on long English button labels.

## Pointing and tooltips

Use the dominant-hand controller ray to point at an icon.

- The icon highlights immediately when the ray is over it.
- Keep the ray over the icon for about **0.5 seconds** to show its tooltip.
- Moving the ray away hides the tooltip.
- You do **not** need to wait for the tooltip before pressing Trigger.
- The active tool remains highlighted so you can see what is selected.

Tooltips contain the English tool name plus a short explanation. The icon remains the primary control so normal modeling does not depend on reading the label.

## Mode selector

The first icon on the Object and Edit toolbars is the **Mode** control. It works like Blender's mode selector.

1. Point at the Mode icon and press Trigger.
2. Choose **Object Mode** or **Edit Mode**.
3. Mesh XR returns to the toolbar for that mode.

### Object Mode

Use Object Mode when you want to work with a complete mesh object.

| Icon meaning | Tool | What it does |
| --- | --- | --- |
| Mode box / arrow | Mode | Opens the Object/Edit mode selector. |
| Pointer | Select | Selects a mesh object with the controller ray. |
| Move arrows | Move | Moves the selected object. |
| Scale box/arrow | Scale | Scales the selected object. |
| Plus/object | Add | Opens primitive creation. |
| Material diamond | Materials | Opens Materials, Textures and UV tools. |
| Navigation arrow | Travel | Opens movement and turning controls. |
| Curved back arrow | Undo | Undoes the last Mesh XR action. |
| Curved forward arrow | Redo | Redoes an undone Mesh XR action. |
| Disk | Save | Saves the Blend project. |
| Trash can | Delete Object | Deletes the active mesh object. Undo restores it. |
| Stop square | Stop VR | Ends the Mesh XR session. |

## Edit Mode

Edit Mode exposes Blender-style vertex, edge and face selection as icons.

| Icon meaning | Tool | What it does |
| --- | --- | --- |
| Mode box / arrow | Mode | Opens the Object/Edit mode selector. |
| Pointer | Select | Selects mesh geometry with the ray. |
| Point | Vertex Select | Changes selection to vertices. |
| Line | Edge Select | Changes selection to edges. |
| Square | Face Select | Changes selection to faces. |
| Move arrows | Move Selection | Moves selected vertices, edges or faces. |
| Scale box/arrow | Scale Selection | Scales selected mesh geometry. |
| Raised face | Extrude | Extrudes the current selection. |
| Square inside square | Inset Faces | Insets selected faces. This is directly available again in the main Edit toolbar. |
| Chamfer corner | Bevel | Bevels selected geometry. |
| Crossed quad | Loop Cut | Opens Loop Cut controls for the selected edge ring. |
| More tools | More Edit | Opens secondary modeling operations. |

## Loop Cut

Loop Cut currently works on a **continuous quad edge ring**.

1. Enter **Edit Mode**.
2. Choose **Edge Select**.
3. Select an edge that belongs to the quad ring you want to cut.
4. Open **Loop Cut**.
5. The detected edge ring is previewed in orange in the scene.
6. Use **- / +** to change the number of cuts from 1 to 16.
7. For a single cut, use the left/right arrow icons to move the cut position in 5% steps.
8. Press the Apply icon to create the cut.
9. Use Undo if you want to restore the previous topology.

For multiple cuts, Mesh XR spaces the cuts evenly. The position control is intended for a single cut.

If Mesh XR cannot follow a valid quad ring, it reports that Loop Cut requires a continuous quad edge ring instead of making an unpredictable cut.

## More Edit tools

The secondary Edit toolbar contains less frequently used mesh operations.

| Icon meaning | Tool | What it does |
| --- | --- | --- |
| Trash can | Delete Geometry | Deletes the selected vertex, edge or face geometry. It does not delete the complete object. |
| Converging lines | Merge | Merges selected vertices. |
| Divided square | Subdivide | Subdivides selected geometry. |
| Overlapping squares | Duplicate | Duplicates selected geometry. |
| Normal arrow | Recalculate Normals | Recalculates selected face normals. |
| Normal arrow | Flip Normals | Reverses selected face normals. |
| Material diamond | Materials | Opens Materials, Textures and UV tools. |
| Undo / Redo | History | Steps through Mesh XR local history. |
| - / + | Step Size | Changes the modeling adjustment step. |
| Left arrow | Back | Returns to the main Edit toolbar. |

## Delete Object vs Delete Geometry

v0.6.5 deliberately keeps these as separate commands.

- **Delete Object** is available in Object Mode and removes the complete active mesh object.
- **Delete Geometry** is available in Edit Mode and only removes the currently selected vertex, edge or face geometry.

Deleting an object is stored in Mesh XR's local history, so **Undo** can restore it and **Redo** can remove it again.

## Inset Faces

Inset was already present in the mesh engine but had become less visible in the workflow. v0.6.5 places **Inset Faces** directly on the main Edit toolbar again.

Inset requires Face Select and one or more selected faces. It keeps the existing Mesh XR preview/cancel/Undo behavior so adjusting the inset does not repeatedly accumulate topology.

## Why icons?

The v0.6.5 UI uses icons for the common modeling workflow so users do not need to understand a long English menu before they can work. Raycast tooltips remain available when an icon is unfamiliar.

Materials, UV and some advanced panels still retain text where a symbolic control would be unclear. Those areas can be converted gradually without sacrificing usability.
