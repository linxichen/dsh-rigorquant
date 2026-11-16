#!/bin/sh
# Install dsh-rigorquant (its declared preset and bundled skills) into DSH.
#   ./install.sh                 → install everything: the compute lane, and the plugin
#                                  (declared preset, model router + its Plugins-page
#                                  card) into a profile
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
MIN_DSH_VERSION="0.2.2-rc.3"
# The core this release was validated through. NOT a ceiling: the band is open
# by the 0.8.1 open-floor policy, so RigorQuant admits every core at or above the
# floor and the floor moves only when a release is validated on the new one. A
# core above this constant therefore gets an advisory that names it, and the
# install continues. Pinned equal to MIN_DSH_VERSION and to package.json's
# `engines.dsh` floor by tests/test_repo_consistency.py.
VALIDATED_DSH_VERSION="0.2.2-rc.3"
# The Agent Teams bundle 0.8.0 enabled. DSH 0.2.2-rc.3 mounts Agent Teams from
# its base bundle (the `agent-team` row and its team tools), and this package is
# published only through 0.2.2-rc.1: a full install therefore REMOVES it from a
# profile that still lists it, whoever enabled it. `--uninstall` still reads the
# old enabled-bundles record to disable anything an older installer turned on
# (Decision 28; docs/adr/0005-rigorquant-on-dsh-0.2.2.md).
RETIRED_TEAM_BUNDLE="@deepseek-ai/dsh-experimental-agent-team-profile"
# DSH 0.1.7 folded the team panel into the base bundle and dropped the
# separate web bundle; npm has no build of it for a 0.1.7-or-later core, and a
# profile that still lists it cannot resolve it. A full install therefore
# removes it from the profile, whoever enabled it (Decision 25).
RETIRED_WEB_BUNDLE="@deepseek-ai/dsh-experimental-agent-team-web-profile"
# The router's roles, in the order of dsh/index.js's ROLES (pinned equal by
# tests/test_installer_agent_teams.py). A saved route ports only when its key
# is `<role>Primary` or `<role>Fallback` for one of these.
RQ_ROUTE_ROLES="root explorer offgrid doublechecker adversary lit-line lit-adversary doc-adversary"
# Marks the block the 0.8.0 installer owned inside a profile's user patch
# (`cordis.patch.yml`). 0.8.1 writes no block, but it must find a 0.8.0 one to
# migrate its rejected config keys, and `--uninstall` must still remove exactly
# the lines that installer wrote and nothing the operator wrote by hand.
TEAM_PATCH_MARK_BEGIN='# >>> dsh-rigorquant BEGIN (managed by ./install.sh; see docs/adr/0001-rigorquant-on-agent-teams.md) >>>'
TEAM_PATCH_MARK_END='# <<< dsh-rigorquant END <<<'

# Whether $HERE is a git checkout OR a linked worktree. In a worktree `.git` is
# a FILE holding the gitdir pointer rather than a directory, so `[ -d ]` alone is
# false there — and a worktree is exactly where this repository's own agents and
# maintainers install from. A copy npm fetched (`npx dsh-rigorquant`) has
# neither, which is the case the `file:` decision below deliberately separates.
is_git_checkout() { [ -d "$HERE/.git" ] || [ -f "$HERE/.git" ]; }

# The version the installed CLI reports, e.g. `0.2.2-rc.3`, read once for the
# whole run: it gates the install (require_dsh_version). Empty when
# `dsh --version` cannot answer at all.
DSH_CORE_VERSION=""

usage() {
  cat <<EOF
Usage: $0 [--skill-only] [--uninstall] [--profile <name>] [--version] [--help]

  Full install requires DSH >= $MIN_DSH_VERSION; a newer core installs with
  an advisory naming the validated core. --skill-only does not.

  (no args)      Install everything: the shared compute lane under
                 \$DSH_HOME/share/rigorquant, and the plugin (the declared
                 RigorQuant preset, role model router + its card on the
                 Plugins page) into the '$PROFILE' profile, with saved routes
                 carried over from settings.yaml.
                 The plugin supplies the skills, so no global copies are made.
  --skill-only   Install ONLY the skills into \$DSH_HOME/skills, for use with
                 any preset and without the plugin.
  --uninstall    Remove the skills, shared lane, and the plugin (and an older
                 release's directory preset).
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
#
# This is the one place a range comparison is written by hand, and it is
# deliberately not the harness's `evaluatePluginCompatibility`: the installer
# runs BEFORE it knows the harness tree is sound (a partial install, a profile
# whose node_modules is broken, an old CLI without that export), so it must
# gate on the CLI's own `--version` without resolving anything out of the
# install it is about to repair. The probes, which only ever run against a
# tree they can resolve, use the harness's gate instead.
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
  actual="$DSH_CORE_VERSION"
  if [ -z "$actual" ]; then
    printf 'error: dsh-rigorquant installs onto dsh >= %s, and the installed CLI reported no version\n' \
      "$MIN_DSH_VERSION" >&2
    exit 2
  fi
  # ONE enforced bound. Below the floor this release is not built for the
  # core: the loader skips the bundle silently, so the operator would get a
  # profile with no RigorQuant and no error. Refuse before copying anything.
  if ! version_at_least "$actual" "$MIN_DSH_VERSION"; then
    printf 'error: dsh-rigorquant requires dsh >= %s (found %s)\n' \
      "$MIN_DSH_VERSION" "$actual" >&2
    printf '       upgrade the DSH CLI before installing the full preset.\n' >&2
    exit 2
  fi
  # Above the validated core the band is open by policy: name the core this
  # release was exercised on and continue. An operator judges the risk; a
  # future core never draws an incompatibility announcement.
  if [ "$actual" != "$VALIDATED_DSH_VERSION" ] && version_at_least "$actual" "$VALIDATED_DSH_VERSION"; then
    printf 'warning: dsh-rigorquant is validated through dsh %s; the installed core is %s.\n' \
      "$VALIDATED_DSH_VERSION" "$actual" >&2
    printf '         the band is open above the floor by policy, so the install continues;\n' >&2
    printf '         this release was not exercised on that core, so check a Team session before a long study.\n' >&2
  fi
}

# The full distribution is only mountable on a harness that serves the surfaces
# it is written against (Decision 28; docs/adr/0005-rigorquant-on-dsh-0.2.2.md): the preset is a
# declared `@deepseek-ai/dsh-agent-preset` row, the router's routes are
# `.volatile()` profile config, the card edits them through `configForms`, and
# the unattended intake ask uses the timed `ask_user_question` mode — none of
# which exists before 0.2.2-rc.3. That core is the validated FLOOR, not a
# ceiling: the band is open above it, so a newer core takes the advisory and
# continues. Fail before copying anything when the installed CLI is older; a
# missing CLI keeps the historical warning and can be installed later (CI's
# install smoke test runs with no `dsh` on PATH).
if [ "$mode" = full ] && command -v dsh >/dev/null 2>&1; then
  DSH_CORE_VERSION="$(dsh --version 2>/dev/null || true)"
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
  # A git checkout (or a linked worktree, where `.git` is a file) is a
  # developer's working tree: install `file:$HERE` so the profile carries a copy
  # of THIS tree, and re-running the script refreshes it. `file:` rather than a
  # bare path, because pnpm resolves a bare directory argument as `link:` — a
  # live symlink into the checkout, so moving or deleting the clone would break
  # the installed profile.
  #
  # Anything else is a copy npm already fetched — `npx dsh-rigorquant` unpacks
  # into a cache directory that disappears afterwards, so a `file:` spec would
  # point at nothing. Install the published version by name instead.
  if is_git_checkout; then
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

# Retire the Agent Teams bundle 0.8.0 managed, and migrate the profile block it
# wrote, idempotently.
#
# DSH 0.2.2-rc.3 folds Agent Teams into the base bundle: the base mounts the
# `agent-team` row and its team tools itself, and the separate
# `@deepseek-ai/dsh-experimental-agent-team-profile` is published only through
# 0.2.2-rc.1. A full install therefore adds, pins and enables no Team bundle.
# What it does instead is clean up what 0.8.0 wrote:
#
#   - remove a retired bundle name the profile still lists (the separate Team
#     bundle and the older web bundle), whichever release enabled it, and fail
#     hard if that removal fails -- the profile cannot boot cleanly while it
#     names a package this core does not serve;
#   - migrate a marked block written by 0.8.0: delete the three `agentTeams`
#     config keys 0.2.2-rc.3's Config rejects (`maxMembers`,
#     `maxMessageBytes`, `disposalTimeoutMs`) and drop the removed names from
#     the enabled-bundles record, leaving every other line alone;
#   - remove the block entirely when nothing but that record is left.
#
# Without `dsh` there is no way to remove a bundle or safely locate the
# profile, so this warns and does nothing else -- the historical behaviour for
# a missing CLI, and how CI's install smoke test (no `dsh` on PATH) stays green
# rather than becoming a refusal.
retire_agent_teams() {
  if ! command -v dsh >/dev/null 2>&1; then
    printf 'warning: dsh is not on PATH; skipped retiring the Agent Teams bundle and migrating the "%s" profile.\n' "$PROFILE" >&2
    return 0
  fi
  profile_dir="$DSH_HOME/profiles/$PROFILE"
  manifest="$profile_dir/package.json"
  patch_file="$profile_dir/cordis.patch.yml"

  # A bundle is PRESENT when the profile lists it in `dsh.profile.bundles` or
  # pins it in dependencies; a bundle listed with no recorded version was
  # enabled by the operator rather than by us, and is removed all the same --
  # this core does not serve that package at any version.
  present="$(node - "$manifest" "$RETIRED_TEAM_BUNDLE" "$RETIRED_WEB_BUNDLE" <<'NODE'
const { existsSync, readFileSync } = require('node:fs')
const [manifest, ...retired] = process.argv.slice(2)
let bundles = []
let dependencies = {}
if (existsSync(manifest)) {
  try {
    const parsed = JSON.parse(readFileSync(manifest, 'utf8'))
    if (Array.isArray(parsed?.dsh?.profile?.bundles)) bundles = parsed.dsh.profile.bundles
    if (parsed?.dependencies !== null && typeof parsed?.dependencies === 'object') dependencies = parsed.dependencies
  } catch {}
}
process.stdout.write(retired.filter((name) => bundles.includes(name) || Object.hasOwn(dependencies, name)).join(' '))
NODE
  )"
  for bundle in $present; do
    if dsh plugin --profile "$PROFILE" remove "$bundle" >/dev/null 2>&1; then
      if [ "$bundle" = "$RETIRED_WEB_BUNDLE" ]; then
        echo "Removed the retired Agent Teams web bundle '$bundle' from the '$PROFILE' profile: DSH 0.1.7 ships the team panel in the base bundle and publishes no web bundle for this core."
      else
        echo "Removed the retired Agent Teams bundle '$bundle' from the '$PROFILE' profile: DSH 0.2.2-rc.3 mounts Agent Teams from the base bundle and publishes no separate bundle."
      fi
    else
      printf 'error: `dsh plugin --profile %s remove %s` failed; the profile cannot boot cleanly while it lists a package this core does not serve.\n' "$PROFILE" "$bundle" >&2
      printf '       remove it yourself (Plugins page, or the command above) and re-run ./install.sh.\n' >&2
      exit 1
    fi
  done

  # SURGICAL migration of the marked block. The three rejected keys go, the
  # record loses the retired names, and everything else in the block survives
  # byte-for-byte: an operator's saved `maxTasks`, a row the ConfigEditor saved
  # after ours, the record itself. A block that then carries no row at all is
  # removed with its markers, because the record only means something while a
  # block an older installer can still see needs it.
  migrated="$(node - "$patch_file" "$TEAM_PATCH_MARK_BEGIN" "$TEAM_PATCH_MARK_END" \
    "$RETIRED_TEAM_BUNDLE $RETIRED_WEB_BUNDLE" <<'NODE'
const { existsSync, readFileSync, writeFileSync } = require('node:fs')
const [patchFile, markBegin, markEnd, retiredList] = process.argv.slice(2)
if (!existsSync(patchFile)) process.exit(0)
const content = readFileSync(patchFile, 'utf8')
const begin = content.indexOf(markBegin)
if (begin === -1) process.exit(0)
const end = content.indexOf(markEnd, begin)
if (end === -1) process.exit(0)
const regionStart = begin + markBegin.length
const original = content.slice(regionStart, end)
let region = original

// 1. The record survives while the block does, but no longer names a bundle
//    the profile cannot have. Reading the record line ALONE matters: a \s*
//    would run past the newline and read the agent-team row as names.
const retired = new Set(retiredList.trim() === '' ? [] : retiredList.trim().split(/\s+/))
const record = region.match(/^# rq-enabled-bundles:[ \t]*(.*)$/m)
let recordChanged = false
if (record !== null) {
  const names = record[1].trim().split(/\s+/).filter(Boolean)
  const kept = names.filter((name) => !retired.has(name))
  if (kept.length !== names.length) {
    region = region.replace(record[0], '# rq-enabled-bundles: ' + kept.join(' '))
    recordChanged = true
  }
}

// 2. Delete the rejected keys, inside the agent-team row only: a row the
//    ConfigEditor saved inside the block keeps whatever it holds. The match
//    is shape-agnostic on purpose: a re-saved block may indent its keys
//    differently or quote the values, and a four-space/integer-only match
//    left the rejected key in place, so the team service never mounted.
const rejected = []
const rows = []
let inAgentTeamRow = false
for (const line of region.split('\n')) {
  if (/^\s*- id: agent-team\s*$/.test(line)) {
    inAgentTeamRow = true
    rows.push(line)
    continue
  }
  if (/^\s*- id: /.test(line)) inAgentTeamRow = false
  if (inAgentTeamRow && /^\s+(maxMembers|maxMessageBytes|disposalTimeoutMs)\s*:\s*(?:\x22[^\x22]*\x22|\x27[^\x27]*\x27|[^\s#]+)?\s*(?:#.*)?$/.test(line)) {
    rejected.push(line.trim().split(':')[0])
    continue
  }
  rows.push(line)
}
region = rows.join('\n')

// 3. Nothing but the record left (and no other row of ours or the harness):
//    the whole block goes. The profile template [] placeholder comes back
//    if the file would otherwise hold no sequence at all.
if (!/^\s*- (?:id:|insert:)/m.test(region)) {
  let rest = content.slice(0, begin) + content.slice(end + markEnd.length)
  rest = rest.replace(/\n{3,}/g, '\n\n')
  if (!/^\s*-\s/m.test(rest.replace(/^#.*$/gm, ''))) rest = rest.replace(/\s+$/, '') + '\n[]\n'
  writeFileSync(patchFile, rest)
  process.stdout.write('Removed the Agent Teams install block from ' + patchFile + ': nothing but the enabled-bundles record remained after the 0.8.0 migration.\n')
  process.exit(0)
}

if (region === original) process.exit(0)
writeFileSync(patchFile, content.slice(0, regionStart) + region + content.slice(end))
const changed = []
if (rejected.length > 0) {
  changed.push('removed ' + rejected.join(', ') + ' (0.2.2-rc.3 mounts the base bundle row, whose Config rejects those keys)')
}
if (recordChanged) changed.push('updated the enabled-bundles record')
process.stdout.write('Migrated the Agent Teams block in ' + patchFile + ': ' + changed.join('; ') + '.\n')
NODE
  )"
  if [ -n "$migrated" ]; then
    printf '%s\n' "$migrated"
  fi
}

# Carry the routes and the default preset a 0.5.0 install saved in
# $DSH_HOME/settings.yaml over into PROFILE's user patch, once (Decision
# 25: the installer ports saved overrides). DSH 0.1.7 keeps settings as
# profile config and imports settings.yaml a single time at its first boot,
# renaming it to settings.yaml.imported first; neither `rigorquant-models` nor the legacy
# `agent-presets:` default maps to an entry id, so both stay behind in that
# file. Read settings.yaml, or settings.yaml.imported when the harness has
# already booted, and write what the harness's own ConfigEditor would:
#   - the routes as the `rq-model-router` row's config (its `.volatile()`
#     fields), keeping only `<role>Primary`/`<role>Fallback` keys the router
#     still declares;
#   - `selectedDefault: rigorquant` on the `agent-preset-registry` row, only
#     when the legacy default was `rigorquant`.
# Once only: a finished port leaves `.rq-settings-ported` in the profile
# directory, so a route cleared on 0.1.7 does not come back from the
# settings.yaml.imported that stays on disk; and a router row already
# carrying any route, or a registry row already carrying a selectedDefault,
# is left alone. YAML is read and written with the `yaml` package the CLI
# ships (resolved from the real path of `dsh`), so no dependency is added and
# `!!js` expressions elsewhere in the patch keep their tag.
port_saved_settings() {
  command -v dsh >/dev/null 2>&1 || return 0
  source_file=""
  for candidate in "$DSH_HOME/settings.yaml" "$DSH_HOME/settings.yaml.imported"; do
    if [ -f "$candidate" ]; then source_file="$candidate"; break; fi
  done
  [ -n "$source_file" ] || return 0
  patch_file="$DSH_HOME/profiles/$PROFILE/cordis.patch.yml"
  [ ! -f "$DSH_HOME/profiles/$PROFILE/.rq-settings-ported" ] || return 0
  if [ ! -d "$DSH_HOME/profiles/$PROFILE" ]; then
    printf 'warning: no "%s" profile to carry the saved routes in %s into; re-run ./install.sh once the plugin installs.\n' "$PROFILE" "$source_file" >&2
    return 0
  fi
  dsh_bin="$(command -v dsh)"
  node - "$dsh_bin" "$source_file" "$patch_file" "$RQ_ROUTE_ROLES" "$TEAM_PATCH_MARK_BEGIN" \
    "$DSH_HOME/profiles/$PROFILE/.rq-settings-ported" <<'NODE'
const { existsSync, readFileSync, realpathSync, writeFileSync } = require('node:fs')
const { createRequire } = require('node:module')
const [dshBin, sourceFile, patchFile, roleList, markBegin, doneMarker] = process.argv.slice(2)
let YAML
try {
  YAML = createRequire(realpathSync(dshBin))('yaml')
} catch {
  process.stderr.write(`warning: could not load the \`yaml\` package the dsh CLI ships; the saved routes and default preset in ${sourceFile} were NOT carried over.\n`)
  process.stderr.write('         set them again on the Plugins page (RigorQuant card) and in Settings -> Agent presets.\n')
  process.exit(0)
}
const isRecord = (value) => typeof value === 'object' && value !== null && !Array.isArray(value)
const nonEmpty = (value) => typeof value === 'string' && value !== ''
const legacy = YAML.parse(readFileSync(sourceFile, 'utf8')) ?? {}
const routeKeys = new Set(roleList.split(' ').flatMap((role) => [`${role}Primary`, `${role}Fallback`]))

const routes = {}
const dropped = []
const saved = isRecord(legacy['rigorquant-models']) ? legacy['rigorquant-models'] : {}
for (const [key, value] of Object.entries(saved)) {
  if (routeKeys.has(key) && isRecord(value) && nonEmpty(value.provider) && nonEmpty(value.model)) {
    routes[key] = { provider: value.provider, model: value.model }
    if (nonEmpty(value.reasoningEffort)) routes[key].reasoningEffort = value.reasoningEffort
  } else {
    dropped.push(key)
  }
}
const legacyDefault = isRecord(legacy['agent-presets']) ? legacy['agent-presets'].default : undefined

const jsTag = { tag: 'tag:yaml.org,2002:js', resolve: (value) => value }
const before = existsSync(patchFile) ? readFileSync(patchFile, 'utf8') : '[]\n'
const document = YAML.parseDocument(before, { customTags: [jsTag] })
if (document.errors.length > 0) {
  process.stderr.write(`warning: ${patchFile} is not valid YAML (${document.errors[0].message}); the saved routes in ${sourceFile} were NOT carried over.\n`)
  process.exit(0)
}
if (!YAML.isSeq(document.contents)) {
  process.stderr.write(`warning: ${patchFile} is not a YAML sequence; the saved routes in ${sourceFile} were NOT carried over.\n`)
  process.exit(0)
}
document.contents.flow = false

// The last id-targeted row for `id` (the one the loader applies last), the
// same match ConfigEditor.edit makes.
function lastRow(id, name) {
  const items = document.contents.items
  for (let index = items.length - 1; index >= 0; index -= 1) {
    const item = items[index]
    if (!YAML.isMap(item) || item.get('id') !== id || item.has('insert')) continue
    if (item.has('name') && item.get('name') !== name) continue
    return item
  }
  return undefined
}
// An id-targeted row replaces the entry's whole config, so new fields merge
// into the row's existing config instead of a second row that would drop it.
// A row the profile does not have yet is written as text afterwards, see
// below.
const newRows = []
let edited = false
function setConfig(id, name, fields, base = {}) {
  const row = lastRow(id, name)
  if (row === undefined) {
    newRows.push({ id, name, config: { ...base, ...fields } })
    return
  }
  if (!YAML.isMap(row.get('config'))) row.set('config', document.createNode({}))
  const config = row.get('config')
  for (const [key, value] of Object.entries(base)) if (!config.has(key)) config.set(key, document.createNode(value))
  for (const [key, value] of Object.entries(fields)) config.set(key, document.createNode(value))
  edited = true
}
function configOf(id, name) {
  const config = lastRow(id, name)?.get('config')
  return YAML.isMap(config) ? config.toJSON() : {}
}

const lines = []
const ROUTER = ['rq-model-router', 'dsh-rigorquant']
const routerConfig = configOf(...ROUTER)
if (Object.keys(routes).length > 0 && !Object.keys(routerConfig).some((key) => routeKeys.has(key))) {
  setConfig(...ROUTER, routes)
  lines.push(`Ported ${Object.keys(routes).length} saved routes from ${sourceFile} into the rq-model-router row of ${patchFile}.`)
  if (dropped.length > 0) {
    lines.push(`  Not ported (no such role, or not a provider/model choice): ${dropped.join(', ')}.`)
  }
}
// `default` is required on the registry row, and a profile row replaces the
// bundle's config, so a new row restates the web bundle's own `standard`.
const REGISTRY = ['agent-preset-registry', '@deepseek-ai/dsh-agent-preset-registry']
if (legacyDefault === 'rigorquant' && configOf(...REGISTRY).selectedDefault === undefined) {
  setConfig(...REGISTRY, { selectedDefault: 'rigorquant' }, { default: 'standard' })
  lines.push(`Set selectedDefault: rigorquant on the agent-preset-registry row of ${patchFile}, the default preset ${sourceFile} saved.`)
}
// New rows go in as text ahead of the retire_agent_teams marker block, never
// appended: the block's END marker is a trailing comment, so a row added to
// the end of the sequence would land inside it and --uninstall would delete
// it with the block.
function insertRows(text) {
  if (newRows.length === 0) return text
  const rows = new YAML.Document(newRows).toString()
  const begin = text.indexOf(markBegin)
  if (begin !== -1) return text.slice(0, begin) + rows + text.slice(begin)
  if (/\[\]\s*$/.test(text)) return text.replace(/\[\]\s*$/, '') + rows
  return (text === '' || text.endsWith('\n') ? text : text + '\n') + rows
}
if (lines.length > 0) {
  const next = insertRows(edited ? String(document) : before)
  const check = YAML.parseDocument(next, { customTags: [jsTag] })
  if (check.errors.length > 0 || !YAML.isSeq(check.contents)) {
    process.stderr.write(`warning: could not write the saved routes in ${sourceFile} into ${patchFile} as valid YAML; nothing was changed.\n`)
    process.exit(0)
  }
  writeFileSync(patchFile, next, { mode: 0o600 })
  process.stdout.write(lines.join('\n') + '\n')
}
writeFileSync(doneMarker, `${sourceFile}\n`)
NODE
}

# Undo exactly what the 0.8.0 installer wrote: the marker block in the
# profile's user patch, and the bundles it recorded having enabled (never a
# bundle the operator had already turned on before installing).
uninstall_agent_teams() {
  patch_file="$DSH_HOME/profiles/$PROFILE/cordis.patch.yml"
  [ -f "$patch_file" ] || return 0
  command -v node >/dev/null 2>&1 || return 0
  output="$(node - "$patch_file" "$TEAM_PATCH_MARK_BEGIN" "$TEAM_PATCH_MARK_END" <<'NODE'
const { readFileSync, writeFileSync } = require('node:fs')
const [patchFile, markBegin, markEnd] = process.argv.slice(2)
const content = readFileSync(patchFile, 'utf8')
const begin = content.indexOf(markBegin)
const end = begin === -1 ? -1 : content.indexOf(markEnd, begin)
if (begin === -1 || end === -1) process.exit(0)
const block = content.slice(begin, end)
const enabledMatch = block.match(/^# rq-enabled-bundles:[ \t]*(.*)$/m)
// Only the lines the old installer wrote go: the markers, the record, and the
// agent-team row. The END marker is a trailing comment, so a row the
// ConfigEditor of the harness saved later sits between the markers and must
// stay.
const kept = []
let inOurRow = false
for (const line of block.split('\n')) {
  if (line.startsWith(markBegin) || /^# rq-enabled-bundles:/.test(line)) continue
  if (/^- id: agent-team\s*$/.test(line)) { inOurRow = true; continue }
  if (inOurRow && /^\s+\S/.test(line)) continue
  inOurRow = false
  kept.push(line)
}
let rest = content.slice(0, begin) + kept.join('\n') + content.slice(end + markEnd.length)
rest = rest.replace(/\n{3,}/g, '\n\n')
// Removing the only block sequence entry can leave a file of nothing but
// comments, which is not valid YAML on its own; restore the placeholder the
// profile template ships so the file still parses as the empty array it is.
if (!/^\s*-\s/m.test(rest.replace(/^#.*$/gm, ''))) rest = rest.replace(/\s+$/, '') + '\n[]\n'
writeFileSync(patchFile, rest)
process.stdout.write('removed\n' + (enabledMatch ? enabledMatch[1].trim() : '') + '\n')
NODE
  )"
  status="$(printf '%s\n' "$output" | sed -n '1p')"
  enabled="$(printf '%s\n' "$output" | sed -n '2p')"
  if [ "$status" = removed ]; then
    echo "Removed the Agent Teams install block from $patch_file."
  fi
  if [ -n "$enabled" ] && command -v dsh >/dev/null 2>&1; then
    for bundle in $enabled; do
      dsh plugin --profile "$PROFILE" remove "$bundle" >/dev/null 2>&1 \
        && echo "Disabled the Agent Teams bundle '$bundle' on the '$PROFILE' profile (an older installer had enabled it)." \
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
  # Written by releases before 0.6.0; DSH 0.1.7 ignores it, and the preset is
  # declared by the plugin now. Still removed so an old install is cleaned up.
  rm -rf "$DSH_HOME/.agent-presets/rigorquant"
  rm -rf "$DSH_HOME/skills/rigorquant"
  rm -rf "$DSH_HOME/skills/arxiv"
  rm -rf "$DSH_HOME/skills/academic-paper-search"
  rm -rf "$DSH_HOME/share/rigorquant"
  rm -f "$DSH_HOME/profiles/$PROFILE/.rq-settings-ported"
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
  if is_git_checkout && [ "$(cd "$HERE" && git config core.hooksPath 2>/dev/null)" = ".githooks" ]; then
    (cd "$HERE" && git config --unset core.hooksPath) 2>/dev/null || true
    echo "Disabled the pre-commit coverage gate (unset core.hooksPath)."
  fi
  echo "Removed the RigorQuant preset, skills, and shared lane."
  exit 0
fi

# Developer convenience for git checkouts only: point git at the repo's hooks
# so every commit runs the coverage gate (.githooks/pre-commit). A linked
# worktree counts (its `.git` is a file, see is_git_checkout). Non-fatal by
# design: exported tarballs / npx cache copies have no .git, and a failed `git
# config` must never fail an install.
if is_git_checkout && [ -x "$HERE/.githooks/pre-commit" ]; then
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
  echo "Installed compute lane to $DSH_HOME/share/rigorquant"
  retire_agent_teams
  port_saved_settings
  echo "Start a new session and pick the 'RigorQuant' preset in the session picker."
fi
