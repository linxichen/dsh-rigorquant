#!/bin/sh
# Install the dsh-rigorquant agent preset (and its bundled skill) into DSH.
#   ./install.sh                 → install the RigorQuant preset
#   ./install.sh --skill-only    → install only the rigorquant skill (any preset)
set -eu
DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL_ONLY=0
[ "${1:-}" = "--skill-only" ] && SKILL_ONLY=1

if [ "$SKILL_ONLY" -eq 1 ]; then
  DEST="$DSH_HOME/skills/rigorquant"
  mkdir -p "$(dirname "$DEST")"
  rm -rf "$DEST"
  cp -R "$HERE/agent-presets/rigorquant/skills/rigorquant" "$DEST"
  echo "Installed skill to $DEST (directory watcher loads it immediately)."
else
  DEST="$DSH_HOME/.agent-presets/rigorquant"
  mkdir -p "$(dirname "$DEST")"
  rm -rf "$DEST"
  cp -R "$HERE/agent-presets/rigorquant" "$DEST"
  echo "Installed preset to $DEST"
  echo "Start a new session and pick the 'RigorQuant' preset in the session picker."
fi
