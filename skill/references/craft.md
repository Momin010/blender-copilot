# Craft rules

Human-made assets (Poly Haven) have real volume, baked bevels, textured PBR and clean names. AI output is usually slabs, flat colour and no detail. Measured on 920 human objects vs 1,889 AI objects (medians): 432 vs 46 faces, 12 vs 4 material nodes, 4 vs 0 image textures, UVs on 99.5% vs 50%, any modifier on 70% vs 19%. Follow these.

1. Never ship a single face, a bare primitive, or a plane with modifiers. Build real volume.
2. Metric, real-world size, scale applied (Ctrl+A) before any bevel.
3. Bevel every visible hard edge (2-3 segments, width about 1-3 percent of the smaller dimension), then Weighted Normal (Keep Sharp) last in the stack. Shade Smooth first. 4.1+ has no Auto Smooth checkbox.
4. Every material is Principled with roughness varied by noise or a texture. Metals: metallic 1.0, roughness 0.2-0.5 with variation. Add Bump or Normal Map.
5. Unwrap UVs for any part with image textures. Never a flat colour.
6. Add detail until both silhouette and close-up read: panel lines, fasteners, labels, fillets, vents.
7. Name objects and materials, use collections, one material per real material.
8. HDRI plus key and rim light; camera 50-85 mm for products, depth of field on.
9. Verify placement numerically (bounding boxes, gaps), then render a close-up and a wide shot.
10. For organic or very detailed shapes, import a real CC0 asset (Poly Haven) instead of faking it from primitives.

Full evidence: ~/software/tools/blender-copilot/research/blender-human-vs-ai.md
