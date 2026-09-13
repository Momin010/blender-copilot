# Blender Copilot

An MCP bridge giving any AI copilot professional-grade control of Blender -
all **3,064 capabilities**, not a hand-picked subset.

Status: **working end to end.** 45/45 tests passing against live Blender 4.5.12 LTS.

<img src="demo/product-hero.png" width="380" alt="Product hero render">

`demo/product-hero.blend` - bevelled body, emissive gradient screen, studio
lighting, reflective floor, depth of field. Built and rendered through the
bridge, no hand-editing in the Blender UI.

## Why this is different

Existing Blender MCP servers expose 22–69 hand-picked tools, roughly 1–3% of
Blender, with no route to the rest. This one exposes everything through 8 tools.

Two mechanisms make that possible:

**Progressive disclosure.** Nothing is preloaded. The agent reads a lean domain
map, searches by intent, and pulls schemas only for what it is about to use.
(Context is append-only, so the saving comes from *never loading* the ~3,050
irrelevant capabilities - not from unloading afterwards.)

**Code as the interface.** For the long tail, `blender_python` runs arbitrary
`bpy` inside Blender. Capability lives in generated code, which is unbounded,
rather than in tool schemas, which are not.

## The capability surface

| Kind | Count | Reached via |
|---|---:|---|
| Operators | 2,391 | `bpy.ops.*` |
| Nodes | 523 | `node_tree.nodes.new(...)` |
| Modifiers | 83 | `object.modifier_add(type=...)` |
| Brushes | 30 | sculpt tool setting |
| Constraints | 28 | `object.constraint_add(type=...)` |
| Grease Pencil FX | 9 | `object.shaderfx_add(type=...)` |
| **Total** | **3,064** | |

The 673 non-operator entries matter more than the count suggests: they include
all 270 geometry nodes, which is most of what procedural work actually uses. An
operator-only index is blind to every one of them.

## Tools

| Tool | Purpose |
|---|---|
| `blender_domains` | Lean map of what exists - counts only, near-zero context cost |
| `blender_search` | Plain-language intent → matching capabilities |
| `blender_describe` | Full parameter schemas, on demand |
| `blender_call` | Run an operator with a synthesized UI context |
| `blender_python` | Arbitrary `bpy` for the long tail |
| `blender_scene` | Structured scene graph |
| `blender_inspect` | Live RNA introspection |
| `blender_render` | Viewport or final render, returned as an image |

## The two hard problems, solved

**Thread safety.** `bpy` is not thread-safe. The socket server never touches it:
requests are queued and drained by a `bpy.app.timers` callback on Blender's main
thread (`addon/blender_copilot/executor.py`).

**Operator context.** Most operators `poll()`-fail outside a real UI context. The
resolver finds or temporarily creates the editor each namespace needs, prepares
it, runs the operator, and restores the layout (`addon/blender_copilot/ctx.py`).
Two cases needed specific handling:

- *Node editors* have `edit_tree == None` until a tree is pinned, because
  `edit_tree` is normally derived during draw and the bridge never draws.
- *UV editing* needs `area.ui_type = 'UV'`, not just `area.type = 'IMAGE_EDITOR'` -
  setting only the area type gives you the image viewer, where every `uv.*`
  operator fails.

Verified working across VIEW_3D, NODE_EDITOR, IMAGE_EDITOR/UV, SEQUENCE_EDITOR,
GRAPH_EDITOR, DOPESHEET_EDITOR and OUTLINER.

## Layout

```
addon/blender_copilot/   Blender-side addon
  executor.py            main-thread job queue
  ctx.py                 context resolution
  handlers.py            RPC methods
  server.py              newline-delimited JSON-RPC over TCP
server/
  mcp_server.py          MCP server (8 tools)
  index.py               BM25 retrieval over all 3,064 capabilities
  client.py              bridge client
  test_bridge.py         27 tests
  test_mcp.py            18 tests
skill/                   the knowledge layer (installed to ~/.claude/skills/blender)
research/                operators.json, capabilities.json
source/                  Blender 4.5 LTS source, shallow clone (reference)
```

## Setup

Needs Blender 4.5 LTS and Python 3.10+.

```bash
git clone https://github.com/Momin010/blender-copilot
cd blender-copilot
./install.sh
```

That symlinks the addon into your Blender addons directory, symlinks the skill
into `~/.claude/skills/` if you use Claude Code, builds the server venv, and
registers the MCP server. It is safe to re-run - which is the point: if you move
the checkout, re-run it and every path gets repointed.

Then enable **Blender Copilot** in Preferences > Add-ons. The bridge starts with
Blender and listens on `127.0.0.1:9876`; toggle it by hand at **View3D > N-panel
> Copilot**.

`source/` is a shallow clone of Blender's own source, kept for reference. It is
gitignored and you do not need it - clone it yourself if you want it:

```bash
git clone --depth 1 -b blender-v4.5-release \
  https://projects.blender.org/blender/blender.git source
```

## Tests

45 tests, all of which need Blender open with the addon enabled.

```bash
cd server
.venv/bin/python test_bridge.py   # 27 - addon internals over the socket
.venv/bin/python test_mcp.py      # 18 - full MCP path, search through render
```

## License

GPL-3.0-or-later. Not a choice - the addon imports `bpy`, so it is a derivative
work of Blender and has to be GPL-compatible. The MCP server in `server/` runs
as its own process and only talks TCP, but it ships under the same license to
keep things simple.

## Version

Blender **4.5 LTS**, locked. Blender dropped Intel-macOS builds after 4.5, so
5.0/5.1/5.2 are Apple-Silicon only and cannot run on this hardware. 4.5 LTS is
supported to mid-2027. Blender 5.0 changed parts of the Geometry Nodes API
(bundles, closures) - that syntax does not apply here.
