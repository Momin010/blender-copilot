"""RPC method implementations.

Everything in this module runs on the main thread (dispatched via executor.submit),
so direct bpy access is safe here and only here.
"""

import io
import base64
import contextlib
import os
import tempfile
import traceback

import bpy

from . import ctx


def ping(_params):
    return {"pong": True, "blender": bpy.app.version_string, "context": ctx.describe()}


# --- Python execution -------------------------------------------------------

# Persistent namespace so an agent can build state across calls, the way a REPL
# does. Cleared only on explicit request.
_globals = {"__name__": "__copilot__"}


def run_python(params):
    """Execute arbitrary Python inside Blender and capture everything useful.

    Returns stdout, stderr, and the value of the final expression (if the last
    statement is one) -- so the agent gets feedback rather than guessing.
    """
    code = params.get("code", "")
    if params.get("reset_namespace"):
        _globals.clear()
        _globals["__name__"] = "__copilot__"
    _globals.setdefault("bpy", bpy)

    out, err = io.StringIO(), io.StringIO()
    value = None
    error = None

    try:
        import ast

        tree = ast.parse(code, mode="exec")
        # If the last statement is an expression, evaluate it separately so we
        # can report its value -- mirrors REPL behaviour.
        tail = None
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            tail = ast.Expression(tree.body.pop().value)

        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            if tree.body:
                exec(compile(tree, "<copilot>", "exec"), _globals)
            if tail is not None:
                value = eval(compile(tail, "<copilot>", "eval"), _globals)
    except BaseException as exc:  # noqa: BLE001 - surfaced to the agent, not raised
        error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }

    return {
        "stdout": out.getvalue(),
        "stderr": err.getvalue(),
        "value": _safe_repr(value),
        "error": error,
    }


def _safe_repr(v, limit=4000):
    if v is None:
        return None
    try:
        s = repr(v)
    except BaseException:  # noqa: BLE001
        return "<unreprable>"
    return s if len(s) <= limit else s[:limit] + f"... <truncated, {len(s)} chars>"


# --- Operator dispatch ------------------------------------------------------


def call_operator(params):
    """Invoke a bpy.ops operator with a synthesized context.

    `name` is the full path minus the prefix, e.g. "mesh.subdivide".
    """
    name = params.get("name", "")
    args = params.get("args") or {}
    exec_ctx = params.get("exec_context", "EXEC_DEFAULT")
    hints = params.get("context_hints") or {}

    if "." not in name:
        return {"error": {"type": "ValueError", "message": f"bad operator name: {name!r}"}}
    namespace, op_name = name.split(".", 1)

    module = getattr(bpy.ops, namespace, None)
    if module is None:
        return {"error": {"type": "AttributeError", "message": f"no namespace bpy.ops.{namespace}"}}
    op = getattr(module, op_name, None)
    if op is None:
        return {"error": {"type": "AttributeError", "message": f"no operator {name}"}}

    with ctx.resolved(namespace, hints) as override:
        try:
            with bpy.context.temp_override(**override):
                if not op.poll():
                    return {
                        "error": {
                            "type": "PollError",
                            "message": (
                                f"{name}.poll() failed -- Blender's state does not allow this "
                                f"operator right now"
                            ),
                        },
                        "context": ctx.describe(),
                    }
                result = op(exec_ctx, **args)
        except BaseException as exc:  # noqa: BLE001
            return {
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                },
                "context": ctx.describe(),
            }

    return {"result": list(result)}


# --- Scene introspection ----------------------------------------------------


def get_scene(params):
    """Structured scene graph. The agent's eyes on the data side."""
    detail = params.get("detail", "summary")
    scene = bpy.context.scene

    objects = []
    for ob in scene.objects:
        entry = {
            "name": ob.name,
            "type": ob.type,
            "visible": ob.visible_get(),
            "location": list(ob.location),
        }
        if detail == "full":
            entry.update(
                {
                    "rotation_euler": list(ob.rotation_euler),
                    "scale": list(ob.scale),
                    "parent": ob.parent.name if ob.parent else None,
                    "modifiers": [{"name": m.name, "type": m.type} for m in ob.modifiers],
                    "materials": [s.material.name for s in ob.material_slots if s.material],
                    "collections": [c.name for c in ob.users_collection],
                }
            )
            if ob.type == "MESH" and ob.data:
                entry["mesh"] = {
                    "vertices": len(ob.data.vertices),
                    "edges": len(ob.data.edges),
                    "polygons": len(ob.data.polygons),
                }
        objects.append(entry)

    return {
        "scene": scene.name,
        "engine": scene.render.engine,
        "frame": {"current": scene.frame_current, "start": scene.frame_start, "end": scene.frame_end},
        "fps": scene.render.fps,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "active_object": bpy.context.active_object.name if bpy.context.active_object else None,
        "selected": [o.name for o in bpy.context.selected_objects],
        "mode": bpy.context.mode,
        "object_count": len(objects),
        "objects": objects,
        "counts": {
            "materials": len(bpy.data.materials),
            "meshes": len(bpy.data.meshes),
            "node_groups": len(bpy.data.node_groups),
            "images": len(bpy.data.images),
            "actions": len(bpy.data.actions),
            "collections": len(bpy.data.collections),
        },
    }


def inspect_rna(params):
    """Describe a bpy.types class or a live datablock path -- properties, types,
    and current values. Lets the agent discover the API instead of guessing."""
    target = params.get("path", "")
    try:
        obj = eval(target, {"bpy": bpy})  # noqa: S307 - deliberate introspection
    except BaseException as exc:  # noqa: BLE001
        return {"error": {"type": type(exc).__name__, "message": str(exc)}}

    rna = getattr(obj, "bl_rna", None)
    if rna is None:
        return {"path": target, "repr": _safe_repr(obj), "properties": None}

    props = []
    for p in rna.properties:
        if p.identifier == "rna_type":
            continue
        entry = {
            "name": p.identifier,
            "type": p.type,
            "description": p.description,
            "readonly": p.is_readonly,
        }
        if p.type == "ENUM":
            entry["values"] = [i.identifier for i in p.enum_items]
        props.append(entry)

    return {
        "path": target,
        "rna": rna.identifier,
        "description": rna.description,
        "repr": _safe_repr(obj, 500),
        "properties": props,
    }


# --- Visual feedback --------------------------------------------------------


def render_view(params):
    """Render the scene (or an OpenGL viewport snapshot) and return it as PNG
    base64, so the agent can actually see what it built."""
    mode = params.get("mode", "viewport")
    width = int(params.get("width", 960))
    height = int(params.get("height", 540))

    scene = bpy.context.scene
    saved = (
        scene.render.resolution_x,
        scene.render.resolution_y,
        scene.render.resolution_percentage,
        scene.render.filepath,
        scene.render.image_settings.file_format,
    )

    path = os.path.join(tempfile.gettempdir(), "copilot_render.png")
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.filepath = path
    scene.render.image_settings.file_format = "PNG"

    try:
        if mode == "viewport" and not bpy.app.background:
            with ctx.resolved("view3d") as override:
                with bpy.context.temp_override(**override):
                    bpy.ops.render.opengl(write_still=True)
        else:
            bpy.ops.render.render(write_still=True)

        with open(path, "rb") as fh:
            data = base64.b64encode(fh.read()).decode("ascii")
    except BaseException as exc:  # noqa: BLE001
        return {"error": {"type": type(exc).__name__, "message": str(exc),
                          "traceback": traceback.format_exc()}}
    finally:
        (
            scene.render.resolution_x,
            scene.render.resolution_y,
            scene.render.resolution_percentage,
            scene.render.filepath,
            scene.render.image_settings.file_format,
        ) = saved
        if os.path.exists(path):
            os.remove(path)

    return {"format": "png", "width": width, "height": height, "base64": data}


METHODS = {
    "ping": ping,
    "run_python": run_python,
    "call_operator": call_operator,
    "get_scene": get_scene,
    "inspect_rna": inspect_rna,
    "render_view": render_view,
}
