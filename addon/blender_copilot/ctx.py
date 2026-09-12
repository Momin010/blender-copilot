"""Context resolution for bpy.ops.

Most operators call poll() against bpy.context and refuse to run when the
expected UI state isn't there: mesh ops want a 3D viewport with an active mesh
in the right mode, node ops want a node editor whose tree matches, sequencer ops
want a sequencer, and so on. Driven headlessly or from a bridge, the "current"
context is whatever area the user happens to be hovering -- which is to say,
arbitrary.

So we synthesize a context: find an area of the type the operator needs, build
an override, and run inside it. When no such area is open we can temporarily
repurpose one, then put it back.
"""

import bpy

# Operator namespace -> the editor it expects. Derived from the 77 namespaces in
# the operator inventory; anything unlisted runs in whatever context is current.
NAMESPACE_AREA = {
    "mesh": "VIEW_3D",
    "object": "VIEW_3D",
    "view3d": "VIEW_3D",
    "sculpt": "VIEW_3D",
    "paint": "VIEW_3D",
    "curve": "VIEW_3D",
    "armature": "VIEW_3D",
    "pose": "VIEW_3D",
    "transform": "VIEW_3D",
    "gpencil": "VIEW_3D",
    "grease_pencil": "VIEW_3D",
    "node": "NODE_EDITOR",
    "sequencer": "SEQUENCE_EDITOR",
    "clip": "CLIP_EDITOR",
    "image": "IMAGE_EDITOR",
    "uv": "IMAGE_EDITOR",
    "mask": "IMAGE_EDITOR",
    "graph": "GRAPH_EDITOR",
    "action": "DOPESHEET_EDITOR",
    "anim": "DOPESHEET_EDITOR",
    "nla": "NLA_EDITOR",
    "outliner": "OUTLINER",
    "file": "FILE_BROWSER",
    "console": "CONSOLE",
    "text": "TEXT_EDITOR",
    "buttons": "PROPERTIES",
    "spreadsheet": "SPREADSHEET",
}

# Some editors are sub-types of an area type, selected via area.ui_type rather
# than area.type. The UV editor is an IMAGE_EDITOR with ui_type "UV" -- setting
# only area.type gives you the image viewer, where every uv.* operator
# poll()-fails. Same pattern for the compositor/geometry-node variants.
NAMESPACE_UI_TYPE = {
    "uv": "UV",
}

# The region an operator actually runs in. Almost always WINDOW; the exceptions
# are header/tool operators, which we don't special-case yet.
REGION = "WINDOW"


def _find_area(area_type, ui_type=None):
    """Return (window, area, region) for the first matching open area.

    When ui_type is given the sub-type must match too -- an IMAGE_EDITOR showing
    a render is not a UV editor, even though area.type is identical.
    """
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != area_type:
                continue
            if ui_type is not None and area.ui_type != ui_type:
                continue
            for region in area.regions:
                if region.type == REGION:
                    return window, area, region
    return None, None, None


def _largest_area():
    """Fallback donor area to temporarily convert. Picks the biggest so the
    swap is least likely to disturb a small pinned editor the user cares about."""
    best = None
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if best is None or (area.width * area.height) > (best[1].width * best[1].height):
                best = (window, area)
    return best


def _resolve_node_tree(hint):
    """Pick the node tree a node-editor operator should act on.

    Order: explicit hint, then the active object's active material, then its
    first geometry-nodes modifier, then the scene compositor, then any tree.
    """
    if hint:
        for coll in (bpy.data.materials, bpy.data.worlds):
            block = coll.get(hint)
            if block is not None and block.node_tree is not None:
                return block.node_tree, block
        tree = bpy.data.node_groups.get(hint)
        if tree is not None:
            return tree, tree

    ob = bpy.context.active_object
    if ob is not None:
        mat = getattr(ob, "active_material", None)
        if mat is not None and mat.node_tree is not None:
            return mat.node_tree, mat
        for mod in getattr(ob, "modifiers", []):
            if mod.type == "NODES" and getattr(mod, "node_group", None):
                return mod.node_group, mod.node_group

    scene = bpy.context.scene
    if scene.use_nodes and scene.node_tree is not None:
        return scene.node_tree, scene

    if bpy.data.node_groups:
        tree = bpy.data.node_groups[0]
        return tree, tree
    return None, None


# Blender's node-tree bl_idname -> the editor's tree_type enum value.
_TREE_TYPE = {
    "ShaderNodeTree": "ShaderNodeTree",
    "GeometryNodeTree": "GeometryNodeTree",
    "CompositorNodeTree": "CompositorNodeTree",
    "TextureNodeTree": "TextureNodeTree",
}


def _prepare_node_editor(space, hints):
    """A freshly-typed node editor has edit_tree == None, so every node operator
    poll()-fails. edit_tree is normally derived during draw; since we never draw,
    we pin a tree explicitly instead.

    Returns a restore callable.
    """
    tree, _owner = _resolve_node_tree(hints.get("node_tree"))
    if tree is None:
        return lambda: None

    prev = (space.tree_type, space.node_tree, space.pin)
    space.tree_type = _TREE_TYPE.get(tree.bl_idname, space.tree_type)
    space.node_tree = tree
    space.pin = True

    def restore():
        space.pin = prev[2]
        space.node_tree = prev[1]
        space.tree_type = prev[0]

    return restore


PREPARE = {"NODE_EDITOR": _prepare_node_editor}


class resolved:
    """Context manager yielding an override dict suitable for temp_override.

    Usage:
        with resolved("mesh") as override:
            with bpy.context.temp_override(**override):
                bpy.ops.mesh.subdivide()

    If the needed editor isn't open, converts the largest area to that type for
    the duration and restores it afterwards. Some editors additionally need
    their space configured before operators will poll -- see PREPARE.
    """

    def __init__(self, namespace, hints=None):
        self.area_type = NAMESPACE_AREA.get(namespace)
        self.ui_type = NAMESPACE_UI_TYPE.get(namespace)
        self.hints = hints or {}
        self._donor = None
        self._original_type = None
        self._original_ui_type = None
        self._restore_space = None

    def __enter__(self):
        if self.area_type is None:
            return {}

        window, area, region = _find_area(self.area_type, self.ui_type)

        if area is None:
            # No such editor open -- borrow one.
            found = _largest_area()
            if found is None:
                return {}
            window, donor = found
            self._donor = donor
            self._original_type = donor.type
            self._original_ui_type = donor.ui_type
            donor.type = self.area_type
            if self.ui_type is not None:
                donor.ui_type = self.ui_type
            area = donor
            region = next((r for r in area.regions if r.type == REGION), None)
            if region is None:
                self._restore()
                return {}

        prepare = PREPARE.get(self.area_type)
        if prepare is not None and area.spaces.active is not None:
            self._restore_space = prepare(area.spaces.active, self.hints)

        override = {"window": window, "area": area, "region": region}
        if window.screen is not None:
            override["screen"] = window.screen
        return override

    def __exit__(self, *exc):
        self._restore()
        return False

    def _restore(self):
        if self._restore_space is not None:
            try:
                self._restore_space()
            except (ReferenceError, AttributeError):
                pass  # area was retyped out from under us; nothing to restore
            self._restore_space = None
        if self._donor is not None and self._original_type is not None:
            # Restore ui_type last: assigning area.type resets the sub-type.
            self._donor.type = self._original_type
            if self._original_ui_type is not None:
                try:
                    self._donor.ui_type = self._original_ui_type
                except TypeError:
                    pass  # sub-type not valid for this area type; type alone suffices
            self._donor = None
            self._original_type = None
            self._original_ui_type = None


def describe():
    """What editors are currently available -- useful for diagnosing poll failures."""
    areas = {}
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            areas[area.type] = areas.get(area.type, 0) + 1
    return {
        "areas": areas,
        "mode": getattr(bpy.context, "mode", None),
        "active_object": getattr(getattr(bpy.context, "active_object", None), "name", None),
        "background": bpy.app.background,
    }
