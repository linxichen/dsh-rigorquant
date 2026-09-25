// RigorQuant compute-lane sync — host half, run once per profile boot.
//
// The preset is declared in the bundle now (Decision 25,
// docs/adr/0002-declared-preset-on-dsh-0.1.7.md), so this row copies no
// preset. What the declaration cannot serve is the compute lane: a uv venv is
// derived state with absolute paths, and node_modules is volatile and
// version-pathed (recorded `env_lane` paths in existing studies' study.json
// would churn). So this row lands the lane, and the files the skill cites
// next to it, where install.sh would, for users who only ran
// `dsh plugin add`:
//
//   env/ mcp/ docs/ → $DSH_HOME/share/rigorquant/<same>
//
// and removes the `$DSH_HOME/.agent-presets/rigorquant` an older release
// (Decision 22) landed there, but only when that tree's marker says this
// package put it there.
//
// Semantics, per managed directory:
// - Idempotent byte-compare: identical trees are left untouched (no mtime
//   churn, no rewrite of files a watcher might be serving).
// - Replace on every sync: a changed or missing file is copied; a target
//   entry the source no longer has is pruned — EXCEPT derived state (.venv,
//   __pycache__, *.pyc, .DS_Store), which is never copied out of a source and
//   never pruned from a target. A provisioned venv at the lane anchor must
//   survive every boot and every package update.
// - Ownership marker: every managed root carries `.rq-sync.json`
//   (managedBy + version + syncedAt), so what this plugin owns stays
//   discoverable after the plugin is gone. There is no uninstall hook in
//   DSH's plugin CLI — `dsh plugin remove` is pnpm delete plus a manifest
//   reconcile, and code that no longer exists cannot run — so removal stays
//   explicit (install.sh --uninstall).
//
// Failure is soft by design: a sync problem logs a warning and never blocks
// the rest of the profile (nor the other rows sharing this package).

import { readdirSync, readFileSync, writeFileSync, mkdirSync, statSync, rmSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { homedir } from 'node:os'
import { fileURLToPath } from 'node:url'

const name = 'rq-lane-sync'
const inject = []

/** Marker file left in every managed ROOT directory (never deeper). */
export const MARKER = '.rq-sync.json'
/** Derived state: never copied out of a source, never pruned from a target. */
export const PRESERVED_NAMES = new Set(['.venv', '__pycache__', '.DS_Store'])
export const PRESERVED_SUFFIXES = ['.pyc']
/** The marker's `managedBy`: what this package stamps, and all it removes. */
const MANAGER = 'dsh-rigorquant'
/** Package-root-relative source dir → its path under $DSH_HOME. */
const MANAGED_DIRS = [
  ['env', join('share', 'rigorquant', 'env')],
  ['mcp', join('share', 'rigorquant', 'mcp')],
  ['docs', join('share', 'rigorquant', 'docs')],
]
/** Where releases before 0.6.0 landed the preset, relative to $DSH_HOME. */
const ORPHANED_PRESET = join('.agent-presets', 'rigorquant')

const pkgRoot = () => fileURLToPath(new URL('..', import.meta.url))

function readVersion() {
  return JSON.parse(readFileSync(join(pkgRoot(), 'package.json'), 'utf8')).version
}

export function dshHome() {
  return process.env.DSH_HOME && process.env.DSH_HOME !== ''
    ? process.env.DSH_HOME
    : join(homedir(), '.dsh')
}

function isPreserved(name) {
  return PRESERVED_NAMES.has(name) || PRESERVED_SUFFIXES.some((s) => name.endsWith(s))
}

function exists(path) {
  return statSync(path, { throwIfNoEntry: false }) !== undefined
}

function bytesEqual(a, b) {
  if (statSync(a).size !== statSync(b).size) return false
  return readFileSync(a).equals(readFileSync(b))
}

/**
 * Copy differing / missing files from source to target, recursively.
 * Returns the list of relative paths written. Derived state is skipped.
 */
function syncTree(sourceDir, targetDir) {
  const written = []
  const walk = (src, dst, rel) => {
    mkdirSync(dst, { recursive: true })
    for (const entry of readdirSync(src)) {
      if (isPreserved(entry)) continue
      const s = join(src, entry)
      const t = join(dst, entry)
      const r = rel ? `${rel}/${entry}` : entry
      if (statSync(s).isDirectory()) walk(s, t, r)
      else if (!exists(t) || !bytesEqual(s, t)) {
        mkdirSync(dirname(t), { recursive: true })
        writeFileSync(t, readFileSync(s))
        written.push(r)
      }
    }
  }
  walk(sourceDir, targetDir, '')
  return written
}

/** Remove target entries the source does not have; derived state and the
 * root's own ownership marker survive. */
function pruneExtras(targetDir, sourceDir) {
  let pruned = 0
  const walk = (dst, src) => {
    for (const entry of readdirSync(dst)) {
      if (isPreserved(entry) || (dst === targetDir && entry === MARKER)) continue
      const d = join(dst, entry)
      const s = join(src, entry)
      if (!exists(s)) {
        rmSync(d, { recursive: true, force: true })
        pruned += 1
      } else if (statSync(d).isDirectory()) walk(d, s)
    }
  }
  walk(targetDir, sourceDir)
  return pruned
}

function readMarker(targetDir) {
  try {
    const raw = JSON.parse(readFileSync(join(targetDir, MARKER), 'utf8'))
    return typeof raw?.version === 'string' ? raw : null
  } catch {
    return null
  }
}

function writeMarker(targetDir, version) {
  writeFileSync(join(targetDir, MARKER), JSON.stringify({
    managedBy: MANAGER,
    version,
    syncedAt: new Date().toISOString(),
  }, null, 2) + '\n')
}

/**
 * Sync one managed ROOT directory. Returns
 *   { status: 'synced', copied, pruned }  — tree was (re)written or adopted
 *   { status: 'current', copied, pruned } — byte-identical, stamp matches
 *   { status: 'absent-source' }           — nothing bundled at this source
 */
export function syncManagedDir(sourceDir, targetDir, { version }) {
  try {
    readdirSync(sourceDir)
  } catch {
    return { status: 'absent-source' }
  }

  const marker = readMarker(targetDir)
  const stampedCurrent = marker !== null && marker.version === version
  mkdirSync(targetDir, { recursive: true })
  const copied = syncTree(sourceDir, targetDir)
  const pruned = pruneExtras(targetDir, sourceDir)
  // A tree that needed no writes and already carries this version's stamp is
  // left exactly as it was; anything else is (re)stamped. An unstamped
  // identical tree (installed by ./install.sh) is adopted without a rewrite.
  if (copied.length === 0 && pruned === 0 && stampedCurrent) {
    return { status: 'current', copied, pruned }
  }
  writeMarker(targetDir, version)
  return { status: 'synced', copied, pruned }
}

/**
 * Remove the preset tree a release before 0.6.0 landed under $DSH_HOME.
 * Only a tree whose marker names this package goes; anything else there is
 * the user's. Returns { status: 'removed' | 'not-ours' | 'absent' }.
 */
export function removeOrphanedPreset(home) {
  const target = join(home, ORPHANED_PRESET)
  if (!exists(target)) return { status: 'absent' }
  if (readMarker(target)?.managedBy !== MANAGER) return { status: 'not-ours' }
  rmSync(target, { recursive: true, force: true })
  return { status: 'removed' }
}

/** Sync every managed directory; returns one outcome per pair. */
export function runSync(home = dshHome()) {
  const root = pkgRoot()
  const version = readVersion()
  return MANAGED_DIRS.map(([src, dst]) => ({
    src,
    dst: join(home, dst),
    result: syncManagedDir(join(root, src), join(home, dst), { version }),
  }))
}

export function apply(ctx, config) {
  if (config?.enabled === false) return
  const home = dshHome()
  let outcomes
  try {
    outcomes = runSync(home)
  } catch (error) {
    ctx.logger?.warn?.(`${name}: lane sync failed: ${errorMessage(error)}`)
    outcomes = []
  }
  for (const { src, dst, result } of outcomes) {
    if (result.status === 'synced') {
      ctx.logger?.info?.(
        `${name}: ${src} -> ${dst} (${result.copied.length} copied, ${result.pruned} pruned)`)
    }
    // 'current' and 'absent-source' are the quiet, intended states.
  }
  try {
    if (removeOrphanedPreset(home).status === 'removed') {
      ctx.logger?.info?.(`${name}: removed ${join(home, ORPHANED_PRESET)}, which the declared preset replaces`)
    }
  } catch (error) {
    ctx.logger?.warn?.(`${name}: orphaned preset removal failed: ${errorMessage(error)}`)
  }
}

const errorMessage = (error) => (error instanceof Error ? error.message : String(error))

export { name, inject }
