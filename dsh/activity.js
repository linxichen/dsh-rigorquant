// RigorQuant team activity — host half.
//
// One live panel for a RigorQuant research lab: which role agents are running,
// what they last did, and a short event feed — served to the browser floater
// (dsh/client.js, `shell.overlay`) as a JSON snapshot over the profile's own
// HTTP route, plus the six role portraits out of docs/figs/.
//
// The panel is PURE MONITORING: every side effect in this module is read-only
// observation of events the core already publishes (session events, agent
// lifecycle, agent/status), and the snapshot is derived freshly per request.
// Nothing here changes routing or model choices — that stays with
// rq-model-router (dsh/index.js), which owns role resolution for the same
// tag.
//
// Routes register lazily on the `webServer` service: headless profiles never
// mount it (the plugin stays an inert monitor there), and under concurrent
// activation it may bind after this row — `internal/service` is the cordis
// binding notification. Both routes are served under /plugins/dsh-rigorquant/,
// the same surface dsh-agent-teams uses for its activity panel.
//
// Design credit: activity-panel concept adapted from dsh-agent-teams
// © NanmiCoder (程序员阿江 / Relakkes), MIT License (see README "The team,
// live").

import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const name = 'rq-activity'
const inject = []
const PRESET_ID = 'rigorquant'

/** Persona tag the preset stamps into every role persona (same as the router). */
const TAG = /\[\[rq:role=([a-z-]+)\]\]/
const ROLES = ['root', 'explorer', 'novel', 'oracle', 'adversary', 'lit-line', 'lit-adversary']

/** role → display name, tool name, and docs/figs portrait file. */
export const ROLE_DEF = {
  root:      { label: 'Orchestrator', tool: 'root persona',            avatar: 'avatar-orchestrator.png' },
  explorer:  { label: 'Explorer',     tool: 'subagent',                avatar: 'avatar-explorer.png' },
  novel:     { label: 'Explorer',     tool: 'subagent_novel',          avatar: 'avatar-explorer.png' },
  oracle:    { label: 'Oracle',       tool: 'subagent_ground_truth',   avatar: 'avatar-oracle.png' },
  adversary: { label: 'Adversary',    tool: 'subagent_adversary',      avatar: 'avatar-adversary.png' },
  'lit-line':     { label: 'Literature', tool: 'subagent_lit_line',    avatar: 'avatar-literature.png' },
  'lit-adversary': { label: 'Literature', tool: 'subagent_lit_adversary', avatar: 'avatar-literature.png' },
  validator: { label: 'Validator',    tool: 'rq_check.py',             avatar: 'avatar-validator.png' },
}

const FEED_AVATAR_FILES = new Set(Object.values(ROLE_DEF).map((def) => def.avatar))
const FIG_DIR = fileURLToPath(new URL('../docs/figs/', import.meta.url))

const FEED_LIMIT = 16
const KEEP_DISPOSED_MS = 60 * 60 * 1000

function tagRole(text) {
  const match = typeof text === 'string' ? TAG.exec(text) : null
  return match !== null && ROLES.includes(match[1]) ? match[1] : null
}

/** First text block of a message, for a feed snippet. */
function textOf(blocks, limit = 90) {
  const list = Array.isArray(blocks) ? blocks : []
  const first = list.find((block) => block && typeof block === 'object'
    && block.type === 'text' && typeof block.text === 'string')
  if (first !== undefined) return first.text.slice(0, limit)
  for (const block of list) {
    if (block && typeof block === 'object' && block.type === 'image') continue
  }
  return ''
}

/** The five-move loop stage suggested by the latest distinctive tool call. */
function stageOf(tools) {
  let stage = 'promise'
  for (const tool of tools) {
    if (/subagent_ground_truth/.test(tool)) stage = 'ground truth'
    else if (/subagent_adversary/.test(tool)) stage = 'attack'
    else if (/subagent/.test(tool)) stage = 'fan out'
    else if (/rq_check/.test(tool)) stage = 'certify'
  }
  return stage
}

function timeOf(event) {
  const t = event?.time
  return typeof t === 'number' ? t : Date.now()
}

function apply(ctx) {
  /** sessionId → live/observed record (agents and sessions share the id). */
  const entries = new Map()
  /** lab root id → lab feed (kept after the lab is disposed, briefly). */
  let routesRegistered = false

  const entryOf = (id) => {
    let entry = entries.get(id)
    if (entry === undefined) {
      entry = {
        id,
        role: null,
        label: null,
        parentId: undefined,
        preset: null,
        status: 'idle',
        disposed: false,
        startedAt: Date.now(),
        lastAt: 0,
        lastKind: null,
        lastText: null,
        toolCount: 0,
        messageCount: 0,
        tools: [],
      }
      entries.set(id, entry)
    }
    return entry
  }

  const touch = (entry, kind, text, at = Date.now()) => {
    entry.lastAt = at
    entry.lastKind = kind
    entry.lastText = text
  }

  const pushFeed = (labId, entry, item) => {
    const lab = entries.get(labId)
    if (lab === undefined) return
    if (!Array.isArray(lab.feed)) lab.feed = []
    lab.feed.push(item)
    if (lab.feed.length > 80) lab.feed.shift()
  }

  const roleOfAgent = (agent) => {
    const header = agent.session?.header ?? {}
    const events = agent.session?.events ?? []
    // A RigorQuant session is created as `standard` and then switched in the
    // picker: the DURABLE header keeps the creation preset forever. The
    // preset that counts is therefore the live composition, then the latest
    // `agent-preset/selected` record in the log, then the creation header.
    let selectedPreset = null
    for (let i = 0; i < Math.min(events.length, 128); i += 1) {
      const event = events[i]
      if (event?.type === 'agent-preset/selected') selectedPreset = event.data?.agentPreset ?? null
    }
    const preset = ctx.get('agentPresets')?.composedPreset(agent.ctx)
      ?? selectedPreset
      ?? header.agentPreset
      ?? null
    if (header.parentSession === undefined && preset === PRESET_ID) {
      return { role: 'root', preset }
    }
    for (let i = 0; i < Math.min(events.length, 64); i += 1) {
      const event = events[i]
      if (event?.type === 'subagent/descriptor') {
        const role = tagRole(event.data?.persona)
        if (role !== null) return { role, preset }
        break
      }
    }
    return { role: null, preset }
  }

  // Seed from live agents: this plugin may mount after a lab is already
  // running (profile boot order, or the web server binding later).
  for (const agent of ctx.get('agents')?.list() ?? []) {
    const { role, preset } = roleOfAgent(agent)
    const entry = entryOf(agent.id)
    entry.role = role
    entry.preset = preset
    entry.parentId = agent.session?.header?.parentSession
  }

  ctx.on('agent/created', ({ agent }) => {
    const { role, preset } = roleOfAgent(agent)
    const entry = entryOf(agent.id)
    entry.role = role
    entry.preset = preset
    entry.parentId = agent.session?.header?.parentSession
  })

  ctx.on('agent/status', ({ agent, status }) => {
    if (status !== 'running' && status !== 'idle') return
    const entry = entries.get(agent.id)
    if (entry !== undefined) entry.status = status
  })

  ctx.on('session/event', (session, event) => {
    const entry = entryOf(session.id)
    const at = timeOf(event)
    const labId = entry.role === 'root' && entry.preset === PRESET_ID
      ? entry.id
      : (entry.parentId ?? null)
    switch (event.type) {
      case 'subagent/descriptor': {
        const role = tagRole(event.data?.persona)
        if (role !== null) entry.role = role
        break
      }
      case 'tool/call': {
        const nameText = String(event.data?.name ?? 'tool')
        entry.toolCount += 1
        let detail = nameText
        try {
          const raw = String(event.data?.arguments ?? '')
          const parsed = JSON.parse(raw)
          const command = typeof parsed === 'object' && parsed !== null
            ? parsed.command ?? parsed.file ?? parsed.pattern ?? parsed.name
            : undefined
          if (typeof command === 'string' && command !== '') detail = `${nameText}: ${command.slice(0, 60)}`
        } catch {
          // Arguments are raw model JSON; the snippet above is enough.
        }
        // The detail travels with the tool name so the stage heuristic can
        // see `bash: … rq_check.py …` too, not only the tool id.
        entry.tools.push(detail)
        if (entry.tools.length > 20) entry.tools.shift()
        touch(entry, 'tool', detail, at)
        if (labId !== null) {
          pushFeed(labId, entry, {
            t: at, sessionId: session.id, role: entry.role, label: entry.role === 'root' ? 'captain' : null,
            kind: 'tool', text: `${entry.role === 'root' ? 'captain' : ROLE_DEF[entry.role]?.label ?? 'agent'} → ${detail}`,
          })
        }
        break
      }
      case 'assistant/message': {
        entry.messageCount += 1
        const snippet = textOf(event.data?.message?.content)
        touch(entry, 'message', snippet || '(message)')
        if (labId !== null) {
          pushFeed(labId, entry, {
            t: at, sessionId: session.id, role: entry.role,
            kind: 'message', text: (entry.role === 'root' ? 'captain' : ROLE_DEF[entry.role]?.label ?? 'agent') + (snippet ? `: ${snippet}` : ''),
          })
        }
        break
      }
      case 'turn/start':
      case 'turn/end':
      case 'step/start':
      case 'step/end':
        touch(entry, 'turn', event.type)
        break
      default:
        if (at > entry.lastAt) touch(entry, 'event', event.type, at)
    }
  })

  ctx.on('session/disposed', (session) => {
    const entry = entries.get(session.id)
    if (entry !== undefined) entry.disposed = true
  })
  ctx.on('agent/disposed', ({ agent }) => {
    const entry = entries.get(agent.id)
    if (entry !== undefined) entry.disposed = true
  })
  ctx.on('agent-preset/selected', (sessionId, agentPreset) => {
    const entry = entries.get(sessionId)
    if (entry === undefined) return
    entry.preset = agentPreset
    // The picker flow creates a session as `standard` and switches: promote a
    // parentless session to captain the moment it becomes a RigorQuant lab,
    // and demote it if the user switches away.
    if (agentPreset === PRESET_ID && entry.parentId === undefined && entry.role !== 'root') {
      entry.role = 'root'
    } else if (agentPreset !== PRESET_ID && entry.role === 'root') {
      entry.role = null
    }
  })

  // Prune disposed entries older than an hour (runs on every snapshot).
  const prune = () => {
    const now = Date.now()
    for (const [id, entry] of entries) {
      if (entry.disposed && now - entry.lastAt > KEEP_DISPOSED_MS) entries.delete(id)
    }
  }

  const memberRow = (entry) => {
    const def = ROLE_DEF[entry.role]
    return {
      sessionId: entry.id,
      role: entry.role,
      label: def?.label ?? entry.role ?? 'agent',
      tool: def?.tool ?? null,
      avatar: def?.avatar ?? null,
      status: entry.status,
      lastKind: entry.lastKind,
      lastText: entry.lastText,
      lastAt: entry.lastAt,
      toolCount: entry.toolCount,
      messageCount: entry.messageCount,
    }
  }

  const snapshot = () => {
    prune()
    const labs = []
    for (const entry of entries.values()) {
      if (entry.role !== 'root' || entry.preset !== PRESET_ID || entry.disposed) continue
      const members = []
      for (const other of entries.values()) {
        if (other.parentId === entry.id && other.role !== null && other.role !== 'root' && !other.disposed) {
          members.push(memberRow(other))
        }
      }
      const feed = (Array.isArray(entry.feed) ? entry.feed : []).slice()
      for (const other of entries.values()) {
        if (other.parentId === entry.id && Array.isArray(other.feed)) feed.push(...other.feed)
      }
      feed.sort((a, b) => b.t - a.t)
      const ordered = feed.slice(0, FEED_LIMIT)
      const working = members.filter((m) => m.status === 'running').length
        + (entry.status === 'running' ? 1 : 0)
      labs.push({
        id: entry.id,
        title: titleOf(entry.id),
        startedAt: entry.startedAt,
        lastAt: entry.lastAt,
        stage: stageOf(entry.tools),
        summary: {
          total: members.length + 1,
          working,
          idle: members.length + 1 - working,
        },
        captain: memberRow(entry),
        members,
        feed: ordered,
      })
    }
    labs.sort((a, b) => b.lastAt - a.lastAt)
    return { labs }
  }

  /** The lab's folded title, if the session-title fold has produced one. */
  const titleOf = (labId) => {
    const session = ctx.get('sessions')?.get(labId)
    if (session === undefined) return null
    const snapshotTitle = ctx.get('sessionTitle')?.get(session)?.title
    return typeof snapshotTitle === 'string' && snapshotTitle !== '' ? snapshotTitle : null
  }

  const registerWebSurface = () => {
    if (routesRegistered) return
    const webServer = ctx.get('webServer')
    if (webServer === undefined) return
    routesRegistered = true
    ctx.effect(() => webServer.register({
      kind: 'exact',
      path: '/plugins/dsh-rigorquant/activity',
      handler: async (req, res) => {
        try {
          const body = JSON.stringify(snapshot())
          res.writeHead(200, {
            'content-type': 'application/json; charset=utf-8',
            'cache-control': 'no-store',
          })
          res.end(body)
        } catch (error) {
          ctx.logger.warn(`rq-activity: snapshot failed: ${String(error)}`)
          res.writeHead(500)
          res.end()
        }
      },
    }), 'rq-activity: snapshot route')
    ctx.effect(() => webServer.register({
      kind: 'prefix',
      path: '/plugins/dsh-rigorquant/avatar',
      handler: async (req, res) => {
        let file = ''
        try {
          file = decodeURIComponent(new URL(req.url ?? '/', 'http://x').pathname.split('/').pop() ?? '')
        } catch {
          res.writeHead(404)
          res.end()
          return
        }
        if (!FEED_AVATAR_FILES.has(file)) {
          res.writeHead(404)
          res.end()
          return
        }
        try {
          const data = readFileSync(join(FIG_DIR, file))
          res.writeHead(200, {
            'content-type': 'image/png',
            'cache-control': 'public, max-age=86400',
          })
          res.end(data)
        } catch {
          ctx.logger.warn(`rq-activity: portrait read failed for ${file}`)
          res.writeHead(404)
          res.end()
        }
      },
    }), 'rq-activity: portrait route')
  }

  registerWebSurface()
  ctx.on('internal/service', (serviceName) => {
    if (serviceName === 'webServer') registerWebSurface()
  })
}

export { name, inject, apply }
