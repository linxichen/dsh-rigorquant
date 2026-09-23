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
// `deployment:persona-prefix` slot — the same shadowing contract every
// preset persona already uses. The "RigorQuant team guard: armed" line, in
// contrast, is a runtime CONTEXT (a distinct harness API from a section — a
// fact about current operating state, the same family as the harness's own
// SANDBOX_POLICY/APPROVAL_POLICY/SUBAGENT_DELEGATION context entries), not
// a persona trait, so it is registered via `systemPrompt.context()`, never
// `.section()`.
//
// Tool budgets here are GLOBAL restriction only (`tools.restrict`), applied
// per-teammate via that teammate's own scope (`agent.ctx`). Per-call
// enforcement — hub-and-spoke messaging, roster-blindness, own-task-only
// board access, the bash network-verb denial for web-denied roles, and
// `spawn_teammate` name/fork refusal on the orchestrator — is `tools.guard`
// (docs/architecture.md, Decision 24; the ADR's "topology by guard"),
// registered per-agent alongside the restriction above, never globally: a
// guard registered through `agent.ctx` applies only to that agent's calls.
//
// A teammate whose name does not parse to a role is skipped silently: no
// composition, no warning, no guard. Refusing an unparseable name at spawn
// time is the orchestrator's own `spawn_teammate` guard below — by the time
// an unparseable-named teammate exists, the Lead's guard already should have
// refused creating it; this module's own skip is defense in depth, not the
// enforcement point.
//
// A brand-new top-level session is NOT necessarily composed as `rigorquant`
// at the moment its own `agent/created` fires: the harness creates a session
// under a default preset first, and a later UI/API `AgentPresets.select()`
// call reparents it (`agent.ctx.get('agentPresets').composedPreset(...)`)
// as a SEPARATE step, recorded as its own `agent-preset/selected` session
// event and re-broadcast as the plain cordis event of the same name — found
// live (docs/upgrade-0.1.6.md §3.11) when a session created under "Standard
// mode" then switched to RigorQuant in the picker left its Lead with no
// "team guard: armed" line and no `spawn_teammate` guard for its entire
// life, because `agent/created` had already run (and skipped, seeing the
// still-default preset) before the switch. A spawned TEAMMATE does not have
// this gap — it "joins its parent's composition in the creation window,
// before `agent/created`" (confirmed live: the same session's teammate was
// correctly composed) — so only the Lead path needs a second trigger:
// listening for `agent-preset/selected` and re-running the same
// dispose-then-reinstall `maybeInstall` once the recompose has already
// landed on `agent.ctx` (the harness composes before appending the event,
// so the composed-preset read below is never stale at that point).

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
 * the same `deployment:persona-prefix` slot every preset persona registers
 * under (pinned by tests/test_repo_consistency.py, since a silent drift
 * would leave a teammate's persona written to a slot nothing reads).
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

// ── topology by guard (Decision 24; docs/adr/0001-rigorquant-on-agent-teams.md) ──
//
// `tools.restrict` (above) masks the GLOBAL catalog and cannot reach the
// scoped Team tools `tool-agent-team` registers directly in each member's own
// scope (`send_message`, `list_agents`, `team_task_list`, `team_task_get`,
// `team_task_update`, `spawn_teammate`, …) — a restriction only filters what
// a scope inherits from the global layer. `tools.guard` is the one API that
// reaches a scoped registration: a monotonic per-call check, registered
// through `agent.ctx` so it applies only to that one agent.

/** Hub-and-spoke's one legal `send_message` target for every teammate — the
 * literal name the Team tool's own prompt teaches callers to use for the
 * Lead (`tool-agent-team`'s `send_message` description: "Team member name,
 * or lead"). No other string is ever a legal teammate-to-teammate target. */
const LEAD_TARGET = 'lead'

/** Every teammate is roster- and board-blind outright (ADR "Consequences"):
 * these two scoped tools are denied regardless of role or tier. */
const ROSTER_BLIND_TOOLS = new Set(['list_agents', 'team_task_list'])

/** The two scoped board tools whose target task must be the caller's own —
 * unowned (not yet claimed) is allowed, so `team_task_update(action:
 * 'claim')` still works; owned by someone else is refused. */
const OWN_TASK_TOOLS = new Set(['team_task_get', 'team_task_update'])

/** Network verbs the bash-curl residual hole denies at the call for
 * web-denied roles (blind roles plus Adversary/Document adversary) — the
 * exact verb set docs/upgrade-0.1.6.md §4.3 and issue #10 name. */
const BASH_NETWORK_VERBS = /\b(curl|wget|pip\s+install|uv\s+(sync|add|pip))\b/

/** Web-denied union: every role without web access (CONTEXT.md's "Web-denied
 * role" — the blind roles plus the Adversary and Document adversary). */
const WEB_DENIED_UNION = new Set([...BLIND_ROLES, ...WEB_DENIED_ROLES])

/** A guard sees `execution.arguments` as `unknown` (it is whatever the model
 * sent, validated only by the tool's own schema); normalize to a plain
 * object so both guards below can read fields without repeating the guard. */
function argsOf(execution) {
  return (execution.arguments && typeof execution.arguments === 'object') ? execution.arguments : {}
}

/**
 * A teammate's guard: hub-and-spoke messaging, roster/board blindness,
 * own-task-only board access, and (for web-denied roles) the bash
 * network-verb denial. Ownership is read live through the service
 * (`teams.getTask`), never cached, so a CAS race cannot stale-allow.
 * @param agent - the exact live teammate this guard is scoped to.
 * @param membership - that teammate's resolved Team identity (`name`).
 * @param role - the parsed role, deciding whether bash network verbs apply.
 * @param teams - the `agentTeams` service, for the live ownership read.
 */
function teammateGuard(agent, membership, role, teams) {
  const webDenied = WEB_DENIED_UNION.has(role)
  return (execution) => {
    const args = argsOf(execution)
    if (execution.name === 'send_message') {
      if (args.target === LEAD_TARGET) return undefined
      return `rq-team: hub-and-spoke — ${membership.name} may message only the Lead, not '${args.target}'`
    }
    if (ROSTER_BLIND_TOOLS.has(execution.name)) {
      return `rq-team: ${membership.name} is roster-blind — ${execution.name} is denied`
    }
    if (OWN_TASK_TOOLS.has(execution.name)) {
      const taskId = args.task_id
      if (typeof taskId !== 'string') return undefined // malformed call: let the tool's own schema validation report it
      let task
      try {
        task = teams.getTask(agent, taskId)
      } catch {
        return undefined // unknown/inaccessible task: let the real call surface the authoritative error
      }
      if (task !== undefined && task.ownerName !== undefined && task.ownerName !== membership.name) {
        return `rq-team: ${membership.name} does not own task '${taskId}' (owned by ${task.ownerName})`
      }
      return undefined
    }
    if (webDenied && execution.name === 'bash') {
      const command = typeof args.command === 'string' ? args.command : ''
      if (BASH_NETWORK_VERBS.test(command)) {
        return `rq-team: ${membership.name} is web-denied — network command refused: ${command}`
      }
    }
    return undefined
  }
}

/**
 * The orchestrator's guard: `spawn_teammate` refuses a name that does not
 * parse to `<role>-<n>` (an unnamed teammate would run the orchestrator
 * persona with the full catalog — Decision 8's exact forbidden failure) and
 * refuses `context: 'fork'` (fork inherits the parent conversation).
 */
function leadGuard() {
  return (execution) => {
    if (execution.name !== 'spawn_teammate') return undefined
    const args = argsOf(execution)
    if (roleFromName(args.name) === null) {
      return `rq-team: spawn_teammate refused — '${args.name}' does not parse to <role>-<n>`
    }
    if (args.context === 'fork') {
      return "rq-team: spawn_teammate refused — context 'fork' inherits the Lead conversation"
    }
    return undefined
  }
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
    const tools = agent.ctx.get('tools')
    if (membership.role === 'lead') {
      const disposeContext = systemPrompt.context({ name: GUARD_CONTEXT_NAME, order: GUARD_CONTEXT_ORDER, text: GUARD_TEXT })
      const disposeGuard = tools !== undefined ? tools.guard(leadGuard()) : () => {}
      installed.set(agent, () => {
        disposeContext()
        disposeGuard()
      })
      return
    }
    const role = roleFromName(membership.name)
    if (role === null) return // unparseable name: skip silently (see module header)
    const persona = personas.get(role)
    if (persona === undefined) return
    const order = systemPrompt.getSectionOrder?.('DEPLOYMENT_PERSONA_PREFIX') ?? 0
    const disposePersona = systemPrompt.section({ name: PERSONA_PREFIX_SECTION, order, text: persona })
    const disposeTools = tools !== undefined ? tools.restrict({ deny: denyListFor(role) }) : () => {}
    const disposeGuard = tools !== undefined ? tools.guard(teammateGuard(agent, membership, role, teams)) : () => {}
    installed.set(agent, () => {
      disposePersona()
      disposeTools()
      disposeGuard()
    })
  }

  // Belt-and-suspenders: warn even if no agent is ever created this boot.
  if (ctx.get('agentTeams') === undefined) warnAbsentOnce()

  for (const agent of ctx.get('agents')?.list() ?? []) maybeInstall(agent)
  ctx.on('agent/created', ({ agent }) => maybeInstall(agent))
  ctx.on('agent/disposed', ({ agent }) => disposeFor(agent))
  // A session composed as rigorquant only AFTER its own agent/created already
  // ran (see module header) needs a second trigger, once the recompose that
  // event announces has actually landed. `sessionId` and `agent.id` are the
  // same identity; a session with no live agent (already gone, or one this
  // profile never tracked) is silently skipped — nothing to (re)install.
  ctx.on('agent-preset/selected', (sessionId) => {
    const agent = ctx.get('agents')?.get(sessionId)
    if (agent !== undefined) maybeInstall(agent)
  })
}

export { name, inject, apply, roleFromName }
