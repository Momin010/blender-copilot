# Geometry Nodes

270 nodes. Blender's procedural modelling engine - the part that competes with
Houdini, and the part most professional environment work now runs through.

## Mental model

A geometry node tree is a function: geometry in, geometry out. It is attached as
a **modifier**, so it never destroys the base mesh - you can change one value and
the whole result rebuilds. That non-destructiveness is the entire point; if you
find yourself applying modifiers to "bake in" a step, ask whether the step
belongs in the tree instead.

Data flows as **fields** (per-element values, like a position or a random number
per point) or **single values**. A socket that shows a diamond accepts a field.

## Creating a tree from scratch

The three things that trip you up: the modifier and the tree are separate
objects, a new tree has no interface sockets, and nothing connects itself.

```python
import bpy

ob = bpy.data.objects['Ground']
mod = ob.modifiers.new("Scatter", 'NODES')
ng = bpy.data.node_groups.new("Scatter", 'GeometryNodeTree')
mod.node_group = ng

# Without these two lines the tree has no input or output and nothing flows.
ng.interface.new_socket("Geometry", in_out='INPUT',  socket_type='NodeSocketGeometry')
ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

n = ng.nodes
gin  = n.new('NodeGroupInput');  gin.location  = (-600, 0)
gout = n.new('NodeGroupOutput'); gout.location = ( 600, 0)
```

`location` is cosmetic but set it anyway - a human will open this tree, and an
unreadable graph is a real cost.

## Scatter: the canonical pattern

Distribute points on a surface, instance geometry onto them, randomize. This is
verified working code.

```python
dist = n.new('GeometryNodeDistributePointsOnFaces')
dist.inputs['Density'].default_value = 1.5

ico = n.new('GeometryNodeMeshIcoSphere')
ico.inputs['Radius'].default_value = 0.35
ico.inputs['Subdivisions'].default_value = 2

inst = n.new('GeometryNodeInstanceOnPoints')

rand = n.new('FunctionNodeRandomValue')
rand.data_type = 'FLOAT_VECTOR'
rand.inputs[0].default_value = (0.5, 0.5, 0.5)   # min
rand.inputs[1].default_value = (1.6, 1.6, 1.6)   # max

join = n.new('GeometryNodeJoinGeometry')

L = ng.links.new
L(gin.outputs[0],           dist.inputs['Mesh'])
L(dist.outputs['Points'],   inst.inputs['Points'])
L(ico.outputs['Mesh'],      inst.inputs['Instance'])
L(rand.outputs['Value'],    inst.inputs['Scale'])
L(inst.outputs['Instances'], join.inputs[0])
L(gin.outputs[0],            join.inputs[0])     # keep the original surface
L(join.outputs[0],           gout.inputs[0])
```

Note `join.inputs[0]` is linked twice - Join Geometry takes multiple links into
one socket. That is normal and correct.

### Socket naming, not indexing

`inst.inputs['Scale']` survives version changes; `inst.inputs[3]` does not.
The exception is nodes with unnamed or duplicate sockets - `FunctionNodeRandomValue`
uses `inputs[0]`/`inputs[1]` for min/max because the names repeat across data
types. When unsure:

```python
[(i, s.name, s.type) for i, s in enumerate(node.inputs)]
```

### `data_type` changes the sockets

Nodes like Random Value, Switch, and Capture Attribute rewire themselves when
`data_type` changes. **Set `data_type` before touching sockets** or you will
write to sockets that are about to be replaced.

## Counting the result

Instances are not real geometry until realized, so `to_mesh()` under-reports
badly - a 600-rock scatter reports 4 vertices. Count through the depsgraph:

```python
deps = bpy.context.evaluated_depsgraph_get()
n_instances = sum(1 for i in deps.object_instances if i.is_instance)
```

Use **Realize Instances** only when you must (export, boolean, per-element
editing). Instances are dramatically cheaper - realizing a large scatter is a
common accidental way to make a scene unopenable.

## Materials on instances

Instanced geometry does not inherit the host object's material. Either assign
the material to the instanced source object, or use **Set Material** inside the
tree:

```python
setmat = n.new('GeometryNodeSetMaterial')
setmat.inputs['Material'].default_value = bpy.data.materials['Rock']
```

## Exposing parameters to the modifier

Inputs you add to the tree interface appear as modifier settings - this is how
you hand a human a tunable asset rather than a black box.

```python
s = ng.interface.new_socket("Density", in_out='INPUT', socket_type='NodeSocketFloat')
s.default_value, s.min_value, s.max_value = 1.5, 0.0, 50.0
L(gin.outputs['Density'], dist.inputs['Density'])

mod["Socket_2"] = 3.0        # set per-object; identifier, not the label
```

The modifier key is the socket's `identifier` (`Socket_2`), not its name. Read
it off `s.identifier` rather than guessing.

## Common nodes by intent

| Intent | Node |
|---|---|
| Scatter on surface | `GeometryNodeDistributePointsOnFaces` |
| Place copies | `GeometryNodeInstanceOnPoints` |
| Make instances real | `GeometryNodeRealizeInstances` |
| Combine geometry | `GeometryNodeJoinGeometry` |
| Read position/normal | `GeometryNodeInputPosition`, `GeometryNodeInputNormal` |
| Move points | `GeometryNodeSetPosition` |
| Per-element randomness | `FunctionNodeRandomValue` |
| Filter elements | `GeometryNodeDeleteGeometry`, `GeometryNodeSeparateGeometry` |
| Store custom data | `GeometryNodeStoreNamedAttribute` |
| Curve to mesh | `GeometryNodeCurveToMesh` |
| Subdivide | `GeometryNodeSubdivisionSurface` |

Search for anything else rather than guessing - `blender_search` covers all 270.

## Version note

Blender 5.0 added **bundles** and **closures**, which change how complex trees
are structured. This is 4.5: that syntax does not exist here.
