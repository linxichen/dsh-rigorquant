// RigorQuant model router — browser half.
//
// One configuration entry on the Plugins page: the bundle's own form, rendered
// on this bundle's page between its description and its rows
// (`plugins.bundle.config`, keyed by the package name), editing the
// `rq-model-router` row's own profile config through `configForms`
// (Decision 25). Each role row stages an explicit primary override (model +
// reasoning effort) and a per-role fallback choice, all picked from the model
// catalog; "inherit" clears the saved field so the router's shipped tier
// matrix (fixed-tier roles) or the parent/session route (root and inherit
// roles) governs again. Only a save writes: the last saved selection is the
// persistent one (the profile's user layer), and leaving the page drops
// whatever was staged. A write the Host refuses (`set`/`unset` resolving
// `false`) is a failed save, shown under the form.
//
// rc.2's Plugins page generates no form for a row's config (the
// `plugins.row.config` slot renders only what a plugin registers), so without
// this card the routes could be edited only by hand in the profile patch.
//
// Shipped in the shell's client-bundle format, because that is what the browser
// half is REQUIRED to be: the web shell appends this file as a classic
// <script> and the module system throws unless the script self-registers via
// `window.__ModuleLoader__.load({ id, factory })`. Executing the bundle only
// registers the factory; every side effect lives in the factory closure and
// runs at materialization, when the loader calls `factory(require)` and takes
// the returned object as this package's exports.
//
// The factory's `require` is the frozen module table: it answers the platform
// seed words (react, cordis, the ui primitives) and nothing else. Reaching for
// React only when the card actually renders keeps materialization cheap.
//
// This file has no build step on purpose -- it has no imports to bundle, so
// hand-authoring the wrapper is the whole toolchain. tests/test_client_bundle.py
// executes it the way the shell does.

window.__ModuleLoader__.load({ id: 'dsh-rigorquant', factory: (require) => {

// The bundle's package name: the key the Plugins page looks the bundle's
// configuration entry up by. It repeats the loader id above on purpose — the
// shell concatenates every plugin's bundle into one classic script, so a
// top-level binding shared with the `load` call would collide with any other
// bundle's; the probe pins that the two literals agree.
const BUNDLE = 'dsh-rigorquant'
// The router row's entry id: the key `configForms` serves its config under,
// and this entry's locale namespace.
const CARD_KEY = 'rq-model-router'
const ROLES = ['root', 'explorer', 'offgrid', 'doublechecker', 'adversary', 'lit-line', 'lit-adversary', 'doc-adversary']
const SLOTS = ['Primary', 'Fallback']
// Invocation frequency per role: the badge tone follows the level, the label
// comes from the locale copy (`roleFreq.<role>`).
const ROLE_FREQ = {
  root: 'high', explorer: 'high', offgrid: 'low', doublechecker: 'medium',
  adversary: 'medium', 'lit-line': 'low', 'lit-adversary': 'low',
  'doc-adversary': 'low',
}

let react = null
function React() {
  if (react === null) react = require('react')
  return react
}

// The settings draft model: the same helpers the Settings surface itself edits
// drafts with, so this card's override/reset semantics cannot drift from the
// seam's. They live on the `settingsSchema` service
// (@deepseek-ai/dsh-client-ui-settings, `rehydrate`/`validate` plus the four
// path helpers). The standalone `@deepseek-ai/dsh-client-schema-form` package
// this card once fell back to was DELETED upstream and is no longer in the
// client module table, so there is nothing to fall back to. See
// RqModelsCardController#schemaForm below.

/**
 * Narrow a stored value to a selectable choice. A `{}` can reach the user layer
 * (the schema makes every choice field optional), and it is not a selection.
 */
function asChoice(value) {
  return value !== undefined && value !== null && typeof value === 'object'
    && typeof value.provider === 'string' && value.provider !== ''
    && typeof value.model === 'string' && value.model !== ''
    ? value
    : null
}

/** The reasoning effort carried by a stored choice, or '' when it defers to the adapter. */
function effortOf(value) {
  return value !== undefined && value !== null && typeof value === 'object'
    && typeof value.reasoningEffort === 'string'
    ? value.reasoningEffort
    : ''
}

/** Observable source (getSnapshot + subscribe) for the `hooks` compartment. */
function createStore(initial) {
  let snapshot = initial
  const listeners = new Set()
  return {
    getSnapshot: () => snapshot,
    subscribe: (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    set: (next) => {
      snapshot = next
      for (const listener of listeners) listener()
    },
  }
}

// `remote` is the 0.1.2 typed Host RPC carrier. Its sub-namespaces are gated:
// Cordis throws `cannot get property "remote.session" without inject` unless
// each one is declared here. The routing card reads session.modelCatalog and
// settings.describe, so declare both sub-namespaces (plus the raw `remote`).
// `configForms` (@deepseek-ai/dsh-client-ui-settings) replaces the
// `settingsScope` service DSH 0.1.7 removed.
const inject = ['slots', 'locale', 'remote', 'remote.session', 'remote.settings', 'configForms']

const copy = {
  en: {
    title: 'RigorQuant model routing',
    description: 'Per-role model overrides and fallbacks for RigorQuant sessions. Left on Inherit, the DoubleChecker and adversary take the router\'s shipped routes (on DeepSeek Account when no API key is set); root follows the chatbox picker, and other roles inherit their session model.',
    inherit: 'Inherit',
    none: 'None',
    effortInherit: 'Default',
    effortUnsupported: 'unsupported',
    modelUndeclared: 'not in provider catalog',
    save: 'Save',
    unavailable: 'Model routing is not served by this profile: the rq-model-router row is off.',
    primary: 'Primary',
    fallback: 'Fallback',
    overridden: 'Overridden',
    reset: 'Clear this override',
    invalid: 'Rejected by the settings schema',
    failed: 'Save rejected — staged edits kept',
    catalogFailed: 'Model catalog unavailable — check connection',
    'role.root': 'Root orchestrator',
    'role.explorer': 'Explorer (method track)',
    'role.offgrid': 'OffGridThinker (off-grid derivation)',
    'role.doublechecker': 'DoubleChecker',
    'role.adversary': 'Adversary',
    'role.lit-line': 'Literature line',
    'role.lit-adversary': 'Literature adversary',
    'role.doc-adversary': 'Document adversary',
    'roleDesc.root': 'Runs the whole study: plans, delegates to every role, checkpoints, and synthesizes.',
    'roleDesc.explorer': 'Proposes candidate methods and routes with exact statements; spawned in parallel batches at each proposal stage.',
    'roleDesc.offgrid': 'Derives from the problem statement with raw model intelligence plus compute tools (sympy/numpy/…) — no web, no literature, no other agents\' results.',
    'roleDesc.doublechecker': 'Re-derives closed forms, invariants, and bounds from first principles, twice by different means.',
    'roleDesc.adversary': 'Audits candidate methods and the checks themselves; eliminates routes only by concrete counterexample.',
    'roleDesc.lit-line': 'Traverses one research line (backward/forward citations) and writes a bounded dossier.',
    'roleDesc.lit-adversary': 'Independently re-retrieves and verifies load-bearing literature claims (validity and freshness).',
    'roleDesc.doc-adversary': 'Audits finished deliverables for self-completeness: every jargon term, symbol, and abbreviation used is defined.',
    'roleFreq.root': 'Frequent',
    'roleFreq.explorer': 'Frequent',
    'roleFreq.offgrid': 'Rare',
    'roleFreq.doublechecker': 'Common',
    'roleFreq.adversary': 'Common',
    'roleFreq.lit-line': 'Rare',
    'roleFreq.lit-adversary': 'Rare',
    'roleFreq.doc-adversary': 'Rare',
  },
  zh: {
    title: 'RigorQuant 角色模型路由',
    description: '为 RigorQuant 会话配置每个角色的模型覆盖与回退。DoubleChecker 与 adversary 留在“继承”时走路由器内置的默认路由（未配置 API key 时改走 DeepSeek 账号）；root 跟随聊天框选择器，其他选择“继承”的角色沿用会话模型。',
    inherit: '继承',
    none: '无',
    effortInherit: '默认',
    effortUnsupported: '不支持',
    modelUndeclared: '不在提供方模型目录中',
    save: '保存',
    unavailable: '当前配置未提供模型路由：rq-model-router 行已关闭。',
    primary: '主选择',
    fallback: '回退',
    overridden: '已覆盖',
    reset: '清除此覆盖',
    invalid: '未通过设置模式校验',
    failed: '保存被拒绝——已保留未写入的修改',
    catalogFailed: '模型目录不可用——请检查连接',
    'role.root': '根编排者',
    'role.explorer': '探索者（方法线）',
    'role.offgrid': '离网思考者（OffGridThinker）',
    'role.doublechecker': '双重复核（DoubleChecker）',
    'role.adversary': '对抗审计',
    'role.lit-line': '文献主线',
    'role.lit-adversary': '文献对抗',
    'role.doc-adversary': '文档对抗',
    'roleDesc.root': '运行整个研究：规划、向各角色派发、检查点与综合。',
    'roleDesc.explorer': '提出候选方法与路径（含精确陈述），在每个提案阶段以并行批次派出。',
    'roleDesc.offgrid': '仅凭模型自身的推理与计算工具（sympy/numpy/…）从问题陈述推导——无网络、无文献、不使用他人的结果。',
    'roleDesc.doublechecker': '从第一性原理重新推导闭式解、不变量与界，以两种不同方式各做一次。',
    'roleDesc.adversary': '审计候选方法与检查本身；仅以具体反例消除路径。',
    'roleDesc.lit-line': '遍历一条研究线（前向/后向引用）并产出有界档案。',
    'roleDesc.lit-adversary': '独立重新检索并核验关键文献论断（有效性与时效性）。',
    'roleDesc.doc-adversary': '审计最终交付物的自足性：所用的每个专业术语、符号与缩写都应有定义。',
    'roleFreq.root': '频繁',
    'roleFreq.explorer': '频繁',
    'roleFreq.offgrid': '少见',
    'roleFreq.doublechecker': '常见',
    'roleFreq.adversary': '常见',
    'roleFreq.lit-line': '少见',
    'roleFreq.lit-adversary': '少见',
    'roleFreq.doc-adversary': '少见',
  },
}

// Page chrome. The Plugins page renders this entry inside its own section on
// the bundle's page (`detailSection`), so the form is a plain block headed the
// way the page heads its rows section — a 14px/500 title with a one-line
// description — followed by the role rows and a footer holding the save.
// The page draws the bundle's title, icon and crumb itself. Tokens are the
// same `--dsw-alias-*` the page's own sections use.
const formStyle = { display: 'flex', flexDirection: 'column', minWidth: 0 }
const sectionHeadStyle = { display: 'flex', flexDirection: 'column', gap: 4, paddingBottom: 8 }
const sectionTitleStyle = { margin: 0, fontSize: 14, lineHeight: '20px', fontWeight: 500, color: 'var(--dsw-alias-label-primary)' }
const cardDescriptionStyle = { fontSize: 13, lineHeight: 1.5, color: 'var(--dsw-alias-label-tertiary)' }
const statusStyle = { margin: 0, fontSize: 12, lineHeight: 1.5, color: 'var(--dsw-alias-label-tertiary)' }
const footerStyle = {
  display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8,
  paddingTop: 16,
}
const saveStyle = {
  appearance: 'none', border: '1px solid transparent', borderRadius: 8,
  padding: '5px 14px', font: 'inherit', fontSize: 13, lineHeight: 1.5, cursor: 'pointer',
  background: 'var(--dsw-alias-label-primary)', color: 'var(--dsw-alias-bg-layer-3)',
}


class RqModelsCardController {
  constructor(ctx) {
    this.ctx = ctx
    this.scope = ctx.configForms.get(CARD_KEY)
    // The staged edit is a DRAFT USER SECTION — the schema-form unit of
    // editing — not a side table of pending values. `undefined` means "no edit
    // staged"; once staged it is a plain object built immutably with
    // setPath/deletePath, so a field's PRESENCE in it carries the same
    // override meaning it carries in the persisted user layer.
    this.draft = undefined
    this.saving = false
    this.failed = undefined
    this.catalog = { status: 'loading', providers: [] }
    /** Rehydrated namespace schema; the same validator the Host resolves with. */
    this.schema = undefined
    this.store = createStore(this.projection())
    this.scope.subscribe(() => this.publish())
    // Bounded lazy catalog retry: this bundle is `immediately`, so `apply`
    // can run in the bootstrap batch before `@deepseek-ai/dsh-api-session-controller`
    // mounts `remote.session` in the application batch. Polling the namespace
    // until it exists keeps a healthy catalog RPC from becoming the generic
    // "unavailable" footer (a boot-ordering race, not a catalog failure).
    this.catalogTimer = undefined
  }

  /**
   * The settings draft model, read from the `settingsSchema` service
   * (@deepseek-ai/dsh-client-ui-settings). The service is not optional in
   * practice: it is provided by the same plugin that provides `configForms`,
   * which this card injects, and `configForms` itself is built on it. The legacy
   * `@deepseek-ai/dsh-client-schema-form` module is gone from the harness AND
   * from the browser's frozen module table, so a require on it would throw
   * inside this controller's construction and take the whole bundle entry
   * down; failing loudly here is the honest alternative.
   */
  schemaForm() {
    const service = this.ctx.get('settingsSchema')
    if (service === undefined) {
      throw new Error('rq-model-router: the settingsSchema service is unavailable on this harness; the model-routing card cannot validate drafts')
    }
    return {
      rehydrateSchema: (serialized) => service.rehydrate(serialized),
      validateDraft: (schema, draft) => service.validate(schema, draft),
      getPath: (value, path) => service.getPath(value, path),
      hasPath: (value, path) => service.hasPath(value, path),
      setPath: (root, path, value) => service.setPath(root, path, value),
      deletePath: (root, path) => service.deletePath(root, path),
    }
  }

  async load() {
    await Promise.all([this.loadCatalog(), this.loadSchema()])
    this.publish()
  }

  async loadCatalog() {
    // The namespace may not be mounted yet under immediate boot. Keep the
    // initial state as `loading` and retry until it exists or the attempt cap
    // is reached, rather than declaring the catalog failed on a boot race.
    if (this.catalogTimer !== undefined) {
      clearTimeout(this.catalogTimer)
      this.catalogTimer = undefined
    }
    this.catalog = { status: 'loading', providers: [] }
    this.publish()
    let attempts = 0
    const attempt = async () => {
      attempts += 1
      const session = this.ctx.remote?.session
      if (session === undefined || typeof session.modelCatalog !== 'function') {
        if (attempts < 60 && typeof window !== 'undefined' && typeof window.setTimeout === 'function') {
          this.catalogTimer = window.setTimeout(attempt, 250)
        } else {
          this.catalog = { status: 'failed', providers: [] }
          this.publish()
        }
        return
      }
      try {
        // DSH 0.1.2's official catalog seam. `connection.api.llm.models` was an
        // older compatibility facade and is absent from the current connection
        // handle, which made this card report a false connection failure.
        const response = await session.modelCatalog()
        if (!response.ok) throw new Error(`${response.error.code}: ${response.error.message}`)
        const providers = (response.value.groups ?? []).map((group) => ({
          id: group.id,
          name: group.name ?? group.id,
          models: (group.models ?? []).map((model) => ({
            id: model.id,
            name: model.name ?? model.id,
            // Keep the model's actual reasoning-effort surface so the effort
            // dropdown lists what the model really supports instead of a
            // hard-coded [off, high, max] that not every route accepts.
            efforts: (model.reasoning?.efforts ?? []).map((effort) => ({
              id: effort.id,
              name: effort.name ?? effort.id,
            })),
          })),
        }))
        this.catalog = { status: 'ready', providers }
      } catch {
        this.catalog = { status: 'failed', providers: [] }
      }
      this.publish()
    }
    await attempt()
  }

  /**
   * The scope snapshot carries the resolved section and the raw layers but not
   * the schema envelope, so the validator is read from the same
   * `settings.describe` view the settings page reads. Rehydrating it gives this
   * card the Host's own validator: a draft this card accepts is one the Host
   * accepts, with no second schema to drift.
   */
  async loadSchema() {
    try {
      const response = await this.ctx.remote.settings.describe()
      if (!response.ok) return
      const view = (response.value.namespaces ?? []).find((entry) => entry.ns === CARD_KEY)
      if (view === undefined) return
      this.schema = this.schemaForm().rehydrateSchema(view.schema)
    } catch {
      // No client-side validation this session; the Host still rejects a bad
      // write, and `failed` reports it.
      this.schema = undefined
    }
  }

  snapshot() {
    return this.scope.getSnapshot()
  }

  /** The persisted user layer: presence here is what marks a field overridden. */
  userLayer() {
    const user = this.snapshot()?.user
    return typeof user === 'object' && user !== null && !Array.isArray(user) ? user : {}
  }

  /** The draft under edit, or the persisted user layer when nothing is staged. */
  editing() {
    return this.draft ?? this.userLayer()
  }

  /**
   * The choice a field currently shows: the draft/user override when the field
   * carries one, otherwise the resolved value (schema defaults, then the
   * plugin's composition base). A field with no override renders as inherit.
   */
  shown(field) {
    const { hasPath, getPath } = this.schemaForm()
    const path = [field]
    const source = hasPath(this.editing(), path) ? this.editing() : undefined
    const value = source === undefined ? undefined : getPath(source, path)
    return asChoice(value)
  }

  /** The value a cleared field falls back to: composition base, then schema defaults. */
  inherited(field) {
    const { getPath } = this.schemaForm()
    return asChoice(getPath(this.snapshot()?.value, [field]))
  }

  projection() {
    const { hasPath } = this.schemaForm()
    const snapshot = this.snapshot()
    const editing = this.editing()
    const user = this.userLayer()
    const fields = {}
    for (const role of ROLES) {
      for (const slot of SLOTS) {
        const field = `${role}${slot}`
        const path = [field]
        fields[field] = {
          choice: this.shown(field),
          inherited: this.inherited(field),
          // Presence semantics, exactly as the settings seam layers: an
          // override equal to the composition default is still an override,
          // and comparing values could not see it.
          overridden: hasPath(editing, path),
          dirty: hasPath(editing, path) !== hasPath(user, path)
            || choiceKey(this.shown(field)) !== choiceKey(asChoice(user[field]))
            || effortOf(editing[field]) !== effortOf(user[field]),
        }
      }
    }
    return {
      available: snapshot?.status === 'ready',
      writable: snapshot?.writable !== false,
      saving: this.saving,
      failed: this.failed,
      catalog: this.catalog,
      fields,
    }
  }

  publish() {
    this.store.set(this.projection())
  }

  /** Stage one field: a choice sets it, `null` clears it (the per-field reset). */
  stage(field, choice) {
    const { setPath, deletePath } = this.schemaForm()
    const base = this.editing()
    this.draft = choice === null
      ? deletePath(base, [field])
      : setPath(base, [field], choice)
    this.failed = undefined
    this.publish()
  }

  discard() {
    if (this.draft === undefined && this.failed === undefined) return
    this.draft = undefined
    this.failed = undefined
    this.publish()
  }

  async save() {
    if (this.saving || this.draft === undefined) return
    const { hasPath } = this.schemaForm()
    const draft = this.draft
    // Validate against the Host's own rehydrated schema before any write, so an
    // invalid draft is reported as one message instead of a partial write.
    if (this.schema !== undefined) {
      const failure = this.schemaForm().validateDraft(this.schema, draft)
      if (failure !== undefined) {
        this.failed = failure
        this.publish()
        return
      }
    }
    this.saving = true
    this.failed = undefined
    this.publish()
    const user = this.userLayer()
    // The draft is the intent; the scope's path ops are how it lands, each
    // fenced by the namespace revision the snapshot carries.
    const operations = []
    for (const role of ROLES) {
      for (const slot of SLOTS) {
        const field = `${role}${slot}`
        const path = [field]
        const staged = hasPath(draft, path)
        const persisted = hasPath(user, path)
        if (staged) {
          if (!persisted || choiceKey(asChoice(draft[field])) !== choiceKey(asChoice(user[field]))
            || effortOf(draft[field]) !== effortOf(user[field])) {
            operations.push(() => this.scope.set(field, draft[field]))
          }
        } else if (persisted) {
          operations.push(() => this.scope.unset(field))
        }
      }
    }
    // `set`/`unset` resolve `false` when the Host refuses the write (or the
    // connection keeps preferences process-local); that is a failed save,
    // exactly like a transport rejection.
    let landed = true
    for (const operation of operations) {
      try {
        if (await operation() !== true) landed = false
      } catch {
        landed = false
      }
    }
    if (landed) this.draft = undefined
    this.saving = false
    this.failed = landed ? undefined : 'write'
    this.publish()
  }

  inject() {
    return {
      hooks: { rqCard: this.store },
      stage: (field, choice) => this.stage(field, choice),
      save: () => this.save(),
      discard: () => this.discard(),
    }
  }
}

function choiceKey(choice) {
  return choice === null ? '' : `${choice.provider}::${choice.model}`
}

function Select(props) {
  const { value, options, onChange, disabled, basis } = props
  return React().createElement('select', {
    value,
    disabled,
    onChange: (event) => onChange(event.target.value),
    style: {
      // A <select> takes its intrinsic width from its widest <option>, and a
      // flex item defaults to min-width:auto — together they refuse to shrink,
      // so a long "provider · model" label pushes the row out of the card.
      // `minWidth: 0` lets it shrink; the basis keeps a sensible resting size.
      flex: basis ?? '1 1 11em', minWidth: 0, maxWidth: '100%',
      padding: '2px 6px', borderRadius: 6,
      border: '1px solid var(--dsw-alias-border-l2)',
      background: 'transparent', color: 'inherit', font: 'inherit', fontSize: 12,
    },
  }, options.map((option) => React().createElement('option', {
    key: option.value, value: option.value,
    ...option.disabled === true ? { disabled: true } : {},
  }, option.label)))
}

function EffortSelect(props) {
  const { t, choice, onChange, efforts } = props
  // Only the chosen model's real effort surfaces are selectable. A model that
  // reports no reasoning metadata takes NO explicit effort at all — offering a
  // generic vocabulary there is exactly what stages a level the route refuses
  // at dispatch — so such a row offers "Default" only. A stored effort the
  // chosen model no longer lists (saved under an older catalog or a route
  // that never supported it) stays visible but disabled until a real choice
  // replaces it; the host router also demotes it at dispatch time.
  const supported = efforts ?? []
  const stored = choice?.reasoningEffort ?? ''
  const stale = stored !== '' && !supported.some((effort) => effort.id === stored)
  const options = [
    { value: '', label: t('effortInherit') },
    ...supported.map((effort) => ({ value: effort.id, label: effort.id })),
    ...stale ? [{ value: stored, label: `${stored} · ${t('effortUnsupported')}`, disabled: true }] : [],
  ]
  return React().createElement(Select, {
    value: choice?.reasoningEffort ?? '',
    options,
    basis: '0 1 8em',
    disabled: choice === null,
    onChange: (effort) => onChange(effort === '' ? undefined : effort),
  })
}

/** Invocation-frequency pill: label from the locale, tone by level (strong→dim). */
function FrequencyBadge(props) {
  const { t, role } = props
  const level = ROLE_FREQ[role] ?? 'low'
  const tone = level === 'high'
    ? 'var(--dsw-alias-label-primary)'
    : level === 'medium'
      ? 'var(--dsw-alias-label-secondary)'
      : 'var(--dsw-alias-label-tertiary)'
  return React().createElement('span', {
    style: {
      alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: 5,
      borderRadius: 999, padding: '0 8px', fontSize: 11, lineHeight: '16px',
      background: 'var(--dsw-alias-bg-module-platform)',
      color: 'var(--dsw-alias-label-secondary)',
    },
  },
    React().createElement('span', {
      style: { width: 6, height: 6, borderRadius: 999, background: tone, flex: 'none' },
    }),
    t(`roleFreq.${role}`))
}

function RoleRow(props) {
  const { t, role, fields, catalog, stage } = props
  const models = []
  for (const provider of catalog.providers) {
    for (const model of provider.models) {
      models.push({
        value: `${provider.id}::${model.id}`,
        label: `${provider.name} · ${model.name}`,
        efforts: model.efforts,
      })
    }
  }
  // Find the currently chosen model's supported effort surfaces so the effort
  // select lists what that exact route accepts (a model that doesn't support
  // "high" must not offer it).
  const modelByKey = new Map(models.map((model) => [model.value, model]))
  // Providers the ready catalog actually listed. A stored model one of them
  // does not list is a route the adapter refuses (UNKNOWN_MODEL, issue #22);
  // a provider absent from the catalog is not judged — its listing may have
  // failed, which the card cannot tell apart from an unknown model.
  const listedProviders = new Map(catalog.providers.map((provider) => [provider.id, provider.name]))
  const renderSlot = (slot) => {
    const field = `${role}${slot}`
    const state = fields[field]
    const choice = state.choice
    const chosenModel = choice === null
      ? undefined
      : modelByKey.get(choiceKey(choice))
    // Name what clearing the field falls back to. `inherited` is the resolved
    // value (schema defaults, then the plugin's composition base), so a role
    // the plugin ships a default for says so instead of reading as empty.
    const placeholder = slot === 'Fallback' ? t('none') : t('inherit')
    const inheritLabel = state.inherited === null
      ? placeholder
      : `${placeholder} · ${state.inherited.model}`
    // Without its own option the select shows "Inherit" for a stored value
    // it cannot match, hiding a broken override behind the placeholder.
    const undeclared = choice !== null && chosenModel === undefined
      && catalog.status === 'ready' && listedProviders.has(choice.provider)
    const options = [
      { value: '', label: inheritLabel },
      ...models,
      ...undeclared
        ? [{ value: choiceKey(choice), label: `${listedProviders.get(choice.provider)} · ${choice.model} · ${t('modelUndeclared')}`, disabled: true }]
        : [],
    ]
    const onModel = (key) => {
      if (key === '') {
        stage(field, null)
        return
      }
      const split = key.split('::')
      const next = { provider: split[0], model: split[1] }
      const targetEfforts = modelByKey.get(key)?.efforts ?? []
      // Carry the previous effort forward only when the new model lists that
      // exact level. A model without reasoning metadata takes no explicit
      // effort at all, and an unlisted level is refused at dispatch — both
      // fall back to the model's default level (no explicit effort).
      if (targetEfforts.some((effort) => effort.id === choice?.reasoningEffort)) {
        next.reasoningEffort = choice.reasoningEffort
      }
      stage(field, next)
    }
    const onEffort = (effort) => {
      if (choice === null) return
      const next = { provider: choice.provider, model: choice.model }
      if (effort !== undefined) next.reasoningEffort = effort
      stage(field, next)
    }
    return React().createElement('div', {
      key: slot,
      style: { display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', minWidth: 0 },
    },
      // Without this the two rows are indistinguishable: the only cue was the
      // placeholder option ("Inherit" vs "None"), which says nothing until the
      // select is opened.
      React().createElement('span', {
        style: {
          flex: 'none', minWidth: '4em', fontSize: 12,
          color: 'var(--dsw-alias-label-tertiary)',
        },
      }, t(slot === 'Fallback' ? 'fallback' : 'primary')),
      React().createElement(Select, { value: choiceKey(choice), options, onChange: onModel }),
      React().createElement(EffortSelect, {
        t, choice, onChange: onEffort,
        efforts: chosenModel === undefined ? undefined : chosenModel.efforts,
      }),
      // Presence in the user layer is the override, so the marker and its
      // reset are driven by `overridden`, never by comparing against the base.
      state.overridden
        ? React().createElement('button', {
          type: 'button',
          onClick: () => stage(field, null),
          title: t('reset'),
          style: {
            appearance: 'none', border: '1px solid var(--dsw-alias-border-l2)',
            borderRadius: 999, padding: '0 8px', font: 'inherit', fontSize: 11,
            lineHeight: '18px', cursor: 'pointer', background: 'none',
            color: 'var(--dsw-alias-label-secondary)',
          },
        }, `${t('overridden')} ×`)
        : null)
  }
  return React().createElement('div', {
    style: {
      display: 'grid', gridTemplateColumns: 'minmax(0, 11em) minmax(0, 1fr)', gap: '2px 12px',
      alignItems: 'center', padding: '8px 0', borderTop: '1px solid var(--dsw-alias-border-l2)',
    },
  },
    React().createElement('div', {
      style: { display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 },
    },
      React().createElement('span', {
        style: { fontSize: 13, color: 'var(--dsw-alias-label-secondary)' },
      }, t(`role.${role}`)),
      React().createElement('span', {
        style: { fontSize: 12, lineHeight: 1.45, color: 'var(--dsw-alias-label-tertiary)' },
      }, t(`roleDesc.${role}`)),
      React().createElement(FrequencyBadge, { t, role })),
    React().createElement('div', { style: { display: 'grid', gap: 4, minWidth: 0 } },
      renderSlot('Primary'),
      renderSlot('Fallback')))
}

function RqModelsCard(props) {
  const R = React()
  // `hooks` is the slot framework's RESERVED inject key: the controller supplies
  // `hooks: { rqCard: store }` and the component receives the bound selector
  // hook `useRqCard` instead — the `hooks` key itself never reaches props.
  const snapshot = props.useRqCard((value) => value)
  const t = props.t
  // Only a save writes. Leaving the page drops every staged edit, so the page
  // view discards on unmount and offers no discard control and no unsaved
  // marker (the Plugins page's form contract). The summary view stages
  // nothing, so its unmount drops nothing. `discard` is bound to the one
  // controller this bundle mounts, so the closure the effect captured stays
  // valid however often the renderer re-runs `inject()` (it does on every
  // locale revision); keying the effect on its identity would drop the draft
  // on a language switch instead.
  const view = props.view
  const { discard } = props
  R.useEffect(() => (view === 'page' ? () => { discard() } : undefined), [view])
  // The page asks every entry for two views: `summary` is the one-liner it
  // places under the title, `page` the form with its own save control.
  if (view === 'summary') return t('description')
  // A profile whose host half does not serve the namespace (the router row is
  // off) says so in place of controls nothing would accept.
  if (!snapshot.available) return R.createElement('p', { role: 'status', style: statusStyle }, t('unavailable'))

  const dirty = Object.values(snapshot.fields).some((field) => field.dirty)

  const body = []
  for (const role of ROLES) {
    body.push(RoleRow({
      t, role, fields: snapshot.fields, catalog: snapshot.catalog, stage: props.stage,
    }))
  }

  const controls = []
  if (snapshot.catalog.status === 'failed') {
    controls.push(R.createElement('span', {
      key: 'catalog',
      style: { flex: 1, minWidth: 0, fontSize: 12, color: 'var(--dsw-alias-label-error)' },
    }, t('catalogFailed')))
  }
  if (snapshot.failed !== undefined) {
    controls.push(R.createElement('span', {
      key: 'failed',
      style: { flex: 1, minWidth: 0, fontSize: 12, color: 'var(--dsw-alias-label-error)' },
      // A schema rejection carries schemastery's own message (the Host's
      // validator, rehydrated here); only the write failure is generic.
    }, snapshot.failed === 'write' ? t('failed') : `${t('invalid')}: ${snapshot.failed}`))
  }
  controls.push(R.createElement('button', {
    key: 'save',
    type: 'button',
    onClick: props.save,
    disabled: snapshot.saving || !snapshot.writable || !dirty,
    style: {
      ...saveStyle,
      ...(snapshot.saving || !snapshot.writable || !dirty ? { opacity: 0.4, cursor: 'default' } : {}),
    },
  }, t('save')))

  return R.createElement('div', { style: formStyle, 'data-rq-models': '' },
    R.createElement('div', { style: sectionHeadStyle },
      R.createElement('h4', { style: sectionTitleStyle }, t('title')),
      R.createElement('span', { style: cardDescriptionStyle }, t('description'))),
    ...body,
    R.createElement('div', { style: footerStyle }, ...controls))
}

function apply(ctx) {
  ctx.effect(() => ctx.locale.register(CARD_KEY, copy), 'rq-model-router: card dictionaries')
  const controller = new RqModelsCardController(ctx)
  ctx.effect(() => {
    void controller.load()
  }, 'rq-model-router: catalog load')
  // The bundle's configuration entry: the Plugins page renders it on this
  // bundle's page, looked up by the package name. (The Settings-tab plugin
  // card slot this entry once used is retired on 0.1.6 — a registration
  // there renders nowhere, silently.)
  ctx.slots.inject('plugins.bundle.config', () => ctx.slots.register(
    {
      name: 'plugins.bundle.config',
      key: BUNDLE,
      locale: CARD_KEY,
      inject: () => controller.inject(),
    },
    (props) => RqModelsCard({ ...props, t: ctx.locale.bind(CARD_KEY) }),
  ))
}

return { apply, inject }
} })
