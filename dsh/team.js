// RigorQuant team composition — host half.
//
// Applies each teammate's role composition — persona, tool-tier budget, and
// (on the orchestrator, the harness's `role: 'lead'` membership) a runtime
// fact that the guard is armed — purely from the teammate's NAME (e.g.
// `doublechecker-1`), resolved through the harness's native Agent Teams
// service. This is the first Teams tracer bullet
// (docs/architecture.md, Decision 24;
// docs/adr/0001-rigorquant-on-agent-teams.md): the classic
// `[[rq:role=...]]` tag mechanism (dsh/index.js) and the seven classic
// delegation rows (agent-presets/rigorquant/agent.cordis.yml) are UNTOUCHED
// and coexist with this module until a later issue removes them.
//
// The `agentTeams` service is OPTIONAL and reached duck-typed by service
// name (`ctx.get('agentTeams')`) — this module never imports any of the
// five `@deepseek-ai/dsh-experimental-agent-team*` packages. When the
// service is absent (Agent Teams not enabled on the profile) this plugin
// warns once and disarms: no persona, no tool restriction, and no armed
// line for anyone, on any session.
//
// Composition is applied per teammate on every `agent/created` — fresh
// (`startup`), `resume`, `clear`, and `compact` all fire it, and none of
// the four persists prior composition in the agent's descriptor, so every
// firing disposes the previous registration (if any) and reinstalls fresh.
// The persona is registered as a system-prompt SECTION at the harness's own
// `deployment:persona-prefix` slot (dsh/index.js's PERSONA_SECTION reads the
// same name) — the same shadowing contract every preset persona already
// uses. The "RigorQuant team guard: armed" line, in contrast, is a runtime
// CONTEXT (a distinct harness API from a section — a fact about current
// operating state, the same family as the harness's own
// SANDBOX_POLICY/APPROVAL_POLICY/SUBAGENT_DELEGATION context entries), not
// a persona trait, so it is registered via `systemPrompt.context()`, never
// `.section()`.
//
// Tool budgets here are GLOBAL restriction only (`tools.restrict`), applied
// per-teammate via that teammate's own scope (`agent.ctx`). Per-call
// enforcement — hub-and-spoke messaging, roster-blindness, own-task-only
// board access, the bash network-verb denial for web-denied roles, and
// `spawn_teammate` name/fork refusal on the orchestrator — is a later issue
// (`tools.guard`, not `tools.restrict`); this module never registers a
// guard.
//
// A teammate whose name does not parse to a role is skipped silently: no
// composition, no warning. Refusing an unparseable name at spawn time is
// the orchestrator's own job (a later issue's `spawn_teammate` guard), not
// this module's — this module is purely compositional/observational.

import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const name = 'rq-team'
const inject = ['agents', 'tools', 'systemPrompt']
const PRESET_ID = 'rigorquant'

/**
 * Every teammate role this module composes. No `root` entry: the
 * orchestrator's own persona stays in the preset's `@deepseek-ai/dsh-persona`
 * row, unchanged by this module.
 */
export const TEAMMATE_ROLES = ['explorer', 'offgrid', 'doublechecker', 'adversary', 'lit-line', 'lit-adversary', 'doc-adversary']

/** Teammate name convention: `<role>-<suffix>`, e.g. `doublechecker-1`. */
const NAME_PATTERN = new RegExp(`^(${TEAMMATE_ROLES.join('|')})-.+$`)

/**
 * The persona slot's reserved section name (dsh-system-prompt contract) —
 * must equal dsh/index.js's own PERSONA_SECTION constant (pinned by
 * tests/test_repo_consistency.py, since a silent drift would leave a
 * teammate's persona written to a slot nothing reads).
 */
const PERSONA_PREFIX_SECTION = 'deployment:persona-prefix'

/**
 * A distinct context (not section) name/order for the guard-armed line —
 * see the module header for why `.context()`, not `.section()`. Order 118
 * sits between the harness's own APPROVAL_POLICY (115) and
 * SUBAGENT_DELEGATION (120) context orders — a plain literal, since
 * `getContextOrder` only resolves the harness's own centrally allocated
 * names, not this module's.
 */
const GUARD_CONTEXT_NAME = 'rq-team:guard-armed'
const GUARD_CONTEXT_ORDER = 118
const GUARD_TEXT = 'RigorQuant team guard: armed'

const PERSONA_DIR = fileURLToPath(new URL('./personas/', import.meta.url))

/** Every teammate is denied these regardless of tier: the orchestrator-owned
 * task-level goal (Decision 10), todo, and the unattended-contract tools. */
const EVERY_TEAMMATE_DENY = ['create_goal', 'update_goal', 'get_goal', 'todo_write', 'ask_user_question', 'exit_plan_mode']
const WEB_DENY = ['web_search', 'web_fetch']
/** Blind roles: no other agent's results, so no web AND no skill (the
 * rigorquant skill carries the working procedure, not raw derivation). */
const BLIND_ROLES = new Set(['offgrid', 'doublechecker'])
/** Web-denied but not blind: no web, but skill stays (its own procedure or
 * audit checklist lives there). */
const WEB_DENIED_ROLES = new Set(['adversary', 'doc-adversary'])

/** Parse a teammate's role from its name, or `null` when it doesn't parse. */
function roleFromName(teammateName) {
  const match = typeof teammateName === 'string' ? NAME_PATTERN.exec(teammateName) : null
  return match !== null ? match[1] : null
}

function denyListFor(role) {
  if (BLIND_ROLES.has(role)) return [...EVERY_TEAMMATE_DENY, ...WEB_DENY, 'skill']
  if (WEB_DENIED_ROLES.has(role)) return [...EVERY_TEAMMATE_DENY, ...WEB_DENY]
  return [...EVERY_TEAMMATE_DENY]
}

/** Read every role's persona file once, at mount. A missing/unreadable file
 * warns and leaves that role uncomposed (defensive; should never happen in a
 * shipped tree — pinned by tests/test_repo_consistency.py). */
function loadPersonas(ctx) {
  const personas = new Map()
  for (const role of TEAMMATE_ROLES) {
    try {
      personas.set(role, readFileSync(join(PERSONA_DIR, `${role}.md`), 'utf8'))
    } catch (error) {
      ctx.logger.warn(`rq-team: failed to load the ${role} persona: ${String(error)}`)
    }
  }
  return personas
}

function apply(ctx, config = {}) {
  const presetId = typeof config.presetId === 'string' ? config.presetId : PRESET_ID
  const personas = loadPersonas(ctx)
  let warnedAbsent = false
  const installed = new Map() // agent -> disposer

  const warnAbsentOnce = () => {
    if (warnedAbsent) return
    warnedAbsent = true
    ctx.logger.warn(
      'rq-team: the agentTeams service is absent — RigorQuant team guard disarmed ' +
      '(no persona, no tool budget, no armed line for anyone)'
    )
  }

  const disposeFor = (agent) => {
    const dispose = installed.get(agent)
    if (dispose !== undefined) {
      dispose()
      installed.delete(agent)
    }
  }

  const maybeInstall = (agent) => {
    const teams = ctx.get('agentTeams')
    if (teams === undefined) {
      warnAbsentOnce()
      return
    }
    const membership = teams.tryMembership(agent)
    if (membership === undefined) return
    // agent/created fires on every source (startup/resume/clear/compact) and
    // none persists prior composition, so every firing disposes then
    // reinstalls fresh rather than skipping a previously-seen agent.
    disposeFor(agent)
    const inRigorQuant = ctx.get('agentPresets')?.composedPreset(agent.ctx) === presetId
    if (!inRigorQuant) return
    const systemPrompt = agent.ctx.get('systemPrompt')
    if (systemPrompt === undefined) return
    if (membership.role === 'lead') {
      installed.set(agent, systemPrompt.context({ name: GUARD_CONTEXT_NAME, order: GUARD_CONTEXT_ORDER, text: GUARD_TEXT }))
      return
    }
    const role = roleFromName(membership.name)
    if (role === null) return // unparseable name: skip silently (see module header)
    const persona = personas.get(role)
    if (persona === undefined) return
    const order = systemPrompt.getSectionOrder?.('DEPLOYMENT_PERSONA_PREFIX') ?? 0
    const disposePersona = systemPrompt.section({ name: PERSONA_PREFIX_SECTION, order, text: persona })
    const tools = agent.ctx.get('tools')
    const disposeTools = tools !== undefined ? tools.restrict({ deny: denyListFor(role) }) : () => {}
    installed.set(agent, () => {
      disposePersona()
      disposeTools()
    })
  }

  // Belt-and-suspenders: warn even if no agent is ever created this boot.
  if (ctx.get('agentTeams') === undefined) warnAbsentOnce()

  for (const agent of ctx.get('agents')?.list() ?? []) maybeInstall(agent)
  ctx.on('agent/created', ({ agent }) => maybeInstall(agent))
  ctx.on('agent/disposed', ({ agent }) => disposeFor(agent))
}

export { name, inject, apply, roleFromName }
