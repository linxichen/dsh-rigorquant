#!/bin/sh
# Install the dsh-rigorquant agent preset (and its bundled skills) into DSH.
#   ./install.sh                 → install everything: preset, compute lane, and the
#                                  plugin (model router + settings card) into a profile
#   ./install.sh --skill-only    → install only the skills, for use with any preset
#                                  and WITHOUT the plugin
#   ./install.sh --uninstall     → remove everything this script installed
#   ./install.sh --version       → print the bundled version
#   ./install.sh --help          → print usage
set -eu
DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
# The profile the plugin half is installed into. `dsh plugin` is a pnpm
# passthrough plus a reconcile step that appends any dependency declaring
# `dsh.bundle.patch` to that profile's dsh.profile.bundles.
PROFILE="${DSH_PROFILE:-web}"
HERE="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(sed -n 's/^[[:space:]]*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$HERE/package.json" 2>/dev/null | head -n1)"

usage() {
  cat <<EOF
Usage: $0 [--skill-only] [--uninstall] [--profile <name>] [--version] [--help]

  (no args)      Install everything: the RigorQuant preset, the shared compute
                 lane under \$DSH_HOME/share/rigorquant, and the plugin (role
                 model router + its Settings card) into the '$PROFILE' profile.
                 The plugin supplies the skills, so no global copies are made.
  --skill-only   Install ONLY the skills into \$DSH_HOME/skills, for use with
                 any preset and without the plugin.
  --uninstall    Remove the preset, skills, shared lane, and the plugin.
  --profile <n>  Profile to install the plugin into (default: $PROFILE).
  --version      Print the bundled version and exit.
  --help         Show this help and exit.
EOF
}

mode=full
while [ "$#" -gt 0 ]; do
  case "$1" in
    --skill-only) mode=skill ;;
    --uninstall)  mode=uninstall ;;
    --profile)
      shift
      [ "$#" -gt 0 ] || { printf 'error: --profile needs a name\n' >&2; exit 2; }
      PROFILE="$1"
      ;;
    --version)    printf 'dsh-rigorquant %s\n' "${VERSION:-unknown}"; exit 0 ;;
    --help|-h)    usage; exit 0 ;;
    *)            printf 'error: unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

# Install (or refresh) the plugin half in PROFILE. `dsh plugin ... add` runs
# pnpm in the profile directory and then reconciles dsh.profile.bundles, so a
# package declaring `dsh.bundle.patch` — this one — becomes a profile layer
# without the user editing any manifest. Installing from "$HERE" rather than
# the registry keeps the plugin and this checkout in step; a stale profile copy
# is the one failure mode that looks like the plugin simply not working.
install_plugin() {
  if ! command -v dsh >/dev/null 2>&1; then
    printf 'warning: dsh is not on PATH; skipped installing the plugin into the "%s" profile.\n' "$PROFILE" >&2
    printf '         install it later with: dsh plugin --profile %s add %s\n' "$PROFILE" "$HERE" >&2
    return 0
  fi
  # `file:` explicitly: pnpm resolves a bare directory argument as `link:`, a
  # live symlink into this checkout, so moving or deleting the clone would
  # break the installed profile. An installer should leave a self-contained
  # copy behind. The cost is that editing this checkout no longer changes the
  # installed plugin -- re-run this script to refresh it.
  if dsh plugin --profile "$PROFILE" add "file:$HERE" >/dev/null 2>&1; then
    echo "Installed the plugin into the '$PROFILE' profile (model router + Settings card)."
  else
    printf 'warning: `dsh plugin --profile %s add %s` failed; the preset and lane are installed, the plugin is not.\n' "$PROFILE" "$HERE" >&2
  fi
}

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
  if command -v dsh >/dev/null 2>&1; then
    # Removing the dependency drops it from dsh.profile.bundles in the same
    # reconcile step that added it, so no manifest is left naming a package
    # that is gone.
    dsh plugin --profile "$PROFILE" remove dsh-rigorquant >/dev/null 2>&1 \
      && echo "Removed the plugin from the '$PROFILE' profile." \
      || true
  fi
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
  # No global skill copies here on purpose: the plugin installed below carries
  # the same skills and serves them from a custom root, which outranks
  # $DSH_HOME/skills. Copying them too would only create shadowed spares that
  # drift out of date. --skill-only is the mode for people who want the skills
  # without the plugin.
  install_plugin
  echo "Installed preset to $DSH_HOME/.agent-presets/rigorquant"
  echo "Installed compute lane to $DSH_HOME/share/rigorquant"
  echo "Start a new session and pick the 'RigorQuant' preset in the session picker."
fi
