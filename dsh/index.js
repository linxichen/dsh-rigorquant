// RigorQuant model router — host half.
//
// One settings namespace (`rigorquant-models`) maps every RigorQuant role to a
// primary model and a per-role fallback model, each with its own reasoning
// effort. No native per-role model row remains under Agent Teams — a
// teammate is created by `spawn_teammate`, which carries no model choice at
// all — so this router carries the shipped tier matrix itself
// (`DEFAULT_PRIMARY`/`DEFAULT_FALLBACK`, resolved through the settings
// section like any other field) and overlays a live Settings override on top
// of it. The `agent/request` waterfall remains the small policy overlay that
// makes live settings and fallback possible.
//
// Role identity (docs/architecture.md Decision 24, amending Decision 23):
// the teammate's NAME is the role. Every agent's Team membership is read
// duck-typed off the optional `agentTeams` service
// (`ctx.get('agentTeams').tryMembership(agent)`, the same call
// `dsh/team.js` resolves composition from) — the Lead is the orchestrator
// (`root`); every other member's role is parsed from its name
// (`<role>-<n>`). An agent with no membership, or whose live composition is
// not this preset, is never touched: it keeps the chatbox/parent model
// exactly as before. The classic persona-tag regex, the persona-assembly
// probe that read a one-shot child's live prompt section, and the
// deprecated synchronous session-event reads that found a continuable
// child's descriptor are gone — nothing here reads history or prompt text
// to find a role anymore.
//
// Degrade lane: when the primary route of a routed role fails terminally
// (no adapter, a model its provider does not declare or cannot resolve, or
// an HTTP 4xx the route cannot recover from), the listener marks that
// session+role degraded and forces one retry, which re-enters agent/request
// and routes to the role's fallback. A successful assistant step on the
// fallback — or the TTL — restores the primary. A fallback that also fails is
// never retried again by this plugin (no retry loop). Every degrade and every
// route-fatal give-up (the fallback failed too, or the role has no fallback)
// is one warning naming the role, the route, and the settings key it came
// from: the teammate's own failure surfaces only as an unaccepted initial
// prompt.
//
// Effort fallback: a stored choice may carry a reasoning effort the exact
// route's model does not support — a model with no reasoning surface at all,
// or one that does not list the saved level. The LLM service rejects such a
// request before any provider I/O (UNSUPPORTED_REASONING_EFFORT) and the
// turn dies with it, so the router consults the model's real effort metadata
// while routing and drops a refused effort: the model's default level
// governs and the stored choice's model override stays intact. A route whose
// metadata cannot be resolved fails open — the request path reports it
// exactly as before.

import z from '@deepseek-ai/schemastery'

const name = 'rq-model-router'
const inject = ['settings']

/** Settings namespace served to the Plugins configuration tab. */
const NS = 'rigorquant-models'
/** Every routable role, in card order. */
export const ROLES = ['root', 'explorer', 'offgrid', 'doublechecker', 'adversary', 'lit-line', 'lit-adversary', 'doc-adversary']
/** Every teammate role, i.e. `ROLES` minus the Lead-only `root` — the same
 *  set `dsh/team.js`'s `TEAMMATE_ROLES` names. Declared here rather than
 *  imported: `dsh/client.js`'s browser bundle carries the same set as a
 *  third independent copy and structurally cannot import either Node
 *  module, so every surface already owns its own copy pinned equal by
 *  tests/test_repo_consistency.py — importing here would leave two of
 *  three surfaces sharing source and one not, for no behavioural gain. */
const TEAMMATE_ROLES = ROLES.filter((role) => role !== 'root')
/** Teammate name convention: `<role>-<suffix>`, e.g. `doublechecker-1` — the
 *  same contract `dsh/team.js`'s `NAME_PATTERN` parses membership by. */
const NAME_PATTERN = new RegExp(`^(${TEAMMATE_ROLES.join('|')})-.+$`)

/** Parse a teammate's role from its Team membership name, or `null` when it
 *  doesn't parse (an unparseable name should already have been refused at
 *  `spawn_teammate` by `dsh/team.js`'s Lead guard; this is defense in depth,
 *  not the enforcement point). */
function roleFromName(teammateName) {
  const match = typeof teammateName === 'string' ? NAME_PATTERN.exec(teammateName) : null
  return match !== null ? match[1] : null
}

const choiceSchema = z.object({
  provider: z.string().required(),
  model: z.string().required(),
  reasoningEffort: z.string(),
})

/** Flat on purpose: every field is a whole choice object the card writes whole.
 *  `.default(void 0)` keeps an absent field absent: schemastery otherwise
 *  materializes a missing object field as `{}` and rejects its required inners. */
const SettingsSchema = z.object(Object.fromEntries(
  ROLES.flatMap((role) => [
    [`${role}Primary`, choiceSchema.default(void 0)],
    [`${role}Fallback`, choiceSchema.default(void 0)],
  ]),
))

// Decision 16's shipped routes. `deepseek-flash` is DeepSeek-V41-Flash
// (efforts off|low|high|max), the flash tier the 0.1.6 default catalog lists.
const DEFAULT_PRIMARY = Object.freeze({ provider: 'deepseek-official', model: 'deepseek-v4-pro', reasoningEffort: 'high' })
const DEFAULT_FALLBACK = Object.freeze({ provider: 'deepseek-official', model: 'deepseek-flash', reasoningEffort: 'low' })

const Config = z.object({
  presetId: z.string().default('rigorquant'),
  degradeTtlMs: z.number().default(600000),
  defaults: SettingsSchema.default({
    // The shipped tier matrix: proof-critical roles on pro with a flash
    // fallback; every other role absent (inherit the session model).
    doublecheckerPrimary: DEFAULT_PRIMARY,
    doublecheckerFallback: DEFAULT_FALLBACK,
    adversaryPrimary: DEFAULT_PRIMARY,
    adversaryFallback: DEFAULT_FALLBACK,
  }),
})

function isRecord(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isChoice(value) {
  return isRecord(value)
    && typeof value.provider === 'string' && value.provider !== ''
    && typeof value.model === 'string' && value.model !== ''
}

/** Codes meaning the exact provider/model pair cannot be resolved at all,
 *  each thrown before any provider I/O with a code and no status: no adapter
 *  owns the provider (`NO_ADAPTER`, from the LLM service or the adapter), the
 *  provider does not declare the model (`UNKNOWN_MODEL`), or its declaration
 *  is broken (`INVALID_CONFIG` — llm-pi-ai's configured-model lookup throws it
 *  for that model's config error or its provider's failed catalog, and
 *  nowhere else). */
const UNRESOLVABLE_ROUTE_CODES = new Set(['NO_ADAPTER', 'UNKNOWN_MODEL', 'INVALID_CONFIG'])

/** A failure the route itself cannot recover from: an unresolvable route or
 *  bad primary.
 *
 * Providers should surface numeric HTTP status, but the official usage-limit
 * response currently exposes its provider code (`1308`) and message while some
 * adapter paths omit `status`. Treat that specific quota exhaustion as terminal
 * too: retrying the same primary cannot help, whereas the role fallback can.
 */
function routeFatal(failure) {
  if (failure === undefined || failure === null) return false
  if (UNRESOLVABLE_ROUTE_CODES.has(failure.code)) return true
  const status = typeof failure.status === 'number'
    ? failure.status
    : typeof failure.status === 'string' ? Number(failure.status) : NaN
  if (Number.isFinite(status) && status >= 400 && status < 500) return true
  return failure.code === '1308' && /usage limit reached/i.test(String(failure.message ?? ''))
}

/** The failure's own identity for a log line: its code, else its status. */
function failureLabel(failure) {
  return String(failure?.code ?? failure?.status ?? 'unknown')
}

/** Apply a live override/fallback while clearing an inherited effort. */
function applyChoice(resolved, choice) {
  const { reasoningEffort: _inheritedEffort, ...withoutInheritedEffort } = resolved
  return {
    ...withoutInheritedEffort,
    provider: choice.provider,
    model: choice.model,
    ...typeof choice.reasoningEffort === 'string' && choice.reasoningEffort !== ''
      ? { reasoningEffort: choice.reasoningEffort }
      : {},
  }
}

function apply(ctx, config) {
  // Registers fiber-scoped: stopping this plugin unregisters the namespace.
  ctx.settings.register(NS, SettingsSchema, { base: config.defaults, applies: 'live' })

  /** sessionId → { role, until, provider, model, choice, gaveUp } while
   *  degraded: `choice` is the fallback degraded to, `gaveUp` whether its own
   *  failure has already warned. */
  const degraded = new Map()
  /** The exact resolved request route, for error-to-primary attribution. */
  const requested = new Map()
  /** provider::model → Set of the effort ids the model's own metadata lists
   *  (empty when it takes no explicit effort at all). Failed lookups are never
   *  cached: a transient registry miss retries on the next request. */
  const effortSurfaces = new Map()
  /** Routes whose effort was dropped, so the fallback logs once per route. */
  const effortFallbacks = new Set()
  /** agentId → the provider/model its no-fallback give-up already warned
   *  about, so a teammate whose every turn dies on it warns once. */
  const noFallbackWarned = new Map()

  /**
   * The reasoning-effort surface of one exact route, from the same `llm`
   * service the model catalog serves the card from. `undefined` means the
   * route could not be resolved (unregistered adapter, unknown model) and the
   * caller must fail open: the request path reports such a route itself.
   */
  async function effortSurface(provider, model) {
    const key = `${provider}::${model}`
    const cached = effortSurfaces.get(key)
    if (cached !== undefined) return cached
    try {
      const info = await ctx.get('llm').resolveModelInfo(provider, model)
      const surface = new Set(info.reasoning?.efforts.map((effort) => effort.id) ?? [])
      effortSurfaces.set(key, surface)
      return surface
    } catch {
      return undefined
    }
  }
  // Adapter (re)registration — a profile edit, an HMR swap — can change what a
  // model supports; drop the cache so the next request re-resolves it.
  ctx.on('llm/adapters-updated', () => {
    effortSurfaces.clear()
  })

  /**
   * Fall back to the model's default effort level when the carried effort is
   * one the exact route refuses. The LLM service rejects such a request
   * before any provider I/O and the turn dies with no recovery — the failure
   * never reaches agent/request-error — so the effort is dropped here, where
   * routing happens. An empty surface (no reasoning metadata) refuses every
   * explicit effort; a listed effort passes through untouched.
   */
  async function withSupportedEffort(route) {
    const effort = route?.reasoningEffort
    if (typeof effort !== 'string' || effort === '') return route
    const surface = await effortSurface(route.provider, route.model)
    if (surface === undefined || surface.has(effort)) return route
    const key = `${route.provider}::${route.model}`
    if (!effortFallbacks.has(key)) {
      effortFallbacks.add(key)
      ctx.logger.info(
        `rq-model-router: ${route.provider}/${route.model} does not support reasoning`
        + ` effort "${effort}"; falling back to the model default level`,
      )
    }
    const { reasoningEffort: _refused, ...withoutEffort } = route
    return withoutEffort
  }

  const section = () => ctx.settings.get(NS)
  const choiceFor = (role, slot) => {
    const value = section()?.[`${role}${slot}`]
    return isChoice(value) ? value : null
  }
  // Both slots read the same resolved (defaults-then-user) section: no
  // native route exists to shadow, so a reset simply falls back to whatever
  // `Config.defaults` states for that field (the shipped tier matrix for
  // DoubleChecker/adversary, absent — inherit — for every other role).
  const primaryFor = (role) => choiceFor(role, 'Primary')
  const fallbackFor = (role) => choiceFor(role, 'Fallback')
  /** One slot's route for a warning: the role, the route, and where it came
   *  from — the settings key the operator edits, marked as the shipped
   *  default when it still equals `Config.defaults` (no override is set). */
  const describeRoute = (role, slot, choice) => {
    const key = `${role}${slot}`
    const base = config.defaults?.[key]
    const shipped = isChoice(base) && base.provider === choice.provider && base.model === choice.model
      && (base.reasoningEffort ?? '') === (choice.reasoningEffort ?? '')
    return `${role} ${slot.toLowerCase()} ${choice.provider}/${choice.model} `
      + `(settings key ${key}${shipped ? ', shipped default' : ''})`
  }

  ctx.on('session/event', (session, event) => {
    if (event.type === 'assistant/message') {
      const d = degraded.get(session.id)
      const source = event.data?.message?.source
      if (d !== undefined && source !== undefined
        && source.model === d.model
        && (d.provider === undefined || source.provider === d.provider)) {
        degraded.delete(session.id)
      }
    }
  })
  ctx.on('session/disposed', (session) => {
    degraded.delete(session.id)
    requested.delete(session.id)
    noFallbackWarned.delete(session.id)
  })
  ctx.on('agent/disposed', ({ agent }) => {
    degraded.delete(agent.id)
    requested.delete(agent.id)
    noFallbackWarned.delete(agent.id)
  })

  /** The teammate's role, resolved purely from its Team membership — never
   *  from history or prompt text. `agentTeams` is optional and reached
   *  duck-typed, the same contract `dsh/team.js` mounts against; absent
   *  (Agent Teams not enabled) or no membership (not a team member, e.g. a
   *  classic fork/workflow child) both mean "not routable" here. The Lead is
   *  the orchestrator (`root`); every other member's role comes from its
   *  name. Only agents whose LIVE composition is this preset are touched —
   *  a Lead or teammate of some other team is left alone. */
  function resolveRole(agent) {
    const teams = ctx.get('agentTeams')
    if (teams === undefined) return null
    const membership = teams.tryMembership(agent)
    if (membership === undefined) return null
    const inRigorQuant = ctx.get('agentPresets')?.composedPreset(agent.ctx) === config.presetId
    if (!inRigorQuant) return null
    return membership.role === 'lead' ? 'root' : roleFromName(membership.name)
  }

  ctx.on('agent/request', async (payload, next) => {
    const resolved = await next()
    const role = resolveRole(payload.agent)
    if (role === null || role === undefined) return resolved
    const agentId = payload.agent.id
    const remember = (route) => {
      requested.set(agentId, { role, provider: route.provider, model: route.model })
      return route
    }
    const d = degraded.get(agentId)
    const active = d !== undefined && d.role === role && d.until > Date.now()
    if (active) {
      const fallback = fallbackFor(role)
      // A live settings edit can remove a fallback while a retry is pending.
      // Do not keep forcing an absent route; let the inherited route run.
      if (fallback === null) {
        degraded.delete(agentId)
        return remember(await withSupportedEffort(resolved))
      }
      d.provider = fallback.provider
      d.model = fallback.model
      d.choice = fallback
      return remember(await withSupportedEffort(applyChoice(resolved, fallback)))
    }

    // The resolved primary is the shipped tier matrix merged with any live
    // Settings override (`ctx.settings.get()` already resolves defaults
    // under the user layer); a role with neither (every role but
    // DoubleChecker/adversary, absent an override) inherits the resolved
    // route untouched.
    const primary = primaryFor(role)
    return remember(await withSupportedEffort(
      primary === null ? resolved : applyChoice(resolved, primary),
    ))
  })

  ctx.on('agent/request-error', async (payload, next) => {
    const action = await next()
    const role = resolveRole(payload.agent)
    if (role === null || role === undefined) return action
    if (!routeFatal(payload.failure)) return action
    // Only act on failures on OUR route: compare against the exact route
    // resolved for this request, not merely the static defaults. This keeps
    // an unrelated picker route out of the fallback lane while correctly
    // covering the shipped matrix and a user override alike.
    const agentId = payload.agent.id
    const route = requested.get(agentId)
    if (route === undefined || route.role !== role || route.provider !== payload.provider) return action
    const cause = failureLabel(payload.failure)
    const d = degraded.get(agentId)
    if (d !== undefined && d.role === role && d.until > Date.now()) {
      // The degraded retry itself failed: never retried again (no loop).
      if (!d.gaveUp && route.model === d.model) {
        d.gaveUp = true
        ctx.logger.warn(
          `rq-model-router: ${describeRoute(role, 'Fallback', d.choice)} also failed (${cause}); `
          + 'not retried, the turn fails',
        )
      }
      return action
    }
    const primary = primaryFor(role)
    if (primary === null || route.model !== primary.model) return action
    const fallback = fallbackFor(role)
    if (fallback === null) {
      const routeKey = `${primary.provider}/${primary.model}`
      if (noFallbackWarned.get(agentId) !== routeKey) {
        noFallbackWarned.set(agentId, routeKey)
        ctx.logger.warn(
          `rq-model-router: ${describeRoute(role, 'Primary', primary)} failed (${cause}) `
          + `and ${role}Fallback is unset: no fallback to degrade to, the turn fails`,
        )
      }
      return action
    }
    degraded.set(agentId, {
      role,
      until: Date.now() + config.degradeTtlMs,
      provider: fallback.provider,
      model: fallback.model,
      choice: fallback,
      gaveUp: false,
    })
    ctx.logger.warn(
      `rq-model-router: ${describeRoute(role, 'Primary', primary)} failed (${cause}); `
      + `degraded to ${fallback.provider}/${fallback.model} `
      + `for ${Math.round(config.degradeTtlMs / 60000)} min`,
    )
    return { kind: 'retry' }
  })
}

export { Config, SettingsSchema, NS, name, apply, inject, DEFAULT_PRIMARY, DEFAULT_FALLBACK }
