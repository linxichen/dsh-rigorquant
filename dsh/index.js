// RigorQuant model router — host half.
//
// One settings namespace (`rigorquant.models`) maps every RigorQuant role to a
// primary model and a per-role fallback model, each with its own reasoning
// effort. Routing happens in the `agent/request` waterfall: this plugin mounts
// at profile boot, so its listener registers before any agent-scoped model
// selection listener and its rewrite composes last — the per-role choice wins
// over both the chatbox picker (root) and parent inheritance (children).
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
const NS = 'rigorquant.models'
/** Persona tag the preset stamps into every role persona. */
const TAG = /\[\[rq:role=([a-z-]+)\]\]/
/** The persona slot's reserved section name (dsh-system-prompt contract). */
const PERSONA_SECTION = 'deployment:persona'
/** Every routable role, in card order. */
export const ROLES = ['root', 'explorer', 'novel', 'oracle', 'adversary', 'lit-line', 'lit-adversary']
/** Tool row → role, for the repo-consistency test and the docs to stay honest. */
export const ROLE_TOOLS = {
  explorer: 'subagent',
  novel: 'subagent_novel',
  oracle: 'subagent_ground_truth',
  adversary: 'subagent_adversary',
  'lit-line': 'subagent_lit_line',
  'lit-adversary': 'subagent_lit_adversary',
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

const DEFAULT_PRIMARY = { provider: 'deepseek-official', model: 'deepseek-v4-pro', reasoningEffort: 'high' }
const DEFAULT_FALLBACK = { provider: 'deepseek-official', model: 'deepseek-v4-flash', reasoningEffort: 'high' }

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

function isChoice(value) {
  return typeof value === 'object' && value !== null
    && typeof value.provider === 'string' && value.provider !== ''
    && typeof value.model === 'string' && value.model !== ''
}

/** A failure the route itself cannot recover from: no adapter, or HTTP 4xx. */
function routeFatal(failure) {
  if (failure === undefined || failure === null) return false
  if (failure.code === 'NO_ADAPTER') return true
  const status = failure.status
  return typeof status === 'number' && status >= 400 && status < 500
}

function tagRole(text) {
  const match = typeof text === 'string' ? TAG.exec(text) : null
  return match !== null && ROLES.includes(match[1]) ? match[1] : null
}

function apply(ctx, config) {
  // Registers fiber-scoped: stopping this plugin unregisters the namespace.
  ctx.settings.register(NS, SettingsSchema, { base: config.defaults, applies: 'live' })

  /** sessionId → role | null (null = resolved, not routable). */
  const roles = new Map()
  /** sessionId → { role, until, model } while degraded to the fallback. */
  const degraded = new Map()

  const section = () => ctx.settings.get(NS)
  const choiceFor = (role, slot) => {
    const value = section()?.[`${role}${slot}`]
    return isChoice(value) ? value : null
  }

  // Descriptor events arrive after our listener exists for continuable
  // children; the events scan below covers cold-resumed ones.
  ctx.on('session/event', (session, event) => {
    if (event.type === 'subagent/descriptor') {
      const role = tagRole(event.data?.persona)
      if (role !== null) roles.set(session.id, role)
    } else if (event.type === 'assistant/message') {
      const d = degraded.get(session.id)
      const source = event.data?.message?.source
      if (d !== undefined && source !== undefined && source.model === d.model) {
        degraded.delete(session.id)
      }
    }
  })
  ctx.on('session/disposed', (session) => {
    roles.delete(session.id)
    degraded.delete(session.id)
  })
  ctx.on('agent/disposed', ({ agent }) => {
    roles.delete(agent.id)
    degraded.delete(agent.id)
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
    const primary = choiceFor(role, 'Primary')
    if (primary === null) return resolved
    const d = degraded.get(payload.agent.id)
    const active = d !== undefined && d.role === role && d.until > Date.now()
    const fallback = active ? choiceFor(role, 'Fallback') : null
    const choice = fallback ?? primary
    if (fallback !== null) d.model = fallback.model
    return {
      ...resolved,
      provider: choice.provider,
      model: choice.model,
      ...typeof choice.reasoningEffort === 'string' && choice.reasoningEffort !== ''
        ? { reasoningEffort: choice.reasoningEffort }
        : {},
    }
  })

  ctx.on('agent/request-error', async (payload, next) => {
    const action = await next()
    const role = await resolveRole(payload.agent)
    if (role === null || role === undefined) return action
    const primary = choiceFor(role, 'Primary')
    const fallback = choiceFor(role, 'Fallback')
    if (primary === null || fallback === null) return action
    const agentId = payload.agent.id
    const d = degraded.get(agentId)
    if (d !== undefined && d.role === role && d.until > Date.now()) return action
    if (!routeFatal(payload.failure)) return action
    // Only degrade failures on OUR route: the picker's model failing is the
    // picker's business (the retry policy), not a role-routing event.
    if (payload.provider !== primary.provider) return action
    degraded.set(agentId, { role, until: Date.now() + config.degradeTtlMs, model: fallback.model })
    ctx.logger.info(
      `rq-model-router: ${role} primary ${primary.provider}/${primary.model} failed `
      + `(${String(payload.failure?.code ?? payload.failure?.status ?? 'unknown')}); `
      + `degraded to ${fallback.provider}/${fallback.model} for ${Math.round(config.degradeTtlMs / 60000)} min`,
    )
    return { kind: 'retry' }
  })
}

export { Config, SettingsSchema, NS, name, apply, inject }
