// Exercises the boot-sync engine the way a host process would, without one.
//
// stdin: a JSON array of steps
//   { "op": "sync", "src": "<dir>", "dst": "<dir>", "version": "x" }
//   { "op": "write", "path": "<file>", "data": "<text>" }
//   { "op": "mkdir", "path": "<dir>" }
//   { "op": "remove", "path": "<path>" }
//   { "op": "read",  "path": "<file>" }
//   { "op": "exists", "path": "<path>" }
// stdout: one JSON line per step result, in order.
// `sync` results are exactly what dsh/sync.js's syncManagedDir returns.

const { mkdirSync, writeFileSync, rmSync, readFileSync, existsSync } = require('node:fs')
const { dirname } = require('node:path')
const { pathToFileURL } = require('node:url')

async function main() {
  const [, , syncModulePath, stepsJson] = process.argv
  const mod = await import(pathToFileURL(syncModulePath).href)
  const steps = JSON.parse(stepsJson)
  const out = []
  for (const step of steps) {
    if (step.op === 'sync') {
      out.push(await mod.syncManagedDir(step.src, step.dst, {
        version: step.version,
        keyFile: step.keyFile,
      }))
    } else if (step.op === 'write') {
      mkdirSync(dirname(step.path), { recursive: true })
      writeFileSync(step.path, step.data)
      out.push({ ok: true })
    } else if (step.op === 'mkdir') {
      mkdirSync(step.path, { recursive: true })
      out.push({ ok: true })
    } else if (step.op === 'remove') {
      rmSync(step.path, { recursive: true, force: true })
      out.push({ ok: true })
    } else if (step.op === 'read') {
      out.push({ data: readFileSync(step.path, 'utf8') })
    } else if (step.op === 'exists') {
      out.push({ exists: existsSync(step.path) })
    } else {
      throw new Error(`unknown op: ${step.op}`)
    }
  }
  process.stdout.write(JSON.stringify(out))
}

main().catch((error) => {
  process.stderr.write(String(error && error.stack || error))
  process.exit(1)
})
