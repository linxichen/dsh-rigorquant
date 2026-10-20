#!/usr/bin/env node
'use strict'
// Judge this package's REAL declared band with the INSTALLED harness's own
// `evaluatePluginCompatibility` — the function the CLI install gate and the
// profile loader call.
//
// This is the S1/S2 regression the band alone cannot express: a pure string
// test cannot catch a band whose prerelease semantics admit the next minor's
// release candidates, and it cannot catch which manifest field the running
// core actually reads. The probe therefore asks the installed gate two things
// and prints them as JSON:
//
//   verdicts    one verdict per probed runtime version, for the manifest this
//               package ships (package.json, or RQ_GATE_MANIFEST for a
//               synthetic manifest a test writes).
//   gateReads   'engines' or 'peers', detected with a manifest whose
//               `engines.dsh` is wide open and whose peer range matches
//               nothing: only a gate that reads `engines.dsh` alone (0.2.1+)
//               accepts it.
//
// Exit codes follow the shared probe contract in ./harness_locator.cjs:
// 0 = answered, 3 = nothing to answer with (no harness, no gate, no manifest).
// The Python tests skip on 3, never on the wording.

const { readFileSync } = require('node:fs')
const { join } = require('node:path')

const {
  EXIT_NO_HARNESS, REPO, exitNoHarness, harnessRequireFor, installedCoreVersion,
  loadCompatibilityGate, resolveHarness, unmetRequirements,
} = require('./harness_locator.cjs')

const PREFIX = 'gate_probe'
const PROBED_VERSIONS = [
  '0.2.0-rc.2', '0.2.1-rc.2', '0.2.1', '0.2.2-rc.1', '0.2.2', '0.3.0',
]

async function main() {
  // No `requireSupportedCore` here on purpose: this probe's job is to report
  // the gate's verdict on versions this package refuses.
  const harness = resolveHarness(undefined)
  if (harness === undefined) exitNoHarness(PREFIX, 'cannot locate an installed harness')
  const harnessRequire = harnessRequireFor(harness, PREFIX)

  const coreVersion = installedCoreVersion(harnessRequire)
  if (coreVersion === undefined) exitNoHarness(PREFIX, `the harness at ${harness} has no @deepseek-ai/dsh`)
  let evaluate
  try {
    evaluate = await loadCompatibilityGate(harnessRequire)
  } catch (error) {
    exitNoHarness(PREFIX, `cannot import the installed compatibility gate: ${String(error?.message ?? error)}`)
  }

  const named = process.env.RQ_GATE_MANIFEST
  const manifestPath = named === undefined || named === '' ? join(REPO, 'package.json') : named
  let manifest
  try {
    manifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
  } catch (error) {
    exitNoHarness(PREFIX, `cannot read the manifest at ${manifestPath}: ${String(error?.message ?? error)}`)
  }

  const verdicts = {}
  for (const version of PROBED_VERSIONS) {
    const issue = evaluate(manifest, {}, version)
    verdicts[version] = issue === undefined
      ? { verdict: 'accepted' }
      : { verdict: 'refused', requirements: unmetRequirements(issue) }
  }

  // Which field decides: an open engines.dsh plus an impossible peer range is
  // accepted only by a gate that reads engines.dsh alone.
  const discriminator = {
    name: 'rq-gate-discriminator',
    version: '0.0.0',
    engines: { dsh: '*' },
    peerDependencies: { '@deepseek-ai/dsh': '>=99.0.0' },
  }
  const gateReads = evaluate(discriminator, {}, coreVersion) === undefined ? 'engines' : 'peers'

  process.stdout.write(JSON.stringify({ coreVersion, gateReads, verdicts }))
}

main().catch((error) => {
  process.stderr.write(`${PREFIX}: ${String(error?.stack ?? error)}\n`)
  process.exit(EXIT_NO_HARNESS)
})
