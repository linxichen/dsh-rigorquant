// Exercises dsh/index.js against a small host-context stub.
//
// The probe is centered on the Teams migration seam (issue #11): role
// identity comes ONLY from the team plugin's membership
// (`ctx.get('agentTeams').tryMembership(agent)`, the same call dsh/team.js
// resolves composition from) plus the agent's live composed preset — never
// from history or prompt text. It asserts:
// - a teammate's role resolves from its Team membership NAME;
// - the shipped tier matrix (DoubleChecker/adversary) applies on its own,
//   with no native route to lean on, when there is no override;
// - an explicit user override wins over that shipped matrix;
// - the degrade-to-fallback lane still fires on a terminal primary failure;
// - the orchestrator (the Lead) inherits absent an override, same as any
//   other unrouted role;
// - an agent with no membership, or whose live composition is not this
//   preset, is never touched.
const fs = require('node:fs')
const vm = require('node:vm')

const NS = 'rigorquant-models'
// The shipped tier matrix as the probe expects it. The router's own constants
// are compared against these below, so a retarget of the fallback cannot pass
// the probe by editing one side.
const SHIPPED_PRIMARY = {
  provider: 'deepseek-official', model: 'deepseek-v4-pro', reasoningEffort: 'high',
}
const SHIPPED_FALLBACK = {
  provider: 'deepseek-official', model: 'deepseek-flash', reasoningEffort: 'low',
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
  // The resolved section's base is `Config.defaults`, which schemastery fills
  // from the router's DEFAULT_* constants; the schema stub above discards that
  // default, so the probe seeds the base from the same exported constants.
  const { DEFAULT_PRIMARY, DEFAULT_FALLBACK } = mod
  equal(DEFAULT_PRIMARY, SHIPPED_PRIMARY, 'shipped primary')
  equal(DEFAULT_FALLBACK, SHIPPED_FALLBACK, 'shipped fallback')
  const listeners = new Map()
  const base = {
    doublecheckerPrimary: clone(DEFAULT_PRIMARY),
    doublecheckerFallback: clone(DEFAULT_FALLBACK),
    adversaryPrimary: clone(DEFAULT_PRIMARY),
    adversaryFallback: clone(DEFAULT_FALLBACK),
  }
  // The resolved settings section: base merged with whatever the "user" layer
  // currently holds — `ctx.settings.get()` always resolves live, so the
  // router needs no separate document-updated listener to see a change.
  let user = {}
  // Every log line, in order; `warnings` holds the warn-level subset, so a
  // scenario can pin that a degrade or give-up is a warning, not chatter.
  const logs = []
  const warnings = []

  // The Team service stub: membership is looked up by agent OBJECT identity,
  // exactly like the real duck-typed `agentTeams.tryMembership(agent)`.
  const membershipByAgent = new Map()
  const teamsService = { tryMembership: (agent) => membershipByAgent.get(agent) }
  const agentPresetsService = { composedPreset: (agentCtx) => agentCtx.__preset }

  // Reasoning-effort surfaces the stub `llm` service reports per exact route —
  // the same metadata the model catalog serves the card from. An empty list is
  // a model with no reasoning surface (it refuses every explicit effort); a
  // route absent from the map is unresolvable (the real service throws) and
  // the router must fail open, leaving the request untouched.
  const effortSurfaces = {
    'deepseek-official::deepseek-v4-pro': ['off', 'low', 'medium', 'high'],
    // DeepSeek-V41-Flash (the 0.1.6 default catalog): no `medium` tier.
    'deepseek-official::deepseek-flash': ['off', 'low', 'high', 'max'],
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

  const ctx = {
    settings: {
      register: () => {},
      get: () => ({ ...base, ...user }),
    },
    logger: {
      info: (message) => logs.push(message),
      warn: (message) => {
        logs.push(message)
        warnings.push(message)
      },
    },
    on: (eventName, handler) => {
      if (!listeners.has(eventName)) listeners.set(eventName, [])
      listeners.get(eventName).push(handler)
      return () => {}
    },
    get: (serviceName) => {
      if (serviceName === 'llm') return llm
      if (serviceName === 'agentTeams') return teamsService
      if (serviceName === 'agentPresets') return agentPresetsService
      return undefined
    },
  }

  const emit = async (eventName, ...args) => {
    for (const handler of listeners.get(eventName) ?? []) await handler(...args)
  }
  const waterfall = async (eventName, payload, resolved) => {
    const handlers = listeners.get(eventName) ?? []
    assert(handlers.length === 1, `${eventName}: expected one router listener`)
    return handlers[0](payload, async () => resolved)
  }

  /** A teammate or the Lead: its Team membership is registered by object
   *  identity, and its live composed preset lives on `ctx.__preset` — the
   *  same shape dsh/team.js's own probe uses. */
  const makeAgent = (id, membership, preset = 'rigorquant') => {
    const agent = { id, ctx: { __preset: preset } }
    membershipByAgent.set(agent, membership)
    return agent
  }

  mod.apply(ctx, {
    presetId: 'rigorquant',
    degradeTtlMs: 600000,
    defaults: base,
  })

  const doublechecker = makeAgent('doublechecker-1', { role: 'teammate', name: 'doublechecker-1' })
  const explorer = makeAgent('explorer-1', { role: 'teammate', name: 'explorer-1' })
  const lead = makeAgent('lead-1', { role: 'lead', name: 'lead' })
  const placeholderRoute = { provider: 'stale-provider', model: 'stale-model', reasoningEffort: 'medium' }

  // ---- Role from the membership name: the shipped matrix applies on its
  // own, with nothing native to lean on, purely because the membership name
  // parses to 'doublechecker'. The incoming (resolved) route is a
  // placeholder that shares nothing with the shipped route, so a pass-through
  // bug cannot pass this assertion by accident.
  equal(
    await waterfall('agent/request', { agent: doublechecker }, placeholderRoute),
    DEFAULT_PRIMARY,
    'the shipped matrix applies from the membership name alone',
  )

  // ---- The orchestrator (the Lead) inherits absent an override — same
  // waterfall, same "no shipped default for this role" rule as any other
  // unrouted role.
  const inheritedRoute = {
    provider: 'parent-provider', model: 'parent-model', reasoningEffort: 'medium',
  }
  equal(
    await waterfall('agent/request', { agent: lead }, inheritedRoute),
    inheritedRoute,
    'the orchestrator inherits absent an override',
  )
  equal(
    await waterfall('agent/request', { agent: explorer }, inheritedRoute),
    inheritedRoute,
    'a role outside the shipped matrix inherits absent an override',
  )

  // ---- An agent with Team membership but composed under a DIFFERENT preset
  // is never touched, even though its name parses cleanly.
  const otherPreset = makeAgent('doublechecker-9', { role: 'teammate', name: 'doublechecker-9' }, 'standard')
  equal(
    await waterfall('agent/request', { agent: otherPreset }, inheritedRoute),
    inheritedRoute,
    'a teammate composed under another preset is left alone',
  )

  // ---- An agent with NO Team membership at all (not a team member) is
  // never touched either.
  const noMembership = { id: 'no-membership-1', ctx: { __preset: 'rigorquant' } }
  equal(
    await waterfall('agent/request', { agent: noMembership }, inheritedRoute),
    inheritedRoute,
    'an agent with no Team membership is left alone',
  )

  // ---- A user override wins over the shipped matrix.
  user = { doublecheckerPrimary: { provider: 'custom-provider', model: 'custom-model' } }
  equal(
    await waterfall('agent/request', { agent: doublechecker }, placeholderRoute),
    { provider: 'custom-provider', model: 'custom-model' },
    'a user override wins over the shipped matrix',
  )

  // ---- Clearing the override (the card's "reset") returns to the SHIPPED
  // default, not to a bare "native" absence — there is no native route left
  // to fall back to under Agent Teams.
  user = {}
  equal(
    await waterfall('agent/request', { agent: doublechecker }, placeholderRoute),
    DEFAULT_PRIMARY,
    'reset returns to the shipped default',
  )

  // ---- The fallback lane: a terminal failure on the shipped primary
  // requests exactly one retry, and the retry uses the configured fallback.
  const action = await waterfall('agent/request-error', {
    agent: doublechecker,
    provider: DEFAULT_PRIMARY.provider,
    failure: { code: 'NO_ADAPTER', message: 'test failure' },
  }, undefined)
  equal(action, { kind: 'retry' }, 'shipped primary failure action')
  equal(
    await waterfall('agent/request', { agent: doublechecker }, placeholderRoute),
    DEFAULT_FALLBACK,
    'fallback retry route',
  )
  const degradedTo = `degraded to ${SHIPPED_FALLBACK.provider}/${SHIPPED_FALLBACK.model}`
  assert(logs.length === 1 && logs[0].includes(degradedTo), 'fallback log')

  await emit('session/event', { id: doublechecker.id }, {
    type: 'assistant/message',
    data: { message: { source: clone(DEFAULT_FALLBACK) } },
  })
  equal(
    await waterfall('agent/request', { agent: doublechecker }, placeholderRoute),
    DEFAULT_PRIMARY,
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
    await waterfall('agent/request', { agent: doublechecker }, placeholderRoute),
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
  const docAdversary = makeAgent('doc-adversary-1', { role: 'teammate', name: 'doc-adversary-1' })
  user = { 'doc-adversaryPrimary': { provider: 'zai', model: 'glm-5.3-flash', reasoningEffort: 'high' } }
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
  await emit('session/event', { id: doublechecker.id }, {
    type: 'assistant/message',
    data: { message: { source: clone(DEFAULT_FALLBACK) } },
  })

  // (c) An effort the model's surface lists is never touched.
  user = { doublecheckerPrimary: { provider: 'deepseek-official', model: 'deepseek-v4-pro', reasoningEffort: 'high' } }
  equal(
    await waterfall('agent/request', { agent: doublechecker }, placeholderRoute),
    { provider: 'deepseek-official', model: 'deepseek-v4-pro', reasoningEffort: 'high' },
    'listed effort passes through',
  )

  // (d) An unresolvable route fails open: the effort rides untouched, and the
  // request path reports the route exactly as it would without the router.
  user = { doublecheckerPrimary: { provider: 'custom-provider', model: 'custom-model', reasoningEffort: 'high' } }
  equal(
    await waterfall('agent/request', { agent: doublechecker }, placeholderRoute),
    { provider: 'custom-provider', model: 'custom-model', reasoningEffort: 'high' },
    'unknown route fails open',
  )

  // (e) A routed role's inherited (passthrough) route is sanitized too: an
  // effort the route does not list drops even without any stored choice.
  const offgrid = makeAgent('offgrid-1', { role: 'teammate', name: 'offgrid-1' })
  user = {}
  equal(
    await waterfall('agent/request', { agent: offgrid }, { provider: 'stub-provider', model: 'stub-model', reasoningEffort: 'max' }),
    { provider: 'stub-provider', model: 'stub-model' },
    'passthrough route drops an unlisted effort',
  )

  // ---- An unresolvable route (issue #22): a saved override naming a model
  // its provider does not declare. The pi-ai adapter throws UNKNOWN_MODEL
  // before any provider I/O; the LLM service turns the throw into a terminal
  // error finish carrying a code and NO status. It must take the same
  // one-shot fallback as NO_ADAPTER, with one warning naming the role,
  // the route, and the settings key it came from.
  const unknownModel = (provider, model) => ({
    code: 'UNKNOWN_MODEL',
    message: `pi-ai provider "${provider}" has no configured model "${model}"`,
  })
  const phantom = { provider: 'linxicloud', model: 'deepseek-v4-flash-dspark' }
  const doublechecker2 = makeAgent('doublechecker-2', { role: 'teammate', name: 'doublechecker-2' })
  user = { doublecheckerPrimary: clone(phantom) }
  equal(
    await waterfall('agent/request', { agent: doublechecker2 }, placeholderRoute),
    phantom,
    'the unresolvable override is what gets requested',
  )
  let warned = warnings.length
  equal(
    await waterfall('agent/request-error', {
      agent: doublechecker2, provider: phantom.provider, failure: unknownModel(phantom.provider, phantom.model),
    }, undefined),
    { kind: 'retry' },
    'UNKNOWN_MODEL with no status degrades to the fallback',
  )
  assert(warnings.length === warned + 1, 'one warning per degrade')
  const degradeWarning = warnings[warnings.length - 1]
  for (const part of ['doublechecker', 'linxicloud/deepseek-v4-flash-dspark', 'doublecheckerPrimary', 'UNKNOWN_MODEL', degradedTo]) {
    assert(degradeWarning.includes(part), `degrade warning names ${part}: ${degradeWarning}`)
  }
  assert(!degradeWarning.includes('shipped default'), 'a stored override is not called the shipped default')
  equal(
    await waterfall('agent/request', { agent: doublechecker2 }, placeholderRoute),
    DEFAULT_FALLBACK,
    'the retry routes to the shipped fallback',
  )
  // The fallback fails too: never retried, and the give-up is a warning
  // naming the fallback route and its key — once, however often it recurs.
  warned = warnings.length
  for (let attempt = 0; attempt < 2; attempt += 1) {
    equal(
      await waterfall('agent/request-error', {
        agent: doublechecker2, provider: DEFAULT_FALLBACK.provider,
        failure: unknownModel(DEFAULT_FALLBACK.provider, DEFAULT_FALLBACK.model),
      }, undefined),
      undefined,
      'a failing fallback is not retried',
    )
  }
  assert(warnings.length === warned + 1, 'the give-up warns once per degrade')
  const giveUpWarning = warnings[warnings.length - 1]
  for (const part of ['doublechecker', 'deepseek-official/deepseek-flash', 'doublecheckerFallback, shipped default', 'UNKNOWN_MODEL']) {
    assert(giveUpWarning.includes(part), `give-up warning names ${part}: ${giveUpWarning}`)
  }

  // The live case: an explorer override with no fallback at all (every role
  // but DoubleChecker/adversary inherits, so nothing ships one). There is no
  // fallback to degrade into, so the action passes through untouched — but the
  // router still gives up out loud, once per teammate, instead of leaving
  // the cause inside the teammate's compressed session log.
  const explorer2 = makeAgent('explorer-2', { role: 'teammate', name: 'explorer-2' })
  user = { explorerPrimary: clone(phantom) }
  equal(
    await waterfall('agent/request', { agent: explorer2 }, placeholderRoute),
    phantom,
    'the explorer override is requested',
  )
  warned = warnings.length
  for (let attempt = 0; attempt < 2; attempt += 1) {
    equal(
      await waterfall('agent/request-error', {
        agent: explorer2, provider: phantom.provider, failure: unknownModel(phantom.provider, phantom.model),
      }, undefined),
      undefined,
      'no fallback: the failure passes through',
    )
  }
  assert(warnings.length === warned + 1, 'the no-fallback give-up warns once per teammate')
  const noFallbackWarning = warnings[warnings.length - 1]
  for (const part of ['explorer', 'linxicloud/deepseek-v4-flash-dspark', 'explorerPrimary', 'no fallback']) {
    assert(noFallbackWarning.includes(part), `no-fallback warning names ${part}: ${noFallbackWarning}`)
  }

  // A transient failure on the same route is not route-fatal: no degrade,
  // no warning (the host's own retry policy owns it).
  const explorer3 = makeAgent('explorer-3', { role: 'teammate', name: 'explorer-3' })
  user = { explorerPrimary: clone(phantom), explorerFallback: clone(DEFAULT_FALLBACK) }
  await waterfall('agent/request', { agent: explorer3 }, placeholderRoute)
  warned = warnings.length
  equal(
    await waterfall('agent/request-error', {
      agent: explorer3, provider: phantom.provider, failure: { code: 'RATE_LIMIT', status: 503, message: 'busy' },
    }, undefined),
    undefined,
    'a transient failure is not route-fatal',
  )
  assert(warnings.length === warned, 'a transient failure warns nothing')

  // An HTTP 4xx on the primary still degrades (a string status included).
  const adversary4xx = makeAgent('adversary-2', { role: 'teammate', name: 'adversary-2' })
  user = {}
  await waterfall('agent/request', { agent: adversary4xx }, placeholderRoute)
  equal(
    await waterfall('agent/request-error', {
      agent: adversary4xx, provider: DEFAULT_PRIMARY.provider, failure: { status: '404', message: 'not found' },
    }, undefined),
    { kind: 'retry' },
    'an HTTP 4xx on the primary degrades',
  )
  assert(warnings[warnings.length - 1].includes('adversary primary') && warnings[warnings.length - 1].includes('(404)'),
    'the 4xx degrade warns with its status')
  assert(warnings[warnings.length - 1].includes('adversaryPrimary, shipped default'),
    'a route with no override is named as the shipped default')

  // INVALID_CONFIG is llm-pi-ai's other unresolvable-model code (a broken
  // model declaration, or the provider's failed catalog): the same one-shot
  // fallback.
  const doublechecker3 = makeAgent('doublechecker-3', { role: 'teammate', name: 'doublechecker-3' })
  await waterfall('agent/request', { agent: doublechecker3 }, placeholderRoute)
  equal(
    await waterfall('agent/request-error', {
      agent: doublechecker3, provider: DEFAULT_PRIMARY.provider,
      failure: { code: 'INVALID_CONFIG', message: 'model "deepseek-v4-pro" has an invalid declaration' },
    }, undefined),
    { kind: 'retry' },
    'INVALID_CONFIG degrades to the fallback',
  )
  assert(warnings[warnings.length - 1].includes('(INVALID_CONFIG); degraded to'), 'the INVALID_CONFIG degrade warns')

  // A role with no primary follows the picker: a route-fatal failure there
  // is the picker's own, so it is left alone and warns nothing.
  const offgrid2 = makeAgent('offgrid-2', { role: 'teammate', name: 'offgrid-2' })
  await waterfall('agent/request', { agent: offgrid2 }, { provider: 'picker-provider', model: 'picker-model' })
  warned = warnings.length
  equal(
    await waterfall('agent/request-error', {
      agent: offgrid2, provider: 'picker-provider', failure: unknownModel('picker-provider', 'picker-model'),
    }, undefined),
    undefined,
    'an UNKNOWN_MODEL on a picker-following role is left alone',
  )
  assert(warnings.length === warned, 'a picker-following role warns nothing')

  // The unrelated-picker guard holds for UNKNOWN_MODEL too: a failure on a
  // provider the router did not route to is left alone, even for a role
  // whose primary and fallback are both set.
  user = { explorerPrimary: clone(phantom), explorerFallback: clone(DEFAULT_FALLBACK) }
  equal(
    await waterfall('agent/request-error', {
      agent: explorer3, provider: 'picker-provider', failure: unknownModel('picker-provider', 'picker-model'),
    }, undefined),
    undefined,
    'an UNKNOWN_MODEL on an unrelated route is left alone',
  )
  assert(warnings.length === warned, 'an unrelated route warns nothing')

  process.stdout.write(JSON.stringify({ ok: true, logs, warnings }))
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`)
  process.exitCode = 1
})
