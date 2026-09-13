# Blender Copilot - Roadmap

Goal: give an AI agent real, real-time, collaborative control of Blender - not a
toy "make me a cube" bridge.

## Target version: 4.5 LTS (locked)

Blender dropped Intel-macOS builds after 4.5 LTS - 5.0/5.1/5.2 ship `arm64`
only. On an i9-9880H, **4.5 LTS is the terminal version** (supported to mid-2027).
Latest release overall is 5.2.0; there is no 6.0.

This is a feature, not a limitation: we build against a frozen LTS API.

## Ground truth (measured 2026-07-27, Blender 4.5.12 LTS)

| Metric | Value |
|---|---|
| `bpy.ops` operators | **2,391** across 77 namespaces |
| `bpy.types` RNA types | **3,780** |
| Geometry node types | 216 |
| Embedded Python | 3.11.11 |
| Source (shallow, v4.5 branch) | `./source`, commit 84afd5f7 |

Largest operator namespaces: `object` (242), `mesh` (161), `node` (147),
`grease_pencil` (116), `wm` (111), `sequencer` (100), `clip` (92).

Full machine-readable inventory: `research/operators.json`.

## The central design constraint

**2,391 operators cannot become 2,391 MCP tools.** Agents degrade badly past
~50-100 tools, and the context cost of the schemas alone would be enormous.

Every existing Blender MCP hits this wall and responds by hand-picking a small
subset - e.g. one popular server exposes 22 tools, another 69. That is why they
all feel like toys: they expose ~1-3% of Blender and the agent can't reach the
rest.

**Our answer: two mechanisms, one index.**

### 1. Deferred tool loading (progressive disclosure)

Nothing is loaded up front. The agent sees only a lean *index* of what exists.
It reasons about intent ("the user is making a movie"), queries the index, and
only the matching handful of tool schemas are injected into context.

This is a real, shipping pattern, not speculation - MCP supports it natively via
`notifications/tools/list_changed`, and Claude Code itself implements it
(`ToolSearch` + deferred tools). We have a working reference to copy.

**Critical constraint:** context is append-only. *Unloading* a tool does not
reclaim its tokens - once a schema is in the conversation it stays. All savings
come from **never loading** the 2,380 tools that were never needed. The
load/unload lifecycle is therefore not where the engineering effort goes.

Where it does go: **retrieval quality.** Mapping "make a movie" → the correct
~15 of 2,391 operators is a search problem, and it is the make-or-break
component of this project. A wrong index silently starves the agent of the tool
it needed.

### 2. Code as the interface

For the long tail the index can't anticipate, a `run_python` tool executes
arbitrary `bpy` inside Blender. Capability lives in generated code (unbounded)
rather than tool schemas (bounded).

### The skill is the index

These fuse: the skill is not merely documentation. It is the retrieval layer -
the thing that turns intent into the right slice of the operator graph, and
teaches the agent to write correct `bpy` for everything else. It is the
centerpiece of the project, not a preparatory step.

## Known hard problems (must be solved, not worked around)

1. **Main-thread marshalling.** `bpy` is not thread-safe. A socket thread must
   enqueue; a `bpy.app.timers` callback on the main thread must dequeue and
   execute. Non-negotiable.
2. **Operator context.** Most `bpy.ops` calls `poll()`-fail when invoked outside
   a real UI context (no active area/region/object). Requires a context-override
   resolver that synthesizes a valid context per operator.
3. **Prefer the data API.** Where possible, bypass `bpy.ops` entirely for
   `bpy.data` / `bmesh` / direct RNA writes - faster, deterministic, no context
   problem, no undo-stack pollution.
4. **Feedback loop.** An agent that cannot see the result is guessing. Needs
   viewport render-back, structured scene graph introspection, and error capture.
5. **Real-time human collaboration.** Must not block the UI, must not stomp the
   user's selection/mode, must be undoable as discrete steps.

## Phases

- **Phase 1 - Research.** Deep feature survey of Blender: every major subsystem,
  how professionals actually use it, and the API path to each. Output: the
  research doc (~5k words) + operator/RNA inventory. *In progress.*
- **Phase 2 - The Skill.** Convert research into a progressively-disclosed skill
  for Claude/Codex: core `bpy` idioms + per-domain reference files.
- **Phase 3 - The Bridge.** Blender addon (main-thread executor, context
  resolver, introspection, render-back) + MCP server.
- **Phase 4 - Collaboration.** Real-time bidirectional sync, undo integration,
  agent-visible viewport state.

## Layout

```
blender-copilot/
  source/      Blender 4.5 LTS source (shallow clone, reference only)
  research/    Phase 1 outputs - inventory JSON + the feature doc
  skill/       Phase 2 - the Claude/Codex skill
  addon/       Phase 3 - Blender-side addon
  server/      Phase 3 - MCP server
```
