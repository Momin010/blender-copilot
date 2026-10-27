# Blender: human vs AI-made meshes, measured

Human: 64 Poly Haven CC0 models (1k .blend), 920 mesh objects, 25 categories (furniture, props, tools, appliances, plants, rocks, ships and more). Downloaded by `api.polyhaven.com`, not committed.
AI: 23 .blend files found on this Mac outside Poly Haven and the Blender source tree (this repo's demo plus rocket, drone-sim and film scenes made in Claude sessions). 22 distinct files after dropping userpref.blend. Duplicates (HYPER1 patch copies, three microdome copies, two live_flight copies) are removed by identical object stats, leaving 12 files and 1889 unique mesh objects.

Method: `blendstats.py` (headless Blender 4.5) writes one JSON line per mesh object to `data/human.jsonl` and `data/ai.jsonl`; `medians.py` computes the table. Medians are per object.

| Metric (median per object) | Human | AI |
|---|---|---|
| Faces | 432 | 46 |
| Vertices | 508 | 76 |
| Modifiers | 2 | 0 |
| Material nodes | 12 | 4 |
| Image textures | 4 | 0 |
| Non-quad face share | 0.08 | 0.17 |
| Has UV layer | 99.5% | 50.4% |
| Has Bevel modifier | 26% | 10% |
| Has Subdivision modifier | 13% | 0.1% |
| Objects with any modifier | 70% | 19% |

## What it means

- AI objects are about 10x coarser (46 vs 432 faces). They read as primitives, which matches the one-asset note: a slab is one face, not a volume.
- Materials are the biggest gap. Humans use 4 image textures and 12 nodes; the AI median is zero textures and 4 nodes, so surfaces are flat Principled colours.
- Half of AI objects have no UV layer at all. Nearly every human object has one, so AI output cannot take a texture even if one is added later.
- AI uses modifiers rarely (19% of objects) and almost never Subdivision. The earlier demo shows the failure mode: when it does, it hangs bevels on a slab instead of modelling.
- Non-quad share is double (0.17 vs 0.08), consistent with imported STL triangles and primitive caps rather than edge-loop modelling.
- Bevels are present in only 10% of AI objects against 26% of human ones, so hard edges stay sharp and catch no light.

## Limitations

- AI provenance is by location and history, not verified per file. Some may have been hand-edited, and many are STL imports of Fusion rocket parts, which are low-poly by nature.
- The AI set is one person's rocket and sim work, 12 distinct files, heavily clustered (one scene gives 904 objects). Per-object medians are dominated by those scenes. This is not a random sample of AI Blender output.
- Poly Haven is curated high quality and prop-like. The AI files are mostly technical parts and scenes, so the task mix differs.
- Poly Haven models are often a few objects; Fusion-style parts are many small objects, which lowers AI medians by itself.
- Textures were not downloaded; image texture counts come from the node tree, not from loaded images. Modifier and bevel counts are from the stored stack, with applied modifiers invisible.
- No significance tests. Treat the direction as solid and the sizes as rough.
