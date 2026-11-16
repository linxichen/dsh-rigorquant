// Exercises dsh/team.js the way a host process would, without one.
//
// Mounts the plugin against a stub ctx (agentTeams arming/membership, the
// subagents identity service, agents backfill, agentPresets) and a per-agent
// stub scope (systemPrompt's section()/context()/getSectionOrder(), tools'
// restrict()/guard()), then drives these scenarios: agentTeams present (a
// lead + several teammates of varying tiers, an unparseable name, a
// non-RigorQuant teammate, a non-RigorQuant ROOT that must never be armed), a
// service that reports the selection still off (no armed context), agentTeams
// absent (warning, no armed context), a resume-sourced re-creation (proves
// composition is reapplied, not skipped as a no-op), and a guard drive that
// fakes a call through every per-call rule (topology by guard: hub-and-spoke
// messaging, roster/board blindness, own-task-only board access, the bash
// network-verb denial for web-denied roles, and the orchestrator's
// subagent/subagent_fork refusal), plus a late preset switch and an
// unload/reload of the plugin over live agents (the Plugins-page toggle),
// and the escalation lane: the Lead's `rq_escalate` tool mounting a stub
// MCP client into the caller or a named teammate. Prints one JSON verdict.
const { pathToFileURL } = require('node:url')

/** One fake teammate/lead: its own agent.ctx scope recording every
 * section()/context()/restrict() call made against it. `status` is what the
 * harness's own roster projection reads (`running` vs `inactive`). */
function makeAgent(id, preset, { status = 'running' } = {}) {
  const sections = []
  const contexts = []
  const restricts = []
  const guards = []
  const registered = []
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
    register: (definition) => {
      registered.push(definition)
      return () => {}
    },
  }
  const agent = {
    id,
    status,
    ctx: {
      __preset: preset,
      get: (name) => {
        if (name === 'systemPrompt') return systemPromptStub
        if (name === 'tools') return toolsStub
        return undefined
      },
    },
  }
  return { agent, recorder: { sections, contexts, restricts, guards, registered, disposedSections } }
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
    tools: recorder.registered.map((definition) => definition.name),
  }
}

/** The 0.2.2 subagent identity service: `rootOf` and `namesOf`, keyed by the
 * exact live Agent. A member absent from either map throws, the way the real
 * service does for an agent outside a live tree. */
function makeSubagents({ roots, names }) {
  return {
    rootOf: (agent) => {
      const root = roots.get(agent)
      if (root === undefined) throw new Error('agent has no active runtime owner')
      return root
    },
    namesOf: (agent) => {
      const entry = names.get(agent)
      if (entry === undefined) throw new Error('agent is not a member of this subagent tree')
      return entry
    },
  }
}

/** The Team service surface the plugin uses: the per-root selection plus the
 * live task board. Every `setEnabled` call is recorded, including the signal. */
function makeTeams({ tasks = new Map(), roster = [] } = {}) {
  const enabled = new Set()
  const calls = []
  return {
    calls,
    service: {
      setEnabled: async (agent, on, signal) => {
        calls.push({ agent: agent.id, enabled: on, signal: signal === undefined ? null : String(signal) })
        if (on) enabled.add(agent)
        else enabled.delete(agent)
      },
      isEnabled: (agent) => enabled.has(agent),
      getTask: (_agent, taskId) => {
        const task = tasks.get(taskId)
        if (task === undefined) throw new Error(`team-task-not-found: ${taskId}`)
        return task
      },
      listMembers: () => roster,
    },
  }
}

/** Drive one fake call through a registered guard, returning the denial
 * reason or `null` when the guard allows it (JSON has no `undefined`). */
function drive(guardFn, name, args) {
  if (guardFn === undefined) return 'NO_GUARD_REGISTERED'
  const reason = guardFn({ name, arguments: args })
  return reason === undefined ? null : reason
}

/** Let the async arming path (setEnabled/isEnabled) settle. */
const flush = () => new Promise((resolve) => setImmediate(resolve))

// Fixture roster statuses the Lead's reuse guard reads live: a settled
// fresh-per-brief teammate (idle or inactive) must never get a new brief,
// while a running one may be answered (a blocking question mid-turn), and
// the reused roles may be briefed again once settled.
const ROSTER_STATUS = {
  'lead': 'running',
  'explorer-1': 'idle',
  'offgrid-1': 'inactive',
  'doublechecker-1': 'running',
  'adversary-1': 'idle',
  'lit-line-1': 'inactive',
}

// Fixture task board for the ownership guard: 'own-task' is owned by
// doublechecker-1, 'foreign-task' by explorer-1, 'unowned-task' has no owner
// yet (still claimable), and any other id is unknown (getTask throws, the
// way the real service does for a bad id).
const TASKS_BY_ID = new Map([
  ['own-task', { id: 'own-task', ownerName: 'doublechecker-1' }],
  ['foreign-task', { id: 'foreign-task', ownerName: 'explorer-1' }],
  ['unowned-task', { id: 'unowned-task', ownerName: undefined }],
])

const ARM_SIGNAL = 'signal:agent-created'

async function runPresentScenario(mod) {
  const listeners = new Map()
  const roots = new Map()
  const names = new Map()
  const allAgents = []
  const teams = makeTeams({ tasks: TASKS_BY_ID })
  const subagents = makeSubagents({ roots, names })
  const ctx = {
    logger: { warn: () => {} },
    effect: () => {},
    on: (name, handler) => {
      if (!listeners.has(name)) listeners.set(name, [])
      listeners.get(name).push(handler)
    },
    get: (name) => {
      if (name === 'agents') return { list: () => allAgents }
      if (name === 'agentPresets') return { composedPreset: (agentCtx) => agentCtx.__preset }
      if (name === 'agentTeams') return teams.service
      if (name === 'subagents') return subagents
      return undefined
    },
  }
  // The emit awaits listener promises, the way cordis awaits an async
  // `agent/created` handler before creation settles.
  const emit = async (name, ...args) => {
    for (const h of listeners.get(name) ?? []) await h(...args)
  }

  /** One tree member: register its identity. Whether it is already live at
   * mount is decided by the caller — an agent already in `agents.list()` is
   * backfilled, not re-created. */
  const member = (id, preset, name, status = 'running') => {
    const made = makeAgent(id, preset, { status })
    names.set(made.agent, { self: name, parent: name === 'lead' ? undefined : 'lead' })
    return made
  }

  const lead = member('lead-1', 'rigorquant', 'lead')
  roots.set(lead.agent, lead.agent)
  const doublechecker1 = member('dc-1', 'rigorquant', 'doublechecker-1', 'running')
  roots.set(doublechecker1.agent, lead.agent)
  const explorer1 = member('ex-1', 'rigorquant', 'explorer-1', 'idle')
  roots.set(explorer1.agent, lead.agent)
  const adversary1 = member('ad-1', 'rigorquant', 'adversary-1', 'idle')
  roots.set(adversary1.agent, lead.agent)
  const unparseable = member('scout-1', 'rigorquant', 'scout-1')
  roots.set(unparseable.agent, lead.agent)
  const nonRigorQuant = member('dc-2', 'standard', 'doublechecker-2')
  roots.set(nonRigorQuant.agent, lead.agent)
  // Roster-only fixtures: the guard reads their names/statuses through the
  // same agents.list()/namesOf pair, but they never fire agent/created.
  const offgrid1 = member('og-1', 'rigorquant', 'offgrid-1', 'inactive')
  roots.set(offgrid1.agent, lead.agent)
  const litLine1 = member('lit-1', 'rigorquant', 'lit-line-1', 'inactive')
  roots.set(litLine1.agent, lead.agent)
  // A non-RigorQuant ROOT: Team must never be armed for it.
  const standardRoot = makeAgent('std-root', 'standard')
  names.set(standardRoot.agent, { self: 'lead' })
  roots.set(standardRoot.agent, standardRoot.agent)
  // A second RigorQuant root created AFTER mount (added to the live list
  // below): proves the signal from agent/created reaches setEnabled and that
  // arming is per root Session.
  const secondRoot = makeAgent('lead-2', 'rigorquant')
  names.set(secondRoot.agent, { self: 'lead' })
  roots.set(secondRoot.agent, secondRoot.agent)

  // Already live at mount: the Lead and the two roster-only fixtures.
  allAgents.push(lead.agent, offgrid1.agent, litLine1.agent)

  let mountError = null
  try {
    mod.apply(ctx)
    await flush() // the live-lead backfill arms asynchronously
    // Created after mount, through agent/created.
    allAgents.push(
      doublechecker1.agent, explorer1.agent, adversary1.agent, unparseable.agent,
      nonRigorQuant.agent, standardRoot.agent, secondRoot.agent,
    )
    await emit('agent/created', { agent: doublechecker1.agent, source: 'startup', signal: ARM_SIGNAL })
    await emit('agent/created', { agent: explorer1.agent, source: 'startup', signal: ARM_SIGNAL })
    await emit('agent/created', { agent: adversary1.agent, source: 'startup', signal: ARM_SIGNAL })
    await emit('agent/created', { agent: unparseable.agent, source: 'startup', signal: ARM_SIGNAL })
    await emit('agent/created', { agent: nonRigorQuant.agent, source: 'startup', signal: ARM_SIGNAL })
    await emit('agent/created', { agent: standardRoot.agent, source: 'startup', signal: ARM_SIGNAL })
    await emit('agent/created', { agent: secondRoot.agent, source: 'startup', signal: ARM_SIGNAL })
  } catch (error) {
    mountError = `${error.name}: ${error.message}`
  }

  const doublechecker1Guard = doublechecker1.recorder.guards[0]
  const explorer1Guard = explorer1.recorder.guards[0]
  const adversary1Guard = adversary1.recorder.guards[0]
  const leadGuard = lead.recorder.guards[0]

  const guardChecks = {
    // Hub-and-spoke: a sibling target is refused, the Lead (by name or by
    // its Session id) is allowed.
    siblingMessageDenied: drive(doublechecker1Guard, 'send_message', { agent: 'explorer-1', message: 'x' }),
    leadMessageAllowed: drive(doublechecker1Guard, 'send_message', { agent: 'lead', message: 'x' }),
    leadSessionIdMessageAllowed: drive(doublechecker1Guard, 'send_message', { agent: 'lead-1', message: 'x' }),
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
    // The orchestrator's delegation guard: bad name and a fork are both
    // refused; a well-formed fresh spawn is allowed.
    spawnBadNameDenied: drive(leadGuard, 'subagent', { name: 'scout-1', description: 'x', prompt: 'p' }),
    spawnForkDenied: drive(leadGuard, 'subagent_fork', { name: 'doublechecker-9', description: 'x', prompt: 'p' }),
    spawnFreshRoleAllowed: drive(leadGuard, 'subagent', { name: 'doublechecker-9', description: 'x', prompt: 'p' }),
    // The orchestrator's reuse guard: a settled fresh-per-brief teammate is
    // never briefed again; a running one may be answered; reused roles may be
    // briefed once settled; a name the roster does not hold is left to the
    // tool's own error.
    briefSettledExplorerDenied: drive(leadGuard, 'send_message', { agent: 'explorer-1', message: 'erratum' }),
    briefInactiveOffgridDenied: drive(leadGuard, 'send_message', { agent: 'offgrid-1', message: 'erratum' }),
    answerRunningDoublecheckerAllowed: drive(leadGuard, 'send_message', { agent: 'doublechecker-1', message: 'answer' }),
    briefSettledAdversaryAllowed: drive(leadGuard, 'send_message', { agent: 'adversary-1', message: 'new brief' }),
    briefInactiveLitLineAllowed: drive(leadGuard, 'send_message', { agent: 'lit-line-1', message: 'new brief' }),
    unknownTargetLeftToTheTool: drive(leadGuard, 'send_message', { agent: 'doublechecker-99', message: 'x' }),
    // The escalation lane is the orchestrator's to grant: a teammate that
    // can see the Lead's scoped tool is still refused at the call.
    teammateEscalateDenied: drive(doublechecker1Guard, 'rq_escalate', {}),
    teammateEscalateOtherDenied: drive(explorer1Guard, 'rq_escalate', { teammate: 'explorer-1' }),
  }

  return {
    mountError,
    guardChecks,
    arming: {
      setEnabledCalls: teams.calls,
      standardRootContexts: standardRoot.recorder.contexts,
      teammateContexts: doublechecker1.recorder.contexts,
      nonRigorQuantTeammateSetEnabled: teams.calls.filter((call) => call.agent === 'dc-2'),
    },
    present: {
      lead: pick(lead.recorder),
      doublechecker1: pick(doublechecker1.recorder),
      explorer1: pick(explorer1.recorder),
      adversary1: pick(adversary1.recorder),
      unparseableName: pick(unparseable.recorder),
      nonRigorQuantTeammate: pick(nonRigorQuant.recorder),
      standardRoot: pick(standardRoot.recorder),
      secondRoot: pick(secondRoot.recorder),
    },
  }
}

/** The service is present but reports the selection still off: no armed
 * context, no persona, no guard — a guard the Team tools do not honor is
 * worse than none. */
async function runUnarmedServiceScenario(mod) {
  const listeners = new Map()
  const roots = new Map()
  const names = new Map()
  const lead = makeAgent('lead-unarmed', 'rigorquant')
  roots.set(lead.agent, lead.agent)
  names.set(lead.agent, { self: 'lead' })
  const teamsService = {
    setEnabled: async () => {}, // accepted but never takes effect
    isEnabled: () => false,
  }
  const ctx = {
    logger: { warn: () => {} },
    effect: () => {},
    on: (name, handler) => {
      if (!listeners.has(name)) listeners.set(name, [])
      listeners.get(name).push(handler)
    },
    get: (name) => {
      if (name === 'agents') return { list: () => [] }
      if (name === 'agentPresets') return { composedPreset: () => 'rigorquant' }
      if (name === 'agentTeams') return teamsService
      if (name === 'subagents') return makeSubagents({ roots, names })
      return undefined
    },
  }
  const emit = async (name, ...args) => {
    for (const h of listeners.get(name) ?? []) await h(...args)
  }
  mod.apply(ctx)
  await emit('agent/created', { agent: lead.agent, source: 'startup' })
  return { lead: pick(lead.recorder) }
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
  const emit = async (name, ...args) => {
    for (const h of listeners.get(name) ?? []) await h(...args)
  }

  const lead = makeAgent('lead-absent', 'rigorquant')
  mod.apply(ctx)
  await emit('agent/created', { agent: lead.agent, source: 'startup' })

  return { warnings, leadContexts: lead.recorder.contexts }
}

async function runResumeScenario(mod) {
  const listeners = new Map()
  const roots = new Map()
  const names = new Map()
  const dc = makeAgent('dc-resume', 'rigorquant')
  const lead = makeAgent('lead-resume', 'rigorquant')
  roots.set(dc.agent, lead.agent)
  roots.set(lead.agent, lead.agent)
  names.set(lead.agent, { self: 'lead' })
  names.set(dc.agent, { self: 'doublechecker-1', parent: 'lead' })
  const teams = makeTeams()
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
      if (name === 'agentTeams') return teams.service
      if (name === 'subagents') return makeSubagents({ roots, names })
      return undefined
    },
  }
  const emit = async (name, ...args) => {
    for (const h of listeners.get(name) ?? []) await h(...args)
  }

  mod.apply(ctx)
  await emit('agent/created', { agent: dc.agent, source: 'startup' })
  const firstSections = dc.recorder.sections.slice()
  await emit('agent/created', { agent: dc.agent, source: 'resume' })
  const disposedAfterResume = dc.recorder.disposedSections.slice()
  const secondSections = dc.recorder.sections.slice(firstSections.length)

  return { firstSections, disposedAfterResume, secondSections }
}

/**
 * A session created under a non-rigorquant preset, later switched to
 * rigorquant via `AgentPresets.select()` — found live (Decision 24):
 * `agent/created` already ran (and skipped, composedPreset still
 * reporting the old preset) before the switch, so without a second trigger
 * the Lead never gets composed for the rest of its life. Simulates the
 * harness's own ordering: `recompose()` lands on `agent.ctx` BEFORE
 * `agent-preset/selected` is announced (mutate `__preset` first, emit
 * second), matching `packages/preset/agent-presets/src/index.ts`'s `swap()`.
 */
async function runLatePresetSelectionScenario(mod) {
  const listeners = new Map()
  const roots = new Map()
  const names = new Map()
  const agentsById = new Map()
  const lead = makeAgent('lead-late', 'standard')
  roots.set(lead.agent, lead.agent)
  names.set(lead.agent, { self: 'lead' })
  agentsById.set(lead.agent.id, lead.agent)
  const teams = makeTeams()
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
      if (name === 'agentTeams') return teams.service
      if (name === 'subagents') return makeSubagents({ roots, names })
      return undefined
    },
  }
  const emit = async (name, ...args) => {
    for (const h of listeners.get(name) ?? []) await h(...args)
  }

  mod.apply(ctx)
  await emit('agent/created', { agent: lead.agent, source: 'startup' })
  const beforeSwitch = pick(lead.recorder)

  lead.agent.ctx.__preset = 'rigorquant'
  await emit('agent-preset/selected', lead.agent.id, 'rigorquant')
  const afterSwitch = pick(lead.recorder)

  return { beforeSwitch, afterSwitch, setEnabledCalls: teams.calls }
}

/** One agent scope that keeps its registrations LIVE and refuses a second
 * registration of a live name — the harness's `NamedEntries` contract
 * ("prompt context \"…\" is already registered in this scope"). Guards and
 * restrictions are anonymous, so they are only counted. */
function makeScopedAgent(id, preset) {
  const live = { sections: new Set(), contexts: new Set(), tools: new Set(), restricts: 0, guards: 0 }
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
    tools: {
      restrict: counted('restricts'),
      guard: counted('guards'),
      register: (definition) => {
        live.tools.add(definition.name)
        return () => { live.tools.delete(definition.name) }
      },
    },
  }
  const agent = { id, status: 'running', ctx: { __preset: preset, get: (name) => services[name] } }
  const snapshot = () => ({
    sections: [...live.sections], contexts: [...live.contexts], tools: [...live.tools],
    restricts: live.restricts, guards: live.guards,
  })
  return { agent, snapshot }
}

/**
 * The Plugins page toggles the rq-team row off and on while a RigorQuant
 * session is live. Unloading the plugin disposes only what its OWN fiber
 * owns (its listeners and effects); every persona, context, restriction and
 * guard it registered went through `agent.ctx`, so they belong to the
 * agent's scope and outlive the plugin unless the plugin disposes them
 * itself. Found live (Decision 24): the Lead stayed armed
 * with rq-team off, and turning it back on could not take effect because the
 * backfill re-registered the still-live armed context by the same name.
 */
async function runUnloadScenario(mod) {
  const lead = makeScopedAgent('lead-toggle', 'rigorquant')
  const dc = makeScopedAgent('dc-toggle', 'rigorquant')
  const roots = new Map([[lead.agent, lead.agent], [dc.agent, lead.agent]])
  const names = new Map([
    [lead.agent, { self: 'lead' }],
    [dc.agent, { self: 'doublechecker-1', parent: 'lead' }],
  ])
  const teams = makeTeams()

  // One plugin fiber: its listeners, and the effects it registered, which
  // cordis disposes in reverse order when the fiber unloads.
  const mount = async () => {
    const disposers = []
    const ctx = {
      logger: { warn: () => {} },
      on: () => {},
      effect: (execute) => { disposers.push(execute()) },
      get: (name) => {
        if (name === 'agents') return { list: () => [lead.agent, dc.agent], get: () => undefined }
        if (name === 'agentPresets') return { composedPreset: (agentCtx) => agentCtx.__preset }
        if (name === 'agentTeams') return teams.service
        if (name === 'subagents') return makeSubagents({ roots, names })
        return undefined
      },
    }
    let error = null
    try {
      mod.apply(ctx)
      await flush()
    } catch (e) {
      error = String((e && e.message) || e)
    }
    const unload = () => { for (const dispose of disposers.reverse()) dispose() }
    return { error, unload }
  }
  const both = () => ({ lead: lead.snapshot(), doublechecker: dc.snapshot() })

  const first = await mount()
  const afterMount = both()
  first.unload()
  const afterUnload = both()
  const second = await mount()
  const afterRemount = both()

  return { firstError: first.error, afterMount, afterUnload, remountError: second.error, afterRemount }
}

/** An agent whose scope can mount a plugin: `agent.ctx.plugin()` records
 * the call and returns a thenable fiber, the way cordis does, that settles
 * after the plugin's startup and rejects with its startup error. A named
 * `failing` agent rejects every mount (a jacobian that cannot start). */
function makeMountableAgent(id, preset, { failing = false } = {}) {
  const base = makeAgent(id, preset)
  const mounts = []
  let disposed = 0
  base.agent.ctx.plugin = (plugin, config) => {
    mounts.push({ plugin: plugin.name, config })
    const settled = failing
      ? Promise.reject(new Error('spawn npx ENOENT'))
      : Promise.resolve()
    return {
      dispose: () => { disposed += 1 },
      then: (onFulfilled, onRejected) => settled.then(onFulfilled, onRejected),
    }
  }
  base.agent.session = { header: { cwd: `/work/${id}` } }
  return { ...base, mounts, disposedCount: () => disposed }
}

/**
 * `rq_escalate` on a live Lead: mount into the caller, into a named live
 * teammate, idempotently, and fail clearly for an unknown or unloaded
 * teammate and for a lane that cannot start.
 */
async function runEscalationScenario(mod) {
  const listeners = new Map()
  const roots = new Map()
  const names = new Map()
  const agentsById = new Map()
  const imports = []
  const stubClient = { name: 'mcp-client', Config: (config) => ({ ...config, validated: true }) }
  const lead = makeMountableAgent('lead-esc', 'rigorquant')
  const dc = makeMountableAgent('dc-esc', 'rigorquant')
  const broken = makeMountableAgent('ad-esc', 'rigorquant', { failing: true })
  const roster = [
    { id: 'lead-esc', name: 'lead', role: 'lead', status: 'running' },
    { id: 'dc-esc', name: 'doublechecker-1', role: 'teammate', status: 'running' },
    { id: 'ad-esc', name: 'adversary-1', role: 'teammate', status: 'running' },
    { id: 'og-esc', name: 'offgrid-1', role: 'teammate', status: 'inactive' },
  ]
  roots.set(lead.agent, lead.agent)
  roots.set(dc.agent, lead.agent)
  roots.set(broken.agent, lead.agent)
  names.set(lead.agent, { self: 'lead' })
  names.set(dc.agent, { self: 'doublechecker-1', parent: 'lead' })
  names.set(broken.agent, { self: 'adversary-1', parent: 'lead' })
  for (const member of [lead, dc, broken]) agentsById.set(member.agent.id, member.agent)
  const teams = makeTeams({ roster })
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
      if (name === 'agentTeams') return teams.service
      if (name === 'subagents') return makeSubagents({ roots, names })
      if (name === 'loader') {
        return {
          import: async (spec) => { imports.push(spec); return { default: stubClient } },
          unwrapExports: (exports) => exports.default ?? exports,
        }
      }
      return undefined
    },
  }
  const emit = async (name, ...args) => {
    for (const h of listeners.get(name) ?? []) await h(...args)
  }

  mod.apply(ctx)
  for (const member of [lead, dc, broken]) {
    await emit('agent/created', { agent: member.agent, source: 'startup' })
  }

  const tool = lead.recorder.registered.find((definition) => definition.name === 'rq_escalate')
  const call = async (args, caller = lead.agent) => {
    try {
      const value = await tool.execute(args, { agent: caller, arguments: args })
      return { value, rendered: tool.output.render(args, value) }
    } catch (error) {
      return { error: String((error && error.message) || error) }
    }
  }

  const intoCaller = await call({})
  const intoCallerAgain = await call({})
  const intoTeammate = await call({ teammate: 'doublechecker-1' })
  const intoTeammateAgain = await call({ teammate: 'doublechecker-1' })
  const unknownTeammate = await call({ teammate: 'doublechecker-9' })
  const unloadedTeammate = await call({ teammate: 'offgrid-1' })
  const failedConnect = await call({ teammate: 'adversary-1' })
  const failedConnectRetried = await call({ teammate: 'adversary-1' })

  // The Plugins page toggles rq-team off and on: the lane stays mounted on
  // the agent, so the reloaded plugin's tool must still see it.
  mod.apply(ctx)
  await emit('agent/created', { agent: lead.agent, source: 'startup' })
  const reloadedTool = lead.recorder.registered.filter((d) => d.name === 'rq_escalate').at(-1)
  let afterReload
  try {
    afterReload = { value: await reloadedTool.execute({}, { agent: lead.agent, arguments: {} }) }
  } catch (error) {
    afterReload = { error: String((error && error.message) || error) }
  }

  return {
    toolRegisteredOnLead: tool !== undefined,
    parameters: tool?.parameters ?? null,
    teammateTools: [dc, broken].map((member) => member.recorder.registered.map((d) => d.name)),
    imports,
    intoCaller,
    intoCallerAgain,
    intoTeammate,
    intoTeammateAgain,
    unknownTeammate,
    unloadedTeammate,
    failedConnect,
    failedConnectRetried,
    afterReload,
    mounts: { lead: lead.mounts, doublechecker: dc.mounts, adversary: broken.mounts },
    failedFibersDisposed: broken.disposedCount(),
  }
}

async function main() {
  const [, , modulePath] = process.argv
  const mod = await import(pathToFileURL(modulePath).href)

  const { mountError, present, guardChecks, arming } = await runPresentScenario(mod)
  const unarmedService = await runUnarmedServiceScenario(mod)
  const absent = await runAbsentScenario(mod)
  const resume = await runResumeScenario(mod)
  const latePresetSelection = await runLatePresetSelectionScenario(mod)
  const unload = await runUnloadScenario(mod)
  const escalation = await runEscalationScenario(mod)

  process.stdout.write(JSON.stringify({
    mountError, present, guardChecks, arming, unarmedService, absent, resume,
    latePresetSelection, unload, escalation,
  }))
}

main().catch((error) => {
  process.stderr.write(String((error && error.stack) || error))
  process.exit(1)
})
