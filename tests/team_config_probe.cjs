#!/usr/bin/env node
'use strict'
// Validate the `agent-team` row config this package ships against the INSTALLED
// Agent Teams service's own Config schema, and report whether the keys it
// relies on still exist in that package.
//
// Why not just validate: schemastery preserves unknown keys, so a Config that
// DROPPED a key still accepts a row carrying it — silently inert (seam S3:
// 0.2.1-rc.2 removed `maxPendingMessagesPerMember` exactly this way). The probe
// therefore answers both questions: `validated` (Config accepts the config) and
// `keysFound` / `deadKeysFound` (the installed package's own source still names
// the key), so a future drop fails a test instead of disappearing.
//
// Exit codes follow ./harness_locator.cjs: 0 = answered, 3 = nothing to
// validate against (no harness, no Agent Teams package, no Config).
// The Python side skips on 3, never on the wording.

const { readFileSync } = require('node:fs')
const { createRequire } = require('node:module')
const { pathToFileURL } = require('node:url')
const { dirname, join } = require('node:path')

const { resolveHarness } = require('./harness_locator.cjs')

const TEAM_PACKAGE = '@deepseek-ai/dsh-experimental-agent-team'
/** The row config ./install.sh writes and cordis.patch.yml restates. */
const LIVE_KEYS = ['maxMembers', 'maxTasks', 'maxMessageBytes', 'disposalTimeoutMs']
/** Keys earlier releases wrote that the installed service must no longer read. */
const DEAD_KEYS = ['maxPendingMessagesPerMember']

const fail = (message) => {
  process.stderr.write(`team_config_probe: ${message}\n`)
  process.exit(3)
}

async function main() {
  const harness = resolveHarness(undefined)
  if (harness === undefined) fail('cannot locate an installed harness')
  const harnessRequire = createRequire(join(harness, '__team_config_probe__.cjs'))

  let entry
  try {
    entry = harnessRequire.resolve(TEAM_PACKAGE)
  } catch (error) {
    fail(`the installed harness has no ${TEAM_PACKAGE}: ${String(error?.message ?? error)}`)
  }
  const packageRoot = dirname(dirname(entry))
  let source
  try {
    source = readFileSync(join(packageRoot, 'lib', 'index.js'), 'utf8')
  } catch (error) {
    fail(`cannot read ${TEAM_PACKAGE}'s source: ${String(error?.message ?? error)}`)
  }

  let mod
  try {
    mod = await import(pathToFileURL(entry).href)
  } catch (error) {
    fail(`cannot import ${TEAM_PACKAGE}: ${String(error?.message ?? error)}`)
  }
  const Config = mod.Config ?? mod.default?.Config
  if (typeof Config !== 'function') fail(`${TEAM_PACKAGE} exports no Config`)

  const coreVersion = JSON.parse(
    readFileSync(harnessRequire.resolve('@deepseek-ai/dsh/package.json'), 'utf8')).version
  const config = JSON.parse(process.argv[2] ?? '{}')
  let validated = true
  try {
    Config(config)
  } catch (error) {
    validated = false
    process.stderr.write(`team_config_probe: ${String(error?.message ?? error)}\n`)
  }

  process.stdout.write(JSON.stringify({
    coreVersion,
    validated,
    keysFound: LIVE_KEYS.filter((key) => source.includes(key)),
    deadKeysFound: DEAD_KEYS.filter((key) => source.includes(key)),
  }))
}

main().catch((error) => {
  process.stderr.write(`team_config_probe: ${String(error?.stack ?? error)}\n`)
  process.exit(3)
})
