#!/bin/sh
# Install the dsh-rigorquant agent preset (and its bundled skills) into DSH.
#   ./install.sh                 → install the preset + skills + shared compute lane
#   ./install.sh --skill-only    → install only the rigorquant + j-space skills (any preset)
#   ./install.sh --uninstall     → remove the installed preset, skills, and lane
#   ./install.sh --version       → print the bundled version
#   ./install.sh --help          → print usage
set -eu
DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
HERE="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(sed -n 's/^[[:space:]]*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$HERE/package.json" 2>/dev/null | head -n1)"

usage() {
  cat <<EOF
Usage: $0 [--skill-only] [--uninstall] [--version] [--help]

  (no args)      Install the RigorQuant preset, its bundled skills, and the
                 shared compute lane under \$DSH_HOME/share/rigorquant.
  --skill-only   Install only the rigorquant + j-space skills (for use with any preset).
  --uninstall    Remove the installed preset, skills, and shared lane.
  --version      Print the bundled version and exit.
  --help         Show this help and exit.
EOF
}

mode=full
case "${1:-}" in
  "")           mode=full ;;
  --skill-only) mode=skill ;;
  --uninstall)  mode=uninstall ;;
  --version)    printf 'dsh-rigorquant %s\n' "${VERSION:-unknown}"; exit 0 ;;
  --help|-h)    usage; exit 0 ;;
  *)            printf 'error: unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then
  printf 'error: too many arguments\n' >&2
  usage >&2
  exit 2
fi

# Copy SRC into a staging directory, then atomically swap it into DEST. This
# never leaves DEST missing on interruption and never silently destroys local
# modifications mid-copy. Runtime caches and the uv virtualenv are stripped:
# they are rebuilt by `uv sync` and must never be installed.
install_dir() {
  src="$1" dest="$2"
  parent="$(dirname "$dest")"
  mkdir -p "$parent"
  stage="$parent/.$(basename "$dest").tmp.$$"
  rm -rf "$stage"
  cp -R "$src" "$stage"
  find "$stage" \( -name '.venv' -o -name '__pycache__' \) -type d -prune -exec rm -rf {} \; 2>/dev/null || true
  find "$stage" \( -name '*.pyc' -o -name '.DS_Store' \) -delete 2>/dev/null || true
  rm -rf "$dest"
  mv "$stage" "$dest"
}

if [ "$mode" = uninstall ]; then
  rm -rf "$DSH_HOME/.agent-presets/rigorquant"
  rm -rf "$DSH_HOME/skills/rigorquant"
  rm -rf "$DSH_HOME/skills/j-space"
  rm -rf "$DSH_HOME/skills/arxiv"
  rm -rf "$DSH_HOME/skills/academic-paper-search"
  rm -rf "$DSH_HOME/share/rigorquant"
  echo "Removed the RigorQuant preset, skills, and shared lane."
  exit 0
fi

if [ "$mode" = skill ]; then
  install_dir "$HERE/agent-presets/rigorquant/skills/rigorquant" "$DSH_HOME/skills/rigorquant"
  install_dir "$HERE/agent-presets/rigorquant/skills/j-space" "$DSH_HOME/skills/j-space"
  install_dir "$HERE/agent-presets/rigorquant/skills/arxiv" "$DSH_HOME/skills/arxiv"
  install_dir "$HERE/agent-presets/rigorquant/skills/academic-paper-search" "$DSH_HOME/skills/academic-paper-search"
  echo "Installed skills to $DSH_HOME/skills/ (rigorquant, j-space, arxiv, academic-paper-search; the directory watcher loads them immediately)."
else
  install_dir "$HERE/agent-presets/rigorquant" "$DSH_HOME/.agent-presets/rigorquant"
  # Stable anchor for the compute lane + escalation docs. SKILL.md Step 2
  # resolves `env_lane` here so the lane is independent of the checkout.
  install_dir "$HERE/env" "$DSH_HOME/share/rigorquant/env"
  install_dir "$HERE/mcp" "$DSH_HOME/share/rigorquant/mcp"
  install_dir "$HERE/docs" "$DSH_HOME/share/rigorquant/docs"
  install_dir "$HERE/agent-presets/rigorquant/skills/j-space" "$DSH_HOME/skills/j-space"
  install_dir "$HERE/agent-presets/rigorquant/skills/arxiv" "$DSH_HOME/skills/arxiv"
  install_dir "$HERE/agent-presets/rigorquant/skills/academic-paper-search" "$DSH_HOME/skills/academic-paper-search"
  echo "Installed global skills j-space, arxiv + academic-paper-search to $DSH_HOME/skills/"
  # If this package is ALSO composed as a plugin (dsh plugin add dsh-rigorquant),
  # its bundle patch serves the same skills from inside the package. A custom
  # skill root outranks $DSH_HOME/skills, so the packaged copies win and these
  # become shadowed spares -- redundant, not conflicting.
  echo "  (shadowed by the packaged copies when dsh-rigorquant is also composed as a plugin)"
  echo "Installed preset to $DSH_HOME/.agent-presets/rigorquant"
  echo "Installed compute lane to $DSH_HOME/share/rigorquant"
  echo "Start a new session and pick the 'RigorQuant' preset in the session picker."
fi
