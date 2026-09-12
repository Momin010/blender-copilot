"""End-to-end test: drive the MCP server over stdio exactly as a client would."""

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{('  -- ' + str(detail)) if detail and not cond else ''}")


def text(result):
    for c in result.content:
        if c.type == "text":
            return c.text
    return ""


async def main():
    params = StdioServerParameters(command=sys.executable, args=["mcp_server.py"])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()

            print("\n[tool surface]")
            tools = (await s.list_tools()).tools
            names = sorted(t.name for t in tools)
            print("  tools:", ", ".join(names))
            check("small fixed tool surface (<=10)", len(tools) <= 10, len(tools))
            check("discovery tools present",
                  {"blender_domains", "blender_search", "blender_describe"} <= set(names))

            print("\n[discovery]")
            d = json.loads(text(await s.call_tool("blender_domains", {})))
            check("domain map reports full capability count",
                  d["total_capabilities"] > 3000, d["total_capabilities"])
            check("domains enumerated", len(d["domains"]) >= 10, len(d["domains"]))

            print("\n[retrieval -- intent to capability]")
            cases = [
                ("simulate cloth on this object", "CLOTH"),
                ("make an object follow a path", "FOLLOW_PATH"),
                ("add subdivision surface", "SUBSURF"),
                ("scatter objects over a surface", "GeometryNodeDistributePointsOnFaces"),
                ("bevel the selected edges", "mesh.bevel"),
                ("export the scene to USD", "wm.usd_export"),
                ("unwrap uvs", "uv.unwrap"),
                ("blur the compositor output", "CompositorNodeBlur"),
            ]
            for query, expected in cases:
                hits = json.loads(text(await s.call_tool("blender_search", {"query": query})))
                found = [h["name"] for h in hits]
                check(f'"{query}" -> {expected}', expected in found, f"got {found[:5]}")

            print("\n[schema on demand]")
            desc = json.loads(text(await s.call_tool("blender_describe", {"names": "mesh.bevel"})))
            check("operator described with live parameters",
                  desc[0].get("parameters") and len(desc[0]["parameters"]) > 5,
                  len(desc[0].get("parameters") or []))
            check("unknown name reports cleanly",
                  "error" in json.loads(text(await s.call_tool(
                      "blender_describe", {"names": "no.such_op"})))[0])

            print("\n[action]")
            await s.call_tool("blender_python", {"code":
                "import bpy\n"
                "bpy.ops.wm.read_homefile(use_empty=True)\n"
                "bpy.ops.mesh.primitive_cube_add()"})
            r1 = json.loads(text(await s.call_tool(
                "blender_call", {"name": "object.modifier_add", "args": '{"type": "SUBSURF"}'})))
            check("operator invoked via MCP", "result" in r1, r1)

            scene = json.loads(text(await s.call_tool("blender_scene", {"detail": "full"})))
            cube = next((o for o in scene["objects"] if o["type"] == "MESH"), None)
            check("modifier visible in scene readback",
                  cube and any(m["type"] == "SUBSURF" for m in cube["modifiers"]),
                  cube.get("modifiers") if cube else None)

            print("\n[long tail via python]")
            r2 = json.loads(text(await s.call_tool("blender_python", {"code":
                "import bpy\n"
                "mat = bpy.data.materials.new('Proc'); mat.use_nodes = True\n"
                "nt = mat.node_tree\n"
                "noise = nt.nodes.new('ShaderNodeTexNoise')\n"
                "bsdf = nt.nodes['Principled BSDF']\n"
                "nt.links.new(noise.outputs['Fac'], bsdf.inputs['Roughness'])\n"
                "len(nt.nodes)"})))
            check("node graph built via python", r2["error"] is None and r2["value"] == "3", r2)

            print("\n[visual feedback]")
            img = await s.call_tool("blender_render", {"mode": "viewport", "width": 320, "height": 180})
            kinds = {c.type for c in img.content}
            check("render returns an image", "image" in kinds, kinds)

    print(f"\n{'='*56}\n{len(PASS)} passed, {len(FAIL)} failed")
    for f in FAIL:
        print("  -", f)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
