# Pipeline: Scene Structure, Interchange, Assets

## Data model

Blender's object model is two layers, and conflating them causes most confusing
bugs:

- **Object** - a transform in a scene. Location, rotation, modifiers, constraints.
- **Object data** (`ob.data`) - the mesh/curve/camera/light itself. Shared.

Ten objects can share one mesh. Editing that mesh changes all ten; editing
`ob.location` changes one. `bpy.data.objects` vs `bpy.data.meshes` are separate
collections.

```python
linked = bpy.data.objects.new("Copy", ob.data)      # shares the mesh
bpy.context.collection.objects.link(linked)

independent = ob.copy()
independent.data = ob.data.copy()                    # now unshared
bpy.context.collection.objects.link(independent)
```

An object created with `bpy.data.objects.new` exists but is invisible until
linked into a collection. Forgetting the link is a classic "my script did
nothing" bug.

## Collections

Collections are the organizing unit - and the unit of linking, instancing and
render visibility.

```python
col = bpy.data.collections.new("Props")
bpy.context.scene.collection.children.link(col)
col.objects.link(ob)
bpy.context.scene.collection.objects.unlink(ob)   # remove from the old one
```

Three different kinds of hiding, frequently confused:

| Property | Meaning |
|---|---|
| `ob.hide_viewport` | Hidden in the viewport only |
| `ob.hide_render` | Excluded from renders only |
| `ob.hide_get()` / `hide_set()` | Per-view-layer temporary hide (the `H` key) |

An object hidden with `H` still renders. That is usually the answer to "why is
this in my render".

## Removing things properly

```python
bpy.data.objects.remove(ob, do_unlink=True)
```

Deleting the object leaves its mesh behind as an orphan. Blender purges
zero-user datablocks on save/reload, or force it:

```python
bpy.ops.outliner.orphans_purge(do_recursive=True)
```

## Linking and appending

**Link** references another file - the asset stays in one place and updates
propagate. **Append** copies it in - self-contained but frozen. Production uses
link for shared assets and append for one-offs.

```python
with bpy.data.libraries.load("/path/assets.blend", link=True) as (src, dst):
    dst.collections = ["Tree"]

for col in dst.collections:
    inst = bpy.data.objects.new(col.name, None)
    inst.instance_type = 'COLLECTION'
    inst.instance_collection = col
    bpy.context.scene.collection.objects.link(inst)
```

Linked data is read-only. To pose or modify it, make a **library override**
(`bpy.ops.object.make_override_library()`) - the modern replacement for proxies.

## Interchange formats

| Format | Operator | Use |
|---|---|---|
| USD | `wm.usd_export` / `wm.usd_import` | The production interchange standard |
| glTF | `export_scene.gltf` | Web, realtime, PBR-native |
| FBX | `export_scene.fbx` | Game engines, legacy animation |
| Alembic | `wm.alembic_export` | Baked geometry caches, VFX |
| OBJ | `wm.obj_export` | Static geometry only, no rig |

```python
bpy.ops.wm.usd_export(filepath="/out/scene.usdc",
                      export_animation=True,
                      export_materials=True,
                      selected_objects_only=False)
```

USD is where professional pipelines have converged - it carries hierarchy,
materials, variants and layering, and every major DCC reads it. Prefer it unless
a target engine demands otherwise. glTF for the web, FBX only when something
downstream requires it.

### What does not survive export

Modifiers, geometry node trees, constraints, drivers and procedural materials
are **Blender concepts**. Exporters bake what they can and silently drop the
rest. Before export:

- Apply or bake modifiers that must persist as geometry
- Bake procedural materials to image textures
- Bake constraint-driven animation to keyframes (`nla.bake`, `visual_keying=True`)
- Apply transforms (`object.transform_apply`) - non-uniform scale breaks in many engines

Telling someone a rig "exported fine" without checking these is how pipelines
break downstream.

## Units and scale

```python
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
```

Blender's unit is 1 metre. Game engines often assume centimetres. Mismatched
scale shows up as physics behaving like the world is enormous, or as objects
arriving 100× too small. Fix scale at export, not by scaling objects.

## Asset library

Marking a datablock as an asset makes it available in the Asset Browser:

```python
ob.asset_mark()
ob.asset_data.tags.new("rock")
ob.asset_generate_preview()
```

This is how a studio builds a reusable library - worth doing for anything
produced more than once.

## File paths

```python
bpy.path.abspath("//textures/wood.png")   # // means "relative to this .blend"
bpy.ops.file.pack_all()                   # embed external files into the .blend
bpy.ops.file.make_paths_relative()
```

Relative paths plus packing is what makes a `.blend` portable. Absolute paths
are the reason files break on another machine.
