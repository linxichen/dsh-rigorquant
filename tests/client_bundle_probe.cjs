// Executes the shipped client half exactly the way the DSH web shell does:
// as a CLASSIC script that must self-register through window.__ModuleLoader__.load
// (packages/client/modules/src/client/system.ts). Prints a JSON verdict.
//
// This is the harness contract, not an approximation of it: the shell appends a
// plain <script src> (no type=module), so an ESM `export` statement never runs
// and the bundle registers nothing.
const fs = require('node:fs')
const vm = require('node:vm')

const [, , bundlePath, pluginId] = process.argv
const code = fs.readFileSync(bundlePath, 'utf8')

let handoff = null
const sandbox = {}
sandbox.window = sandbox
sandbox.globalThis = sandbox
// In the VM the bundle's `console` is this object, so a stray console.log in
// the bundle would leak into the JSON verdict stdout. Collect instead of
// emitting: diagnostics stay on the verdict, stdout stays pure JSON.
const collectedLogs = []
sandbox.console = { ...console, log: (...args) => { collectedLogs.push(args.map(String).join(' ')) } }
// The card's lazy catalog retry uses window.setTimeout; the VM window is the
// sandbox itself, so surface the host timers. The move pill re-reads its team
// view on an interval, so the interval pair is surfaced too (the browser has
// both).
sandbox.setTimeout = setTimeout
sandbox.clearTimeout = clearTimeout
sandbox.setInterval = setInterval
sandbox.clearInterval = clearInterval
sandbox.window.__ModuleLoader__ = { load: (h) => { handoff = h } }
vm.createContext(sandbox)

const verdict = { registered: false, mode: 'service' }
/** Set by the mount block; reused by the delayed-namespace scenario. */
let pluginSurface = null
try {
  vm.runInContext(code, sandbox, { filename: bundlePath })
} catch (error) {
  verdict.executionError = `${error.name}: ${error.message}`
  process.stdout.write(JSON.stringify(verdict))
  process.exit(0)
}

if (handoff === null) {
  process.stdout.write(JSON.stringify(verdict))
  process.exit(0)
}

verdict.registered = true
verdict.id = handoff.id
verdict.factoryIsFunction = typeof handoff.factory === 'function'
// 0.1.6 made client sessions references and dropped the list's `current`
// field (client-session-references, 2026-09-15). A read of it is silent —
// `undefined`, never an error — so the source is scanned for the member
// itself: `.current` followed by a non-word character (a name merely ending
// in "...current", like `currentSessionId`, does not match).
verdict.currentFieldReads = (code.match(/\.current\b/g) ?? []).length
verdict.retiredSettingsSlotReferences = (code.match(/settings\.plugin\.item/g) ?? []).length
// The pill must read its team view through the Team namespace's `view` RPC.
// A projection-shaped read is dead code on the installed 0.1.6-alpha.2: that
// client store does not exist there — `git grep projectionsBySession` over the
// harness is empty — so the read is silently undefined and the pill renders
// nothing on every real session, forever. The probe's behavioural scenarios
// above are what prove the replacement works; this pin is on the READ EXPRESSION
// (comments explaining the retired API are prose, not a read), so the fictional
// call cannot come back behind a feature check.
verdict.fictionalProjectionReads = (code.match(/useSessions\s*\(|state\.projectionsBySession/g) ?? []).length
verdict.teamNamespaceReads = (code.match(/remote\.agentTeams/g) ?? []).length

// The module table only answers platform seed words; anything else is a
// guaranteed runtime throw in the browser, so record what was asked for.
// @deepseek-ai/dsh-client-schema-form is deliberately NOT in the table: it was
// deleted upstream (its helpers folded into the `settingsSchema` service) and
// is absent from the browser's frozen seed list, so a residual require of it
// must fail here exactly as it would in the page.
const PLATFORM = new Set([
  'react', 'react/jsx-runtime', 'react-dom', 'react-dom/client', '@deepseek-ai/cordis',
  '@deepseek-ai/dsh-client-ui-slots', '@deepseek-ai/dsh-client-web-react',
  '@deepseek-ai/dsh-client-ui-primitives', '@deepseek-ai/dsh-client-ui-attachment',
])
const required = []
const registrations = []
/** Disposers the mount context's effects returned, in registration order. */
const effectDisposers = []
const rings = []
const ops = []
let modelCatalogCalls = 0
// Mutable persisted user layer: the ops the card emits land here, so a
// follow-up edit sees the same layering the real seam would show it.
const userLayer = {}
// The move pill reads the Lead's live team view through the Team package's own
// browser seam: the `remote.agentTeams` namespace, whose `view(agentId)`
// answers `RemoteResult<TeamView>`
// (agent-team `lib/typert.remote-client.d.ts`; the same call
// `client-ui-agent-team`'s own header action makes). That is the ONLY read
// that works on the installed 0.1.6-alpha.2: the client Session store has no
// `projectionsBySession` there — `git grep projectionsBySession` over the
// installed harness is empty — so a projection-shaped read is silently
// undefined forever, and the pill renders nothing on every real session.
// `remote.agentTeams` is INJECTED, never read off the root context: with the
// Team bundle unmounted the namespace does not exist, the `ctx.inject` gate
// never fires, and the pill never registers at all — "renders nothing when
// the namespace is absent" as a registration gate, not a null branch.
//
// Two fake sessions cover the header's two shapes: 'lab-lead' (a Team Lead, no
// parent) and 'lab-teammate' (a teammate whose own header must resolve back to
// the same Lead's board via `subagent.address.parentSessionId`). `teamViews` is
// the mutable per-Lead source a scenario flips between "no team running"
// (the namespace answers a failed RemoteResult) and a populated TeamView.
const sessionSnapshots = {
  'lab-lead': { subagent: undefined },
  'lab-teammate': { subagent: { address: { parentSessionId: 'lab-lead' } } },
}
let teamViews = {}
const teamViewLeadIds = []
const teamNamespace = {
  view: async (leadSessionId) => {
    teamViewLeadIds.push(leadSessionId)
    return teamViews[leadSessionId] === undefined
      ? { ok: false, error: { code: 'team/not-found' } }
      : { ok: true, value: teamViews[leadSessionId] }
  },
}
/** Session-scoped standard props for one session, layered onto whatever the
 *  registration's own `inject()` face contributes (propsOf below). */
const sessionPropsFor = (sessionId) => ({
  sessionId,
  useSession: (selector) => selector(sessionSnapshots[sessionId]),
})
// Minimal React: enough to run renders of a function component and record the
// element tree. The card needs createElement plus a snapshot hook; the pill
// additionally loads its team view asynchronously, so state and effects are
// REAL here — `mount` below renders, runs the effects a render scheduled,
// settles their promises, and renders again until the tree stops moving, which
// is the loop React itself drives. Hook slots are positional per component.
const hookSlots = []
let hookCursor = 0
let hookDirty = false
const react = {
  createElement: (type, props, ...children) => ({
    type: typeof type === 'function' ? (type.name || 'component') : type,
    // Keep the function itself so a scenario can render one node level deeper
    // than the framework would: the card's selects are function components.
    fn: typeof type === 'function' ? type : undefined,
    props: props ?? {},
    children: children.flat(Infinity).filter((child) => child !== null && child !== undefined),
  }),
  useState: (initial) => {
    const slot = (hookSlots[hookCursor] ??= {
      value: typeof initial === 'function' ? initial() : initial,
    })
    hookCursor += 1
    return [slot.value, (next) => {
      const value = typeof next === 'function' ? next(slot.value) : next
      if (value !== slot.value) {
        slot.value = value
        hookDirty = true
      }
    }]
  },
  useMemo: (factory) => factory(),
  useCallback: (fn) => fn,
  useRef: (initial) => {
    const slot = (hookSlots[hookCursor] ??= { ref: { current: initial } })
    hookCursor += 1
    return slot.ref
  },
  useEffect: (effect, deps) => {
    const slot = (hookSlots[hookCursor] ??= {})
    hookCursor += 1
    const same = slot.deps !== undefined && deps !== undefined
      && slot.deps.length === deps.length && deps.every((dep, i) => dep === slot.deps[i])
    if (same) return
    slot.deps = deps === undefined ? undefined : [...deps]
    slot.effect = effect
  },
  useId: () => 'probe-id',
  useSyncExternalStore: (_subscribe, getSnapshot) => getSnapshot(),
}
// Test double for the settings draft model. These mirror the seam's documented
// semantics: presence marks an override (hasPath), setPath/deletePath edit
// immutably, and deletePath is the per-field reset. The card must not depend on
// anything beyond that contract.
const schemaForm = {
  getPath: (value, path) => path.reduce(
    (node, key) => (typeof node === 'object' && node !== null ? node[key] : undefined),
    value,
  ),
  hasPath: (value, path) => {
    const parent = path.slice(0, -1).reduce(
      (node, key) => (typeof node === 'object' && node !== null ? node[key] : undefined),
      value,
    )
    if (typeof parent !== 'object' || parent === null) return false
    return path[path.length - 1] in parent
  },
  setPath: (root, path, value) => {
    if (path.length === 0) throw new Error('setPath needs a non-empty path')
    const next = { ...root }
    next[path[path.length - 1]] = value
    return next
  },
  deletePath: (root, path) => {
    if (path.length === 0) throw new Error('deletePath needs a non-empty path')
    if (!(path[path.length - 1] in (root ?? {}))) return root
    const next = { ...root }
    delete next[path[path.length - 1]]
    return next
  },
  rehydrateSchema: (serialized) => ({ serialized }),
  validateDraft: () => undefined,
}
// The `settingsSchema` service (@deepseek-ai/dsh-client-ui-settings): the same
// helpers under the service surface (rehydrate/validate; path helpers
// unchanged). It is the ONLY draft model this card may use.
const settingsSchemaService = {
  rehydrate: (serialized) => ({ serialized }),
  validate: () => undefined,
  getPath: schemaForm.getPath,
  hasPath: schemaForm.hasPath,
  setPath: schemaForm.setPath,
  deletePath: schemaForm.deletePath,
}
/** Props as the slot framework composes them from a registration's face:
 *  every `hooks` source becomes a bound `use<Name>` selector hook and the
 *  `hooks` key itself never reaches the component (ui-slots InjectFace). */
const propsOf = (face) => {
  const props = { t: (key) => key }
  for (const [name, value] of Object.entries(face)) {
    if (name === 'hooks') continue
    props[name] = value
  }
  for (const [name, source] of Object.entries(face.hooks ?? {})) {
    props[`use${name[0].toUpperCase()}${name.slice(1)}`] = (selector) => selector(source.getSnapshot())
  }
  return props
}
/** Poll `done` at `stepMs` until it holds or `steps` elapse. */
const settle = async (done, steps = 100, stepMs = 10) => {
  for (let i = 0; i < steps; i += 1) {
    if (done()) return true
    await new Promise((resolve) => setTimeout(resolve, stepMs))
  }
  return done()
}
/** Render one function component the way React mounts it: render, run the
 *  effects that render scheduled, let their promises settle, re-render while
 *  anything changed, and hand back the final tree plus the cleanups an unmount
 *  would run (the pill re-reads its team view on a timer, so its interval MUST
 *  be cleared or this process never exits). */
const mount = async (component, props, budget = 12) => {
  hookSlots.length = 0
  hookCursor = 0
  hookDirty = false
  let tree = null
  const cleanups = []
  for (let pass = 0; pass < budget; pass += 1) {
    hookCursor = 0
    hookDirty = false
    tree = component(props)
    const due = hookSlots.filter((slot) => typeof slot.effect === 'function')
    if (due.length === 0 && !hookDirty) break
    for (const slot of due) {
      const effect = slot.effect
      slot.effect = undefined
      const cleanup = effect()
      if (typeof cleanup === 'function') cleanups.push(cleanup)
    }
    await new Promise((resolve) => setTimeout(resolve, 0))
  }
  return { tree, cleanups }
}
const reqStub = (spec) => {
  required.push(spec)
  if (!PLATFORM.has(spec)) throw new Error(`module table cannot answer "${spec}"`)
  if (spec === 'react') return react
  return {}
}
try {
  const exports = handoff.factory(reqStub)
  verdict.applyIsFunction = typeof exports?.apply === 'function'
  verdict.inject = exports?.inject ?? null
} catch (error) {
  verdict.factoryError = `${error.name}: ${error.message}`
}
verdict.required = required

// Mount the plugin the way cordis does: `apply(ctx)` against a context stubbing
// exactly the services the module declares in `inject`. A card that registers
// but throws on mount is the next failure after registration.
if (verdict.applyIsFunction) {
  const cards = []
  // `remote` is injected as a required Cordis service, so production code must
  // use ctx.remote (not ctx.get('remote')). Keep the probe shaped the same way.
  // Cordis gates sub-namespace access: `remote.session`/`remote.settings` are
  // only reachable when declared in the plugin's `inject`, otherwise it throws
  // `cannot get property "remote.session" without inject`. Model the remote as
  // a Proxy over the declared set so a bundle that forgets a sub-namespace
  // fails at apply() exactly as it does in the harness.
  const declaredRemote = verdict.inject ?? []
  const remoteNamespaces = {
    session: {
      modelCatalog: async () => {
        modelCatalogCalls += 1
        return {
          ok: true,
          value: {
            groups: [{ id: 'deepseek', name: 'DeepSeek', models: [{ id: 'v4-pro', name: 'V4 Pro' }] }],
            failures: [], routableProviders: ['deepseek'], default: { provider: 'deepseek', model: 'v4-pro' },
          },
        }
      },
    },
    settings: {
      describe: async () => ({
        ok: true,
        value: { namespaces: [{ ns: 'rigorquant-models', schema: { uid: 1, refs: {} } }] },
      }),
    },
    // The namespace the move pill reads its roster and board through. It is
    // reached only from inside `ctx.inject(['remote.agentTeams'], …)`, never
    // from the root context (the gate below enforces that).
    agentTeams: teamNamespace,
  }
  /** One remote face, gated on the namespaces its scope actually injected. */
  const makeRemote = (allowed) => new Proxy(remoteNamespaces, {
    get(target, prop) {
      if (typeof prop === 'string' && prop in target) {
        if (!allowed.includes(`remote.${prop}`)) {
          throw new Error(`cannot get property "remote.${prop}" without inject`)
        }
        return target[prop]
      }
      return Reflect.get(target, prop)
    },
  })
  const remote = makeRemote(declaredRemote)
  // Services this scope's context provides. `remote.agentTeams` is one of them
  // here — this composition has the Team bundle — but it is reached only from
  // inside the scope that injects it, never off the root context.
  const injectDeps = []
  const provides = (name) => [
    'slots', 'locale', 'remote', 'remote.session', 'remote.settings', 'settingsScope',
    'remote.agentTeams',
  ].includes(name)
  const ctx = {
    // `ctx.effect` runs the body at once and keeps what it returns as the
    // disposer; the disposers are collected so the disposal scenario can run
    // them the way a fiber unload does.
    effect: (fn) => { const dispose = fn(); if (typeof dispose === 'function') effectDisposers.push(dispose); return dispose },
    // Cordis's scoped service gate: the callback runs once every named service
    // exists, against a scope that reaches exactly those namespaces.
    inject: (deps, fn) => {
      injectDeps.push(deps)
      if (deps.some((dep) => !provides(dep))) return undefined
      return fn({ ...ctx, remote: makeRemote([...declaredRemote, ...deps]) })
    },
    remote,
    get: (name) => (name === 'settingsSchema' ? settingsSchemaService : undefined),
    locale: { register: () => {}, bind: () => (key) => key },
    settingsScope: {
      bind: () => ({
        getSnapshot: () => ({
          status: 'ready', writable: true, mode: 'host', revision: 1,
          value: { doublecheckerPrimary: { provider: 'deepseek', model: 'v4-pro' } },
          base: { doublecheckerPrimary: { provider: 'deepseek', model: 'v4-pro' } },
          user: userLayer,
        }),
        subscribe: () => () => {},
        set: async (field, value) => { ops.push({ op: 'set', field, value }); userLayer[field] = value },
        unset: async (field) => { ops.push({ op: 'unset', field }); delete userLayer[field] },
      }),
    },
    slots: {
      inject: (ring, fn) => { rings.push(ring); return fn() },
      register: (descriptor, component) => {
        cards.push(descriptor.id ?? descriptor.key)
        registrations.push({ descriptor, component })
        return descriptor
      },
    },
  }
  // A fresh materialization for the mount: the loader memoizes one record per
  // bundle, so the surface under test is a factory result, not a reused one.
  const surface = handoff.factory(reqStub)
  pluginSurface = surface
  try {
    surface.apply(ctx)
    verdict.mounted = true
    verdict.mountedRings = rings
    verdict.cards = cards
    // The Plugins page finds a bundle's form by the slot name and the KEY:
    // `plugins.bundle.config` keyed by the bundle's package name, which is
    // also the id the bundle registered with the loader.
    const card = registrations.find((reg) => reg.descriptor.name !== 'conversation.session.header.utilities')
    verdict.cardSlot = card?.descriptor.name ?? null
    verdict.cardKey = card?.descriptor.key ?? null
  } catch (error) {
    verdict.mounted = false
    verdict.mountError = `${error.name}: ${error.message}`
  }

  // Render the registered component with props composed the way the slot
  // framework composes them. The `hooks` compartment is RESERVED: each source
  // `name` reaches the component as a bound `use<Name>` selector hook and the
  // `hooks` key itself is stripped (ui-slots InjectFace). A component reading
  // props.hooks therefore crashes at render even though registration succeeded
  // -- registration and render are separate failure surfaces.
  if (registrations.length > 0) {
    const { descriptor, component } = registrations[0]
    const props = propsOf(descriptor.inject())
    verdict.renderProps = Object.keys(props).sort()
    // The page asks every configuration entry for two views through its
    // owner props: `summary` is the one-liner under the title, `page` the
    // form with its own save control (ui-plugin-manager slot-contract). Only
    // a save writes: there is no discard control and no unsaved marker.
    const textOf = (node, found = []) => {
      if (typeof node === 'string') found.push(node)
      else if (node !== null && typeof node === 'object') for (const child of node.children ?? []) textOf(child, found)
      return found
    }
    const buttonsOf = (node, found = []) => {
      if (node === null || typeof node !== 'object') return found
      if (node.type === 'button') found.push(textOf(node).join(''))
      for (const child of node.children ?? []) buttonsOf(child, found)
      return found
    }
    try {
      const summary = component({ ...props, view: 'summary' })
      verdict.summaryView = typeof summary === 'string' ? summary : (summary?.type ?? null)
      const page = component({ ...props, view: 'page' })
      verdict.rendered = true
      verdict.rootType = page?.type ?? null
      verdict.pageButtons = buttonsOf(page)
      verdict.pageText = textOf(page)
    } catch (error) {
      verdict.rendered = false
      verdict.renderError = `${error.name}: ${error.message}`
    }
  }

  // The move pill is the second registration
  // (conversation.session.header.utilities, scope 'session'); its behaviours
  // are exercised by the async scenario below, which drives the real
  // `remote.agentTeams.view` face the way the browser does.
}

// Drive the draft model through the same face the card uses. This is the
// schema-form contract in motion: staging a choice records an override,
// staging null clears it (the per-field reset), and save turns the draft into
// the scope's fenced path ops -- set for what is overridden, unset for what
// was cleared.
async function exerciseDraft() {
  if (registrations.length === 0) return
  const face = registrations[0].descriptor.inject()
  const read = () => face.hooks.rqCard.getSnapshot()
  const FIELD = 'explorerPrimary'
  const CHOICE = { provider: 'deepseek', model: 'v4-flash' }

  verdict.draft = { start: read().fields[FIELD].overridden }
  face.stage(FIELD, CHOICE)
  verdict.draft.afterStage = {
    overridden: read().fields[FIELD].overridden,
    dirty: read().fields[FIELD].dirty,
    choice: read().fields[FIELD].choice,
  }
  face.discard()
  verdict.draft.afterDiscard = read().fields[FIELD].overridden

  // A role the plugin ships a base default for reads as inherited, not empty.
  verdict.draft.inheritedDoubleChecker = read().fields.doublecheckerPrimary.inherited

  face.stage(FIELD, CHOICE)
  await face.save()
  verdict.draft.ops = ops.map((entry) => `${entry.op}:${entry.field}`)
  verdict.draft.afterSaveDirty = read().fields[FIELD].dirty
  // The saved override is now the persisted layer, so the field still reads as
  // overridden with nothing staged.
  verdict.draft.persistedOverride = read().fields[FIELD].overridden

  // Clearing it is the per-field reset: deletePath on the draft, unset on the wire.
  ops.length = 0
  face.stage(FIELD, null)
  await face.save()
  verdict.draft.resetOps = ops.map((entry) => `${entry.op}:${entry.field}`)
  verdict.draft.afterReset = read().fields[FIELD].overridden
}

// Immediate-boot regression: the card must WAIT for the session Remote to be
// mounted rather than fail on a bootstrap-batch boot race. `remote.session` is
// absent at apply time; after a short delay the controller's retry observes it
// and loads the catalog, leaving status 'ready' instead of 'failed'.
//
// This scenario is deliberately isolated: it re-runs apply() on a fresh context
// and tracks its own registry + catalog counter so it cannot perturb the main
// mount or draft scenarios (which read shared probe globals).
async function exerciseDelayedCatalog() {
  if (pluginSurface === null) return
  let sessionRemote
  let delayedCalls = 0
  const delayedRegs = []
  const delayedNamespaces = {
    get session() { return sessionRemote },
    settings: { describe: async () => ({ ok: true, value: { namespaces: [{ ns: 'rigorquant-models', schema: { uid: 1, refs: {} } }] } }) },
  }
  const delayedRemote = new Proxy(delayedNamespaces, {
    get(target, prop) {
      if (typeof prop === 'string' && prop in target) {
        if (!(verdict.inject ?? []).includes(`remote.${prop}`)) {
          throw new Error(`cannot get property "remote.${prop}" without inject`)
        }
        return Reflect.get(target, prop)
      }
      return Reflect.get(target, prop)
    },
  })
  const delayedCtx = {
    remote: delayedRemote,
    locale: { register: () => {}, bind: () => (key) => key },
    settingsScope: {
      bind: () => ({
        getSnapshot: () => ({ status: 'ready', writable: true, mode: 'host', revision: 1, value: {}, base: {}, user: {} }),
        subscribe: () => () => {},
        set: async () => {},
        unset: async () => {},
      }),
    },
    slots: {
      inject: (ring, fn) => fn(),
      register: (descriptor, component) => { delayedRegs.push({ descriptor, component }); return descriptor },
    },
    effect: (fn) => fn(),
    // This scenario is about the card's catalog retry; the Team namespace is
    // not in its composition, so the pill's injected callback never runs.
    inject: () => undefined,
    // Serve the settingsSchema service so the card never falls back to the
    // legacy schema-form module require (which would perturb `required`).
    get: (name) => (name === 'settingsSchema' ? settingsSchemaService : undefined),
  }
  pluginSurface.apply(delayedCtx)
  // Mount the session namespace a few retry windows later.
  setTimeout(() => {
    sessionRemote = {
      modelCatalog: async () => {
        delayedCalls += 1
        return {
          ok: true,
          value: {
            groups: [{ id: 'deepseek', name: 'DeepSeek', models: [{ id: 'v4-pro', name: 'V4 Pro' }] }],
            failures: [], routableProviders: ['deepseek'], default: { provider: 'deepseek', model: 'v4-pro' },
          },
        }
      },
    }
  }, 120)
  await new Promise((resolve) => setTimeout(resolve, 900))
  const card = delayedRegs.find((reg) => reg.descriptor.name === 'plugins.bundle.config')
  verdict.delayedCatalogStatus = card?.descriptor?.inject?.().hooks?.rqCard?.getSnapshot?.().catalog?.status ?? null
  verdict.delayedCatalogCalls = delayedCalls
}

// The effort dropdown contract, rendered against a READY catalog. The probe's
// one catalog model carries no reasoning metadata, so every effort select must
// offer exactly the "Default" option — never a generic vocabulary (that
// fallback is what once saved an effort a route refuses, killing every turn on
// it with UNSUPPORTED_REASONING_EFFORT). A stored effort the model does not
// list stays visible but disabled: honest display, not re-selectable.
async function exerciseEffortDropdown() {
  if (registrations.length === 0) return
  // The card loads its catalog asynchronously; wait for it to settle.
  const { component } = registrations[0]
  const face = registrations[0].descriptor.inject()
  await settle(() => ['ready', 'failed'].includes(face.hooks.rqCard.getSnapshot().catalog.status), 100, 20)
  const props = propsOf(face)
  const renderNode = (node) => {
    if (node === null || typeof node !== 'object') return node
    // Render one function-component level the framework would: the card's
    // selects (Select / EffortSelect) are function components, and the stub's
    // createElement does not invoke them.
    if (typeof node.fn === 'function') {
      try {
        return renderNode(node.fn(node.props))
      } catch {
        return null
      }
    }
    return {
      type: node.type,
      props: node.props,
      children: (node.children ?? []).map(renderNode),
    }
  }
  const collectSelects = (node, found = []) => {
    if (node === null || typeof node !== 'object') return found
    if (node.type === 'select') {
      found.push({
        value: node.props?.value,
        options: (node.children ?? [])
          .filter((child) => child !== null && typeof child === 'object' && child.type === 'option')
          .map((option) => ({
            value: option.props?.value,
            label: (option.children ?? []).join(''),
            disabled: option.props?.disabled === true,
          })),
      })
    }
    for (const child of node.children ?? []) collectSelects(child, found)
    return found
  }
  const effortSelects = (tree) => collectSelects(renderNode(tree))
    .filter((select) => select.options.some((option) => option.label === 'effortInherit'))
  // The role rows are the page view's form; the summary view is one line.
  const pageProps = { ...props, view: 'page' }
  const cleanTree = component(pageProps)
  verdict.effortSelectCount = effortSelects(cleanTree).length
  verdict.effortSelectsDefaultOnly = effortSelects(cleanTree).every((select) =>
    select.options.length === 1 && select.options[0].value === '' && select.options[0].disabled === false)
  face.stage('explorerPrimary', { provider: 'deepseek', model: 'v4-pro', reasoningEffort: 'high' })
  const stale = effortSelects(component(pageProps)).filter((select) => select.value === 'high')
  verdict.staleEffortOptions = stale.length === 1 ? stale[0].options : null
  face.discard()
}

// The move pill in full. It reads the Lead's roster and board through the
// injected `remote.agentTeams.view` namespace — the only team read the
// installed 0.1.6-alpha.2 browser half serves — resolving a teammate's own
// header back to its Lead, and rendering nothing while there is no team.
async function exerciseMovePill() {
  // Registration is already evidenced by `mountedRings`/`cards` (asserted by
  // the ring test); this scenario owns behaviour only.
  const pill = registrations.find((reg) => reg.descriptor.id === 'rigorquant-move')
  if (pill === undefined) return
  const props = propsOf(pill.descriptor.inject())
  const mountPill = async (sessionId) => {
    const mounted = await mount(pill.component, { ...props, ...sessionPropsFor(sessionId) })
    // The pill re-reads on an interval; unmount, or this process never exits.
    mounted.cleanups.forEach((cleanup) => cleanup())
    return mounted.tree
  }
  const titlesOf = (node, found = []) => {
    if (node === null || typeof node !== 'object') return found
    if (typeof node.props?.title === 'string') found.push(node.props.title)
    for (const child of node.children ?? []) titlesOf(child, found)
    return found
  }

  try {
    // No team running: the namespace answers a failed RemoteResult (a Lead with
    // no team has no view). Nothing renders and nothing throws.
    teamViews = {}
    verdict.pillNullWithoutTeam = (await mountPill('lab-lead')) === null
    verdict.pillRenderedAbsent = true

    // A completed Fan-out task and a still-pending Ground-truth task blocked on
    // it: the move must read as the SHALLOWEST incomplete layer (Ground-truth),
    // never the completed one. `blockedBy` also names an id absent from the
    // board (a stale edge to a task another round already dropped) to prove a
    // dangling edge is ignored rather than crashing. One RUNNING teammate
    // (doublechecker-1) must produce a badge; an idle one (explorer-1) and the
    // Lead row must not.
    teamViewLeadIds.length = 0
    teamViews = {
      'lab-lead': {
        members: [
          { id: 'lab-lead', name: 'root', role: 'lead', status: 'running', diagnostics: [] },
          { id: 'lab-explorer-1', name: 'explorer-1', role: 'teammate', status: 'idle', diagnostics: [] },
          { id: 'lab-dc-1', name: 'doublechecker-1', role: 'teammate', status: 'running', diagnostics: [] },
        ],
        tasks: [
          {
            id: 'task-1', revision: 1, subject: 'explore', description: '', status: 'completed',
            blockedBy: [], writeScopes: [], ready: true, writeScopeWarnings: [],
          },
          {
            id: 'task-2', revision: 1, subject: 'verify', description: '', status: 'pending',
            blockedBy: ['task-1', 'task-9'], writeScopes: [], ready: false, writeScopeWarnings: [],
          },
        ],
      },
    }
    const tree = await mountPill('lab-lead')
    verdict.pillRendered = tree !== null && typeof tree === 'object'
    verdict.pillMoveText = tree?.children?.[0]?.children?.[0] ?? null
    verdict.pillBadgeTitles = titlesOf(tree)
    // A teammate's OWN header must resolve the same Lead's board through
    // `subagent.address.parentSessionId` — opening a teammate shows the same
    // pill, not a blank one. The view source is keyed by Lead alone, so a
    // failed resolution would render nothing instead of the board.
    verdict.pillFromTeammateRendered = (await mountPill('lab-teammate')) !== null
    verdict.pillViewLeadIds = [...new Set(teamViewLeadIds)]
  } catch (error) {
    verdict.pillRendered = false
    verdict.pillRenderError = `${error.name}: ${error.message}`
  }
  teamViews = {}
}

// The Team namespace is OPTIONAL. With the Team bundle unmounted there is no
// team to read, so the pill must not register at all — the `ctx.inject` gate,
// not a null branch inside the component. A second, Team-less context proves
// it: the card still mounts on its own services, and no
// conversation.session.header.utilities ring is ever claimed.
async function exercisePillGate() {
  if (pluginSurface === null) return
  const gateRings = []
  const gateDeps = []
  const teamlessNamespaces = {
    session: {
      modelCatalog: async () => ({
        ok: true,
        value: { groups: [], failures: [], routableProviders: [], default: { provider: 'deepseek', model: 'v4-pro' } },
      }),
    },
    settings: { describe: async () => ({ ok: true, value: { namespaces: [] } }) },
  }
  const gateRemote = new Proxy(teamlessNamespaces, {
    get(target, prop) {
      if (typeof prop === 'string' && prop in target) {
        if (!(verdict.inject ?? []).includes(`remote.${prop}`)) {
          throw new Error(`cannot get property "remote.${prop}" without inject`)
        }
        return target[prop]
      }
      return Reflect.get(target, prop)
    },
  })
  const gateCtx = {
    remote: gateRemote,
    locale: { register: () => {}, bind: () => (key) => key },
    settingsScope: {
      bind: () => ({
        getSnapshot: () => ({ status: 'ready', writable: true, mode: 'host', revision: 1, value: {}, base: {}, user: {} }),
        subscribe: () => () => {},
        set: async () => {},
        unset: async () => {},
      }),
    },
    slots: {
      inject: (ring, fn) => { gateRings.push(ring); return fn() },
      register: (descriptor) => descriptor,
    },
    effect: (fn) => fn(),
    get: (name) => (name === 'settingsSchema' ? settingsSchemaService : undefined),
    // The gate itself: no Team bundle in this composition, so an injected
    // callback that asks for `remote.agentTeams` never runs.
    inject: (deps, fn) => {
      gateDeps.push(deps)
      if (deps.includes('remote.agentTeams')) return undefined
      return fn(gateCtx)
    },
  }
  pluginSurface.apply(gateCtx)
  verdict.pillGateDeps = gateDeps
  verdict.pillGateRings = gateRings
}

// A fiber unload runs every effect disposer collected during mount: `ctx.effect`
// keeps what the body RETURNS as the disposer. Nothing this bundle registers
// mounts a DOM side effect any more (the retired activity floater's
// docked-panel dodge stylesheet was the only one), so this proves a fiber
// unload runs cleanly rather than checking a specific artifact. Runs after
// the scenarios that need the first mount alive and before the
// delayed-catalog scenario, which mounts a second time on its own context.
function exerciseDisposal() {
  for (const dispose of effectDisposers.splice(0).reverse()) {
    try { dispose() } catch (error) { verdict.disposeError = `${error.name}: ${error.message}` }
  }
}

Promise.resolve().then(() => exerciseEffortDropdown()).catch((error) => {
  verdict.effortDropdownError = `${error.name}: ${error.message}`
}).then(() => exerciseMovePill()).catch((error) => {
  verdict.pillRenderError = `${error.name}: ${error.message}`
}).then(() => exerciseDraft()).catch((error) => {
  verdict.draftError = `${error.name}: ${error.message}`
}).then(() => exerciseDisposal()).catch((error) => {
  verdict.disposeError = `${error.name}: ${error.message}`
}).then(() => exerciseDelayedCatalog()).catch((error) => {
  verdict.delayedCatalogError = `${error.name}: ${error.message}`
}).then(() => exercisePillGate()).catch((error) => {
  verdict.pillGateError = `${error.name}: ${error.message}`
}).finally(() => {
  verdict.modelCatalogCalls = modelCatalogCalls
  process.stdout.write(JSON.stringify(verdict))
})
