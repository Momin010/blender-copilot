"""Blender Copilot MCP server.

Architecture: progressive disclosure.

Blender exposes 3,064 distinct capabilities. Loading them as MCP tools is not an
option -- agents degrade badly past ~100 tools and the schemas alone would
dominate the context window. Instead the agent gets a small fixed tool set:

  blender_domains      the lean map -- what exists, counts only
  blender_search       intent -> the handful of capabilities that match
  blender_describe     full schema for specific capabilities, on demand
  blender_call         invoke an operator with a synthesized UI context
  blender_python       arbitrary bpy for the long tail
  blender_scene        structured scene graph
  blender_inspect      live RNA introspection
  blender_render       see the result

Note on "unloading": MCP conversation context is append-only, so dropping a tool
after use does not reclaim its tokens. The saving comes entirely from never
loading the ~3,050 capabilities a given task doesn't need. That is why the
schema surface here is fixed and small, and depth is reached through search
rather than through more tools.
"""

import base64
import json
import sys

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.types import Image

from client import Bridge, BridgeError
from index import OperatorIndex

mcp = FastMCP("blender-copilot")
_index = OperatorIndex()
_bridge = None


def bridge():
    """Lazy, self-healing connection to the addon inside Blender."""
    global _bridge
    if _bridge is None:
        _bridge = Bridge()
    try:
        _bridge.call("ping")
    except Exception:
        _bridge = Bridge()
        try:
            _bridge.connect()
        except OSError as exc:
            raise BridgeError(
                "Cannot reach Blender. Is it running with the Copilot Bridge addon "
                f"enabled (View3D > sidebar > Copilot)? Underlying error: {exc}"
            ) from exc
    return _bridge


# --- Discovery --------------------------------------------------------------


@mcp.tool()
def blender_domains() -> str:
    """Map of everything Blender can do, as counts by domain. Start here when you
    do not yet know which part of Blender a task needs. Costs almost nothing --
    it lists no individual capabilities. Follow up with blender_search."""
    return json.dumps(
        {
            "total_capabilities": len(_index),
            "domains": _index.domain_map(),
            "next": "call blender_search with a plain-language description of the goal",
        },
        indent=1,
    )


@mcp.tool()
def blender_search(query: str, limit: int = 12, domain: str = "", kind: str = "") -> str:
    """Find the Blender capabilities that match an intent, in plain language.

    Searches all 3,064 capabilities -- operators, geometry/shader/compositor
    nodes, modifiers, constraints and brushes -- not just operators. Many things
    users ask for (cloth, bevel, subdivision, follow-path) are modifiers or
    constraints rather than operators, so search rather than guessing an
    operator name.

    Args:
        query: what you want to achieve, e.g. "scatter rocks over a landscape"
        limit: max results
        domain: optional filter, one of the keys from blender_domains
        kind: optional filter -- operator, node, modifier, constraint, brush
    """
    hits = _index.search(query, limit=limit, domain=domain or None)
    if kind:
        hits = [h for h in hits if h["kind"] == kind]
    return json.dumps(
        [
            {
                "name": h["name"],
                "kind": h["kind"],
                "description": h["description"],
                "usage": h["usage"],
            }
            for h in hits
        ],
        indent=1,
    )


@mcp.tool()
def blender_describe(names: str) -> str:
    """Full detail for specific capabilities: every parameter, with types and
    enum values where available. Pass a comma-separated list of names returned
    by blender_search. This is the on-demand schema load -- only pull what you
    are about to use."""
    out = []
    for name in [n.strip() for n in names.split(",") if n.strip()]:
        entry = _index.get(name)
        if entry is None:
            out.append({"name": name, "error": "not found -- use blender_search"})
            continue
        record = dict(entry)
        # For operators, enrich with live RNA so the agent gets real types and
        # enum values rather than just property names.
        if entry["kind"] == "operator":
            try:
                rna = bridge().call("inspect_rna", path=f"bpy.ops.{name}.get_rna_type()")
                record["parameters"] = rna.get("properties")
            except Exception:
                pass  # static property list already present
        out.append(record)
    return json.dumps(out, indent=1)


# --- Action -----------------------------------------------------------------


@mcp.tool()
def blender_call(name: str, args: str = "{}", node_tree: str = "") -> str:
    """Run a Blender operator with a correctly synthesized UI context.

    Handles the context problem for you: finds or temporarily creates the editor
    the operator needs (3D viewport, node editor, UV editor, sequencer, ...),
    runs it there, and restores the layout afterwards.

    Args:
        name: operator name without the bpy.ops prefix, e.g. "mesh.subdivide"
        args: JSON object of operator arguments, e.g. '{"number_cuts": 2}'
        node_tree: for node operators, the material or node group to act on

    A PollError means Blender's *state* is wrong (wrong mode, nothing selected,
    no animation data), not that the context was missing -- fix the state first.
    """
    try:
        parsed = json.loads(args) if args.strip() else {}
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"args must be a JSON object: {exc}"})

    hints = {"node_tree": node_tree} if node_tree else {}
    result = bridge().call("call_operator", name=name, args=parsed, context_hints=hints)
    return json.dumps(result, indent=1)


@mcp.tool()
def blender_python(code: str, reset_namespace: bool = False) -> str:
    """Execute Python inside Blender with full bpy access, and get back stdout,
    the value of the final expression, and any traceback.

    This is the escape hatch for everything the fixed tool set does not cover --
    building node graphs, driving bmesh, batch edits, custom logic. Variables
    persist between calls like a REPL.

    Prefer the data API (bpy.data, bmesh, direct RNA assignment) over bpy.ops
    where you can: it is faster, deterministic, has no context requirements and
    does not flood the undo stack.
    """
    r = bridge().call("run_python", code=code, reset_namespace=reset_namespace)
    return json.dumps(r, indent=1)


# --- Feedback ---------------------------------------------------------------


@mcp.tool()
def blender_scene(detail: str = "summary") -> str:
    """The current scene as structured data: objects, types, transforms,
    modifiers, materials, mesh statistics, frame range, render engine.

    Call this before acting so you know what you are working with, and after
    acting to confirm it worked. detail is "summary" or "full"."""
    return json.dumps(bridge().call("get_scene", detail=detail), indent=1)


@mcp.tool()
def blender_inspect(path: str) -> str:
    """Introspect any live Blender object: its RNA type, every property, types,
    and enum options. Use this to discover the API instead of guessing.

    Example paths: "bpy.context.scene.render", "bpy.data.objects['Cube']",
    "bpy.data.materials['Mat'].node_tree.nodes['Principled BSDF']"
    """
    return json.dumps(bridge().call("inspect_rna", path=path), indent=1)


@mcp.tool()
def blender_render(mode: str = "viewport", width: int = 960, height: int = 540):
    # Deliberately unannotated: FastMCP dispatches on the runtime value, and a
    # `Image | str` union is not expressible as a pydantic return schema.
    """Render and return the image so you can actually see the current state.

    mode "viewport" is a fast OpenGL snapshot; "final" runs the render engine
    and is much slower. Look at the result rather than assuming your change
    worked."""
    r = bridge().call("render_view", mode=mode, width=width, height=height, _timeout=600)
    if "error" in r:
        return json.dumps(r)
    return Image(data=base64.b64decode(r["base64"]), format="png")


if __name__ == "__main__":
    try:
        mcp.run()
    except KeyboardInterrupt:
        sys.exit(0)
