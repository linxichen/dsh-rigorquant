// Executes the shipped client half exactly the way the DSH web shell does:
// as a CLASSIC script that must self-register through window.__ModuleLoader__.load
// (packages/client/modules/src/client/system.ts). Prints a JSON verdict.
//
// This is the harness contract, not an approximation of it: the shell appends a
// plain <script src> (no type=module), so an ESM `export` statement never runs
// and the bundle registers nothing.
const fs = require('node:fs')
const vm = require('node:vm')

const [, , bundlePath, pluginId, mode] = process.argv
const RC2 = mode === 'rc2'
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
sandbox.document = {
  querySelectorAll: () => [],
  createElement: () => ({ dataset: {}, setAttribute() {}, remove() {} }),
  head: { append() {}, appendChild() {} },
}
// The card's lazy catalog retry uses window.setTimeout; the VM window is the
// sandbox itself, so surface the host timers.
sandbox.setTimeout = setTimeout
sandbox.clearTimeout = clearTimeout
sandbox.window.__ModuleLoader__ = { load: (h) => { handoff = h } }
vm.createContext(sandbox)

const verdict = { registered: false, mode: RC2 ? 'rc2' : 'rc7' }
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

// The module table only answers platform seed words; anything else is a
// guaranteed runtime throw in the browser, so record what was asked for.
// In rc2 mode the legacy draft-model package is DELETED from the table (that
// is the rc.2 change), so any require of it throws and proves the bundle
// reached the settingsSchema service instead.
const PLATFORM = new Set([
  'react', 'react/jsx-runtime', 'react-dom', 'react-dom/client', '@deepseek-ai/cordis',
  '@deepseek-ai/dsh-client-ui-slots', '@deepseek-ai/dsh-client-web-react',
  '@deepseek-ai/dsh-client-ui-primitives', '@deepseek-ai/dsh-client-ui-attachment',
  ...(RC2 ? [] : ['@deepseek-ai/dsh-client-schema-form']),
])
const required = []
const registrations = []
const rings = []
const ops = []
let modelCatalogCalls = 0
// Mutable persisted user layer: the ops the card emits land here, so a
// follow-up edit sees the same layering the real seam would show it.
const userLayer = {}
// Minimal React: enough to run one render pass of a function component and
// record the element tree. The card only needs createElement plus the hooks it
// calls; the framework supplies its snapshot through the bound selector hook.
const react = {
  createElement: (type, props, ...children) => ({
    type: typeof type === 'function' ? (type.name || 'component') : type,
    props: props ?? {},
    children: children.flat(Infinity).filter((child) => child !== null && child !== undefined),
  }),
  useState: (initial) => [typeof initial === 'function' ? initial() : initial, () => {}],
  useMemo: (factory) => factory(),
  useCallback: (fn) => fn,
  useRef: (initial) => ({ current: initial }),
  useEffect: () => {},
  useId: () => 'probe-id',
  useSyncExternalStore: (_subscribe, getSnapshot) => getSnapshot(),
}
// Test double for the settings draft model. These mirror
// @deepseek-ai/dsh-client-schema-form's documented semantics: presence marks an
// override (hasPath), setPath/deletePath edit immutably, and deletePath is the
// per-field reset. The card must not depend on anything beyond that contract.
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
// rc.2's settingsSchema service: the same helpers under the service surface
// (renames rehydrateSchema->rehydrate, validateDraft->validate; path helpers
// unchanged), provided by @deepseek-ai/dsh-client-ui-settings.
const settingsSchemaService = {
  rehydrate: (serialized) => ({ serialized }),
  validate: () => undefined,
  getPath: schemaForm.getPath,
  hasPath: schemaForm.hasPath,
  setPath: schemaForm.setPath,
  deletePath: schemaForm.deletePath,
}
const reqStub = (spec) => {
  required.push(spec)
  if (!PLATFORM.has(spec)) throw new Error(`module table cannot answer "${spec}"`)
  if (spec === 'react') return react
  if (spec === '@deepseek-ai/dsh-client-schema-form') return schemaForm
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
  }
  const remote = new Proxy(remoteNamespaces, {
    get(target, prop) {
      if (typeof prop === 'string' && prop in target) {
        if (!declaredRemote.includes(`remote.${prop}`)) {
          throw new Error(`cannot get property "remote.${prop}" without inject`)
        }
        return target[prop]
      }
      return Reflect.get(target, prop)
    },
  })
  const ctx = {
    effect: (fn) => fn(),
    remote,
    get: (name) => (RC2 && name === 'settingsSchema'
      ? settingsSchemaService
      : undefined),
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
    const face = descriptor.inject()
    const props = { t: (key) => key }
    for (const [name, value] of Object.entries(face)) {
      if (name === 'hooks') continue
      props[name] = value
    }
    for (const [name, source] of Object.entries(face.hooks ?? {})) {
      props[`use${name[0].toUpperCase()}${name.slice(1)}`] = (selector) => selector(source.getSnapshot())
    }
    verdict.renderProps = Object.keys(props).sort()
    try {
      const tree = component(props)
      verdict.rendered = true
      verdict.rootType = tree?.type ?? null
    } catch (error) {
      verdict.rendered = false
      verdict.renderError = `${error.name}: ${error.message}`
    }
  }

  // The activity floater is a second registration (root-scoped shell.overlay).
  // Its panel must render null while no lab is running — and must not crash.
  if (registrations.length > 1) {
    const { descriptor, component } = registrations[1]
    const face = descriptor.inject()
    const props = { t: (key) => key }
    for (const [name, value] of Object.entries(face)) {
      if (name === 'hooks') continue
      props[name] = value
    }
    for (const [name, source] of Object.entries(face.hooks ?? {})) {
      props[`use${name[0].toUpperCase()}${name.slice(1)}`] = (selector) => selector(source.getSnapshot())
    }
    try {
      const overlayTree = component(props)
      verdict.overlayRendered = true
      verdict.overlayTree = overlayTree === null ? null : (overlayTree.type ?? 'element')
    } catch (error) {
      verdict.overlayRendered = false
      verdict.overlayRenderError = `${error.name}: ${error.message}`
    }

    // Current-session scoping: the floater appears only while the current
    // session is a lab (its captain session or one of its subagents). Two labs
    // in the store, but a non-lab current session must render null; a matching
    // current session must render (the collapsed pill).
    const scopeStore = face.hooks.rqActivity
    const mkLab = (id) => ({
      id, title: id, stage: 'fan out',
      summary: { total: 1, working: 0, idle: 1 },
      captain: { label: 'Orchestrator', status: 'idle' },
      members: [], feed: [],
    })
    const scopedRender = () => {
      try { return component(props) } catch { return null }
    }
    scopeStore.set({
      status: 'ready', anchorRight: null, currentSessionId: 'unrelated',
      labs: [mkLab('lab-current'), mkLab('lab-other')],
    })
    verdict.scopeMismatchNull = scopedRender() === null
    scopeStore.set({
      status: 'ready', anchorRight: null, currentSessionId: 'lab-current',
      labs: [mkLab('lab-current'), mkLab('lab-other')],
    })
    verdict.scopeMatchRendered = scopedRender() !== null
  }
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
// mount, rc2, or draft scenarios (which read shared probe globals).
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
  const card = delayedRegs.find((reg) => reg.descriptor.key === 'rigorquant-models')
  verdict.delayedCatalogStatus = card?.descriptor?.inject?.().hooks?.rqCard?.getSnapshot?.().catalog?.status ?? null
  verdict.delayedCatalogCalls = delayedCalls
}

exerciseDraft().catch((error) => {
  verdict.draftError = `${error.name}: ${error.message}`
}).then(() => exerciseDelayedCatalog()).catch((error) => {
  verdict.delayedCatalogError = `${error.name}: ${error.message}`
}).finally(() => {
  verdict.modelCatalogCalls = modelCatalogCalls
  process.stdout.write(JSON.stringify(verdict))
})
