# How Professionals Actually Work

Knowing 3,064 capabilities is not the same as knowing the order to use them in.
This file is about sequence and judgement.

## The universal principle: stay non-destructive

Amateur Blender applies everything immediately. Professional Blender defers
commitment as long as possible: modifiers instead of edits, node trees instead
of baked geometry, constraints instead of keyframes, collections instead of
duplicated objects.

The reason is not purity — it is that **every project changes direction**. Work
that can absorb a change costs hours; work that cannot costs days.

Apply a modifier only when you need the result as real geometry: export,
booleans, per-vertex sculpting. Then keep the unapplied version in a hidden
collection.

## Modelling

1. **Blockout** with primitives. Get proportion and silhouette right before any
   detail. Most bad models are bad at this stage and no amount of detail rescues them.
2. **Refine** the base mesh. Keep it quad-dominant and light — a few thousand
   polygons. Subdivision adds density later.
3. **Modifiers** for repetition and smoothing: Mirror for symmetry, Array for
   repeats, Subdivision Surface for smooth forms, Bevel for edge highlights.
4. **Retopology** only if the model came from sculpting and needs clean
   topology for animation.
5. **UV unwrap** with deliberate seams, then pack.

Modifier order is not cosmetic: Mirror before Subdivision welds the seam;
Subdivision before Mirror produces a visible crease down the middle.

Edge flow should follow the form's structure — loops around eyes and mouths on a
face, along panel lines on hard surfaces. Triangles and n-gons are fine on
static props and a real problem on anything that deforms.

## Hard-surface vs organic

**Hard surface** (machines, architecture, props): booleans plus Bevel and
Weighted Normals. Sharp, controlled edges. Bevel needs a small width and 2–3
segments to catch light — an unbevelled edge is perfectly sharp and therefore
invisible, which is why untextured hard-surface renders look flat.

**Organic** (creatures, characters): sculpt from a base mesh with dynamic
topology or multiresolution, then retopologize to clean quads for animation.

## Texturing

1. Unwrap first. Texturing before UVs wastes the work.
2. Block in base materials with Principled BSDF — get value and roughness
   relationships right before detail.
3. Add variation: nothing in reality is uniform. Noise into roughness is the
   cheapest realism upgrade available.
4. Add wear where it physically happens: edges, crevices, contact points.
   Pointiness from the Geometry node masks this procedurally.

Roughness variation reads as more realistic than color variation. A single-color
object with varied roughness looks real; a multicolored object with flat
roughness looks like plastic.

## Lighting

Light before texturing if the mood is defined; texture first if the object is.

Start with an HDRI for ambient, then add a key. Judge in the final view
transform (AgX) — lighting judged in Standard will be wrong.

Contrast is what makes an image read. Evenly lit scenes are the most common
failure, and they look like renders rather than photographs.

## Animation

1. **Blocking** — key the extreme poses only, on constant interpolation. Judge
   timing before touching anything else.
2. **Spline** — switch to Bezier and let motion flow between the keys.
3. **Polish** — overlapping action, follow-through, breakdowns.

Timing and spacing carry almost all of the quality. Smooth interpolation on
badly timed keys is still bad animation.

Animate on 2s (a key every 2 frames) for stylized work; 1s for realism.

## Simulation

Simulations are slow and iterative. Work at low resolution until behaviour is
right, then raise it once. Always bake before rendering — an unbaked sim can
evaluate differently and pop.

Order matters: cloth on an animated character needs the animation finished
first. Re-animating after simulating means re-simulating.

## Rendering and output

- Iterate at 25–50% resolution.
- Denoise; do not brute-force samples.
- Render image sequences, never straight to video.
- Enable Cryptomatte if there is any chance of compositing.
- Save passes as multilayer EXR.

## Compositing

Grading in the compositor is far cheaper than re-rendering. Standard chain:
Render Layers → Denoise → Glare → Color Balance → Composite.

Subtle glare on highlights and a slight vignette do more for perceived quality
than most 3D-side work. But compositing cannot fix bad lighting — it amplifies
what is there.

## Video editing (VSE)

Blender's sequencer is genuinely capable for assembling shots:

```python
scene.sequence_editor_create()
se = scene.sequence_editor
strip = se.sequences.new_movie("shot01", "/renders/shot01.mp4", channel=1, frame_start=1)
```

Also accepts image sequences (`new_image`), and `new_scene` to reference a
Blender scene directly — that is how you cut between shots without exporting.

## Common failure modes

| Symptom | Usual cause |
|---|---|
| Render is black | No camera assigned to `scene.camera`, or no lights |
| Object invisible | Created but never linked to a collection |
| Object renders despite being hidden | `hide_get()` hides the viewport only |
| Material looks wrong | Roughness/normal texture left in sRGB instead of Non-Color |
| Geometry nodes output nothing | Tree has no interface sockets |
| Scatter reports 4 vertices | Counting `to_mesh()` instead of depsgraph instances |
| Export loses the rig | Constraints not baked with `visual_keying=True` |
| Scene unusably slow | Instances realized when they did not need to be |
| Stale transform after frame change | Used `frame_current` instead of `frame_set()` |

## Judgement

When asked for something visual, look at the render before reporting success.
The pipeline can execute perfectly and still produce a bad image — geometry in
the right place, lighting flat, materials grey. Executing the operators is the
easy half.
