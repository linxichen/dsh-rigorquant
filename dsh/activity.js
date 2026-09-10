// RigorQuant team activity — host half.
//
// One live panel for a RigorQuant research lab: which role agents are running,
// what they last did, and a short event feed — served to the browser floater
// (dsh/client.js, `shell.overlay`) as a JSON snapshot over the profile's own
// HTTP route, plus the role portraits out of docs/figs/.
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
const ROLES = ['root', 'explorer', 'offgrid', 'doublechecker', 'adversary', 'lit-line', 'lit-adversary', 'doc-adversary']

/** role → display name, tool name, and docs/figs portrait file. */
export const ROLE_DEF = {
  root:      { label: 'Orchestrator',   tool: 'root persona',                avatar: 'avatar-orchestrator.png' },
  explorer:  { label: 'Explorer',       tool: 'subagent_explorer',           avatar: 'avatar-explorer.png' },
  offgrid:   { label: 'OffGridThinker', tool: 'subagent_offgrid',            avatar: 'avatar-offgrid.png' },
  doublechecker: { label: 'DoubleChecker', tool: 'subagent_double_checker',   avatar: 'avatar-doublechecker.png' },
  adversary: { label: 'Adversary',      tool: 'subagent_adversary',          avatar: 'avatar-adversary.png' },
  'lit-line':     { label: 'Literature', tool: 'subagent_lit_line',           avatar: 'avatar-literature.png' },
  // Roster/caption label: full and unambiguous (the hub-and-spoke node uses a
  // shorter variant in ROLE_DEF_CLIENT because of node width).
  'lit-adversary': { label: 'Literature adversary', tool: 'subagent_lit_adversary', avatar: 'avatar-literature-adversary.png' },
  'doc-adversary': { label: 'Document',  tool: 'subagent_document_adversary', avatar: 'avatar-document-adversary.png' },
  validator: { label: 'Validator',    tool: 'rq_check.py',                 avatar: 'avatar-validator.png' },
}

const FEED_AVATAR_FILES = new Set(Object.values(ROLE_DEF).map((def) => def.avatar))
const FIG_DIR = fileURLToPath(new URL('../docs/figs/', import.meta.url))

/** tool name → role, reverse of ROLE_DEF for the subagent tools. */
const TOOL_ROLE = {}
for (const [role, def] of Object.entries(ROLE_DEF)) {
  const tool = def?.tool
  if (typeof tool === 'string' && tool.startsWith('subagent')) TOOL_ROLE[tool] = role
}

/**
 * Best-effort role hint from a subagent descriptor label. One-shot spawns
 * carry no persona, so when the parent's subagent tool call was never
 * observed (e.g. seeding live agents after a profile restart) the label is
 * the only signal left. Conservative: only clear prefixes map.
 */
function labelRole(label) {
  if (typeof label !== 'string') return null
  const l = label.toLowerCase()
  if (l.includes('lit line') || l.includes('literature line')) return 'lit-line'
  if (l.includes('lit adversary') || l.includes('lit-adversary')
    || l.includes('literature adversary') || l.includes('literature verif')) return 'lit-adversary'
  // 'gt-'/'ground truth' labels predate the DoubleChecker rename and still map.
  if (/^gt[- ]/.test(l) || l.includes('ground truth') || l.includes('ground-truth')) return 'doublechecker'
  if (l.includes('double check') || l.includes('double-check') || l.includes('doublecheck')) return 'doublechecker'
  if (l.includes('off grid') || l.includes('off-grid') || l.includes('offgrid')) return 'offgrid'
  if (l.includes('adversary')) return 'adversary'
  if (l.includes('explorer')) return 'explorer'
  return null
}

const FEED_LIMIT = 16
const KEEP_DISPOSED_MS = 60 * 60 * 1000
// A role is shown as actively working if it emitted session events within this
// window, even when their agent status never surfaced as 'running' (one-shot
// subagents finish faster than the client's poll).
const RECENT_ACTIVE_MS = 30 * 1000

function tagRole(text) {
  const match = typeof text === 'string' ? TAG.exec(text) : null
  return match !== null && ROLES.includes(match[1]) ? match[1] : null
}

/** Whether a session header describes a subagent child (same rule as the router).
 *
 * `origin: 'subagent'` is the durable discriminator; `parentSession` is fork
 * lineage, so a forked top-level session carries it while staying
 * root-eligible. */
function isChildHeader(header) {
  return header?.origin === 'subagent'
}

/** The session's OWN event log.
 *
 * `Session.events` was removed in 0.1.2-rc.1, so a `?.events ?? []` read is a
 * silently empty panel; `ownEvents()` is the current accessor and excludes the
 * fork-inherited prefix that `snapshotEvents()` still returns.
 *
 * Neither accessor means this is not a Session this build can observe. THROW
 * rather than return an empty array: the whole failure mode being fixed here
 * was a removed API degrading into an empty panel with no diagnostic. */
function ownEventsOf(session) {
  if (typeof session?.ownEvents === 'function') return session.ownEvents()
  if (typeof session?.snapshotEvents === 'function') return session.snapshotEvents()
  throw new Error('rq-activity: the session exposes neither ownEvents() nor snapshotEvents(); refusing to report an empty panel')
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
    if (/subagent_double_checker/.test(tool)) stage = 'ground truth'
    else if (/subagent_adversary/.test(tool)) stage = 'attack'
    else if (/subagent_document_adversary/.test(tool)) stage = 'certify'
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
  /** parent session id → role FIFO, fed by subagent* tool calls. */
  const pendingSpawns = new Map()
  /** sessionId → { seq, title }: `sessionTitle.get()` folds the whole log, and
   *  the snapshot asks for it per lab on every HTTP poll. */
  const titleCache = new Map()

  const entryOf = (id) => {
    let entry = entries.get(id)
    if (entry === undefined) {
      entry = {
        id,
        role: null,
        label: null,
        parentId: undefined,
        /** `header.origin` — 'subagent' only for a real child; fork lineage
         *  (`parentSession`) is a different fact and does not demote a
         *  top-level session out of lab detection. */
        origin: null,
        preset: null,
        status: 'idle',
        disposed: false,
        startedAt: Date.now(),
        lastAt: 0,
        lastActiveAt: 0,
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
    if (kind === 'tool' || kind === 'message') entry.lastActiveAt = at
  }

  const pushFeed = (labId, entry, item) => {
    const lab = entries.get(labId)
    if (lab === undefined) return
    if (!Array.isArray(lab.feed)) lab.feed = []
    lab.feed.push(item)
    if (lab.feed.length > 80) lab.feed.shift()
  }

  /** The preset a session runs under.
   *
   * A RigorQuant session is created as `standard` and then switched in the
   * picker, and the DURABLE creation header keeps the value it started with
   * forever. The order is therefore: the live composition, then the
   * `agentPreset` Session projection (which is exactly what replaced the
   * header as the authority), then a bounded scan of the session's own log,
   * and only then the creation header. */
  const presetOf = (agent) => {
    const header = agent.session?.header ?? {}
    const live = ctx.get('agentPresets')?.composedPreset(agent.ctx)
    if (typeof live === 'string' && live !== '') return live
    const projections = ctx.get('sessionProjections')
    if (projections !== undefined) {
      const state = projections.stateOf(agent.session, 'agentPreset')
      if (typeof state === 'string' && state !== '') return state
    }
    const events = ownEventsOf(agent.session)
    let selected = null
    for (let i = 0; i < Math.min(events.length, 128); i += 1) {
      const event = events[i]
      if (event?.type === 'agent-preset/selected') selected = event.data?.agentPreset ?? null
    }
    return selected ?? header.agentPreset ?? null
  }

  const roleOfAgent = (agent) => {
    const header = agent.session?.header ?? {}
    const preset = presetOf(agent)
    if (!isChildHeader(header) && preset === PRESET_ID) {
      return { role: 'root', preset }
    }
    const events = ownEventsOf(agent.session)
    for (let i = 0; i < Math.min(events.length, 64); i += 1) {
      const event = events[i]
      if (event?.type === 'subagent/descriptor') {
        const role = tagRole(event.data?.persona) ?? labelRole(event.data?.label)
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
    entry.origin = agent.session?.header?.origin ?? null
  }

  ctx.on('agent/created', ({ agent }) => {
    const { role, preset } = roleOfAgent(agent)
    const parentId = agent.session?.header?.parentSession
    let finalRole = role
    // One-shot subagents carry no persona tag. The parent's subagent* tool
    // call is the reliable role signal: consume the FIFO hint it queued, but
    // only when the persona/label scan left the role unresolved.
    if (parentId !== undefined) {
      const queue = pendingSpawns.get(parentId)
      if (queue !== undefined && queue.length > 0) {
        const hinted = queue.shift()
        if (finalRole === null && hinted !== undefined) finalRole = hinted
        if (queue.length === 0) pendingSpawns.delete(parentId)
      }
    }
    const entry = entryOf(agent.id)
    entry.role = finalRole
    entry.preset = preset
    entry.parentId = parentId
    entry.origin = agent.session?.header?.origin ?? null
  })

  ctx.on('agent/status', ({ agent, status }) => {
    if (status !== 'running' && status !== 'idle') return
    const entry = entries.get(agent.id)
    if (entry !== undefined) entry.status = status
  })

  ctx.on('session/event', (session, event) => {
    const entry = entryOf(session.id)
    // Backfill the child discriminator for sessions first seen through their
    // log (a cold session, or one that predates this plugin's mount).
    if (entry.origin === null) entry.origin = session.header?.origin ?? null
    const at = timeOf(event)
    const labId = entry.role === 'root' && entry.preset === PRESET_ID
      ? entry.id
      : (entry.parentId ?? null)
    switch (event.type) {
      case 'subagent/descriptor': {
        const role = tagRole(event.data?.persona) ?? labelRole(event.data?.label)
        if (role !== null) entry.role = role
        break
      }
      case 'tool/call': {
        const nameText = String(event.data?.name ?? 'tool')
        // A subagent* tool call announces the role of the child it is about
        // to spawn; queue it so agent/created can attach the role when the
        // child's descriptor carries no persona (one-shot spawns).
        const spawnRole = TOOL_ROLE[nameText]
        if (spawnRole !== undefined) {
          const queue = pendingSpawns.get(session.id) ?? []
          queue.push(spawnRole)
          pendingSpawns.set(session.id, queue)
        }
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
      case 'step/start':
        entry.lastActiveAt = at
        touch(entry, 'turn', event.type, at)
        break
      case 'turn/end':
      case 'step/end':
        touch(entry, 'turn', event.type, at)
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
    // top-level session to captain the moment it becomes a RigorQuant lab, and
    // demote it if the user switches away. A real child is excluded by
    // `origin`; `parentSession` alone would also exclude a FORKED top-level
    // session, which is root-eligible.
    if (agentPreset === PRESET_ID && entry.origin !== 'subagent' && entry.role !== 'root') {
      entry.role = 'root'
    } else if (agentPreset !== PRESET_ID && entry.role === 'root') {
      entry.role = null
    }
  })

  // Prune disposed entries older than an hour (runs on every snapshot). Clock
  // from the later of last activity and creation, so a subagent disposed with
  // no timed event yet (lastAt 0) is not deleted the instant it ends.
  const prune = () => {
    const now = Date.now()
    for (const [id, entry] of entries) {
      if (entry.disposed && now - Math.max(entry.lastAt, entry.startedAt) > KEEP_DISPOSED_MS) {
        entries.delete(id)
        titleCache.delete(id)
      }
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
      // Authoritative live activity: read the member's current agent status
      // straight from the registry (the same memberActivity signal
      // dsh-agent-teams uses), not from accumulated status events. Fall back to
      // the last recorded status, then to recent session activity, so a role
      // lights while its agent is running and fades after it goes idle. A
      // disposed agent is gone from the registry and is simply idle.
      status: (() => {
        if (entry.disposed) return 'idle'
        const live = ctx.get('agents')?.get(entry.id)
        const liveStatus = live !== undefined && (live.status === 'running' || live.status === 'idle')
          ? live.status
          : entry.status
        if (liveStatus === 'running') return 'running'
        if (entry.lastActiveAt > 0 && Date.now() - entry.lastActiveAt < RECENT_ACTIVE_MS) return 'running'
        return 'idle'
      })(),
      disposed: entry.disposed,
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
      const liveMembers = []
      for (const other of entries.values()) {
        // Disposed members stay in the roster (pruned after KEEP_DISPOSED_MS)
        // so the graph shows every role that ran rather than going empty; the
        // live-team summary and roster rows count only agents still around.
        if (other.parentId === entry.id && other.role !== null && other.role !== 'root') {
          const row = memberRow(other)
          members.push(row)
          if (!other.disposed) liveMembers.push(row)
        }
      }
      const feed = (Array.isArray(entry.feed) ? entry.feed : []).slice()
      for (const other of entries.values()) {
        if (other.parentId === entry.id && Array.isArray(other.feed)) feed.push(...other.feed)
      }
      feed.sort((a, b) => b.t - a.t)
      const ordered = feed.slice(0, FEED_LIMIT)
      const working = liveMembers.filter((m) => m.status === 'running').length
        + (entry.status === 'running' ? 1 : 0)
      const total = liveMembers.length + 1
      labs.push({
        id: entry.id,
        title: titleOf(entry.id),
        startedAt: entry.startedAt,
        lastAt: entry.lastAt,
        stage: stageOf(entry.tools),
        summary: {
          total,
          working,
          idle: total - working,
        },
        captain: memberRow(entry),
        members,
        feed: ordered,
      })
    }
    labs.sort((a, b) => b.lastAt - a.lastAt)
    return { labs }
  }

  /** The lab's folded title, if the session-title fold has produced one.
   *
   * `sessionTitle.get()` folds the session's WHOLE log, and the snapshot asks
   * for it once per lab on every HTTP poll, so the answer is cached against
   * the session cursor the fold was taken at. */
  const titleOf = (labId) => {
    const session = ctx.get('sessions')?.get(labId)
    if (session === undefined) return null
    const seq = session.seq
    const cached = titleCache.get(labId)
    if (cached !== undefined && cached.seq === seq) return cached.title
    const snapshotTitle = ctx.get('sessionTitle')?.get(session)?.title
    const title = typeof snapshotTitle === 'string' && snapshotTitle !== '' ? snapshotTitle : null
    titleCache.set(labId, { seq, title })
    return title
  }

  const registerWebSurface = () => {
    if (routesRegistered) return
    const webServer = ctx.get('webServer')
    if (webServer === undefined) return
    // One effect owns BOTH routes. `webServer.register` throws on a duplicate
    // (kind, path) and Cordis `emit` contains nothing, so a throw on the
    // `internal/service` path must neither leave the flag set (which would
    // wedge the monitor permanently) nor strand a half-registered pair. The
    // flag moves only after both registrations succeed.
    try {
      ctx.effect(() => {
        const disposers = []
        try {
          disposers.push(webServer.register({
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
          }))
          disposers.push(webServer.register({
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
          }))
        } catch (error) {
          for (const dispose of disposers.reverse()) dispose()
          throw error
        }
        routesRegistered = true
        return () => { for (const dispose of disposers.reverse()) dispose() }
      }, 'rq-activity: web surface')
    } catch (error) {
      ctx.logger.warn(`rq-activity: web surface registration failed: ${String(error)}`)
    }
  }

  registerWebSurface()
  ctx.on('internal/service', (serviceName) => {
    if (serviceName === 'webServer') registerWebSurface()
  })
}

export { name, inject, apply }
