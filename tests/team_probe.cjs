// Exercises dsh/team.js the way a host process would, without one.
//
// Mounts the plugin against a stub ctx (agentTeams membership, agents
// backfill, agentPresets) and a per-agent stub scope (systemPrompt's
// section()/context()/getSectionOrder(), tools' restrict()), then drives
// three scenarios: agentTeams present (a lead + several teammates of
// varying tiers, an unparseable name, a non-RigorQuant teammate), agentTeams
// absent (warning, no armed context), and a resume-sourced re-creation
// (proves composition is reapplied, not skipped as a no-op). Prints one
// JSON verdict.
const { pathToFileURL } = require('node:url')

/** One fake teammate/lead: its own agent.ctx scope recording every
 * section()/context()/restrict() call made against it. */
function makeAgent(id, preset) {
  const sections = []
  const contexts = []
  const restricts = []
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
  return { agent, recorder: { sections, contexts, restricts, disposedSections } }
}

function pick(recorder) {
  return { sections: recorder.sections, contexts: recorder.contexts, restricts: recorder.restricts }
}

async function runPresentScenario(mod) {
  const listeners = new Map()
  const membershipByAgent = new Map()
  const agentsBackfill = []
  const teamsService = { tryMembership: (agent) => membershipByAgent.get(agent) }
  const ctx = {
    logger: { warn: () => {} },
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

  return {
    mountError,
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

async function main() {
  const [, , modulePath] = process.argv
  const mod = await import(pathToFileURL(modulePath).href)

  const { mountError, present } = await runPresentScenario(mod)
  const absent = await runAbsentScenario(mod)
  const resume = await runResumeScenario(mod)

  process.stdout.write(JSON.stringify({ mountError, present, absent, resume }))
}

main().catch((error) => {
  process.stderr.write(String((error && error.stack) || error))
  process.exit(1)
})
