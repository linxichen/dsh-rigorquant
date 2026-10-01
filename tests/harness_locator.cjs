'use strict'
// Harness resolution shared by the repository's probes.
//
// Two probes need the same three answers: which `@deepseek-ai` directory is
// the installed harness, which core version it is, and whether this package
// supports that core. Keeping them here means the probes cannot disagree about
// what "the installed harness" means, and there is exactly one place that
// calls the harness's own compatibility gate.

const { readFileSync, existsSync, realpathSync } = require('node:fs')
const { createRequire } = require('node:module')
const { pathToFileURL } = require('node:url')
const { join, resolve, dirname } = require('node:path')
const { execFileSync } = require('node:child_process')

const REPO = resolve(__dirname, '..')

/** Locate the `@deepseek-ai` directory of the installed DSH. */
function findHarnessModules() {
  const candidates = []
  try {
    const bin = execFileSync('sh', ['-c', 'command -v dsh'], { encoding: 'utf8' }).trim()
    if (bin !== '') {
      const real = realpathSync(bin)
      // <pkg>/lib/bin.js → <pkg>/node_modules/@deepseek-ai
      const pkgRoot = resolve(dirname(real), '..')
      candidates.push(join(pkgRoot, 'node_modules', '@deepseek-ai'))
    }
  } catch {
    // No dsh on PATH: fall through to the module-path probe.
  }
  for (const base of require.main?.paths ?? []) {
    if (base.endsWith(join('node_modules', '@deepseek-ai'))) candidates.push(base)
  }
  for (const dir of candidates) {
    if (dir !== undefined && existsSync(dir)) return dir
  }
  return undefined
}

/** The harness directory named by an argument, the environment, or `dsh` on PATH. */
function resolveHarness(argument, env = process.env) {
  const named = argument ?? env.RQ_HARNESS_MODULES
  return named === undefined || named === '' ? findHarnessModules() : resolve(named)
}

/** The version of the core this harness directory belongs to, or undefined. */
function installedCoreVersion(harnessRequire) {
  try {
    return JSON.parse(readFileSync(harnessRequire.resolve('@deepseek-ai/dsh/package.json'), 'utf8')).version
  } catch {
    return undefined
  }
}

/** The `@deepseek-ai/dsh` range this package declares, read from its manifest. */
function declaredRange() {
  try {
    return JSON.parse(readFileSync(join(REPO, 'package.json'), 'utf8')).peerDependencies['@deepseek-ai/dsh']
  } catch {
    return undefined
  }
}

/**
 * Judge the installed core with the harness's OWN compatibility gate — the
 * function the CLI install gate and the profile loader call — so a prerelease
 * rule or a range-syntax nuance can never disagree between a probe and the
 * thing it predicts.
 * @returns `{ verdict: 'supported' | 'refused' | 'unjudged', detail }`
 */
async function judgeCore(harnessRequire, version) {
  let evaluate
  try {
    ({ evaluatePluginCompatibility: evaluate } = await import(
      pathToFileURL(harnessRequire.resolve('@deepseek-ai/dsh-app-boot')).href))
  } catch (error) {
    return { verdict: 'unjudged', detail: String(error?.message ?? error) }
  }
  const issue = evaluate(JSON.parse(readFileSync(join(REPO, 'package.json'), 'utf8')), {}, version)
  if (issue === undefined) return { verdict: 'supported' }
  return {
    verdict: 'refused',
    detail: `${issue.runtimeVersion} is outside the range this package supports (${JSON.stringify(issue.peers)})`,
  }
}

module.exports = { REPO, declaredRange, findHarnessModules, installedCoreVersion, judgeCore, resolveHarness }
