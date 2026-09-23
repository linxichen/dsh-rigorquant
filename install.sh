#!/bin/sh
# Install the dsh-rigorquant agent preset (and its bundled skills) into DSH.
#   ./install.sh                 → install everything: preset, compute lane, and the
#                                  plugin (model router + its Plugins-page card) into a profile
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
MIN_DSH_VERSION="0.1.6-alpha.2"
# The two optional bundles that carry Agent Teams — the harness's Beta "Agent
# Teams" and "Agent Teams Web UI" cards on the Plugins page. RigorQuant 0.5.0
# runs team-only, so a full install enables both and raises the team
# service's lifetime member cap (docs/adr/0001-rigorquant-on-agent-teams.md).
TEAM_BUNDLE_HOST="@deepseek-ai/dsh-experimental-agent-team-profile"
TEAM_BUNDLE_WEB="@deepseek-ai/dsh-experimental-agent-team-web-profile"
# Marks the block this installer owns inside a profile's user patch
# (`cordis.patch.yml`), so a re-run finds it and `--uninstall` can remove
# exactly it and nothing the operator wrote by hand.
TEAM_PATCH_MARK_BEGIN='# >>> dsh-rigorquant BEGIN (managed by ./install.sh; see docs/adr/0001-rigorquant-on-agent-teams.md) >>>'
TEAM_PATCH_MARK_END='# <<< dsh-rigorquant END <<<'

usage() {
  cat <<EOF
Usage: $0 [--skill-only] [--uninstall] [--profile <name>] [--version] [--help]

  Full install requires DSH >= $MIN_DSH_VERSION; --skill-only does not.

  (no args)      Install everything: the RigorQuant preset, the shared compute
                 lane under \$DSH_HOME/share/rigorquant, and the plugin (role
                 model router + its card on the Plugins page) into the
                 '$PROFILE' profile. The plugin supplies the skills, so no
                 global copies are made.
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

# Compare semver, including prerelease identifiers, without relying on GNU
# `sort -V` (the installer also runs on macOS). DSH is a Node application, so
# node is already a deployment prerequisite whenever `dsh` is present.
version_at_least() {
  actual="$1" minimum="$2"
  node - "$actual" "$minimum" <<'NODE'
const [actual, minimum] = process.argv.slice(2)
function parse(raw) {
  const match = String(raw).trim().match(/^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$/)
  if (!match) return null
  return { numbers: match.slice(1, 4).map(Number), pre: match[4] === undefined ? null : match[4].split('.') }
}
function compare(a, b) {
  for (let i = 0; i < 3; i += 1) {
    if (a.numbers[i] !== b.numbers[i]) return a.numbers[i] - b.numbers[i]
  }
  if (a.pre === null && b.pre === null) return 0
  if (a.pre === null) return 1
  if (b.pre === null) return -1
  const length = Math.max(a.pre.length, b.pre.length)
  for (let i = 0; i < length; i += 1) {
    if (i >= a.pre.length) return -1
    if (i >= b.pre.length) return 1
    const left = a.pre[i]
    const right = b.pre[i]
    if (left === right) continue
    const leftNumber = /^\d+$/.test(left)
    const rightNumber = /^\d+$/.test(right)
    if (leftNumber && rightNumber) return Number(left) - Number(right)
    if (leftNumber !== rightNumber) return leftNumber ? -1 : 1
    return left < right ? -1 : 1
  }
  return 0
}
const a = parse(actual)
const b = parse(minimum)
if (a === null || b === null) process.exit(2)
process.exit(compare(a, b) >= 0 ? 0 : 1)
NODE
}

require_dsh_version() {
  actual="$(dsh --version 2>/dev/null || true)"
  if [ -z "$actual" ] || ! version_at_least "$actual" "$MIN_DSH_VERSION"; then
    printf 'error: dsh-rigorquant requires dsh >= %s (found %s)\n' \
      "$MIN_DSH_VERSION" "${actual:-unknown}" >&2
    printf '       upgrade the DSH CLI before installing the full preset.\n' >&2
    exit 2
  fi
}

# The full distribution is only mountable on the harness it was written
# against: the persona row uses the `prefix`/`suffix` split (0.1.3-alpha.2
# replaced the single `text` key, and a row whose config fails rejects the
# WHOLE preset mount), the child-delivery contract is the final assistant
# message (`report` was removed in 0.1.2-rc.1), the deliverables flow needs
# the `present` tool (0.1.5), and the browser half registers into slots
# 0.1.6-alpha.2 introduced — on 0.1.5 the routing card and the activity
# floater render nothing at all, silently. Fail before copying anything when
# the installed CLI is older; a missing CLI keeps the historical warning and
# can be installed later.
if [ "$mode" = full ] && command -v dsh >/dev/null 2>&1; then
  require_dsh_version
fi

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
  # Which spec to install depends on where this script is running from.
  #
  # A git checkout is a developer's working tree: install `file:$HERE` so the
  # profile carries a copy of THIS tree, and re-running the script refreshes
  # it. `file:` rather than a bare path, because pnpm resolves a bare directory
  # argument as `link:` — a live symlink into the checkout, so moving or
  # deleting the clone would break the installed profile.
  #
  # Anything else is a copy npm already fetched — `npx dsh-rigorquant` unpacks
  # into a cache directory that disappears afterwards, so a `file:` spec would
  # point at nothing. Install the published version by name instead.
  if [ -d "$HERE/.git" ]; then
    spec="file:$HERE"
  else
    spec="dsh-rigorquant@${VERSION:-latest}"
  fi
  if dsh plugin --profile "$PROFILE" add "$spec" >/dev/null 2>&1; then
    echo "Installed the plugin ($spec) into the '$PROFILE' profile (model router + its card on the Plugins page)."
  else
    printf 'warning: `dsh plugin --profile %s add %s` failed; the preset and lane are installed, the plugin is not.\n' "$PROFILE" "$spec" >&2
  fi
}

# Enable the Agent Teams bundles on PROFILE and raise the team service's
# lifetime member cap, both idempotently.
#
# A profile's enabled bundles are `dsh.profile.bundles` in its package.json —
# the same list `dsh plugin add` reconciles, so only the bundles actually
# absent are added (`dsh plugin add` also lazily initializes the profile
# directory, including an empty `cordis.patch.yml`, when it does not exist
# yet). Without `dsh` there is no way to add a bundle or safely locate/create
# a profile, so this warns and does nothing else — the historical behaviour
# for a missing CLI, and how CI's install smoke test (no `dsh` on PATH) stays
# green.
install_agent_teams() {
  if ! command -v dsh >/dev/null 2>&1; then
    printf 'warning: dsh is not on PATH; skipped enabling Agent Teams for the "%s" profile.\n' "$PROFILE" >&2
    printf '         install it later and re-run, or add %s and %s\n' "$TEAM_BUNDLE_HOST" "$TEAM_BUNDLE_WEB" >&2
    printf '         yourself (Plugins page, or dsh plugin --profile %s add <pkg>).\n' "$PROFILE" >&2
    return 0
  fi
  profile_dir="$DSH_HOME/profiles/$PROFILE"
  manifest="$profile_dir/package.json"
  patch_file="$profile_dir/cordis.patch.yml"

  missing="$(node - "$manifest" "$TEAM_BUNDLE_HOST" "$TEAM_BUNDLE_WEB" <<'NODE'
const { existsSync, readFileSync } = require('node:fs')
const [manifest, ...wanted] = process.argv.slice(2)
let bundles = []
if (existsSync(manifest)) {
  try {
    const parsed = JSON.parse(readFileSync(manifest, 'utf8'))?.dsh?.profile?.bundles
    if (Array.isArray(parsed)) bundles = parsed
  } catch {}
}
process.stdout.write(wanted.filter((name) => !bundles.includes(name)).join(' '))
NODE
  )"

  enabled=""
  if [ -n "$missing" ]; then
    # Unquoted on purpose: node emits the missing names space-separated, and a
    # package name contains no whitespace or glob character, so the split is
    # the argument list and the glob cannot fire.
    if dsh plugin --profile "$PROFILE" add $missing >/dev/null 2>&1; then
      for bundle in $missing; do echo "Enabled the Agent Teams bundle '$bundle' on the '$PROFILE' profile."; done
      enabled="$missing"
    else
      printf 'warning: `dsh plugin --profile %s add %s` failed; Agent Teams may not be fully enabled.\n' "$PROFILE" "$missing" >&2
    fi
  fi

  # Append the cap override under our marker, unless it is already there
  # (idempotent: a second run of an already-installed profile writes
  # nothing). A freshly-initialized patch file is a bare `[]`; a block
  # sequence cannot follow a flow-style empty array in the same YAML
  # document, so that placeholder is replaced rather than appended after.
  written="$(node - "$patch_file" "$enabled" "$TEAM_PATCH_MARK_BEGIN" "$TEAM_PATCH_MARK_END" <<'NODE'
const { existsSync, readFileSync, writeFileSync, mkdirSync } = require('node:fs')
const { dirname } = require('node:path')
const [patchFile, enabled, markBegin, markEnd] = process.argv.slice(2)
const content = existsSync(patchFile) ? readFileSync(patchFile, 'utf8') : ''
if (content.includes(markBegin)) process.exit(0)
const block = [
  markBegin,
  '# rq-enabled-bundles: ' + enabled,
  '- id: agent-team',
  '  config:',
  '    maxMembers: 64',
  '    maxTasks: 256',
  '    maxPendingMessagesPerMember: 64',
  '    maxMessageBytes: 65536',
  '    disposalTimeoutMs: 5000',
  markEnd,
  '',
].join('\n')
const next = /\[\]\s*$/.test(content)
  ? content.replace(/\[\]\s*$/, '') + block
  : (content === '' || content.endsWith('\n') ? content : content + '\n') + block
mkdirSync(dirname(patchFile), { recursive: true })
writeFileSync(patchFile, next)
process.stdout.write(block)
NODE
  )"
  if [ -n "$written" ]; then
    echo "Wrote the Agent Teams maxMembers override to $patch_file:"
    printf '%s\n' "$written" | sed 's/^/  /'
  fi
}

# Undo exactly what install_agent_teams wrote: the marker block in the
# profile's user patch, and the bundles it recorded having enabled (never a
# bundle the operator had already turned on before installing).
uninstall_agent_teams() {
  patch_file="$DSH_HOME/profiles/$PROFILE/cordis.patch.yml"
  [ -f "$patch_file" ] || return 0
  command -v node >/dev/null 2>&1 || return 0
  enabled="$(node - "$patch_file" "$TEAM_PATCH_MARK_BEGIN" "$TEAM_PATCH_MARK_END" <<'NODE'
const { readFileSync, writeFileSync } = require('node:fs')
const [patchFile, markBegin, markEnd] = process.argv.slice(2)
const content = readFileSync(patchFile, 'utf8')
const begin = content.indexOf(markBegin)
const end = begin === -1 ? -1 : content.indexOf(markEnd, begin)
if (begin === -1 || end === -1) process.exit(0)
const enabledMatch = content.slice(begin, end).match(/^# rq-enabled-bundles:\s*(.*)$/m)
let rest = content.slice(0, begin) + content.slice(end + markEnd.length)
rest = rest.replace(/\n{3,}/g, '\n\n')
// Removing the only block sequence entry can leave a file of nothing but
// comments, which is not valid YAML on its own; restore the placeholder the
// profile template ships so the file still parses as the empty array it is.
if (!/^\s*-\s/m.test(rest.replace(/^#.*$/gm, ''))) rest = rest.replace(/\s+$/, '') + '\n[]\n'
writeFileSync(patchFile, rest)
process.stdout.write(enabledMatch ? enabledMatch[1].trim() : '')
NODE
  )"
  echo "Removed the Agent Teams maxMembers override from $patch_file."
  if [ -n "$enabled" ] && command -v dsh >/dev/null 2>&1; then
    for bundle in $enabled; do
      dsh plugin --profile "$PROFILE" remove "$bundle" >/dev/null 2>&1 \
        && echo "Disabled the Agent Teams bundle '$bundle' on the '$PROFILE' profile (the installer had enabled it)." \
        || true
    done
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
  rm -rf "$DSH_HOME/skills/arxiv"
  rm -rf "$DSH_HOME/skills/academic-paper-search"
  rm -rf "$DSH_HOME/share/rigorquant"
  uninstall_agent_teams
  if command -v dsh >/dev/null 2>&1; then
    # Removing the dependency drops it from dsh.profile.bundles in the same
    # reconcile step that added it, so no manifest is left naming a package
    # that is gone.
    dsh plugin --profile "$PROFILE" remove dsh-rigorquant >/dev/null 2>&1 \
      && echo "Removed the plugin from the '$PROFILE' profile." \
      || true
  fi
  # Undo the hook wiring only when it still points at ours.
  if [ -d "$HERE/.git" ] && [ "$(cd "$HERE" && git config core.hooksPath 2>/dev/null)" = ".githooks" ]; then
    (cd "$HERE" && git config --unset core.hooksPath) 2>/dev/null || true
    echo "Disabled the pre-commit coverage gate (unset core.hooksPath)."
  fi
  echo "Removed the RigorQuant preset, skills, and shared lane."
  exit 0
fi

# Developer convenience for git checkouts only: point git at the repo's hooks
# so every commit runs the coverage gate (.githooks/pre-commit). Non-fatal by
# design: exported tarballs / npx cache copies have no .git, and a failed `git
# config` must never fail an install.
if [ -d "$HERE/.git" ] && [ -x "$HERE/.githooks/pre-commit" ]; then
  if (cd "$HERE" && git config core.hooksPath .githooks) 2>/dev/null; then
    echo "Enabled the pre-commit coverage gate (git config core.hooksPath .githooks)."
  fi
fi

if [ "$mode" = skill ]; then
  install_dir "$HERE/agent-presets/rigorquant/skills/rigorquant" "$DSH_HOME/skills/rigorquant"
  install_dir "$HERE/agent-presets/rigorquant/skills/arxiv" "$DSH_HOME/skills/arxiv"
  install_dir "$HERE/agent-presets/rigorquant/skills/academic-paper-search" "$DSH_HOME/skills/academic-paper-search"
  echo "Installed skills to $DSH_HOME/skills/ (rigorquant, arxiv, academic-paper-search; the directory watcher loads them immediately)."
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
  install_agent_teams
  echo "Start a new session and pick the 'RigorQuant' preset in the session picker."
fi
