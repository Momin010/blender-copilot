# Shading and Materials

104 shader nodes. Materials in Blender are node graphs; the UI sliders are just
a view onto them.

## Creating a material

```python
import bpy

mat = bpy.data.materials.new("Rock")
mat.use_nodes = True          # without this there is no node tree at all
ob.data.materials.append(mat)

nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]   # present by default
```

Assigning to `ob.data.materials` puts the material on the *mesh* (shared by all
users of that mesh). `ob.material_slots[0].link = 'OBJECT'` makes it per-object
instead — needed when two objects share a mesh but differ in look.

## Principled BSDF

One node covers almost all physically-based surfaces. Verified 4.5 input names:

`Base Color`, `Metallic`, `Roughness`, `IOR`, `Alpha`, `Normal`,
`Diffuse Roughness`, `Subsurface Weight`, `Subsurface Radius`, `Subsurface Scale`,
`Specular IOR Level`, `Specular Tint`, `Anisotropic`, `Emission Color`,
`Emission Strength`, `Coat Weight`, `Transmission Weight`, `Sheen Weight`.

**These names changed in 4.x.** Older tutorials say `Subsurface`,
`Specular`, `Emission`, `Transmission` — those keys raise `KeyError` here. If a
name fails, list them rather than guessing:

```python
[i.name for i in bsdf.inputs]
```

### Physical defaults that read as "professional"

- Metal: `Metallic = 1.0`, `Base Color` is the metal's tint, `Roughness` 0.1–0.4.
  Metals have no diffuse — a grey metal with `Metallic = 0.5` is not a real material.
- Dielectric (plastic, wood, stone): `Metallic = 0.0`, vary `Roughness`.
- Nothing in the real world is `Roughness = 0.0`. Use 0.05 as the floor.
- `Base Color` values above ~0.8 are brighter than any real diffuse surface.

## Procedural texturing

```python
noise = nt.nodes.new('ShaderNodeTexNoise')
noise.inputs['Scale'].default_value = 12.0

ramp = nt.nodes.new('ShaderNodeValToRGB')       # Color Ramp
ramp.color_ramp.elements[0].color = (0.05, 0.06, 0.08, 1)
ramp.color_ramp.elements[1].color = (0.35, 0.30, 0.26, 1)

nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
```

Colors are always RGBA — a 3-tuple raises. Color ramps start with exactly two
elements; add more with `ramp.color_ramp.elements.new(position)`.

### Adding stops to a ramp

```python
e = ramp.color_ramp.elements.new(0.5)
e.color = (0.2, 0.18, 0.15, 1)
```

## Image textures

```python
tex = nt.nodes.new('ShaderNodeTexImage')
tex.image = bpy.data.images.load("/path/to/albedo.png")
nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
```

**Color space matters.** Albedo/diffuse maps are `'sRGB'`; roughness, metallic,
normal and displacement maps are **data**, not color:

```python
rough_tex.image.colorspace_settings.name = 'Non-Color'
```

Getting this wrong is the single most common cause of "my PBR material looks
wrong" — the values are silently gamma-shifted.

Normal maps need a Normal Map node between texture and shader:

```python
nm = nt.nodes.new('ShaderNodeNormalMap')
nt.links.new(nrm_tex.outputs['Color'], nm.inputs['Color'])
nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
```

## UV coordinates

By default textures use the active UV map. To control it explicitly:

```python
uvmap = nt.nodes.new('ShaderNodeUVMap')
uvmap.uv_map = "UVMap"
nt.links.new(uvmap.outputs['UV'], tex.inputs['Vector'])
```

For procedural textures on objects that move, use **Object** coordinates from a
Texture Coordinate node — Generated coordinates stretch with the bounding box.

## World / environment lighting

```python
world = bpy.data.worlds.new("W")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs['Color'].default_value = (0.05, 0.07, 0.12, 1)
bg.inputs['Strength'].default_value = 1.0
```

For an HDRI, feed an `ShaderNodeTexEnvironment` into the Background color. An
HDRI does more for realism than any amount of material tweaking — reach for it
before adding lights.

## Node groups

Reusable shader logic. Same interface API as geometry nodes:

```python
grp = bpy.data.node_groups.new("Weathering", 'ShaderNodeTree')
grp.interface.new_socket("Fac", in_out='INPUT', socket_type='NodeSocketFloat')
grp.interface.new_socket("Color", in_out='OUTPUT', socket_type='NodeSocketColor')

inst = nt.nodes.new('ShaderNodeGroup')
inst.node_tree = grp
```

## Common nodes by intent

| Intent | Node |
|---|---|
| Main surface | `ShaderNodeBsdfPrincipled` |
| Procedural pattern | `ShaderNodeTexNoise`, `ShaderNodeTexVoronoi`, `ShaderNodeTexMusgrave` |
| Remap values | `ShaderNodeValToRGB`, `ShaderNodeMapRange` |
| Blend two shaders | `ShaderNodeMixShader` |
| Mask by geometry | `ShaderNodeNewGeometry` (pointiness, incoming) |
| Math | `ShaderNodeMath`, `ShaderNodeVectorMath` |
| Emission | `ShaderNodeEmission` |
| Fake depth | `ShaderNodeBump`, `ShaderNodeNormalMap` |
