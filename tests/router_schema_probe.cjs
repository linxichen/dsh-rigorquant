#!/usr/bin/env node
// Validate the router's Config against the REAL schemastery the harness ships.
//
// tests/router_probe.cjs exercises `apply()` with a STUB schema builder: that
// is the right shape for routing behaviour and the wrong shape for the schema
// itself, because the stub cannot tell whether `.description()` disturbs
// `meta.volatile`, whether `.default(void 0)` still keeps an absent field
// absent, or whether a route field is a live cell at all. Those are exactly
// the properties the harness's generated settings page depends on:
// `SettingsForms.volatileForm` keeps ONLY `meta.volatile` subtrees, and it
// renders each kept field's `meta.description`.
//
// Usage:
//   node tests/router_schema_probe.cjs [harness-modules-dir]
//
// Defaults to `RQ_HARNESS_MODULES`, then the `@deepseek-ai` directory of the
// `dsh` on PATH. Prints one JSON verdict on stdout. Exit codes are the shared
// probe contract in ./harness_locator.cjs: 0 = green, 1 = a real problem,
// 2 = the installed core is refused, 3 = nothing to validate against.

'use strict'

const { readFileSync } = require('node:fs')
const { createRequire } = require('node:module')
const { pathToFileURL } = require('node:url')
const { join, resolve } = require('node:path')
const vm = require('node:vm')

const { EXIT_NO_HARNESS, EXIT_PROBLEM, REPO, requireSupportedCore, resolveHarness } = require('./harness_locator.cjs')

const harness = resolveHarness(process.argv[2])
if (harness === undefined) {
  process.stderr.write('router_schema_probe: cannot locate an installed harness; pass its @deepseek-ai directory\n')
  process.exit(EXIT_NO_HARNESS)
}
const harnessRequire = createRequire(join(harness, '__probe__.cjs'))

/**
 * Load `dsh/index.js` into a fresh context with the REAL schemastery bound to
 * its import, the way the loader would.
 */
function loadRouter(z) {
  let source = readFileSync(join(REPO, 'dsh', 'index.js'), 'utf8')
  source = source.replace("import z from '@deepseek-ai/schemastery'", 'const z = schemaStub')
  source = source.replace(/^export const /gm, 'const ')
  source = source.replace(/^export \{ ([^}]+) \}$/m, 'module.exports = { $1 }')
  // ROUTE_KEYS and ROLE_LABELS are module-local: the plugin's public exports
  // are the Config and apply(). The probe asks the module for them instead of
  // restating either list.
  source += '\nmodule.exports.ROUTE_KEYS = ROUTE_KEYS\nmodule.exports.ROLE_LABELS = ROLE_LABELS\n'
  const module = { exports: {} }
  vm.runInNewContext(source, {
    module, schemaStub: z, console, Date, Error, Map, Math, Object, Promise, RegExp, Set, String,
  }, { filename: join(REPO, 'dsh', 'index.js') })
  return module.exports
}

async function main() {
  const installedCore = await requireSupportedCore(harnessRequire, 'router_schema_probe')

  let z
  try {
    z = (await import(pathToFileURL(harnessRequire.resolve('@deepseek-ai/schemastery')).href)).default
  } catch (error) {
    process.stderr.write(`router_schema_probe: the harness ships no usable schemastery: ${String(error?.message ?? error)}\n`)
    process.exit(EXIT_NO_HARNESS)
  }

  const { Config, ROUTE_KEYS: moduleRouteKeys, ROLE_LABELS: roleLabels } = loadRouter(z)

  // The module's own list is the source of truth for which fields there are;
  // nothing here rebuilds it from ROLES.
  const routeKeys = moduleRouteKeys.slice().sort()
  // The slot vocabulary the module's own route fields use (the card declares
  // the same two), derived from those fields rather than restated.
  const slots = [...new Set(routeKeys.map((key) => key.endsWith('Primary') ? 'Primary' : 'Fallback'))]
  const fields = Config.dict ?? {}
  const volatile = Object.entries(fields)
    .filter(([, schema]) => schema?.meta?.volatile === true)
    .map(([key]) => key)
    .sort()
  const descriptions = Object.fromEntries(
    Object.entries(fields).map(([key, schema]) => [key, schema?.meta?.description]),
  )

  const problems = []
  const expected = routeKeys.join(', ')
  if (volatile.join(', ') !== expected) {
    problems.push(`the live (meta.volatile) fields are [${volatile.join(', ')}], expected the route fields [${expected}]`)
  }
  for (const key of routeKeys) {
    const description = descriptions[key]
    if (typeof description !== 'string' || description === '') {
      problems.push(`${key} has no description, so the generated settings field is bare`)
      continue
    }
    const role = key.replace(/(Primary|Fallback)$/, '')
    const slot = key.slice(role.length).toLowerCase()
    if (!description.includes(slot)) {
      problems.push(`${key}'s description does not say which slot it is: ${description}`)
    }
    if (description.includes('undefined')) {
      problems.push(`${key}'s description has a missing label: ${description}`)
    }
    if (description.length < 40) {
      problems.push(`${key}'s description is too thin to say what the field means: ${description}`)
    }
  }
  for (const key of Object.keys(fields)) {
    if (routeKeys.includes(key)) continue
    // `volatileForm` drops these; a description on them renders nowhere and
    // claims a presence the core cannot honour.
    if (descriptions[key] !== undefined) {
      problems.push(`${key} is not volatile, so its description renders nowhere: ${descriptions[key]}`)
    }
  }

  // The runtime contract the loader wires: defaults survive, and every route
  // field is a live cell whose absent value reads as undefined.
  const built = Config({ presetId: 'rigorquant' })
  if (built.presetId !== 'rigorquant') problems.push('the presetId default did not survive')
  if (built.degradeTtlMs !== 600000) problems.push('the degradeTtlMs default did not survive')
  for (const key of routeKeys) {
    const cell = built[key]
    if (cell === null || typeof cell !== 'object' || typeof cell.get !== 'function') {
      problems.push(`${key} is not a volatile cell after evaluation: ${JSON.stringify(cell)}`)
      continue
    }
    if (cell.get() !== undefined) {
      problems.push(`${key} reads as set when nothing was saved: ${JSON.stringify(cell.get())}`)
    }
  }

  process.stdout.write(JSON.stringify({
    ok: problems.length === 0,
    harness,
    installedCore,
    routeKeys,
    slots,
    roleLabels,
    volatile,
    descriptions,
    problems,
  }, null, 2) + '\n')
  process.exit(problems.length === 0 ? 0 : EXIT_PROBLEM)
}

main().catch((error) => {
  process.stderr.write(`router_schema_probe: ${String(error?.stack ?? error)}\n`)
  process.exit(EXIT_PROBLEM)
})
