#!/usr/bin/env node
'use strict'
// Validate the two Agent Teams / delegation config surfaces this package ships
// against the INSTALLED packages' own schemas and constructors.
//
// Input (`argv[2]`, JSON): the `subagent` row config this package's bundle patch
// overrides. The probe answers two questions about it:
//
//   `subagentValidated`  `@deepseek-ai/dsh-subagent`'s own Config accepts it.
//   `subagentKeysFound`  that package's source still names `maxDepth` and
//                        `maxActiveSubagents`, so a future rename fails a test
//                        instead of silently going inert (schemastery preserves
//                        unknown keys: a dropped key still "validates").
//
// The second half pins the retired `agent-team` row by MOUNTING it, not by
// scanning source text. 0.2.2-rc.3's `TeamService.Config` is a schemastery
// object that PRESERVES unknown keys, so calling the schema alone accepts
// `maxMembers`, `maxMessageBytes` and `disposalTimeoutMs`; the rejection lives
// in the service constructor (`TEAM_INVALID_CONFIG`). The probe therefore
// constructs the installed service on a fresh `@deepseek-ai/cordis` Context
// once per config: the base bundle's `{maxTasks: 256}` must construct, and
// each 0.8.0 dead key must throw. A deleted rejection would then fail this
// probe even if the error string survived in the built source.
//
// Exit codes follow ./harness_locator.cjs: 0 = answered, 1 = a real problem,
// 2 = the installed core is refused (like every validating probe, it passes
// `requireSupportedCore` first), 3 = nothing to validate against (no harness,
// no package, no Context). The Python side skips on 2 and 3, never on the
// wording.

const { readFileSync } = require('node:fs')
const { pathToFileURL } = require('node:url')
const { dirname, join } = require('node:path')

const {
  EXIT_PROBLEM, exitNoHarness, harnessRequireFor, requireSupportedCore,
  resolveHarness,
} = require('./harness_locator.cjs')

const PREFIX = 'team_config_probe'
const SUBAGENT_PACKAGE = '@deepseek-ai/dsh-subagent'
const TEAM_PACKAGE = '@deepseek-ai/dsh-agent-team'
const CORDIS_PACKAGE = '@deepseek-ai/cordis'
/** Keys the installed subagent Config must still declare. */
const SUBAGENT_KEYS = ['maxDepth', 'maxActiveSubagents']
/** Keys 0.8.0 shipped that the installed TeamService constructor rejects. */
const REMOVED_TEAM_KEYS = ['maxMembers', 'maxMessageBytes', 'disposalTimeoutMs']
/** The base bundle's own Team row value; the bundle patch must not restate it. */
const BASE_TEAM_CONFIG = { maxTasks: 256 }

/** Resolve, import and return one installed package plus its built source. */
async function loadPackage(harnessRequire, spec) {
  let entry
  try {
    entry = harnessRequire.resolve(spec)
  } catch (error) {
    exitNoHarness(PREFIX, `the installed harness has no ${spec}: ${String(error?.message ?? error)}`)
  }
  // The subagent key scan reads the package's built source: <root>/lib/index.js
  // is the layout of every published build, and the entry resolves inside <root>/lib.
  const packageRoot = dirname(dirname(entry))
  let source
  try {
    source = readFileSync(join(packageRoot, 'lib', 'index.js'), 'utf8')
  } catch (error) {
    exitNoHarness(PREFIX, `cannot read ${spec}'s source: ${String(error?.message ?? error)}`)
  }
  let mod
  try {
    mod = await import(pathToFileURL(entry).href)
  } catch (error) {
    exitNoHarness(PREFIX, `cannot import ${spec}: ${String(error?.message ?? error)}`)
  }
  return { mod, source }
}

/** The installed `@deepseek-ai/cordis` Context class, for constructing the
 * service the way the loader would. */
async function loadContext(harnessRequire) {
  let entry
  try {
    entry = harnessRequire.resolve(CORDIS_PACKAGE)
  } catch (error) {
    exitNoHarness(PREFIX, `the installed harness has no ${CORDIS_PACKAGE}: ${String(error?.message ?? error)}`)
  }
  try {
    const mod = await import(pathToFileURL(entry).href)
    if (typeof mod.Context !== 'function') {
      exitNoHarness(PREFIX, `${CORDIS_PACKAGE} exports no Context class`)
    }
    return mod.Context
  } catch (error) {
    exitNoHarness(PREFIX, `cannot import ${CORDIS_PACKAGE}: ${String(error?.message ?? error)}`)
  }
}

/** Construct one service on a fresh Context; return its error, or undefined.
 * A fresh Context per attempt matters: a successful construction registers
 * the service on the context, and the next attempt would throw "already
 * registered" instead of judging the config. */
function constructionError(Service, Context, config) {
  try {
    void new Service(new Context(), config)
    return undefined
  } catch (error) {
    return error
  }
}

async function main() {
  const harness = resolveHarness(undefined)
  if (harness === undefined) exitNoHarness(PREFIX, 'cannot locate an installed harness')
  const harnessRequire = harnessRequireFor(harness, PREFIX)
  const coreVersion = await requireSupportedCore(harnessRequire, PREFIX)
  if (coreVersion === undefined) exitNoHarness(PREFIX, `the harness at ${harness} has no @deepseek-ai/dsh`)

  const subagent = await loadPackage(harnessRequire, SUBAGENT_PACKAGE)
  const subagentConfig = subagent.mod.SubagentRuntime?.Config ?? subagent.mod.Config ?? subagent.mod.default?.Config
  if (typeof subagentConfig !== 'function') exitNoHarness(PREFIX, `${SUBAGENT_PACKAGE} exports no Config`)

  const config = JSON.parse(process.argv[2] ?? '{}')
  let subagentValidated = true
  try {
    subagentConfig(config)
  } catch (error) {
    subagentValidated = false
    process.stderr.write(`${PREFIX}: ${String(error?.message ?? error)}\n`)
  }

  const team = await loadPackage(harnessRequire, TEAM_PACKAGE)
  const TeamService = team.mod.TeamService
  if (typeof TeamService !== 'function') exitNoHarness(PREFIX, `${TEAM_PACKAGE} exports no TeamService class`)
  const teamConfig = TeamService.Config ?? team.mod.Config ?? team.mod.default?.Config
  if (typeof teamConfig !== 'function') exitNoHarness(PREFIX, `${TEAM_PACKAGE} exports no Config`)
  const Context = await loadContext(harnessRequire)

  // The base bundle's row must validate AND construct: a schema that accepts
  // a config the constructor refuses would report a green row that cannot mount.
  let teamRowAccepted = true
  try {
    teamConfig(BASE_TEAM_CONFIG)
  } catch (error) {
    teamRowAccepted = false
    process.stderr.write(`${PREFIX}: ${String(error?.message ?? error)}\n`)
  }
  const baseError = constructionError(TeamService, Context, BASE_TEAM_CONFIG)
  if (baseError !== undefined) {
    teamRowAccepted = false
    process.stderr.write(`${PREFIX}: the base agent-team row did not construct: ${String(baseError?.message ?? baseError)}\n`)
  }

  // Each dead key is judged by mounting the installed service: Config keeps
  // unknown keys, so only the constructor can reject them.
  const removedTeamKeysRejected = []
  const removedTeamKeyErrors = {}
  for (const key of REMOVED_TEAM_KEYS) {
    const error = constructionError(TeamService, Context, { ...BASE_TEAM_CONFIG, [key]: 64 })
    if (error === undefined) continue // accepted: the installed core predates the removal
    if (error.code === 'TEAM_INVALID_CONFIG') removedTeamKeysRejected.push(key)
    else removedTeamKeyErrors[key] = String(error.code ?? error.message ?? error)
  }

  process.stdout.write(JSON.stringify({
    coreVersion,
    subagentValidated,
    subagentKeysFound: SUBAGENT_KEYS.filter((key) => subagent.source.includes(key)),
    teamRowAccepted,
    removedTeamKeysRejected,
    removedTeamKeyErrors,
  }))
}

main().catch((error) => {
  process.stderr.write(`${PREFIX}: ${String(error?.stack ?? error)}\n`)
  process.exit(EXIT_PROBLEM)
})
