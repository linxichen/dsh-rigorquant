// RigorQuant self-installing distribution — host half (boot sync).
//
// The bundle-patch plane cannot express an agent preset: the harness's own
// profile overlay pins the `agent-presets` row's roots to the shipped preset
// root, and discovery is a filesystem scan of `$DSH_HOME/.agent-presets` —
// nothing a `cordis.patch.yml` row config can reach (Decision 23). It cannot
// host the compute lane either: a uv venv is derived state with absolute
// paths, and node_modules is volatile (pnpm update/remove would delete a
// provisioned lane mid-study) and version-pathed (recorded `env_lane` paths
// in existing studies' study.json would churn).
//
// So this row does what install.sh does — lands files — from inside the host
// process, once per profile boot:
//
//   agent-presets/rigorquant → $DSH_HOME/.agent-presets/rigorquant
//   env/ mcp/ docs/          → $DSH_HOME/share/rigorquant/<same>
//
// Semantics, per managed directory:
// - Idempotent byte-compare: identical trees are left untouched (no mtime
//   churn, no rewrite of files a watcher might be serving).
// - Replace on install/upgrade: a changed or missing file is copied; a target
//   entry the source no longer has is pruned — EXCEPT derived state (.venv,
//   __pycache__, *.pyc, .DS_Store), which is never copied out of a source and
//   never pruned from a target. A provisioned venv at the lane anchor must
//   survive every boot and every package update.
// - Local-edit preservation: the preset is meant to be edited in place (the
//   escalation lane enables `mcp-jacobian` by flipping a row in the INSTALLED
//   composition). A target stamped with the CURRENT package version whose
//   files all still exist is therefore left alone (`kept-local`); an upgrade
//   (the version stamp moves) legitimately replaces shipped files and with
//   them any local tweaks — the same contract as re-running install.sh.
// - Ownership marker: every managed root carries `.rq-sync.json`
//   (managedBy + version + syncedAt), so what this plugin owns stays
//   discoverable after the plugin is gone. There is no uninstall hook in
//   DSH's plugin CLI — `dsh plugin remove` is pnpm delete plus a manifest
//   reconcile, and code that no longer exists cannot run — so removal stays
//   explicit (install.sh --uninstall), and an orphaned preset is benign: it
//   is self-contained (skills travel inside the preset directory) and simply
//   routes nothing without the router.
//
// Failure is soft by design: a sync problem logs a warning and never blocks
// the rest of the profile (nor the router row sharing this package).

import { readdirSync, readFileSync, writeFileSync, mkdirSync, statSync, rmSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { homedir } from 'node:os'
import { fileURLToPath } from 'node:url'

const name = 'rq-preset-sync'
const inject = []

/** Marker file left in every managed ROOT directory (never deeper). */
export const MARKER = '.rq-sync.json'
/** Derived state: never copied out of a source, never pruned from a target. */
export const PRESERVED_NAMES = new Set(['.venv', '__pycache__', '.DS_Store'])
export const PRESERVED_SUFFIXES = ['.pyc']
/** The one file whose presence makes each managed target meaningful. */
const KEY_FILES = {
  'agent-presets/rigorquant': 'agent.cordis.yml',
  env: 'pyproject.toml',
  mcp: 'jacobian.md',
  docs: 'architecture.md',
}
/** Package-root-relative source dir → its path under $DSH_HOME. */
const MANAGED_DIRS = [  ['agent-presets/rigorquant', join('.agent-presets', 'rigorquant')],
  ['env', join('share', 'rigorquant', 'env')],
  ['mcp', join('share', 'rigorquant', 'mcp')],
  ['docs', join('share', 'rigorquant', 'docs')],
]

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

function filesUnder(root) {
  const out = []
  const walk = (dir) => {
    for (const entry of readdirSync(dir)) {
      if (isPreserved(entry)) continue
      const path = join(dir, entry)
      if (statSync(path).isDirectory()) walk(path)
      else out.push(path)
    }
  }
  walk(root)
  return out
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

/** Remove target entries the source does not have; derived state survives. */
function pruneExtras(targetDir, sourceDir) {
  let pruned = 0
  const walk = (dst, src) => {
    for (const entry of readdirSync(dst)) {
      if (isPreserved(entry)) continue
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
    managedBy: 'dsh-rigorquant',
    version,
    syncedAt: new Date().toISOString(),
  }, null, 2) + '\n')
}

/**
 * Sync one managed ROOT directory. Returns
 *   { status: 'synced', copied, pruned }  — tree was (re)written
 *   { status: 'current' }                 — byte-identical, stamp matches
 *   { status: 'kept-local' }              — same-version stamp; user edits kept
 *   { status: 'absent-source' }           — nothing bundled at this source
 */
export function syncManagedDir(sourceDir, targetDir, { version, keyFile = 'agent.cordis.yml' } = {}) {
  try {
    readdirSync(sourceDir)
  } catch {
    return { status: 'absent-source' }
  }

  const marker = readMarker(targetDir)
  const stampedCurrent = marker !== null && marker.version === version
  if (stampedCurrent && exists(join(targetDir, keyFile))) {
    // Same version, already ours: keep local edits unless the tree lost a
    // shipped file (a partial delete is damage, not a preference).
    const missing = filesUnder(sourceDir).some((src) =>
      !exists(join(targetDir, src.slice(sourceDir.length + 1))))
    if (!missing) return { status: 'kept-local' }
  }

  mkdirSync(targetDir, { recursive: true })
  const copied = syncTree(sourceDir, targetDir)
  const pruned = pruneExtras(targetDir, sourceDir)
  writeMarker(targetDir, version)
  // A tree that needed no writes but carried no stamp yet (e.g. installed by
  // ./install.sh) takes ownership quietly rather than rewriting everything.
  return copied.length === 0 && pruned === 0 && stampedCurrent
    ? { status: 'current', copied, pruned }
    : { status: 'synced', copied, pruned }
}

/** Sync every managed directory; returns one outcome per pair. */
export function runSync() {
  const root = pkgRoot()
  const home = dshHome()
  const version = readVersion()
  return MANAGED_DIRS.map(([src, dst]) => ({
    src,
    dst: join(home, dst),
    result: syncManagedDir(join(root, src), join(home, dst), { version, keyFile: KEY_FILES[src] }),
  }))
}

export function apply(ctx, config) {
  if (config?.enabled === false) return
  let outcomes
  try {
    outcomes = runSync()
  } catch (error) {
    ctx.logger?.warn?.(`rq-preset-sync: failed: ${error instanceof Error ? error.message : String(error)}`)
    return
  }
  for (const { src, dst, result } of outcomes) {
    if (result.status === 'absent-source') continue
    if (result.status === 'synced') {
      ctx.logger?.info?.(
        `rq-preset-sync: ${src} -> ${dst} (${result.copied} copied, ${result.pruned} pruned)`)
    }
    // 'current' and 'kept-local' are the quiet, intended states.
  }
}

export { name, inject }
