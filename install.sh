#!/usr/bin/env bash
# Wire this checkout into Blender and your MCP client. Safe to re-run - it just
# repoints everything at wherever the repo currently lives, which is what you
# want after moving it.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLENDER_VER="${BLENDER_VER:-4.5}"

case "$(uname -s)" in
  Darwin) ADDONS="$HOME/Library/Application Support/Blender/$BLENDER_VER/scripts/addons" ;;
  Linux)  ADDONS="$HOME/.config/blender/$BLENDER_VER/scripts/addons" ;;
  *)      echo "Unsupported OS. Set ADDONS= by hand and re-run." >&2; exit 1 ;;
esac

mkdir -p "$ADDONS"
ln -sfn "$REPO/addon/blender_copilot" "$ADDONS/blender_copilot"
echo "addon  -> $ADDONS/blender_copilot"

if [ -d "$HOME/.claude/skills" ]; then
  ln -sfn "$REPO/skill" "$HOME/.claude/skills/blender"
  echo "skill  -> $HOME/.claude/skills/blender"
fi

python3 -m venv "$REPO/server/.venv"
"$REPO/server/.venv/bin/pip" install -q -r "$REPO/server/requirements.txt"
echo "venv   -> $REPO/server/.venv"

if command -v claude >/dev/null 2>&1; then
  claude mcp remove blender >/dev/null 2>&1 || true
  claude mcp add blender -- "$REPO/server/.venv/bin/python" "$REPO/server/mcp_server.py"
  echo "mcp    -> registered with claude"
else
  echo
  echo "claude CLI not found. Register the server manually:"
  echo "  command: $REPO/server/.venv/bin/python"
  echo "  args:    $REPO/server/mcp_server.py"
fi

echo
echo "Done. Enable 'Blender Copilot' in Blender > Preferences > Add-ons, then"
echo "open the N-panel in the 3D view and check the Copilot tab."
