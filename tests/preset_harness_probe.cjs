#!/usr/bin/env node
// Validate an agent-preset composition against the CONFIG SCHEMAS of the
// packages actually installed in a DSH deployment.
//
// This is the upgrade check that catches what the release notes do not: a row
// whose `config` no longer satisfies the plugin's own schemastery schema. The
// DSH loader rejects such a row at mount time and fails the WHOLE preset
// (`agent-presets: preset "<id>" failed to mount`), so a schema drift is not a
// degraded feature — it is an unmountable preset. Running this before an
// upgrade turns that into a one-line diff.
//
// Why it works this way: the authoritative schema is the one in the installed
// package, so this probe imports the real `Config` (or `resolveConfig`) from
// the deployment's own `node_modules` and applies it to each row. No schema is
// re-declared here, so this file cannot drift from the harness.
//
// Usage:
//   node tests/preset_harness_probe.cjs [preset-dir-or-file] [harness-modules-dir]
//
// Defaults: agent-presets/rigorquant/agent.cordis.yml and the @deepseek-ai
// directory of the `dsh` install found on PATH (falling back to the active
// Node module paths). Exit code 0 = every enabled row validates.
//
// Only Node and the installed harness are required; `js-yaml` is resolved from
// the harness install, so this probe adds no dependency to this repository.

'use strict'

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

const [presetArg, harnessArg] = process.argv.slice(2)
const presetFile = presetArg === undefined
  ? join(REPO, 'agent-presets', 'rigorquant', 'agent.cordis.yml')
  : resolve(presetArg)
const presetDir = presetFile.endsWith('.yml') ? dirname(presetFile) : presetFile
const composition = presetFile.endsWith('.yml') ? presetFile : join(presetFile, 'agent.cordis.yml')

const harness = harnessArg === undefined ? findHarnessModules() : resolve(harnessArg)
if (harness === undefined) {
  process.stderr.write('preset_harness_probe: cannot locate an installed harness; pass its @deepseek-ai directory\n')
  process.exit(2)
}
if (!existsSync(composition)) {
  process.stderr.write(`preset_harness_probe: no composition at ${composition}\n`)
  process.exit(2)
}

const harnessRequire = createRequire(join(harness, '__probe__.cjs'))
const yaml = harnessRequire('js-yaml')

// `!!js` is the composition plane's escape hatch for values only the boot
// environment can produce (platform switches, baseUrl-relative paths). The
// probe evaluates them with the same three names the loader exposes, and
// substitutes an opaque marker when evaluation is impossible, so a row is
// still reached.
const JsTag = new yaml.Type('tag:yaml.org,2002:js', {
  kind: 'scalar',
  resolve: (data) => typeof data === 'string',
  construct: (data) => {
    try {
      // eslint-disable-next-line no-new-func
      return new Function('process', 'baseUrl', `return (${data})`)(process, `file://${presetDir}/`)
    } catch {
      return `<js:${data}>`
    }
  },
})
const doc = yaml.load(readFileSync(composition, 'utf8'), {
  schema: yaml.DEFAULT_SCHEMA.extend([JsTag]),
})

const rows = []
const walk = (list, path) => {
  for (const [index, row] of (list ?? []).entries()) {
    const label = path === '' ? `row ${index + 1}` : `${path} > row ${index + 1}`
    if (row === null || typeof row !== 'object' || Array.isArray(row)) {
      rows.push({ label, name: '<malformed>' })
      continue
    }
    rows.push({ label, id: row.id, name: row.name, disabled: row.disabled === true, config: row.config ?? {}, group: row.group === true })
    if (row.group === true) walk(row.config, `${label} (${row.id})`)
  }
}
walk(doc, '')

let failed = 0
let skipped = 0

async function main() {
for (const row of rows) {
  if (row.group === true) continue
  const suffix = row.disabled ? ' [disabled]' : ''
  const name = row.name
  if (typeof name !== 'string' || name === '') {
    process.stdout.write(`MALFORMED   ${row.label}\n`)
    failed += 1
    continue
  }
  // Cordis built-ins (groups) are not npm packages.
  if (name.startsWith('cordis:')) {
    process.stdout.write(`builtin     ${name}  (${row.label})\n`)
    continue
  }
  let resolved
  try {
    resolved = harnessRequire.resolve(name)
  } catch (error) {
    process.stdout.write(`UNRESOLVED  ${name}  (${row.label})${suffix}\n              ${String(error.message).split('\n')[0]}\n`)
    if (!row.disabled) failed += 1
    continue
  }
  let mod
  try {
    mod = await import(pathToFileURL(resolved).href)
  } catch (error) {
    process.stdout.write(`IMPORT-FAIL ${name}  (${row.label})${suffix}\n              ${String(error.message).split('\n')[0]}\n`)
    if (!row.disabled) failed += 1
    continue
  }
  const schema = mod.Config
  const resolveConfig = mod.resolveConfig ?? mod.resolveOptions
  if (typeof schema !== 'function' || schema.type === undefined) {
    if (typeof resolveConfig === 'function') {
      try {
        resolveConfig(row.config)
        process.stdout.write(`OK(resolve) ${name}  (${row.label})${suffix}\n`)
      } catch (error) {
        process.stdout.write(`CONFIG-FAIL ${name}  (${row.label})${suffix}\n`)
        for (const line of String(error.message).split('\n').slice(0, 8)) process.stdout.write(`              ${line}\n`)
        if (!row.disabled) failed += 1
      }
      continue
    }
    process.stdout.write(`no-schema   ${name}  (${row.label})${suffix}\n`)
    skipped += 1
    continue
  }
  try {
    schema(row.config)
    process.stdout.write(`OK          ${name}  (${row.label})${suffix}\n`)
  } catch (error) {
    process.stdout.write(`CONFIG-FAIL ${name}  (${row.label})${suffix}\n`)
    for (const line of String(error.message).split('\n').slice(0, 8)) process.stdout.write(`              ${line}\n`)
    if (!row.disabled) failed += 1
  }
}
}

main()
  .then(() => {
    process.stdout.write(
      `\n${composition}\n${rows.length} rows; ${failed} hard failure(s); ${skipped} without an exported Config\n`,
    )
    process.exit(failed === 0 ? 0 : 1)
  })
  .catch((error) => {
    process.stderr.write(`preset_harness_probe: ${String(error?.stack ?? error)}\n`)
    process.exit(2)
  })
