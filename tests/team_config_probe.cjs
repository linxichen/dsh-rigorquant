#!/usr/bin/env node
'use strict'
// Validate the two Agent Teams / delegation config surfaces this package ships
// against the INSTALLED packages' own schemas, and report whether each key the
// bundle patch relies on still exists in that package.
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
// The second half pins the retired `agent-team` row. 0.2.2-rc.3's TeamService
// constructor throws TEAM_INVALID_CONFIG for `maxMembers`, `maxMessageBytes`
// and `disposalTimeoutMs`; its Config schema keeps unknown keys, so the probe
// scans the installed source for the removal marker AND for each key name.
// `teamRowAccepted` proves the base bundle's `{maxTasks: 256}` still validates.
//
// Exit codes follow ./harness_locator.cjs: 0 = answered, 2 = the installed
// core is refused (like every validating probe, it passes
// `requireSupportedCore` first), 3 = nothing to validate against (no harness,
// no package, no Config). The Python side skips on 2 and 3, never on the
// wording.

const { readFileSync } = require('node:fs')
const { pathToFileURL } = require('node:url')
const { dirname, join } = require('node:path')

const {
  EXIT_NO_HARNESS, exitNoHarness, harnessRequireFor, requireSupportedCore, resolveHarness,
} = require('./harness_locator.cjs')

const PREFIX = 'team_config_probe'
const SUBAGENT_PACKAGE = '@deepseek-ai/dsh-subagent'
const TEAM_PACKAGE = '@deepseek-ai/dsh-agent-team'
/** Keys the installed subagent Config must still declare. */
const SUBAGENT_KEYS = ['maxDepth', 'maxActiveSubagents']
/** Keys 0.8.0 shipped that the installed TeamService rejects. */
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
  // The key scan reads the package's built source: <root>/lib/index.js is the
  // layout of every published build, and the entry resolves inside <root>/lib.
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
  const teamConfig = team.mod.TeamService?.Config ?? team.mod.Config ?? team.mod.default?.Config
  if (typeof teamConfig !== 'function') exitNoHarness(PREFIX, `${TEAM_PACKAGE} exports no Config`)
  let teamRowAccepted = true
  try {
    teamConfig(BASE_TEAM_CONFIG)
  } catch (error) {
    teamRowAccepted = false
    process.stderr.write(`${PREFIX}: ${String(error?.message ?? error)}\n`)
  }

  process.stdout.write(JSON.stringify({
    coreVersion,
    subagentValidated,
    subagentKeysFound: SUBAGENT_KEYS.filter((key) => subagent.source.includes(key)),
    teamRowAccepted,
    removedTeamKeysFound: REMOVED_TEAM_KEYS.filter((key) => team.source.includes(key)),
    removedTeamKeysRejected: team.source.includes('no longer supported')
      && team.source.includes('TEAM_INVALID_CONFIG'),
  }))
}

main().catch((error) => {
  process.stderr.write(`${PREFIX}: ${String(error?.stack ?? error)}\n`)
  process.exit(EXIT_NO_HARNESS)
})
