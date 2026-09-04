// Exercises dsh/index.js against a small host-context stub.
//
// The probe is intentionally centered on the 0.1.2 migration seam:
// - the native DoubleChecker primary must pass through without an unconditional
//   agent/request rewrite;
// - a raw user primary must still override that native route;
// - a native-primary terminal failure must enter the custom fallback lane;
// - resetting the user layer must return to the native route.
const fs = require('node:fs')
const vm = require('node:vm')

const NS = 'rigorquant-models'
const DEFAULT_PRIMARY = {
  provider: 'deepseek-official', model: 'deepseek-v4-pro', reasoningEffort: 'high',
}
const DEFAULT_FALLBACK = {
  provider: 'deepseek-official', model: 'deepseek-v4-flash', reasoningEffort: 'low',
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

function equal(actual, expected, label) {
  const left = JSON.stringify(actual)
  const right = JSON.stringify(expected)
  assert(left === right, `${label}: expected ${right}, got ${left}`)
}

// Load the host module without requiring npm install in a repository-only test
// checkout. This is not a second implementation: the source is evaluated as
// CommonJS with only Schemastery's declaration builder stubbed, because the
// probe exercises apply() and never validates a config document.
function loadHostModule(modulePath) {
  let source = fs.readFileSync(modulePath, 'utf8')
  source = source.replace("import z from '@deepseek-ai/schemastery'", 'const z = schemaStub')
  source = source.replace(/^export const /gm, 'const ')
  source = source.replace(/^export \{ ([^}]+) \}$/m, 'module.exports = { $1 }')
  const schema = {
    required() { return this },
    default() { return this },
    min() { return this },
  }
  const schemaStub = {
    object() { return schema },
    string() { return schema },
    number() { return schema },
  }
  const module = { exports: {} }
  vm.runInNewContext(source, {
    module,
    schemaStub,
    console,
    Date,
    Error,
    Map,
    Math,
    Object,
    Promise,
    RegExp,
    Set,
    String,
  }, { filename: modulePath })
  return module.exports
}

async function main() {
  const [, , modulePath] = process.argv
  const mod = loadHostModule(modulePath)
  const listeners = new Map()
  const section = {
    doublecheckerPrimary: clone(DEFAULT_PRIMARY),
    doublecheckerFallback: clone(DEFAULT_FALLBACK),
    adversaryPrimary: clone(DEFAULT_PRIMARY),
    adversaryFallback: clone(DEFAULT_FALLBACK),
  }
  let user = {}
  const logs = []

  const ctx = {
    settings: {
      register: () => {},
      get: () => section,
      describe: () => [{ ns: NS, user: clone(user) }],
    },
    logger: { info: (message) => logs.push(message) },
    on: (name, handler) => {
      if (!listeners.has(name)) listeners.set(name, [])
      listeners.get(name).push(handler)
      return () => {}
    },
    get: (name) => (name === 'llm' ? llm : undefined),
  }

  // Reasoning-effort surfaces the stub `llm` service reports per exact route —
  // the same metadata the model catalog serves the card from. An empty list is
  // a model with no reasoning surface (it refuses every explicit effort); a
  // route absent from the map is unresolvable (the real service throws) and
  // the router must fail open, leaving the request untouched.
  const effortSurfaces = {
    'deepseek-official::deepseek-v4-pro': ['off', 'low', 'medium', 'high'],
    'deepseek-official::deepseek-v4-flash': ['off', 'low', 'medium', 'high'],
    'zai::glm-5.3-flash': [],
    'stub-provider::stub-model': ['low'],
  }
  const llm = {
    resolveModelInfo: async (provider, model) => {
      const key = `${provider}::${model}`
      if (!(key in effortSurfaces)) throw new Error(`NO_ADAPTER: ${key}`)
      return { reasoning: { efforts: effortSurfaces[key].map((id) => ({ id, name: id })) } }
    },
  }

  const emit = async (name, ...args) => {
    for (const handler of listeners.get(name) ?? []) await handler(...args)
  }
  const waterfall = async (name, payload, resolved) => {
    const handlers = listeners.get(name) ?? []
    assert(handlers.length === 1, `${name}: expected one router listener`)
    return handlers[0](payload, async () => resolved)
  }
  const makeAgent = (id, role) => {
    const events = [{
      type: 'subagent/descriptor',
      data: { persona: `role [[rq:role=${role}]]` },
    }]
    return {
      id,
      session: {
        id,
        header: { parentSession: 'root-session', agentPreset: NS },
        // DSH 0.1.2 sessions expose their event log through snapshotEvents().
        snapshotEvents: () => events,
      },
      ctx: { get: () => undefined },
    }
  }

  mod.apply(ctx, {
    presetId: 'rigorquant',
    degradeTtlMs: 600000,
    defaults: section,
  })

  const doublechecker = makeAgent('doublechecker-1', 'doublechecker')
  const explorer = makeAgent('explorer-1', 'explorer')
  const nativeRoute = clone(DEFAULT_PRIMARY)

  // No user primary: the route already resolved by native agentOptions must
  // pass through unchanged.
  equal(
    await waterfall('agent/request', { agent: doublechecker }, nativeRoute),
    nativeRoute,
    'native doublechecker default',
  )
  const inheritedRoute = {
    provider: 'parent-provider', model: 'parent-model', reasoningEffort: 'medium',
  }
  equal(
    await waterfall('agent/request', { agent: explorer }, inheritedRoute),
    inheritedRoute,
    'inherited explorer route',
  )

  // A raw user primary is an intentional override. Omitting effort clears the
  // inherited value, matching the native model-selection contract.
  user = { doublecheckerPrimary: { provider: 'custom-provider', model: 'custom-model' } }
  await emit('settings/document-updated', NS, 1)
  equal(
    await waterfall('agent/request', { agent: doublechecker }, nativeRoute),
    { provider: 'custom-provider', model: 'custom-model' },
    'explicit doublechecker override',
  )

  // Resetting the raw user field returns to native agentOptions rather than to
  // another custom rewrite.
  user = {}
  await emit('settings/document-updated', NS, 2)
  equal(
    await waterfall('agent/request', { agent: doublechecker }, nativeRoute),
    nativeRoute,
    'reset doublechecker override',
  )

  // The native primary still participates in the custom fallback policy. A
  // terminal failure requests exactly one retry, and the retry uses the
  // configured fallback route.
  const action = await waterfall('agent/request-error', {
    agent: doublechecker,
    provider: DEFAULT_PRIMARY.provider,
    failure: { code: 'NO_ADAPTER', message: 'test failure' },
  }, undefined)
  equal(action, { kind: 'retry' }, 'native primary failure action')
  equal(
    await waterfall('agent/request', { agent: doublechecker }, nativeRoute),
    DEFAULT_FALLBACK,
    'fallback retry route',
  )
  assert(logs.length === 1 && logs[0].includes('degraded to deepseek-official/deepseek-v4-flash'), 'fallback log')

  await emit('session/event', doublechecker.session, {
    type: 'assistant/message',
    data: { message: { source: clone(DEFAULT_FALLBACK) } },
  })
  equal(
    await waterfall('agent/request', { agent: doublechecker }, nativeRoute),
    nativeRoute,
    'primary restored after fallback success',
  )

  // The DeepSeek official quota response can carry provider code 1308 and its
  // usage-limit text without a normalized numeric status. It is terminal for
  // this primary and must take the same one-shot fallback lane as a normal 429.
  const quotaAction = await waterfall('agent/request-error', {
    agent: doublechecker,
    provider: DEFAULT_PRIMARY.provider,
    failure: { code: '1308', message: 'Usage limit reached for 5 hour.' },
  }, undefined)
  equal(quotaAction, { kind: 'retry' }, 'usage-limit fallback action')
  equal(
    await waterfall('agent/request', { agent: doublechecker }, nativeRoute),
    DEFAULT_FALLBACK,
    'usage-limit fallback route',
  )
  assert(logs.length === 2 && logs[1].includes('(1308)'), 'usage-limit fallback log')

  // ---- Effort fallback: a reasoning effort the exact route refuses falls
  // back to the model's default level instead of dying in
  // UNSUPPORTED_REASONING_EFFORT before any provider I/O.

  // (a) The regression route: a model with NO reasoning surface refuses every
  // explicit effort. The stored doc-adversary primary keeps its model
  // override but loses the effort; the inherited route's effort was already
  // cleared by applyChoice.
  const docAdversary = makeAgent('doc-adversary-1', 'doc-adversary')
  user = { 'doc-adversaryPrimary': { provider: 'zai', model: 'glm-5.3-flash', reasoningEffort: 'high' } }
  await emit('settings/document-updated', NS, 3)
  equal(
    await waterfall('agent/request', { agent: docAdversary }, { provider: 'p', model: 'm', reasoningEffort: 'medium' }),
    { provider: 'zai', model: 'glm-5.3-flash' },
    'refused effort demoted to the model default',
  )
  assert(logs.length === 3 && logs[2].includes('zai/glm-5.3-flash does not support reasoning effort "high"'), 'demotion log')

  // (b) The demotion is stable and logs once per route, not per request.
  equal(
    await waterfall('agent/request', { agent: docAdversary }, { provider: 'p', model: 'm', reasoningEffort: 'medium' }),
    { provider: 'zai', model: 'glm-5.3-flash' },
    'demotion is stable across requests',
  )
  assert(logs.length === 3, 'the demotion log fires once per route')

  // Restore the doublechecker lane from the quota scenario's degrade state.
  await emit('session/event', doublechecker.session, {
    type: 'assistant/message',
    data: { message: { source: clone(DEFAULT_FALLBACK) } },
  })

  // (c) An effort the model's surface lists is never touched.
  user = { doublecheckerPrimary: { provider: 'deepseek-official', model: 'deepseek-v4-pro', reasoningEffort: 'high' } }
  await emit('settings/document-updated', NS, 4)
  equal(
    await waterfall('agent/request', { agent: doublechecker }, nativeRoute),
    { provider: 'deepseek-official', model: 'deepseek-v4-pro', reasoningEffort: 'high' },
    'listed effort passes through',
  )

  // (d) An unresolvable route fails open: the effort rides untouched, and the
  // request path reports the route exactly as it would without the router.
  user = { doublecheckerPrimary: { provider: 'custom-provider', model: 'custom-model', reasoningEffort: 'high' } }
  await emit('settings/document-updated', NS, 5)
  equal(
    await waterfall('agent/request', { agent: doublechecker }, nativeRoute),
    { provider: 'custom-provider', model: 'custom-model', reasoningEffort: 'high' },
    'unknown route fails open',
  )

  // (e) A routed role's inherited (passthrough) route is sanitized too: an
  // effort the route does not list drops even without any stored choice.
  const offgrid = makeAgent('offgrid-1', 'offgrid')
  user = {}
  await emit('settings/document-updated', NS, 6)
  equal(
    await waterfall('agent/request', { agent: offgrid }, { provider: 'stub-provider', model: 'stub-model', reasoningEffort: 'max' }),
    { provider: 'stub-provider', model: 'stub-model' },
    'passthrough route drops an unlisted effort',
  )

  process.stdout.write(JSON.stringify({ ok: true, logs }))
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`)
  process.exitCode = 1
})
