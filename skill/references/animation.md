# Animation, Rigging and Constraints

## Keyframes

The data API is far more reliable than the keyframe operators.

```python
ob = bpy.data.objects['Cube']
ob.location = (0, 0, 0)
ob.keyframe_insert(data_path="location", frame=1)
ob.location.x = 5
ob.keyframe_insert(data_path="location", frame=24)
```

`data_path` is the RNA path relative to the object: `"location"`,
`"rotation_euler"`, `"scale"`, `"hide_viewport"`. Index a single channel with
`index=0` (x). Nested data works too:
`ob.data.keyframe_insert(data_path="lens", frame=1)` on a camera.

Removing: `ob.keyframe_delete(data_path="location", frame=24)`.

## Interpolation and easing

Default interpolation is Bezier, which is right for most motion. Constant for
mechanical steps, Linear for continuous rotation.

```python
for fc in ob.animation_data.action.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = 'BEZIER'
        kp.easing = 'AUTO'
```

`animation_data` is `None` until the first keyframe exists - always guard:

```python
if ob.animation_data and ob.animation_data.action:
    ...
```

**Anything mechanical looks wrong with default easing.** Real motion accelerates
and decelerates; constant-velocity movement reads as amateur. Conversely, a
machine that eases into position reads as floaty. Match the easing to the thing.

## Frame range and timing

```python
scene = bpy.context.scene
scene.frame_start, scene.frame_end = 1, 250
scene.render.fps = 24
scene.frame_set(100)     # use frame_set, not frame_current, to force a depsgraph update
```

`frame_current = 100` sets the number without re-evaluating dependencies.
`frame_set(100)` does both. If you read a transform after changing the frame and
get a stale value, this is why.

## Drivers

Drivers link one property to another by expression - the backbone of rigging.

```python
fcurve = ob.driver_add("location", 2)     # z
drv = fcurve.driver
drv.type = 'SCRIPTED'

var = drv.variables.new()
var.name = 'ctrl'
var.targets[0].id = bpy.data.objects['Controller']
var.targets[0].data_path = 'location.x'

drv.expression = "ctrl * 0.5"
```

Remove with `ob.driver_remove("location", 2)`.

## Constraints - 28 types

Constraints are not operators; they are added by type. Non-destructive and
evaluated in order.

```python
c = ob.constraints.new(type='FOLLOW_PATH')
c.target = bpy.data.objects['Path']
c.use_curve_follow = True
```

Using the data API (`ob.constraints.new`) avoids the selection dependency of
`bpy.ops.object.constraint_add`.

The ones that carry most real work:

| Type | Use |
|---|---|
| `COPY_LOCATION` / `COPY_ROTATION` / `COPY_SCALE` | Direct linkage, often with an influence below 1 |
| `COPY_TRANSFORMS` | All three at once |
| `TRACK_TO` / `DAMPED_TRACK` | Aim at a target - cameras, eyes, turrets |
| `FOLLOW_PATH` | Motion along a curve |
| `CHILD_OF` | Parenting that can be animated on and off |
| `LIMIT_LOCATION` / `LIMIT_ROTATION` | Keep a control inside a valid range |
| `IK` | Inverse kinematics (bones only) |
| `ARMATURE` | Multi-bone weighted binding |

Order matters: constraints evaluate top to bottom, each on the result of the
last. A Limit after a Copy behaves very differently from before it.

## Armatures and bones

Bones live in three different collections depending on mode, and confusing them
is the most common rigging error:

- `armature.data.edit_bones` - **Edit mode only**. Where you set head/tail.
- `armature.data.bones` - the rest/definition data. Read-only structure.
- `armature.pose.bones` - **Pose mode**. Where you animate and add constraints.

```python
bpy.ops.object.armature_add()
arm = bpy.context.view_layer.objects.active

bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones
root = eb[0]
root.name = "root"
child = eb.new("upper_arm")
child.head = root.tail
child.tail = child.head + Vector((0, 0, 1))
child.parent = root
child.use_connect = True
bpy.ops.object.mode_set(mode='OBJECT')

# constraints go on POSE bones, not edit bones
pb = arm.pose.bones["upper_arm"]
ik = pb.constraints.new(type='IK')
ik.chain_count = 2
```

`edit_bones` references become invalid the moment you leave Edit mode. Do not
hold them across a mode change.

## Skinning

```python
bpy.ops.object.select_all(action='DESELECT')
mesh_ob.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.parent_set(type='ARMATURE_AUTO')   # automatic weights
```

Automatic weights get you 80% of the way; the remainder is weight painting,
which is genuinely manual. Do not claim a rig is finished because it binds.

## Shape keys

```python
mesh_ob.shape_key_add(name="Basis")
key = mesh_ob.shape_key_add(name="Smile")
key.data[0].co.z += 0.1
key.value = 0.5
```

The first key must be `Basis` - it is the neutral state everything else is a
delta from.

## Baking to keyframes

Simulations and constraints do not export. Bake before handing off:

```python
bpy.ops.nla.bake(frame_start=1, frame_end=250, only_selected=True,
                 visual_keying=True, clear_constraints=False, bake_types={'POSE'})
```

`visual_keying=True` captures the *evaluated* result - without it you bake the
raw values and lose everything the constraints were doing.
