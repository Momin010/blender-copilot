# Rendering, Lighting and Cameras

## Engines

```python
scene = bpy.context.scene
scene.render.engine = 'CYCLES'              # or 'BLENDER_EEVEE_NEXT', 'BLENDER_WORKBENCH'
```

**Gotcha:** `CYCLES` does not appear in
`scene.render.bl_rna.properties['engine'].enum_items` even when the Cycles addon
is enabled - dynamically registered engines are not in the static RNA enum.
Assignment still works. Do not conclude Cycles is unavailable because it is
missing from that list.

| Engine | Use |
|---|---|
| `BLENDER_EEVEE_NEXT` | Real-time rasterizer. Seconds per frame. Default in 4.5. |
| `CYCLES` | Path tracer. Physically accurate, minutes per frame. |
| `BLENDER_WORKBENCH` | Solid/matcap preview. Playblasts and clay renders. |

EEVEE Next in 4.5 does real raytraced reflections and shadows, which closed much
of the historic gap. Use Cycles when you need caustics, accurate transmission,
or true global illumination; use EEVEE for everything else, especially animation.

## Cycles settings

```python
cy = scene.cycles
cy.device = 'GPU'          # falls back to CPU if unconfigured
cy.samples = 128
cy.use_denoising = True
cy.use_adaptive_sampling = True
cy.adaptive_threshold = 0.01
cy.max_bounces = 12
```

With denoising on, 64–128 samples is usually enough. Pushing samples to 1000
without denoising is a common way to waste hours for no visible gain.

On this machine `cycles.device` reports `CPU` - an Intel Mac with no CUDA/OptiX
path. Expect Cycles to be slow here and prefer EEVEE for iteration.

## Resolution and output

```python
r = scene.render
r.resolution_x, r.resolution_y = 1920, 1080
r.resolution_percentage = 100        # drop to 25–50 for fast previews
r.filepath = "/tmp/out/frame_"
r.image_settings.file_format = 'PNG'
r.image_settings.color_depth = '16'
r.film_transparent = True            # alpha background for compositing
```

For animation output, **render an image sequence, not a video file.** A crashed
render loses one frame instead of everything, and you can re-render individual
frames. Assemble to video afterwards in the sequencer.

```python
bpy.ops.render.render(write_still=True)              # single frame
bpy.ops.render.render(animation=True)                # full range
```

## Color management

```python
scene.view_settings.view_transform = 'AgX'   # 4.5 default; 'Filmic' in older files
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = 0.0
```

AgX handles bright highlights gracefully instead of clipping them to white.
Setting `view_transform = 'Standard'` gives you raw sRGB - correct only when
rendering UI elements or texture bakes, never for photographic work.

## Lighting

```python
bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
sun = bpy.context.view_layer.objects.active
sun.data.energy = 4.0
sun.rotation_euler = (math.radians(50), 0, math.radians(40))
```

| Type | Units | Notes |
|---|---|---|
| `SUN` | irradiance (W/m²), 1–10 | Position irrelevant, only rotation matters |
| `POINT` | watts, 100–1000 | `shadow_soft_size` controls shadow softness |
| `AREA` | watts | Most controllable; `size` drives softness |
| `SPOT` | watts | `spot_size`, `spot_blend` |

Sun energy and point energy are in different units - a sun at 1000 is not
"bright", it is broken.

**Three-point lighting** is the reliable default: a bright key at ~45° off
camera, a fill at ~1/3 the key's power on the opposite side, and a rim behind
the subject to separate it from the background. An HDRI world often replaces
fill entirely and looks better.

Soft light comes from *large* emitters. A small area light scaled up is the
single most effective realism change available.

## Cameras

```python
bpy.ops.object.camera_add(location=(12, -12, 8))
cam = bpy.context.view_layer.objects.active
cam.rotation_euler = (math.radians(62), 0, math.radians(45))
scene.camera = cam                    # required, or renders fail

cam.data.lens = 50                    # mm
cam.data.dof.use_dof = True
cam.data.dof.focus_object = bpy.data.objects['Subject']
cam.data.dof.aperture_fstop = 2.8
```

Focal length choices carry meaning: 24–35mm exaggerates depth (environments,
drama), 50mm is neutral, 85–135mm compresses (portraits, product). Defaulting
everything to 50mm is safe but flat.

Aiming a camera by hand is error-prone - use a constraint:

```python
c = cam.constraints.new(type='TRACK_TO')
c.target = bpy.data.objects['Subject']
```

## Viewport preview vs final

`blender_render(mode="viewport")` is an OpenGL snapshot - near-instant, ignores
the render engine. Use it for iteration and layout checks.

`mode="final"` runs the actual engine. Use sparingly, and reduce
`resolution_percentage` while iterating.

## Render layers and passes

```python
vl = scene.view_layers[0]
vl.use_pass_combined = True
vl.use_pass_z = True
vl.use_pass_normal = True
vl.use_pass_cryptomatte_object = True
```

Cryptomatte gives per-object masks for compositing without re-rendering - enable
it on anything destined for post. Save as **OpenEXR multilayer** to keep passes
in one file.
