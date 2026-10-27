import json, statistics as s
K = ["faces", "verts", "modifiers", "mat_nodes", "image_textures", "nonquad_share"]
def load(p, dedupe):
    seen, rows = set(), []
    for l in open(p):
        r = json.loads(l)
        k = tuple(v for a, v in r.items() if a != "file")
        if dedupe and k in seen:
            continue
        seen.add(k)
        rows.append(r)
    return rows
for name, dd in [("human", False), ("ai", True)]:
    r = load(f"data/{name}.jsonl", dd)
    print(name, "objects", len(r), "files", len({x["file"] for x in r}))
    for k in K:
        print(" ", k, round(s.median(x[k] for x in r), 3))
    for k in ["has_uv", "bevel", "subsurf"]:
        print(" ", k, "share", round(sum(x[k] for x in r) / len(r), 3))
    print("  with modifiers", round(sum(x["modifiers"] > 0 for x in r) / len(r), 3))
    print("  faces<=6", round(sum(x["faces"] <= 6 for x in r) / len(r), 3))
