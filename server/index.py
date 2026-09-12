"""Operator retrieval index.

The whole architecture rests on this: 2,391 operators cannot all live in the
agent's context, so the agent must be able to ask "what do I need for X" and get
back the right handful. Retrieval quality is the ceiling on the entire project --
a miss here silently starves the agent of the tool it needed.

Deliberately dependency-free (pure-python BM25). This runs inside whatever
environment the MCP server is launched from, and a pip install is a failure mode
we don't need.
"""

import json
import math
import os
import re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OPERATORS = os.path.join(HERE, "..", "research", "operators.json")
CAPABILITIES = os.path.join(HERE, "..", "research", "capabilities.json")

# Blender's UI vocabulary and users' vocabulary are not the same. An agent told
# "make a movie" must reach the sequencer; nothing in that namespace says "movie".
# These expansions are the bridge between intent and Blender's own naming.
SYNONYMS = {
    "movie": ["sequencer", "render", "animation", "frame", "video", "strip"],
    "video": ["sequencer", "strip", "movie", "render"],
    "edit": ["sequencer", "strip", "cut", "trim"],
    "film": ["render", "camera", "sequencer", "animation"],
    "animate": ["keyframe", "action", "fcurve", "anim", "pose"],
    "animation": ["keyframe", "action", "fcurve", "anim", "pose", "graph"],
    "rig": ["armature", "bone", "pose", "constraint", "weight"],
    "rigging": ["armature", "bone", "pose", "constraint", "weight"],
    "character": ["armature", "pose", "bone", "weight", "shape"],
    "texture": ["material", "image", "uv", "node", "shader"],
    "shading": ["material", "node", "shader"],
    "shader": ["material", "node"],
    "material": ["node", "shader"],
    "model": ["mesh", "vertex", "edge", "face", "extrude"],
    "modeling": ["mesh", "vertex", "edge", "face", "extrude"],
    "sculpt": ["brush", "dyntopo", "mask", "sculpt"],
    "procedural": ["node", "geometry", "modifier"],
    "simulation": ["physics", "rigidbody", "cloth", "fluid", "particle", "softbody"],
    "physics": ["rigidbody", "cloth", "fluid", "particle", "softbody", "collision"],
    "smoke": ["fluid", "physics", "domain"],
    "fire": ["fluid", "physics", "domain"],
    "light": ["lamp", "light", "world", "emission"],
    "lighting": ["lamp", "light", "world", "emission", "render"],
    "camera": ["camera", "view3d", "lens", "track"],
    "export": ["export", "wm", "io", "usd", "obj", "fbx", "gltf", "alembic"],
    "import": ["import", "wm", "io", "usd", "obj", "fbx", "gltf", "alembic"],
    "unwrap": ["uv", "seam", "unwrap", "island"],
    "retopo": ["mesh", "remesh", "decimate", "snap"],
    "vfx": ["clip", "track", "compositor", "node", "mask"],
    "tracking": ["clip", "track", "solve", "marker"],
    "compositing": ["node", "compositor", "render"],
    "grease": ["gpencil", "grease_pencil", "draw", "stroke"],
    "2d": ["gpencil", "grease_pencil", "image"],
    "hair": ["particle", "curves", "hair"],
    "cloth": ["cloth", "physics", "pin"],
    # Procedural vocabulary. Users say "scatter"; the node is called "Distribute
    # Points on Faces" and shares no word with the query -- pure lexical search
    # cannot bridge that on its own.
    "scatter": ["distribute", "points", "instance", "faces", "poisson"],
    "instance": ["instance", "realize", "points", "collection"],
    "duplicate": ["instance", "array", "duplicate", "copy"],
    "randomize": ["random", "noise", "value", "jitter"],
    "grow": ["extrude", "solidify", "offset"],
    "deform": ["deform", "lattice", "warp", "simple_deform", "cast"],
    "bend": ["simple_deform", "curve", "deform"],
    "smooth": ["smooth", "subsurf", "subdivision", "relax"],
    "reduce": ["decimate", "dissolve", "remesh"],
    "optimize": ["decimate", "remesh", "cleanup"],
    "cut": ["knife", "bisect", "boolean", "trim"],
    "hole": ["boolean", "inset", "delete"],
    "boolean": ["boolean", "modifier", "mesh"],
    "array": ["array", "modifier", "duplicate"],
    "mirror": ["mirror", "modifier", "symmetry"],
    "subdivide": ["subdivision", "subsurf", "smooth"],
}

# Namespaces grouped into the domains a user actually thinks in. Used for
# filtered browsing and for the domain map the agent reads first.
DOMAINS = {
    "modeling": ["mesh", "object", "curve", "curves", "surface", "transform", "metaball",
                 "modifier"],
    "sculpting": ["sculpt", "sculpt_curves", "brush", "paint"],
    "shading": ["material", "node", "world", "texture", "shader_node"],
    "uv": ["uv", "image"],
    "animation": ["anim", "action", "graph", "nla", "pose", "armature", "marker", "screen",
                  "constraint"],
    "rendering": ["render", "scene", "view3d", "cycles"],
    "compositing": ["node", "mask", "compositor_node"],
    "video": ["sequencer", "clip"],
    "physics": ["rigidbody", "fluid", "cloth", "ptcache", "particle", "physics", "boid"],
    "procedural": ["geometry_node", "node", "modifier"],
    "grease_pencil": ["gpencil", "grease_pencil", "paintcurve", "shader_fx"],
    "io": ["wm", "export_scene", "import_scene", "export_mesh", "import_mesh", "file", "asset"],
    "scripting": ["text", "console", "script", "preferences", "workspace"],
    "outliner": ["outliner", "collection", "object"],
}

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text):
    """Lowercase, split, and also split snake_case/CamelCase compounds so that
    'primitive_cube_add' matches a query for 'cube'."""
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return _TOKEN.findall(text.lower())


class OperatorIndex:
    """BM25 over Blender's full capability surface.

    Not just operators. Large parts of Blender are not operators at all --
    modifiers and constraints are enum values on a single `*_add` operator, and
    node types are pure RNA classes instantiated via `nodes.new()`. An
    operator-only index is blind to 673 capabilities including all 270 geometry
    nodes, which is most of what procedural work actually uses.
    """

    K1 = 1.5
    B = 0.75

    def __init__(self, path=OPERATORS, capabilities=CAPABILITIES):
        with open(path) as fh:
            raw = json.load(fh)

        self.ops = []
        for namespace, entries in raw.items():
            for e in entries:
                self.ops.append(
                    {
                        "kind": "operator",
                        "name": f"{namespace}.{e['n']}",
                        "namespace": namespace,
                        "description": e["desc"],
                        "properties": e["props"],
                        "usage": f"bpy.ops.{namespace}.{e['n']}(...)",
                    }
                )

        self.ops.extend(self._load_capabilities(capabilities))

        self._docs = []
        for op in self.ops:
            # Name tokens repeated: a query word appearing in the capability's
            # own name is a far stronger signal than one buried in prose.
            tokens = (
                _tokenize(op["name"]) * 3
                + _tokenize(op.get("label", "")) * 3
                + _tokenize(op["namespace"]) * 2
                + _tokenize(op["description"])
                + _tokenize(" ".join(op.get("properties", [])))
            )
            self._docs.append(Counter(tokens))

        self._lengths = [sum(d.values()) for d in self._docs]
        self._avglen = sum(self._lengths) / len(self._lengths)

        self._postings = defaultdict(list)
        for i, doc in enumerate(self._docs):
            for term in doc:
                self._postings[term].append(i)

        n = len(self._docs)
        self._idf = {
            term: math.log(1 + (n - len(ids) + 0.5) / (len(ids) + 0.5))
            for term, ids in self._postings.items()
        }

        self._by_name = {op["name"]: op for op in self.ops}

    @staticmethod
    def _load_capabilities(path):
        """Fold non-operator capabilities into the same searchable space, each
        carrying the exact call needed to use it."""
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            cat = json.load(fh)

        out = []
        for e in cat.get("modifiers", []):
            out.append({
                "kind": "modifier", "name": e["id"], "label": e["label"],
                "namespace": "modifier", "description": e["desc"],
                "usage": f"bpy.ops.object.modifier_add(type='{e['id']}')",
            })
        for e in cat.get("constraints", []):
            out.append({
                "kind": "constraint", "name": e["id"], "label": e["label"],
                "namespace": "constraint", "description": e["desc"],
                "usage": f"bpy.ops.object.constraint_add(type='{e['id']}')",
            })
        for e in cat.get("shader_fx", []):
            out.append({
                "kind": "shader_fx", "name": e["id"], "label": e["label"],
                "namespace": "shader_fx", "description": e["desc"],
                "usage": f"bpy.ops.object.shaderfx_add(type='{e['id']}')",
            })
        for e in cat.get("brushes", []):
            out.append({
                "kind": "brush", "name": e["id"], "label": e["label"],
                "namespace": "brush", "description": e["desc"],
                "usage": f"bpy.context.tool_settings.sculpt.brush.sculpt_tool = '{e['id']}'",
            })
        for e in cat.get("nodes", []):
            tree = e.get("tree") or "NodeTree"
            out.append({
                "kind": "node", "name": e["id"], "label": e["label"],
                "namespace": {"GeometryNodeTree": "geometry_node",
                              "ShaderNodeTree": "shader_node",
                              "CompositorNodeTree": "compositor_node",
                              "TextureNodeTree": "texture_node"}.get(tree, "node"),
                "description": e["desc"], "tree": tree,
                "usage": f"node_tree.nodes.new('{e['id']}')",
            })
        return out

    def __len__(self):
        return len(self.ops)

    def expand(self, query):
        """Add Blender-native vocabulary for the user's own words."""
        terms = _tokenize(query)
        out = list(terms)
        for t in terms:
            out.extend(SYNONYMS.get(t, []))
        return out

    def search(self, query, limit=15, domain=None, namespace=None):
        terms = self.expand(query)
        scores = defaultdict(float)

        for term in terms:
            ids = self._postings.get(term)
            if not ids:
                continue
            idf = self._idf[term]
            for i in ids:
                tf = self._docs[i][term]
                norm = 1 - self.B + self.B * self._lengths[i] / self._avglen
                scores[i] += idf * (tf * (self.K1 + 1)) / (tf + self.K1 * norm)

        allowed = None
        if domain:
            allowed = set(DOMAINS.get(domain, []))
        if namespace:
            allowed = {namespace} if allowed is None else (allowed & {namespace})

        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        results = []
        for i, score in ranked:
            op = self.ops[i]
            if allowed is not None and op["namespace"] not in allowed:
                continue
            results.append({**op, "score": round(score, 3)})
            if len(results) >= limit:
                break
        return results

    def get(self, name):
        return self._by_name.get(name)

    def domain_map(self):
        """The lean overview the agent reads before it knows what it needs.

        Counts only -- never the operators themselves. This is what keeps the
        default context cost near zero.
        """
        counts = Counter(op["namespace"] for op in self.ops)
        out = {}
        for domain, namespaces in DOMAINS.items():
            present = {ns: counts[ns] for ns in namespaces if counts.get(ns)}
            if present:
                out[domain] = {"operators": sum(present.values()), "namespaces": present}
        return out
