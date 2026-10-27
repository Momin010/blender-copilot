import bpy, sys, json, os

out, *files = sys.argv[sys.argv.index("--") + 1:]
with open(out, "w") as f:
    for path in files:
        bpy.ops.wm.open_mainfile(filepath=path)
        for o in bpy.data.objects:
            if o.type != "MESH":
                continue
            m = o.data
            mats = [s.material for s in o.material_slots if s.material and s.material.node_tree]
            nodes = [n for mt in mats for n in mt.node_tree.nodes]
            mods = [x.type for x in o.modifiers]
            n = len(m.polygons)
            f.write(json.dumps({
                "file": os.path.basename(path), "object": o.name,
                "faces": n, "verts": len(m.vertices), "modifiers": len(mods),
                "has_uv": len(m.uv_layers) > 0,
                "mat_nodes": len(nodes),
                "image_textures": sum(x.type == "TEX_IMAGE" for x in nodes),
                "bevel": "BEVEL" in mods, "subsurf": "SUBSURF" in mods,
                "nonquad_share": sum(len(p.vertices) != 4 for p in m.polygons) / n if n else 0,
            }) + "\n")
