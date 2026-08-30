// RigorQuant model router — host half.
//
// One settings namespace (`rigorquant-models`) maps every RigorQuant role to a
// primary model and a per-role fallback model, each with its own reasoning
// effort. DSH 0.1.2's native `agentOptions` supplies the shipped primary for
// fixed-tier roles (oracle/adversary); this router rewrites only an explicit
// user override or an active fallback. The `agent/request` waterfall remains
// the small policy overlay that makes live settings and fallback possible.
//
// Role identity comes from the preset itself: every role persona in
// agent-presets/rigorquant/agent.cordis.yml carries a machine-readable tag
// `[[rq:role=<role>]]`. Continuable children persist the persona in their
// first `subagent/descriptor` event; one-shot (foreground) children carry it
// only in their live system prompt, so the fallback probe assembles the
// child's prompt once and reads the persona section. Children without a tag
// (fork, workflow workers, ralph rounds) and sessions on other presets are
// never touched: they keep the chatbox/parent model exactly as before.
//
// Degrade lane: when the primary route of a routed role fails terminally
// (no adapter, or an HTTP 4xx the route cannot recover from), the listener
// marks that session+role degraded and forces one retry, which re-enters
// agent/request and routes to the role's fallback. A successful assistant
// step on the fallback — or the TTL — restores the primary. A fallback that
// also fails is never retried again by this plugin (no retry loop).
//
// The `root` role applies ONLY to sessions without a parentSession: a spawned
// workflow worker or ralph child also runs under the rigorquant preset, but it
// is not the root and inherits its route.

import z from '@deepseek-ai/schemastery'

const name = 'rq-model-router'
const inject = ['settings']

/** Settings namespace served to the Plugins configuration tab. */
const NS = 'rigorquant-models'
/** Persona tag the preset stamps into every role persona. */
const TAG = /\[\[rq:role=([a-z-]+)\]\]/
/** The persona slot's reserved section name (dsh-system-prompt contract). */
const PERSONA_SECTION = 'deployment:persona'
/** Every routable role, in card order. */
export const ROLES = ['root', 'explorer', 'novel', 'oracle', 'adversary', 'lit-line', 'lit-adversary', 'doc-adversary']
/** Tool row → role, for the repo-consistency test and the docs to stay honest. */
export const ROLE_TOOLS = {
  explorer: 'subagent',
  novel: 'subagent_novel',
  oracle: 'subagent_ground_truth',
  adversary: 'subagent_adversary',
  'lit-line': 'subagent_lit_line',
  'lit-adversary': 'subagent_lit_adversary',
  'doc-adversary': 'subagent_document_adversary',
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

const DEFAULT_PRIMARY = Object.freeze({ provider: 'deepseek-official', model: 'deepseek-v4-pro', reasoningEffort: 'high' })
const DEFAULT_FALLBACK = Object.freeze({ provider: 'deepseek-official', model: 'deepseek-v4-flash', reasoningEffort: 'low' })

// These fixed-tier defaults are also declared on the corresponding native
// tool-subagent rows. Keeping the map here lets the fallback policy recognize
// a failure of the native route without rewriting that route on every request.
const NATIVE_PRIMARY = Object.freeze({
  oracle: DEFAULT_PRIMARY,
  adversary: DEFAULT_PRIMARY,
})

const Config = z.object({
  presetId: z.string().default('rigorquant'),
  degradeTtlMs: z.number().default(600000),
  defaults: SettingsSchema.default({
    // The shipped tier matrix: proof-critical roles on pro with a flash
    // fallback; every other role absent (inherit the session model).
    oraclePrimary: DEFAULT_PRIMARY,
    oracleFallback: DEFAULT_FALLBACK,
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

/** A failure the route itself cannot recover from: no adapter or bad primary.
 *
 * Providers should surface numeric HTTP status, but the official usage-limit
 * response currently exposes its provider code (`1308`) and message while some
 * adapter paths omit `status`. Treat that specific quota exhaustion as terminal
 * too: retrying the same primary cannot help, whereas the role fallback can.
 */
function routeFatal(failure) {
  if (failure === undefined || failure === null) return false
  if (failure.code === 'NO_ADAPTER') return true
  const status = typeof failure.status === 'number'
    ? failure.status
    : typeof failure.status === 'string' ? Number(failure.status) : NaN
  if (Number.isFinite(status) && status >= 400 && status < 500) return true
  return failure.code === '1308' && /usage limit reached/i.test(String(failure.message ?? ''))
}

function tagRole(text) {
  const match = typeof text === 'string' ? TAG.exec(text) : null
  return match !== null && ROLES.includes(match[1]) ? match[1] : null
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

  /** sessionId → role | null (null = resolved, not routable). */
  const roles = new Map()
  /** sessionId → { role, until, provider, model } while degraded. */
  const degraded = new Map()
  /** The exact resolved request route, for error-to-primary attribution. */
  const requested = new Map()

  const section = () => ctx.settings.get(NS)
  const choiceFor = (role, slot) => {
    const value = section()?.[`${role}${slot}`]
    return isChoice(value) ? value : null
  }

  // `settings.get()` is the resolved section, so it cannot distinguish a
  // user override from the composition base. That distinction matters now:
  // the oracle/adversary rows carry their shipped primary through native
  // `agentOptions`; the router must not rewrite those native requests on every
  // step. Keep a detached raw user section and refresh it on every document
  // change, including a reset whose resolved value happens to stay equal to
  // the base.
  let userSection = {}
  const refreshUserSection = () => {
    try {
      const descriptor = ctx.settings.describe().find((entry) => entry.ns === NS)
      userSection = isRecord(descriptor?.user) ? descriptor.user : {}
    } catch {
      // A transient description failure should fail open to native/parent
      // routing, never strand an agent on a stale custom choice.
      userSection = {}
    }
  }
  refreshUserSection()
  ctx.on('settings/document-updated', (namespace) => {
    if (namespace === NS) refreshUserSection()
  })

  const userChoiceFor = (role, slot) => {
    const value = userSection[`${role}${slot}`]
    return isChoice(value) ? value : null
  }
  const nativePrimaryFor = (role) => NATIVE_PRIMARY[role] ?? null
  const fallbackFor = (role) => userChoiceFor(role, 'Fallback') ?? choiceFor(role, 'Fallback')

  // Descriptor events arrive after our listener exists for continuable
  // children; the events scan below covers cold-resumed ones.
  ctx.on('session/event', (session, event) => {
    if (event.type === 'subagent/descriptor') {
      const role = tagRole(event.data?.persona)
      if (role !== null) roles.set(session.id, role)
    } else if (event.type === 'assistant/message') {
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
    roles.delete(session.id)
    degraded.delete(session.id)
    requested.delete(session.id)
  })
  ctx.on('agent/disposed', ({ agent }) => {
    roles.delete(agent.id)
    degraded.delete(agent.id)
    requested.delete(agent.id)
  })
  // A session that switches preset must be re-resolved (either direction).
  ctx.on('agent-preset/selected', (sessionId, agentPreset) => {
    if (agentPreset === config.presetId) {
      if (roles.get(sessionId) === null) roles.delete(sessionId)
    } else {
      roles.delete(sessionId)
    }
  })

  /** One-shot children keep their persona only in the live prompt scope. */
  async function probePersonaRole(agent) {
    try {
      const systemPrompt = agent.ctx.get('systemPrompt')
      if (systemPrompt === undefined) return null
      const assembly = await systemPrompt.assemble({ agent, scope: agent })
      const persona = (assembly.sections ?? []).find((s) => s.name === PERSONA_SECTION)
      return tagRole(persona?.text)
    } catch {
      return null
    }
  }

  async function resolveRole(agent) {
    const id = agent.id
    if (roles.has(id)) return roles.get(id)
    const header = agent.session.header
    // The establishing provider appends exactly one descriptor; it is early,
    // but a continuable child's lineage seed can push it past the head.
    const events = agent.session.events
    for (let i = 0; i < Math.min(events.length, 64); i += 1) {
      const event = events[i]
      if (event.type === 'subagent/descriptor') {
        const role = tagRole(event.data?.persona)
        if (role !== null) {
          roles.set(id, role)
          return role
        }
        break
      }
    }
    // A child (descriptor without a tag, or none yet) is never the root role.
    if (header.parentSession !== undefined) {
      const role = await probePersonaRole(agent)
      roles.set(id, role)
      return role
    }
    const preset = header.agentPreset ?? ctx.get('agentPresets')?.composedPreset(agent.ctx)
    const role = preset === config.presetId ? 'root' : null
    roles.set(id, role)
    return role
  }

  ctx.on('agent/request', async (payload, next) => {
    const resolved = await next()
    const role = await resolveRole(payload.agent)
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
      // Do not keep forcing an absent route; let the native/parent route run.
      if (fallback === null) {
        degraded.delete(agentId)
        return remember(resolved)
      }
      d.provider = fallback.provider
      d.model = fallback.model
      return remember(applyChoice(resolved, fallback))
    }

    // A role's fixed shipped default is supplied by the native tool's
    // `agentOptions`. Only an explicit user primary override belongs in this
    // waterfall; otherwise the resolved native/parent route is authoritative.
    const override = userChoiceFor(role, 'Primary')
    return remember(override === null ? resolved : applyChoice(resolved, override))
  })

  ctx.on('agent/request-error', async (payload, next) => {
    const action = await next()
    const role = await resolveRole(payload.agent)
    if (role === null || role === undefined) return action
    const primary = userChoiceFor(role, 'Primary') ?? nativePrimaryFor(role)
    const fallback = fallbackFor(role)
    if (primary === null || fallback === null) return action
    const agentId = payload.agent.id
    const d = degraded.get(agentId)
    if (d !== undefined && d.role === role && d.until > Date.now()) return action
    if (!routeFatal(payload.failure)) return action
    // Only degrade failures on OUR route: compare against the exact route
    // resolved for this request, not merely the static native-default map.
    // This keeps an unrelated picker route out of the fallback lane while
    // correctly covering native agentOptions and user overrides alike.
    const route = requested.get(agentId)
    if (route === undefined || route.role !== role
      || route.model !== primary.model || route.provider !== payload.provider) return action
    degraded.set(agentId, {
      role,
      until: Date.now() + config.degradeTtlMs,
      provider: fallback.provider,
      model: fallback.model,
    })
    ctx.logger.info(
      `rq-model-router: ${role} primary ${primary.provider}/${primary.model} failed `
      + `(${String(payload.failure?.code ?? payload.failure?.status ?? 'unknown')}); `
      + `degraded to ${fallback.provider}/${fallback.model} for ${Math.round(config.degradeTtlMs / 60000)} min`,
    )
    return { kind: 'retry' }
  })
}

export { Config, SettingsSchema, NS, name, apply, inject }
