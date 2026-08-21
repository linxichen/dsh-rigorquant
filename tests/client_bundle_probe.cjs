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
sandbox.console = console
sandbox.document = {
  querySelectorAll: () => [],
  createElement: () => ({ dataset: {}, setAttribute() {}, remove() {} }),
  head: { append() {}, appendChild() {} },
}
sandbox.window.__ModuleLoader__ = { load: (h) => { handoff = h } }
vm.createContext(sandbox)

const verdict = { registered: false, mode: RC2 ? 'rc2' : 'rc7' }
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
const ops = []
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
  const ctx = {
    effect: (fn) => fn(),
    get: (name) => (name === 'connection'
      ? {
        api: {
          llm: { models: async () => ({ result: { ok: false, error: { code: 'stub', message: 'stub' } } }) },
          settings: {
            describe: async () => ({
              result: { ok: true, value: { namespaces: [{ ns: 'rigorquant-models', schema: { uid: 1, refs: {} } }] } },
            }),
          },
        },
      }
      : (RC2 && name === 'settingsSchema'
        ? settingsSchemaService
        : undefined)),
    locale: { register: () => {}, bind: () => (key) => key },
    settingsScope: {
      bind: () => ({
        getSnapshot: () => ({
          status: 'ready', writable: true, mode: 'host', revision: 1,
          value: { oraclePrimary: { provider: 'deepseek', model: 'v4-pro' } },
          base: { oraclePrimary: { provider: 'deepseek', model: 'v4-pro' } },
          user: userLayer,
        }),
        subscribe: () => () => {},
        set: async (field, value) => { ops.push({ op: 'set', field, value }); userLayer[field] = value },
        unset: async (field) => { ops.push({ op: 'unset', field }); delete userLayer[field] },
      }),
    },
    slots: {
      inject: (ring, fn) => { verdict.mountRing = ring; return fn() },
      register: (descriptor, component) => {
        cards.push(descriptor.key)
        registrations.push({ descriptor, component })
        return descriptor
      },
    },
  }
  // A fresh materialization for the mount: the loader memoizes one record per
  // bundle, so the surface under test is a factory result, not a reused one.
  const surface = handoff.factory(reqStub)
  try {
    surface.apply(ctx)
    verdict.mounted = true
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
  verdict.draft.inheritedOracle = read().fields.oraclePrimary.inherited

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

exerciseDraft().catch((error) => {
  verdict.draftError = `${error.name}: ${error.message}`
}).finally(() => {
  process.stdout.write(JSON.stringify(verdict))
})
