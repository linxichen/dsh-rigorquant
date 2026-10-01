'use strict'
// Harness resolution shared by the repository's probes.
//
// Two probes need the same three answers: which `@deepseek-ai` directory is
// the installed harness, which core version it is, and whether this package
// supports that core. Keeping them here means the probes cannot disagree about
// what "the installed harness" means, and there is exactly one place that
// calls the harness's own compatibility gate — and one place that decides the
// exit codes the Python tests switch on.

const { readFileSync, existsSync, realpathSync } = require('node:fs')
const { pathToFileURL } = require('node:url')
const { join, resolve, dirname } = require('node:path')
const { execFileSync } = require('node:child_process')

const REPO = resolve(__dirname, '..')

/**
 * Exit codes every probe shares. The Python side switches on the CODE, never
 * on the wording of a message:
 *   0  the probe's verdict is green
 *   1  the probe found a real problem
 *   2  the installed core is REFUSED (a supported core exists and this is not it)
 *   3  nothing to validate against at all (no harness, no gate, no preset package)
 * A refusal is not "no harness": one test asserts the refusal, so the two
 * cases must be distinguishable without reading prose.
 */
const EXIT_PROBLEM = 1
const EXIT_REFUSED = 2
const EXIT_NO_HARNESS = 3

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

/** This package's own manifest, read once. */
let manifest
function ownManifest() {
  if (manifest === undefined) manifest = JSON.parse(readFileSync(join(REPO, 'package.json'), 'utf8'))
  return manifest
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
    return ownManifest().peerDependencies['@deepseek-ai/dsh']
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
  const issue = evaluate(ownManifest(), {}, version)
  if (issue === undefined) return { verdict: 'supported' }
  return {
    verdict: 'refused',
    detail: `${issue.runtimeVersion} is outside the range this package supports (${JSON.stringify(issue.peers)})`,
  }
}

/**
 * The one gate every probe passes before it validates anything: judge the
 * installed core and exit with the shared code when there is nothing this
 * package can be validated against.
 *
 * @param harnessRequire - resolver anchored at the harness being probed.
 * @param prefix - the calling probe's diagnostic prefix.
 * @returns the installed core version, or undefined when the harness has none.
 */
async function requireSupportedCore(harnessRequire, prefix) {
  const version = installedCoreVersion(harnessRequire)
  if (version === undefined) return undefined
  const judged = await judgeCore(harnessRequire, version)
  if (judged.verdict === 'unjudged') {
    process.stderr.write(`${prefix}: cannot judge the installed harness ${version}: ${judged.detail}\n`)
    process.exit(EXIT_NO_HARNESS)
  }
  if (judged.verdict === 'refused') {
    process.stderr.write(
      `${prefix}: the installed harness ${judged.detail};`
      + ' validating against it would prove nothing about a supported core\n')
    process.exit(EXIT_REFUSED)
  }
  return version
}

module.exports = {
  EXIT_NO_HARNESS,
  EXIT_PROBLEM,
  EXIT_REFUSED,
  REPO,
  declaredRange,
  findHarnessModules,
  installedCoreVersion,
  judgeCore,
  requireSupportedCore,
  resolveHarness,
}
