// Exercises dsh/activity.js the way a host process would, without one.
//
// Mounts the plugin against a stub ctx (events, webServer, agents, sessions),
// drives the RigorQuant lifecycle events through it, then calls the two
// registered HTTP handlers the way the web shell would. Prints one JSON
// verdict with: the snapshot body (labs/members/feed/stage/summary), the
// portrait route responses, and any mount error.
const { pathToFileURL } = require('node:url')

async function main() {
  const [, , modulePath] = process.argv
  const mod = await import(pathToFileURL(modulePath).href)

  // ---- stub ctx ----------------------------------------------------------
  const listeners = new Map()
  const effects = []
  const routes = []
  const ctx = {
    logger: { warn: () => {} },
    on: (name, handler) => {
      if (!listeners.has(name)) listeners.set(name, [])
      listeners.get(name).push(handler)
    },
    effect: (fn, label) => {
      effects.push({ fn, label })
      if (typeof fn === 'function') fn()
      return () => {}
    },
    get: (name) => {
      if (name === 'webServer') {
        return {
          register: (route) => {
            routes.push(route)
            return () => {}
          },
        }
      }
      if (name === 'agents') {
        return {
          list: () => seedAgents,
          get: (id) => seedAgents.find((agent) => agent.id === id),
        }
      }
      if (name === 'sessions') return { get: (id) => ({ id }) }
      if (name === 'sessionTitle') return { get: () => ({ title: 'Boundary cases of the VaR estimator' }) }
      if (name === 'agentPresets') return { composedPreset: () => undefined }
      return undefined
    },
  }

  const emit = (name, ...args) => {
    for (const handler of listeners.get(name) ?? []) handler(...args)
  }

  // ---- the scenario ------------------------------------------------------
  // Cold start: the lab and one explorer are already live when the plugin
  // mounts (seedAgents), then more events arrive while the floater polls.
  const rootAgent = {
    id: 'lab-1',
    ctx: {},
    status: 'running',
    session: {
      id: 'lab-1',
      header: { agentPreset: 'rigorquant', parentSession: undefined },
      events: [],
    },
  }
  const explorerAgent = {
    id: 'child-1',
    ctx: {},
    status: 'running',
    session: {
      id: 'child-1',
      header: { agentPreset: 'rigorquant', parentSession: 'lab-1' },
      events: [{
        type: 'subagent/descriptor',
        data: { persona: 'you are the explorer [[rq:role=explorer]]' },
      }],
    },
  }
  // A second session created as `standard` that switches after the plugin
  // mounts — must be promoted by the agent-preset/selected listener.
  const laterLabAgent = {
    id: 'lab-2',
    ctx: {},
    session: {
      id: 'lab-2',
      header: { agentPreset: 'standard', parentSession: undefined },
      events: [],
    },
  }
  // The one-shot subagent (opaque label, no persona) — tests the queue role
  // fallback, then the running→disposed lifecycle (lights up, then stays in
  // the roster as idle while the live-team summary counts only live agents).
  const oneShotChild = {
    id: 'child-shot-1',
    ctx: {},
    session: {
      id: 'child-shot-1',
      header: { agentPreset: 'rigorquant', parentSession: 'lab-2' },
      events: [{ type: 'subagent/descriptor', data: { label: 'Draft paper audience spec' } }],
    },
  }
  const seedAgents = [rootAgent, explorerAgent, laterLabAgent]

  let mountError = null
  try {
    mod.apply(ctx)
    emit('agent/status', { agent: rootAgent, status: 'running' })
    emit('agent/status', { agent: explorerAgent, status: 'running' })
    emit('agent-preset/selected', 'lab-2', 'rigorquant')
    emit('session/event', rootAgent.session, {
      type: 'assistant/message', time: 1000,
      data: { message: { content: [{ type: 'text', text: 'Split the question into sub-problems.' }] } },
    })
    emit('session/event', explorerAgent.session, {
      type: 'tool/call', time: 2000,
      data: { name: 'bash', arguments: '{"command":"ls studies/"}' },
    })
    emit('session/event', rootAgent.session, {
      type: 'tool/call', time: 3000,
      data: { name: 'subagent_double_checker', arguments: '{}' },
    })
    // One-shot subagent under the promoted lab: the captain's subagent_lit_line
    // tool call queues the role, then the child arrives with only an opaque
    // label (no persona tag) — the queue must attach 'lit-line'.
    emit('session/event', laterLabAgent.session, {
      type: 'tool/call', time: 2500,
      data: { name: 'subagent_lit_line', arguments: '{}' },
    })
    emit('agent/created', { agent: oneShotChild })
    emit('agent/status', { agent: oneShotChild, status: 'running' })
    // A second one-shot subagent that NEVER surfaces a running agent status:
    // its role (doublechecker, from the descriptor label) must still light up because
    // it emitted session activity just now (the RECENT_ACTIVE_MS fallback).
    const shot2 = {
      id: 'child-shot-2',
      ctx: {},
      session: {
        id: 'child-shot-2',
        header: { agentPreset: 'rigorquant', parentSession: 'lab-2' },
        events: [{ type: 'subagent/descriptor', data: { label: 'GT-A symbolic derivation' } }],
      },
    }
    emit('agent/created', { agent: shot2 })
    emit('session/event', shot2.session, {
      type: 'tool/call', time: Date.now() - 1000,
      data: { name: 'bash', arguments: '{}' },
    })
  } catch (error) {
    mountError = `${error.name}: ${error.message}`
  }

  const verdict = { mountError, routes: routes.map((r) => `${r.kind}:${r.path}`) }

  // ---- drive the HTTP surface -------------------------------------------
  const activityRoute = routes.find((r) => r.path === '/plugins/dsh-rigorquant/activity')
  const portraitRoute = routes.find((r) => r.path === '/plugins/dsh-rigorquant/avatar')

  const call = async (route, url) => {
    const captured = { code: null, headers: null, body: null }
    const res = {
      writeHead: (code, headers) => { captured.code = code; captured.headers = headers },
      end: (body) => { captured.body = body },
    }
    await route.handler({ url }, res)
    return captured
  }

  if (activityRoute !== undefined) {
    const { code, body } = await call(activityRoute, '/plugins/dsh-rigorquant/activity')
    verdict.snapshotCode = code
    verdict.snapshot = JSON.parse(body)
  }
  // Dispose the one-shot subagent, then re-read: it must stay in the roster as
  // idle (so the hub map keeps the role) while the live-team summary
  // counts only the still-present agents.
  emit('agent/disposed', { agent: oneShotChild })
  if (activityRoute !== undefined) {
    const { body } = await call(activityRoute, '/plugins/dsh-rigorquant/activity')
    verdict.snapshotDisposed = JSON.parse(body)
  }
  if (portraitRoute !== undefined) {
    const ok = await call(portraitRoute, '/plugins/dsh-rigorquant/avatar/avatar-orchestrator.png')
    verdict.portraitOk = { code: ok.code, type: ok.headers?.['content-type'], isPng: Buffer.isBuffer(ok.body) }
    const bad = await call(portraitRoute, '/plugins/dsh-rigorquant/avatar/../../etc/passwd')
    verdict.portraitBad = { code: bad.code }
  }

  process.stdout.write(JSON.stringify(verdict))
}

main().catch((error) => {
  process.stderr.write(String(error && error.stack || error))
  process.exit(1)
})
