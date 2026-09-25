// Exercises dsh/team.js the way a host process would, without one.
//
// Mounts the plugin against a stub ctx (agentTeams membership, agents
// backfill, agentPresets) and a per-agent stub scope (systemPrompt's
// section()/context()/getSectionOrder(), tools' restrict()/guard()), then
// drives these scenarios: agentTeams present (a lead + several teammates of
// varying tiers, an unparseable name, a non-RigorQuant teammate), agentTeams
// absent (warning, no armed context), a resume-sourced re-creation (proves
// composition is reapplied, not skipped as a no-op), and a guard drive that
// fakes a call through every per-call rule (topology by guard: hub-and-spoke
// messaging, roster/board blindness, own-task-only board access, the bash
// network-verb denial for web-denied roles, and the orchestrator's
// spawn_teammate name/fork refusal), plus a late preset switch and an
// unload/reload of the plugin over live agents (the Plugins-page toggle).
// Prints one JSON verdict.
const { pathToFileURL } = require('node:url')

/** One fake teammate/lead: its own agent.ctx scope recording every
 * section()/context()/restrict() call made against it. */
function makeAgent(id, preset) {
  const sections = []
  const contexts = []
  const restricts = []
  const guards = []
  const disposedSections = []
  const systemPromptStub = {
    section: (spec) => {
      sections.push(spec)
      return () => { disposedSections.push(spec.name) }
    },
    context: (spec) => {
      contexts.push(spec)
      return () => {}
    },
    getSectionOrder: (n) => (n === 'DEPLOYMENT_PERSONA_PREFIX' ? 0 : undefined),
  }
  const toolsStub = {
    restrict: (filter) => {
      restricts.push(filter)
      return () => {}
    },
    guard: (fn) => {
      guards.push(fn)
      return () => {}
    },
  }
  const agent = {
    id,
    ctx: {
      __preset: preset,
      get: (name) => {
        if (name === 'systemPrompt') return systemPromptStub
        if (name === 'tools') return toolsStub
        return undefined
      },
    },
  }
  return { agent, recorder: { sections, contexts, restricts, guards, disposedSections } }
}

/** A point-in-time copy — `recorder`'s arrays are live and keep mutating, so
 * a caller comparing two points in time (e.g. before/after a re-trigger)
 * must snapshot each side, not alias the same underlying arrays. */
function pick(recorder) {
  return {
    sections: recorder.sections.slice(),
    contexts: recorder.contexts.slice(),
    restricts: recorder.restricts.slice(),
    guardCount: recorder.guards.length,
  }
}

/** Drive one fake call through a registered guard, returning the denial
 * reason or `null` when the guard allows it (JSON has no `undefined`). */
function drive(guardFn, name, args) {
  if (guardFn === undefined) return 'NO_GUARD_REGISTERED'
  const reason = guardFn({ name, arguments: args })
  return reason === undefined ? null : reason
}

// Fixture roster the Lead's reuse guard reads live statuses from: a settled
// fresh-per-brief teammate (idle or inactive) must never get a new brief,
// while a running one may be answered (a blocking question mid-turn), and
// the reused roles may be briefed again once settled.
const ROSTER = [
  { name: 'lead', role: 'lead', status: 'running' },
  { name: 'explorer-1', role: 'teammate', status: 'idle' },
  { name: 'offgrid-1', role: 'teammate', status: 'inactive' },
  { name: 'doublechecker-1', role: 'teammate', status: 'running' },
  { name: 'adversary-1', role: 'teammate', status: 'idle' },
  { name: 'lit-line-1', role: 'teammate', status: 'inactive' },
]

// Fixture task board for the ownership guard: 'own-task' is owned by
// doublechecker-1, 'foreign-task' by explorer-1, 'unowned-task' has no owner
// yet (still claimable), and any other id is unknown (getTask throws, the
// way the real service does for a bad id).
const TASKS_BY_ID = new Map([
  ['own-task', { id: 'own-task', ownerName: 'doublechecker-1' }],
  ['foreign-task', { id: 'foreign-task', ownerName: 'explorer-1' }],
  ['unowned-task', { id: 'unowned-task', ownerName: undefined }],
])

async function runPresentScenario(mod) {
  const listeners = new Map()
  const membershipByAgent = new Map()
  const agentsBackfill = []
  const teamsService = {
    tryMembership: (agent) => membershipByAgent.get(agent),
    getTask: (_agent, taskId) => {
      const task = TASKS_BY_ID.get(taskId)
      if (task === undefined) throw new Error(`team-task-not-found: ${taskId}`)
      return task
    },
    listMembers: () => ROSTER,
  }
  const ctx = {
    logger: { warn: () => {} },
    effect: () => {},
    on: (name, handler) => {
      if (!listeners.has(name)) listeners.set(name, [])
      listeners.get(name).push(handler)
    },
    get: (name) => {
      if (name === 'agents') return { list: () => agentsBackfill }
      if (name === 'agentPresets') return { composedPreset: (agentCtx) => agentCtx.__preset }
      if (name === 'agentTeams') return teamsService
      return undefined
    },
  }
  const emit = (name, ...args) => { for (const h of listeners.get(name) ?? []) h(...args) }

  const lead = makeAgent('lead-1', 'rigorquant')
  membershipByAgent.set(lead.agent, { role: 'lead', name: 'lead' })
  const doublechecker1 = makeAgent('dc-1', 'rigorquant')
  membershipByAgent.set(doublechecker1.agent, { role: 'teammate', name: 'doublechecker-1' })
  const explorer1 = makeAgent('ex-1', 'rigorquant')
  membershipByAgent.set(explorer1.agent, { role: 'teammate', name: 'explorer-1' })
  const adversary1 = makeAgent('ad-1', 'rigorquant')
  membershipByAgent.set(adversary1.agent, { role: 'teammate', name: 'adversary-1' })
  const unparseable = makeAgent('scout-1', 'rigorquant')
  membershipByAgent.set(unparseable.agent, { role: 'teammate', name: 'scout-1' })
  const nonRigorQuant = makeAgent('dc-2', 'standard')
  membershipByAgent.set(nonRigorQuant.agent, { role: 'teammate', name: 'doublechecker-2' })

  // The lead is already live when the plugin mounts — exercises the backfill
  // loop, not just agent/created.
  agentsBackfill.push(lead.agent)

  let mountError = null
  try {
    mod.apply(ctx)
    emit('agent/created', { agent: doublechecker1.agent, source: 'startup' })
    emit('agent/created', { agent: explorer1.agent, source: 'startup' })
    emit('agent/created', { agent: adversary1.agent, source: 'startup' })
    emit('agent/created', { agent: unparseable.agent, source: 'startup' })
    emit('agent/created', { agent: nonRigorQuant.agent, source: 'startup' })
  } catch (error) {
    mountError = `${error.name}: ${error.message}`
  }

  const doublechecker1Guard = doublechecker1.recorder.guards[0]
  const explorer1Guard = explorer1.recorder.guards[0]
  const adversary1Guard = adversary1.recorder.guards[0]
  const leadGuard = lead.recorder.guards[0]

  const guardChecks = {
    // Hub-and-spoke: a sibling target is refused, the Lead is allowed.
    siblingMessageDenied: drive(doublechecker1Guard, 'send_message', { target: 'explorer-1' }),
    leadMessageAllowed: drive(doublechecker1Guard, 'send_message', { target: 'lead' }),
    // Roster/board blindness: unconditional for every teammate.
    listAgentsDenied: drive(doublechecker1Guard, 'list_agents', {}),
    taskListDenied: drive(doublechecker1Guard, 'team_task_list', {}),
    // Own-task-only board access, read live through the (fake) service.
    ownTaskGetAllowed: drive(doublechecker1Guard, 'team_task_get', { task_id: 'own-task' }),
    foreignTaskGetDenied: drive(doublechecker1Guard, 'team_task_get', { task_id: 'foreign-task' }),
    unownedTaskClaimAllowed: drive(doublechecker1Guard, 'team_task_update', { task_id: 'unowned-task', action: 'claim' }),
    foreignTaskUpdateDenied: drive(doublechecker1Guard, 'team_task_update', { task_id: 'foreign-task', action: 'complete' }),
    // Bash network verbs: denied for a web-denied role (blind and
    // web-denied-only both), allowed for an open role (explorer).
    blindBashCurlDenied: drive(doublechecker1Guard, 'bash', { command: 'curl https://example.com' }),
    webDeniedBashWgetDenied: drive(adversary1Guard, 'bash', { command: 'wget https://example.com/file' }),
    openRoleBashCurlAllowed: drive(explorer1Guard, 'bash', { command: 'curl https://example.com' }),
    blindBashPlainAllowed: drive(doublechecker1Guard, 'bash', { command: 'ls -la' }),
    // The orchestrator's spawn_teammate guard: bad name and fork are both
    // refused; a well-formed fresh spawn is allowed.
    spawnBadNameDenied: drive(leadGuard, 'spawn_teammate', { name: 'scout-1', context: 'fresh' }),
    spawnForkDenied: drive(leadGuard, 'spawn_teammate', { name: 'doublechecker-9', context: 'fork' }),
    spawnFreshRoleAllowed: drive(leadGuard, 'spawn_teammate', { name: 'doublechecker-9', context: 'fresh' }),
    // The orchestrator's reuse guard: a settled fresh-per-brief teammate is
    // never briefed again; a running one may be answered; reused roles may be
    // briefed once settled; a name the roster does not hold is left to the
    // tool's own error.
    briefSettledExplorerDenied: drive(leadGuard, 'send_message', { target: 'explorer-1', message: 'erratum' }),
    briefInactiveOffgridDenied: drive(leadGuard, 'send_message', { target: 'offgrid-1', message: 'erratum' }),
    answerRunningDoublecheckerAllowed: drive(leadGuard, 'send_message', { target: 'doublechecker-1', message: 'answer' }),
    briefSettledAdversaryAllowed: drive(leadGuard, 'send_message', { target: 'adversary-1', message: 'new brief' }),
    briefInactiveLitLineAllowed: drive(leadGuard, 'send_message', { target: 'lit-line-1', message: 'new brief' }),
    unknownTargetLeftToTheTool: drive(leadGuard, 'send_message', { target: 'doublechecker-99', message: 'x' }),
  }

  return {
    mountError,
    guardChecks,
    present: {
      lead: pick(lead.recorder),
      doublechecker1: pick(doublechecker1.recorder),
      explorer1: pick(explorer1.recorder),
      adversary1: pick(adversary1.recorder),
      unparseableName: pick(unparseable.recorder),
      nonRigorQuantTeammate: pick(nonRigorQuant.recorder),
    },
  }
}

async function runAbsentScenario(mod) {
  const listeners = new Map()
  const warnings = []
  const ctx = {
    logger: { warn: (message) => warnings.push(message) },
    effect: () => {},
    on: (name, handler) => {
      if (!listeners.has(name)) listeners.set(name, [])
      listeners.get(name).push(handler)
    },
    get: (name) => {
      if (name === 'agents') return { list: () => [] }
      if (name === 'agentPresets') return { composedPreset: () => 'rigorquant' }
      // agentTeams intentionally absent
      return undefined
    },
  }
  const emit = (name, ...args) => { for (const h of listeners.get(name) ?? []) h(...args) }

  const lead = makeAgent('lead-absent', 'rigorquant')
  mod.apply(ctx)
  emit('agent/created', { agent: lead.agent, source: 'startup' })

  return { warnings, leadContexts: lead.recorder.contexts }
}

async function runResumeScenario(mod) {
  const listeners = new Map()
  const membershipByAgent = new Map()
  const teamsService = { tryMembership: (agent) => membershipByAgent.get(agent) }
  const ctx = {
    logger: { warn: () => {} },
    effect: () => {},
    on: (name, handler) => {
      if (!listeners.has(name)) listeners.set(name, [])
      listeners.get(name).push(handler)
    },
    get: (name) => {
      if (name === 'agents') return { list: () => [] }
      if (name === 'agentPresets') return { composedPreset: (agentCtx) => agentCtx.__preset }
      if (name === 'agentTeams') return teamsService
      return undefined
    },
  }
  const emit = (name, ...args) => { for (const h of listeners.get(name) ?? []) h(...args) }

  const dc = makeAgent('dc-resume', 'rigorquant')
  membershipByAgent.set(dc.agent, { role: 'teammate', name: 'doublechecker-1' })

  mod.apply(ctx)
  emit('agent/created', { agent: dc.agent, source: 'startup' })
  const firstSections = dc.recorder.sections.slice()
  emit('agent/created', { agent: dc.agent, source: 'resume' })
  const disposedAfterResume = dc.recorder.disposedSections.slice()
  const secondSections = dc.recorder.sections.slice(firstSections.length)

  return { firstSections, disposedAfterResume, secondSections }
}

/**
 * A session created under a non-rigorquant preset, later switched to
 * rigorquant via `AgentPresets.select()` — found live (docs/upgrade-0.1.6.md
 * §3.11): `agent/created` already ran (and skipped, composedPreset still
 * reporting the old preset) before the switch, so without a second trigger
 * the Lead never gets composed for the rest of its life. Simulates the
 * harness's own ordering: `recompose()` lands on `agent.ctx` BEFORE
 * `agent-preset/selected` is announced (mutate `__preset` first, emit
 * second), matching `packages/preset/agent-presets/src/index.ts`'s `swap()`.
 */
async function runLatePresetSelectionScenario(mod) {
  const listeners = new Map()
  const membershipByAgent = new Map()
  const agentsById = new Map()
  const teamsService = { tryMembership: (agent) => membershipByAgent.get(agent) }
  const ctx = {
    logger: { warn: () => {} },
    effect: () => {},
    on: (name, handler) => {
      if (!listeners.has(name)) listeners.set(name, [])
      listeners.get(name).push(handler)
    },
    get: (name) => {
      if (name === 'agents') return { list: () => [], get: (id) => agentsById.get(id) }
      if (name === 'agentPresets') return { composedPreset: (agentCtx) => agentCtx.__preset }
      if (name === 'agentTeams') return teamsService
      return undefined
    },
  }
  const emit = (name, ...args) => { for (const h of listeners.get(name) ?? []) h(...args) }

  const lead = makeAgent('lead-late', 'standard')
  membershipByAgent.set(lead.agent, { role: 'lead', name: 'lead' })
  agentsById.set(lead.agent.id, lead.agent)

  mod.apply(ctx)
  emit('agent/created', { agent: lead.agent, source: 'startup' })
  const beforeSwitch = pick(lead.recorder)

  lead.agent.ctx.__preset = 'rigorquant'
  emit('agent-preset/selected', lead.agent.id, 'rigorquant')
  const afterSwitch = pick(lead.recorder)

  return { beforeSwitch, afterSwitch }
}

/** One agent scope that keeps its registrations LIVE and refuses a second
 * registration of a live name — the harness's `NamedEntries` contract
 * ("prompt context \"…\" is already registered in this scope"). Guards and
 * restrictions are anonymous, so they are only counted. */
function makeScopedAgent(id, preset) {
  const live = { sections: new Set(), contexts: new Set(), restricts: 0, guards: 0 }
  const named = (set, kind) => (spec) => {
    if (set.has(spec.name)) throw new Error(`prompt ${kind} "${spec.name}" is already registered in this scope`)
    set.add(spec.name)
    return () => { set.delete(spec.name) }
  }
  const counted = (key) => () => {
    live[key] += 1
    return () => { live[key] -= 1 }
  }
  const services = {
    systemPrompt: {
      section: named(live.sections, 'section'),
      context: named(live.contexts, 'context'),
      getSectionOrder: () => 0,
    },
    tools: { restrict: counted('restricts'), guard: counted('guards') },
  }
  const agent = { id, ctx: { __preset: preset, get: (name) => services[name] } }
  const snapshot = () => ({
    sections: [...live.sections], contexts: [...live.contexts], restricts: live.restricts, guards: live.guards,
  })
  return { agent, snapshot }
}

/**
 * The Plugins page toggles the rq-team row off and on while a RigorQuant
 * session is live. Unloading the plugin disposes only what its OWN fiber
 * owns (its listeners and effects); every persona, context, restriction and
 * guard it registered went through `agent.ctx`, so they belong to the
 * agent's scope and outlive the plugin unless the plugin disposes them
 * itself. Found live (docs/upgrade-0.1.6.md §3.15): the Lead stayed armed
 * with rq-team off, and turning it back on could not take effect because the
 * backfill re-registered the still-live armed context by the same name.
 */
async function runUnloadScenario(mod) {
  const lead = makeScopedAgent('lead-toggle', 'rigorquant')
  const dc = makeScopedAgent('dc-toggle', 'rigorquant')
  const membershipByAgent = new Map([
    [lead.agent, { role: 'lead', name: 'lead' }],
    [dc.agent, { role: 'teammate', name: 'doublechecker-1' }],
  ])
  const teamsService = { tryMembership: (agent) => membershipByAgent.get(agent) }

  // One plugin fiber: its listeners, and the effects it registered, which
  // cordis disposes in reverse order when the fiber unloads.
  const mount = () => {
    const disposers = []
    const ctx = {
      logger: { warn: () => {} },
      on: () => {},
      effect: (execute) => { disposers.push(execute()) },
      get: (name) => {
        if (name === 'agents') return { list: () => [lead.agent, dc.agent], get: () => undefined }
        if (name === 'agentPresets') return { composedPreset: (agentCtx) => agentCtx.__preset }
        if (name === 'agentTeams') return teamsService
        return undefined
      },
    }
    let error = null
    try {
      mod.apply(ctx)
    } catch (e) {
      error = String((e && e.message) || e)
    }
    const unload = () => { for (const dispose of disposers.reverse()) dispose() }
    return { error, unload }
  }
  const both = () => ({ lead: lead.snapshot(), doublechecker: dc.snapshot() })

  const first = mount()
  const afterMount = both()
  first.unload()
  const afterUnload = both()
  const second = mount()
  const afterRemount = both()

  return { firstError: first.error, afterMount, afterUnload, remountError: second.error, afterRemount }
}

async function main() {
  const [, , modulePath] = process.argv
  const mod = await import(pathToFileURL(modulePath).href)

  const { mountError, present, guardChecks } = await runPresentScenario(mod)
  const absent = await runAbsentScenario(mod)
  const resume = await runResumeScenario(mod)
  const latePresetSelection = await runLatePresetSelectionScenario(mod)
  const unload = await runUnloadScenario(mod)

  process.stdout.write(JSON.stringify({ mountError, present, guardChecks, absent, resume, latePresetSelection, unload }))
}

main().catch((error) => {
  process.stderr.write(String((error && error.stack) || error))
  process.exit(1)
})
