"""Regression suite for the Blender Copilot bridge.

Run against a live Blender with the addon enabled:
    python3 test_bridge.py

Covers the two things that make or break a bridge: main-thread marshalling and
context resolution across editor types.
"""

import sys

from client import Bridge

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{('  -- ' + str(detail)) if detail and not cond else ''}")


def setup(b):
    """Deterministic scene: fresh file plus the datablocks the editors need."""
    r = b.call(
        "run_python",
        code="""
import bpy
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.mesh.primitive_cube_add()
# bpy.context.active_object is absent right after read_homefile -- the context
# has no 3D-view screen yet. The view layer always resolves.
cube = bpy.context.view_layer.objects.active
cube.name = "Cube"
if not cube.data.uv_layers:
    cube.data.uv_layers.new()

mat = bpy.data.materials.new("BridgeMat")
mat.use_nodes = True
cube.data.materials.append(mat)

bpy.context.scene.use_nodes = True

cube.keyframe_insert(data_path="location", frame=1)
cube.location.x += 2
cube.keyframe_insert(data_path="location", frame=20)

bpy.ops.object.camera_add()
bpy.ops.object.light_add(type="SUN")
bpy.context.view_layer.objects.active = cube
cube.select_set(True)
"scene ready"
""",
    )
    assert r["error"] is None, r["error"]


def test_transport(b):
    print("\n[transport]")
    check("ping responds", b.call("ping")["pong"] is True)
    r = b.call("run_python", code='print("out"); 1 + 1')
    check("stdout captured", r["stdout"].strip() == "out", r["stdout"])
    check("expression value returned", r["value"] == "2", r["value"])
    r = b.call("run_python", code="1/0")
    check("exception captured not raised", r["error"]["type"] == "ZeroDivisionError")
    b.call("run_python", code="_persist = 7")
    check("namespace persists across calls", b.call("run_python", code="_persist")["value"] == "7")
    r = b.call("run_python", code="_persist", reset_namespace=True)
    check("namespace reset works", r["error"] is not None)

    # Large payload must survive chunked socket reads.
    big = "x = [" + ",".join(str(i) for i in range(20000)) + "]\nlen(x)"
    check("large payload (>100KB) round-trips", b.call("run_python", code=big)["value"] == "20000")


def test_context(b):
    """Each namespace needs a different editor; none of them are open by default."""
    print("\n[context resolution]")
    cases = [
        ("object.shade_smooth", {}),
        ("mesh.select_all", {"action": "SELECT"}),
        ("node.select_all", {"action": "SELECT"}),
        ("uv.select_all", {"action": "SELECT"}),
        ("graph.select_all", {"action": "SELECT"}),
        ("sequencer.refresh_all", {}),
        ("outliner.expanded_toggle", {}),
        ("anim.channels_expand", {}),
        ("transform.translate", {"value": (0.1, 0, 0)}),
    ]
    for name, args in cases:
        needs_edit = name.startswith(("mesh.", "uv."))
        if needs_edit:
            b.call("run_python", code='import bpy; bpy.ops.object.mode_set(mode="EDIT"); '
                                      'bpy.ops.mesh.select_all(action="SELECT")')
        r = b.call("call_operator", name=name, args=args)
        check(f"{name} runs with synthesized context", "result" in r,
              r.get("error", {}).get("message"))
        if needs_edit:
            b.call("run_python", code='import bpy; bpy.ops.object.mode_set(mode="OBJECT")')


def test_area_restoration(b):
    print("\n[area restoration]")
    before = b.call("ping")["context"]["areas"]
    for name, args in [("node.select_all", {"action": "SELECT"}),
                       ("sequencer.refresh_all", {}),
                       ("graph.select_all", {"action": "SELECT"})]:
        b.call("call_operator", name=name, args=args)
    after = b.call("ping")["context"]["areas"]
    check("borrowed areas restored to original layout", before == after, f"{before} != {after}")


def test_errors(b):
    print("\n[error reporting]")
    r = b.call("call_operator", name="nonsense.operator")
    check("unknown operator reported", "error" in r)
    r = b.call("call_operator", name="notanamespace")
    check("malformed name reported", r["error"]["type"] == "ValueError")
    r = b.call("call_operator", name="mesh.subdivide")
    check("poll failure is a clean error with context",
          "error" in r and r["error"]["type"] == "PollError" and "context" in r)


def test_introspection(b):
    print("\n[introspection]")
    s = b.call("get_scene", detail="full")
    names = {o["name"] for o in s["objects"]}
    check("scene lists objects", "Cube" in names, names)
    cube = next(o for o in s["objects"] if o["name"] == "Cube")
    check("mesh stats present", cube["mesh"]["vertices"] == 8, cube.get("mesh"))
    check("materials listed", "BridgeMat" in cube["materials"], cube["materials"])
    r = b.call("inspect_rna", path="bpy.context.scene.render")
    check("rna introspection returns properties", len(r["properties"]) > 50, len(r.get("properties") or []))
    enums = [p for p in r["properties"] if p["type"] == "ENUM" and p.get("values")]
    check("enum values enumerated", len(enums) > 0)


def test_render(b):
    print("\n[visual feedback]")
    r = b.call("render_view", mode="viewport", width=320, height=180, _timeout=180)
    ok = "error" not in r and len(r.get("base64", "")) > 1000
    check("viewport render returns png", ok, r.get("error"))
    if ok:
        import base64
        check("png magic bytes valid", base64.b64decode(r["base64"][:16])[:4] == b"\x89PNG")


def main():
    b = Bridge().connect()
    setup(b)
    test_transport(b)
    test_context(b)
    test_area_restoration(b)
    test_errors(b)
    test_introspection(b)
    test_render(b)

    print(f"\n{'='*56}\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        for f in FAIL:
            print(f"  - {f}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
