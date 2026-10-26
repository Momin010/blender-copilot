# Human Blender work vs AI Blender work

Evidence: Poly Haven Barrel_01 (CC0) inspected headless; this repo's demo/product-hero.blend inspected the same way; web critiques of Blender MCP.

| Measured | Human (Poly Haven Barrel_01) | AI (our product-hero.blend) |
|---|---|---|
| Geometry | 1398 faces, 1284 quads, real dimensions 0.56 x 0.56 x 0.88 m, bevels baked into the mesh | Body is 1 face plus Bevel, Solidify, Bevel modifiers; everything is a modifier on a slab |
| Material | 12 nodes: Texture Coordinate, Mapping, image textures (diffuse, roughness/ARM, normal map), Normal Map node | Titanium, Floor, Island are 2 nodes (Principled + Output), flat values, no texture, no roughness variation |
| UVs | 1 clean UV layer, textures use it | 1 default layer, nothing uses it |
| Scene structure | Single named object, one named material, metric | No collections, 7 loose objects |
| Smoothing | Smooth shading with bevelled edges catching light | No Weighted Normal or smooth-by-angle on hard parts |
| Lighting | HDRI plus key/rim is the standard product setup | Key, Fill, Rim lights, 85 mm camera (this part is fine) |

## What generic MCP output looks like (web critiques)

- Python primitives give "boxes and blobs"; organic or detailed forms are very hard to build that way ([MindStudio](https://www.mindstudio.ai/blog/claude-blender-mcp-real-world-performance), [3D AI Studio](https://www.3daistudio.com/3d-generator-ai-comparison-alternatives-guide/blender-mcp)).
- Objects are often placed wrongly relative to each other and visual self-checks are inconsistent ([Practicaly](https://www.practicaly.ai/p/guide-claude-for-3d-design)).
- Materials are mostly colour, roughness and metallic numbers, no image textures.

## Differences and rules

| Difference | What humans do | Rule for the AI |
|---|---|---|
| Single-face slabs | Real volume, quads, edge loops | Model parts as real solids (extrude, loop cut, bmesh), never a plane plus Solidify |
| Sharp edges | Bevel every hard edge, 0.5-2 mm at real scale | Bevel width = 1-3 percent of the smaller dimension, 2-3 segments, Limit Method Angle or Weight |
| Shading | Smooth shading + Weighted Normal (Keep Sharp) after Bevel ([manual](https://docs.blender.org/manual/en/4.1/modeling/modifiers/normals/weighted_normal.html)) | Shade Smooth, then Bevel, then Weighted Normal last. 4.1+ has no Auto Smooth checkbox ([notes](https://developer.blender.org/docs/release_notes/4.1/modeling/)) |
| Flat materials | Image-based PBR with roughness map, normal map, wear | Every material needs roughness variation (noise or map), never one flat colour; add a Bump or Normal Map node |
| Scale | Metric, real size, scale applied | Unit system metric, model in metres at real size, apply scale (Ctrl+A) before bevel |
| Detail | Panel lines, screws, vents, fillets, small chamfers | Add secondary and tertiary detail: panel gaps, fasteners, labels, vents. Wrong if silhouette is a box |
| Structure | Named objects, collections, one material per part | Name everything, put parts in collections, parent assemblies |
| Lighting/camera | HDRI + key + rim, 50-85 mm product lens | HDRI plus key and rim, 50-85 mm, depth of field, filmic/AgX ("Medium High Contrast") |
| Verification | Look, fix, look again | Render a close-up and a wide shot after each stage; check placement by bounding boxes, not by eye alone |

## Rules the AI must follow

1. Never ship a part that is a single face, a bare primitive or a plane with modifiers. Build real volume.
2. Real-world metric scale, scale applied, before any bevel.
3. Bevel all visible hard edges (2-3 segments), then Weighted Normal last in the stack.
4. Every material: Principled with roughness varied by noise or a texture; metals metallic 1.0, roughness 0.2-0.5 with variation; add bump or normal.
5. UV unwrap any part that gets an image texture; procedural is fine otherwise, but never a flat colour.
6. Add detail until the silhouette and the close-up both read: panel lines, fasteners, labels, fillets.
7. Name objects and materials, use collections, one material per real-world material.
8. Light with HDRI plus key and rim; camera 50-85 mm for products, depth of field on.
9. Verify placement numerically (bounding boxes, gaps, contact), then render close-up and wide before calling it done.
10. For organic or very detailed shapes, say so and import a real asset (Poly Haven CC0) instead of faking it from primitives.

Not verified: modifier order beyond the manual's Weighted Normal page; the 1-3 percent bevel figure is a working heuristic, not a quoted standard.
