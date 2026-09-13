---
name: blender
description: Drive Blender professionally through the Copilot MCP bridge - modeling, geometry nodes, shading, animation, rigging, physics, rendering, compositing, video editing and USD pipeline work. Use whenever the task involves creating, editing, inspecting or rendering anything in Blender.
---

# Blender

You have live control of a running Blender 4.5 LTS instance. Blender exposes
**3,064 capabilities**; almost none of them are loaded into your context. Find
what you need instead of guessing.

## The loop

1. **`blender_scene`** - see what you are working with. Always, before acting.
2. **`blender_search`** - describe the goal in plain language, get capabilities.
3. **`blender_describe`** - pull the exact parameters for what you picked.
4. **`blender_call`** or **`blender_python`** - do it.
5. **`blender_render`** - look at the result. Do not assume it worked.

Skip step 5 only when the change is non-visual.

## Do not guess operator names

`bpy.ops` has 2,391 operators and the names are not guessable. Worse, **much of
Blender is not an operator at all**:

| You want | It is actually | Reached via |
|---|---|---|
| Cloth, subdivision, bevel, array, mirror | one of 83 **modifiers** | `bpy.ops.object.modifier_add(type=...)` |
| Follow path, track to, IK | one of 28 **constraints** | `bpy.ops.object.constraint_add(type=...)` |
| Scatter, noise, blur, math | one of 523 **nodes** | `node_tree.nodes.new('...')` |

`blender_search` covers all of these in one place. Always search first.

## Prefer the data API over operators

`bpy.ops` replays the UI: it depends on context, mutates selection, and floods
the undo stack. Direct data access does not.

```python
# Fragile - depends on what is selected and which mode you are in
bpy.ops.object.select_all(action='DESELECT')
bpy.data.objects['Cube'].select_set(True)
bpy.ops.transform.translate(value=(0, 0, 2))

# Robust - says exactly what it means
bpy.data.objects['Cube'].location.z += 2
```

Use operators when there is no data-API equivalent (unwrapping, remeshing,
booleans applied in place, most mesh edit-mode work). Use `bmesh` for heavy mesh
editing.

## Hard-won gotchas

These are real failures encountered while building this bridge. They will cost
you a debugging cycle each.

**`bpy.context.active_object` can be missing.** Right after
`wm.read_homefile()` the context has no 3D-view screen and the attribute does
not exist. `bpy.context.view_layer.objects.active` always resolves - prefer it.

**`to_mesh()` does not include instances.** A geometry-nodes scatter producing
600 rocks still reports 4 vertices. Count through the depsgraph instead:

```python
deps = bpy.context.evaluated_depsgraph_get()
sum(1 for i in deps.object_instances if i.is_instance)
```

**PollError means state, not context.** The bridge already synthesizes the
editor an operator needs. If you still get `PollError`, Blender's *state* is
wrong: wrong mode, nothing selected, no animation data, no UV layer. Fix the
precondition, then retry. `graph.select_all` fails until the object has
f-curves; `uv.select_all` fails until you are in Edit mode with a UV layer.

**Mode changes are explicit.** `bpy.ops.object.mode_set(mode='EDIT')` before
mesh edit-mode operators, and back to `'OBJECT'` afterwards. Leaving Blender in
Edit mode breaks later operations.

**Node sockets: index by name, not position.** `node.inputs['Roughness']` is
stable across versions; `node.inputs[7]` is not.

**Geometry node groups need explicit interface sockets.** A new tree has no
input or output socket, so nothing flows:

```python
ng.interface.new_socket("Geometry", in_out='INPUT',  socket_type='NodeSocketGeometry')
ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
```

**Instances have no material from the ground object.** Assign the material to
the instanced geometry, or use a Set Material node inside the tree.

## Version

Blender **4.5 LTS**. Blender 5.0+ changed parts of the Geometry Nodes API
(bundles, closures) - that syntax will not work here. Target 4.5.

## Deeper references

Load only what the task needs:

- `references/geometry-nodes.md` - procedural modelling, scattering, instancing
- `references/shading.md` - materials, the node graph, PBR
- `references/animation.md` - keyframes, drivers, rigging, constraints
- `references/rendering.md` - EEVEE/Cycles, lighting, cameras, output
- `references/pipeline.md` - USD/glTF/FBX, collections, linking, scene structure
- `references/workflows.md` - how professionals actually sequence this work
