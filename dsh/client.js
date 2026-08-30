// RigorQuant model router — browser half.
//
// One card in the Plugins settings tab, keyed by the `rigorquant-models`
// settings namespace this package's host half serves. Each role row stages an
// explicit primary override (model + reasoning effort) and a per-role fallback
// choice; "inherit" clears the user layer for that field so the native
// tool-subagent default (fixed-tier roles) or the parent/session route (root and
// inherit roles) governs again. The last saved selection is the persistent one:
// it lives in the settings user layer, not in this page's state.
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

const CARD_KEY = 'rigorquant-models'
const ROLES = ['root', 'explorer', 'novel', 'oracle', 'adversary', 'lit-line', 'lit-adversary', 'doc-adversary']
const SLOTS = ['Primary', 'Fallback']
const EFFORTS = ['off', 'high', 'max']
// Invocation frequency per role: the badge tone follows the level, the label
// comes from the locale copy (`roleFreq.<role>`).
const ROLE_FREQ = {
  root: 'high', explorer: 'high', novel: 'low', oracle: 'medium',
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
// seam's. Resolved per-controller for dual-version compatibility: DSH
// >= 0.1.1-rc.2 folds these helpers into the `settingsSchema` service
// (@deepseek-ai/dsh-client-ui-settings, renames rehydrateSchema->rehydrate and
// validateDraft->validate, and deletes the standalone package); DSH
// <= 0.1.0-rc.8 ships them as @deepseek-ai/dsh-client-schema-form. See
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

// `remote` is the 0.1.2 typed Host RPC carrier. The settings card uses its
// canonical session.modelCatalog endpoint rather than the removed
// connection.api.llm.models compatibility facade.
const inject = ['slots', 'locale', 'remote', 'settingsScope']

const copy = {
  en: {
    title: 'RigorQuant model routing',
    description: 'Per-role model overrides and fallbacks for RigorQuant sessions. Native tool defaults supply oracle and adversary; root follows the chatbox picker, and other roles inherit their session model.',
    inherit: 'Inherit',
    none: 'None',
    effortInherit: 'Default',
    save: 'Save',
    discard: 'Discard',
    expand: 'Expand',
    collapse: 'Collapse',
    pending: 'Unsaved',
    primary: 'Primary',
    fallback: 'Fallback',
    overridden: 'Overridden',
    reset: 'Clear this override',
    invalid: 'Rejected by the settings schema',
    failed: 'Save rejected — staged edits kept',
    catalogFailed: 'Model catalog unavailable — check connection',
    'role.root': 'Root orchestrator',
    'role.explorer': 'Explorer (method track)',
    'role.novel': 'Explorer (novelty isolation)',
    'role.oracle': 'Ground-truth oracle',
    'role.adversary': 'Adversary',
    'role.lit-line': 'Literature line',
    'role.lit-adversary': 'Literature adversary',
    'role.doc-adversary': 'Document adversary',
    'roleDesc.root': 'Runs the whole study: plans, delegates to every role, checkpoints, and synthesizes.',
    'roleDesc.explorer': 'Proposes candidate methods and routes with exact statements; spawned in parallel batches at each proposal stage.',
    'roleDesc.novel': 'Derives from the problem statement only — no prior context, no web. The novelty-isolation lane for critical routes.',
    'roleDesc.oracle': 'Re-derives closed forms, invariants, and bounds from first principles, twice by different means.',
    'roleDesc.adversary': 'Audits candidate methods and the checks themselves; eliminates routes only by concrete counterexample.',
    'roleDesc.lit-line': 'Traverses one research line (backward/forward citations) and writes a bounded dossier.',
    'roleDesc.lit-adversary': 'Independently re-retrieves and verifies load-bearing literature claims (validity and freshness).',
    'roleDesc.doc-adversary': 'Audits finished deliverables for self-completeness: every jargon term, symbol, and abbreviation used is defined.',
    'roleFreq.root': 'Frequent',
    'roleFreq.explorer': 'Frequent',
    'roleFreq.novel': 'Rare',
    'roleFreq.oracle': 'Common',
    'roleFreq.adversary': 'Common',
    'roleFreq.lit-line': 'Rare',
    'roleFreq.lit-adversary': 'Rare',
    'roleFreq.doc-adversary': 'Rare',
  },
  zh: {
    title: 'RigorQuant 角色模型路由',
    description: '为 RigorQuant 会话配置每个角色的模型覆盖与回退。oracle 与 adversary 使用原生工具默认值；root 跟随聊天框选择器，其他选择“继承”的角色沿用会话模型。',
    inherit: '继承',
    none: '无',
    effortInherit: '默认',
    save: '保存',
    discard: '放弃',
    expand: '展开',
    collapse: '收起',
    pending: '未保存',
    primary: '主选择',
    fallback: '回退',
    overridden: '已覆盖',
    reset: '清除此覆盖',
    invalid: '未通过设置模式校验',
    failed: '保存被拒绝——已保留未写入的修改',
    catalogFailed: '模型目录不可用——请检查连接',
    'role.root': '根编排者',
    'role.explorer': '探索者（方法线）',
    'role.novel': '探索者（新颖性隔离）',
    'role.oracle': '真值预言机',
    'role.adversary': '对抗审计',
    'role.lit-line': '文献主线',
    'role.lit-adversary': '文献对抗',
    'role.doc-adversary': '文档对抗',
    'roleDesc.root': '运行整个研究：规划、向各角色派发、检查点与综合。',
    'roleDesc.explorer': '提出候选方法与路径（含精确陈述），在每个提案阶段以并行批次派出。',
    'roleDesc.novel': '仅基于问题陈述推导——无前序上下文、无网络。关键路径的新颖性隔离通道。',
    'roleDesc.oracle': '从第一性原理重新推导闭式解、不变量与界，以两种不同方式各做一次。',
    'roleDesc.adversary': '审计候选方法与检查本身；仅以具体反例消除路径。',
    'roleDesc.lit-line': '遍历一条研究线（前向/后向引用）并产出有界档案。',
    'roleDesc.lit-adversary': '独立重新检索并核验关键文献论断（有效性与时效性）。',
    'roleDesc.doc-adversary': '审计最终交付物的自足性：所用的每个专业术语、符号与缩写都应有定义。',
    'roleFreq.root': '频繁',
    'roleFreq.explorer': '频繁',
    'roleFreq.novel': '少见',
    'roleFreq.oracle': '常见',
    'roleFreq.adversary': '常见',
    'roleFreq.lit-line': '少见',
    'roleFreq.lit-adversary': '少见',
    'roleFreq.doc-adversary': '少见',
  },
}

// Card chrome. `settings.plugin.item` renders its entries into a <ul>, so a
// card MUST be an <li> — a bare <div> lands outside the card frame, which is
// what "showing at root level" looks like. PluginCard itself is exported as a
// type only and lives behind the bundle purity gate, so the chrome is restated
// here against the same `--dsw-alias-*` tokens the built-in cards use.
const cardStyle = (open) => ({
  listStyle: 'none',
  overflow: 'hidden',
  border: '1px solid var(--dsw-alias-border-l2)',
  borderRadius: 12,
  background: open ? 'var(--dsw-alias-bg-layer-2)' : 'var(--dsw-alias-bg-layer-3)',
  borderColor: open ? 'var(--dsw-alias-label-dimmed)' : 'var(--dsw-alias-border-l2)',
})
const headerStyle = {
  boxSizing: 'border-box', width: '100%', appearance: 'none', border: 0,
  background: 'none', font: 'inherit', color: 'inherit', textAlign: 'left',
  cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12,
  padding: '14px 16px', borderRadius: 12,
}
const headTextStyle = { flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }
const nameStyle = { fontSize: 15, fontWeight: 600, lineHeight: 1.4, color: 'var(--dsw-alias-label-primary)' }
const cardDescriptionStyle = { fontSize: 13, lineHeight: 1.5, color: 'var(--dsw-alias-label-tertiary)' }
const pendingStyle = {
  flex: 'none', borderRadius: 999, padding: '1px 8px', fontSize: 11, lineHeight: '17px',
  fontWeight: 500, whiteSpace: 'nowrap',
  background: 'var(--dsw-alias-bg-module-platform)', color: 'var(--dsw-alias-label-secondary)',
}
const bodyStyle = { borderTop: '1px solid var(--dsw-alias-border-l2)', margin: '0 16px', paddingBottom: 8 }
const footerStyle = {
  display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8,
  padding: '12px 0 4px', borderTop: '1px solid var(--dsw-alias-border-l2)',
}
const buttonBase = {
  appearance: 'none', border: '1px solid transparent', borderRadius: 8,
  padding: '5px 14px', font: 'inherit', fontSize: 13, lineHeight: 1.5, cursor: 'pointer',
}
const discardStyle = {
  ...buttonBase, borderColor: 'var(--dsw-alias-border-l2)', background: 'none',
  color: 'var(--dsw-alias-label-secondary)',
}
const saveStyle = {
  ...buttonBase, background: 'var(--dsw-alias-label-primary)', color: 'var(--dsw-alias-bg-layer-3)',
}

/** Disclosure chevron, drawn inline: the icon set is a platform module whose
 *  export names this package cannot verify at build time (it has no build). */
function Chevron(props) {
  return React().createElement('svg', {
    width: 14, height: 14, viewBox: '0 0 14 14', 'aria-hidden': 'true',
    style: {
      flex: 'none', color: 'var(--dsw-alias-label-tertiary)',
      transition: 'transform .16s', transform: props.open ? 'rotate(180deg)' : 'none',
    },
  }, React().createElement('path', {
    d: 'M3.5 5.25 7 8.75l3.5-3.5', fill: 'none', stroke: 'currentColor',
    strokeWidth: 1.5, strokeLinecap: 'round', strokeLinejoin: 'round',
  }))
}


class RqModelsCardController {
  constructor(ctx) {
    this.ctx = ctx
    this.scope = ctx.settingsScope.bind({ namespace: CARD_KEY })
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
  }

  /**
   * The settings draft model, dual-version:
   * - DSH >= 0.1.1-rc.2 folds it into the `settingsSchema` service
   *   (@deepseek-ai/dsh-client-ui-settings), renaming rehydrateSchema->rehydrate
   *   and validateDraft->validate and DELETING the standalone package;
   * - DSH <= 0.1.0-rc.8 ships it as @deepseek-ai/dsh-client-schema-form.
   * Prefer the service (optional read; absent on older harnesses); fall back
   * to the legacy module so one build runs on both. The path helpers keep
   * their names on both surfaces.
   */
  schemaForm() {
    const service = this.ctx.get('settingsSchema')
    if (service !== undefined) {
      return {
        rehydrateSchema: (serialized) => service.rehydrate(serialized),
        validateDraft: (schema, draft) => service.validate(schema, draft),
        getPath: (value, path) => service.getPath(value, path),
        hasPath: (value, path) => service.hasPath(value, path),
        setPath: (root, path, value) => service.setPath(root, path, value),
        deletePath: (root, path) => service.deletePath(root, path),
      }
    }
    return require('@deepseek-ai/dsh-client-schema-form')
  }

  async load() {
    await Promise.all([this.loadCatalog(), this.loadSchema()])
    this.publish()
  }

  async loadCatalog() {
    try {
      // DSH 0.1.2's official catalog seam. `connection.api.llm.models` was an
      // older compatibility facade and is absent from the current connection
      // handle, which made this card report a false connection failure.
      const response = await this.ctx.get('remote')?.session?.modelCatalog()
      if (response === undefined) throw new Error('session model catalog remote unavailable')
      if (!response.ok) throw new Error(`${response.error.code}: ${response.error.message}`)
      const providers = (response.value.groups ?? []).map((group) => ({
        id: group.id,
        name: group.name ?? group.id,
        models: (group.models ?? []).map((model) => ({ id: model.id, name: model.name ?? model.id })),
      }))
      this.catalog = { status: 'ready', providers }
    } catch {
      this.catalog = { status: 'failed', providers: [] }
    }
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
      const response = await this.ctx.get('remote')?.settings?.describe()
      if (response === undefined || !response.ok) return
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
    let landed = true
    for (const operation of operations) {
      try {
        await operation()
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
  }, option.label)))
}

function EffortSelect(props) {
  const { t, choice, onChange } = props
  const options = [
    { value: '', label: t('effortInherit') },
    ...EFFORTS.map((effort) => ({ value: effort, label: effort })),
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
      models.push({ value: `${provider.id}::${model.id}`, label: `${provider.name} · ${model.name}` })
    }
  }
  const renderSlot = (slot) => {
    const field = `${role}${slot}`
    const state = fields[field]
    const choice = state.choice
    // Name what clearing the field falls back to. `inherited` is the resolved
    // value (schema defaults, then the plugin's composition base), so a role
    // the plugin ships a default for says so instead of reading as empty.
    const placeholder = slot === 'Fallback' ? t('none') : t('inherit')
    const inheritLabel = state.inherited === null
      ? placeholder
      : `${placeholder} · ${state.inherited.model}`
    const options = [
      { value: '', label: inheritLabel },
      ...models,
    ]
    const onModel = (key) => {
      if (key === '') {
        stage(field, null)
        return
      }
      const split = key.split('::')
      const next = { provider: split[0], model: split[1] }
      if (typeof choice?.reasoningEffort === 'string' && choice.reasoningEffort !== '') next.reasoningEffort = choice.reasoningEffort
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
      React().createElement(EffortSelect, { t, choice, onChange: onEffort }),
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
  const [open, setOpen] = R.useState(false)
  const t = props.t
  // A deployment that does not serve this namespace should show no trace of the
  // plugin, rather than a card the user cannot act on.
  if (!snapshot.available) return null

  const dirty = Object.values(snapshot.fields).some((field) => field.dirty)
  const title = t('title')

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
    key: 'discard',
    type: 'button',
    onClick: props.discard,
    disabled: snapshot.saving || !dirty,
    style: { ...discardStyle, ...(snapshot.saving || !dirty ? { opacity: 0.4, cursor: 'default' } : {}) },
  }, t('discard')))
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

  const header = R.createElement('button', {
    type: 'button',
    style: headerStyle,
    'aria-expanded': open,
    'aria-label': `${t(open ? 'collapse' : 'expand')}: ${title}`,
    onClick: () => { setOpen(!open) },
  },
    R.createElement('span', { style: headTextStyle },
      R.createElement('span', { style: nameStyle }, title),
      R.createElement('span', { style: cardDescriptionStyle }, t('description'))),
    // Carried on the header so a collapsed card still says it holds edits.
    dirty ? R.createElement('span', { style: pendingStyle }, t('pending')) : null,
    R.createElement(Chevron, { open }))

  return R.createElement('li', { style: cardStyle(open) },
    header,
    open
      ? R.createElement('div', { style: bodyStyle },
        ...body,
        R.createElement('div', { style: footerStyle }, ...controls))
      : null)
}

function apply(ctx) {
  ctx.effect(() => ctx.locale.register(CARD_KEY, copy), 'rq-model-router: card dictionaries')
  const controller = new RqModelsCardController(ctx)
  ctx.effect(() => {
    void controller.load()
  }, 'rq-model-router: catalog load')
  ctx.slots.inject('settings.plugin.item', () => ctx.slots.register(
    {
      name: 'settings.plugin.item',
      key: CARD_KEY,
      locale: CARD_KEY,
      inject: () => controller.inject(),
    },
    (props) => RqModelsCard({ ...props, t: ctx.locale.bind(CARD_KEY) }),
  ))
  applyActivityOverlay(ctx)
}

// ---------------------------------------------------------------- activity
// The team-activity floater (design adapted from dsh-agent-teams — see
// README "The team, live"). Registered into the root-scoped `shell.overlay`
// list: a pill vertically centered on the main window's right edge, expanded
// into a live panel whenever one or more RigorQuant labs are running. Data
// comes from the host half (dsh/activity.js) by polling
// /plugins/dsh-rigorquant/activity — a JSON snapshot of role agents, their
// status and last actions, plus the loop stage. Every color below is a
// --dsw-alias token, so the panel follows the shell's own theme.

const ACTIVITY_NS = 'rigorquant-activity'
const ACTIVITY_URL = '/plugins/dsh-rigorquant/activity'
const POLL_MS = 2000

/** role → display label (mirrors the host ROLE_DEF; the client bundle is standalone). */
const ROLE_DEF_CLIENT = {
  root: { label: 'Orchestrator', avatar: 'avatar-orchestrator.png' },
  explorer: { label: 'Explorer', avatar: 'avatar-explorer.png' },
  novel: { label: 'Explorer', avatar: 'avatar-explorer.png' },
  oracle: { label: 'Oracle', avatar: 'avatar-oracle.png' },
  adversary: { label: 'Adversary', avatar: 'avatar-adversary.png' },
  'lit-line': { label: 'Literature', avatar: 'avatar-literature.png' },
  'lit-adversary': { label: 'Literature', avatar: 'avatar-literature-adversary.png' },
  'doc-adversary': { label: 'Document', avatar: 'avatar-document-adversary.png' },
}

const activityCopy = {
  en: {
    title: 'RigorQuant Activity',
    collapse: 'Collapse',
    expand: 'Expand',
    working: 'working',
    idle: 'idle',
    members: 'members',
    feed: 'activity',
    empty: 'No RigorQuant session running.',
    live: 'live',
    credit: 'Design adapted from dsh-agent-teams © NanmiCoder (MIT)',
    now: 'now',
    history: 'history',
    hideHistory: 'hide',
    pending: 'pending',
    float: 'float',
    dock: 'dock',
  },
  zh: {
    title: 'RigorQuant 活动',
    collapse: '收起',
    expand: '展开',
    working: '执行中',
    idle: '空闲',
    members: '成员',
    feed: '动态',
    empty: '当前没有 RigorQuant 会话。',
    live: '实时',
    credit: '设计改编自 dsh-agent-teams © NanmiCoder (MIT)',
    now: '刚刚',
    history: '条历史',
    hideHistory: '收起',
    pending: '待命',
    float: '浮动',
    dock: '停靠',
  },
}

/** Set once when the first live lab appears, so the panel opens itself. */
let activityAutoExpanded = false
/** The user's collapse decision wins until the page reloads. */
let activityCollapsed = true
/** Lab ids whose feed history is expanded; default shows only the latest. */
const activityFeedOpen = new Set()
let activityStore = null

/** One shared mutable state the store publishes (never handed out raw). */
const activityState = {
  status: 'idle', labs: [], anchorRight: null, currentSessionId: null,
  panelLayout: null, panelBounds: null,
}

function snapshotStore() {
  if (activityStore === null) {
    activityStore = createStore({
      status: activityState.status, labs: [], anchorRight: null, currentSessionId: null,
      panelLayout: null, panelBounds: null,
    })
  }
  return activityStore
}

const publishActivity = () => snapshotStore().set({ ...activityState, labs: activityState.labs })

/**
 * Horizontal dock for the floater: the RIGHT EDGE of the active conversation
 * column, measured the same way dsh-agent-teams does — against the
 * `[data-shell-overlay]` layer and the `[data-phase='active']` element that
 * ui-layout/ui-conversation publish. The left workspace rail and right-docked
 * panels (dsh-better-sidebar's task view) both stay clear: when such a panel
 * opens and the conversation column shrinks, the ResizeObserver re-measures
 * and the pill follows. Best-effort by design: without a measurable column it
 * falls back to the viewport edge.
 */
const PANEL_DOCK_RIGHT = 18

function sameBounds(left, right) {
  if (left === null || right === null) return left === right
  return left.width === right.width && left.height === right.height && left.anchorRight === right.anchorRight
}

/** Measure the shell-overlay box and the active conversation's right edge,
 * publishing both the pill's `right` offset and the dock/floating bounds the
 * panel geometry resolves against. Best-effort: falls back to the viewport. */
function measureAnchorRight() {
  try {
    if (typeof document === 'undefined' || typeof document.querySelector !== 'function') return
    const overlay = document.querySelector('[data-shell-overlay]')
    if (overlay === null || overlay === undefined || typeof overlay.getBoundingClientRect !== 'function') return
    const overlayRect = overlay.getBoundingClientRect()
    const conversation = document.querySelector("[data-phase='active']")
    let right = PANEL_DOCK_RIGHT
    let anchorRight = overlayRect.width
    if (conversation !== null && conversation !== undefined
      && typeof conversation.getBoundingClientRect === 'function') {
      const conversationRect = conversation.getBoundingClientRect()
      anchorRight = Math.min(Math.max(conversationRect.right - overlayRect.left, 0), overlayRect.width)
      right = Math.round(overlayRect.width - anchorRight + PANEL_DOCK_RIGHT)
    }
    const bounds = { width: overlayRect.width, height: overlayRect.height, anchorRight }
    let changed = false
    if (right !== activityState.anchorRight) { activityState.anchorRight = right; changed = true }
    if (!sameBounds(activityState.panelBounds, bounds)) { activityState.panelBounds = bounds; changed = true }
    if (changed) publishActivity()
  } catch {
    // Layout probing is best-effort; the viewport fallback still renders.
  }
}

function persistPanelLayout(layout) {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(PANEL_LAYOUT_STORAGE_KEY, JSON.stringify(layout))
    }
  } catch {
    // Storage may be unavailable (private mode, strict sandbox).
  }
}

function applyPanelLayout(layout) {
  activityState.panelLayout = layout
  publishActivity()
  updatePanelShift()
}

/** Dodge the main text area: while the expanded panel is docked-open, make
 * the active conversation column yield width so the panel never covers text. */
function updatePanelShift() {
  try {
    const root = typeof document !== 'undefined' ? document.documentElement : null
    if (root === null) return
    const compact = (activityState.panelBounds?.width ?? window.innerWidth ?? Infinity) <= PANEL_COMPACT_BREAKPOINT
    const expanded = !activityCollapsed
    const docked = activityState.panelLayout?.mode === 'docked'
    if (expanded && docked && !compact) {
      const width = activityState.panelLayout?.width ?? PANEL_DEFAULT_WIDTH
      root.setAttribute(PANEL_OPEN_ATTRIBUTE, '')
      root.style.setProperty(PANEL_SHIFT_PROPERTY, `${width + PANEL_CONVERSATION_GAP + 18}px`)
    } else {
      root.removeAttribute(PANEL_OPEN_ATTRIBUTE)
      root.style.removeProperty(PANEL_SHIFT_PROPERTY)
    }
  } catch {
    // Best-effort: if the root is unavailable there is nothing to shift.
  }
}

function setActivityCollapsed(collapsed) {
  activityCollapsed = collapsed
  publishActivity()
  updatePanelShift()
}

/** Walk the headers/resize handles: bound the gesture to the current layout. */
function beginPanelGesture(kind, edge, event, layout, bounds) {
  if (typeof window === 'undefined') return
  const startX = event.clientX
  const startY = event.clientY
  const onMove = (moveEvent) => {
    const dx = moveEvent.clientX - startX
    const dy = moveEvent.clientY - startY
    applyPanelLayout(kind === 'move'
      ? movePanelLayout(layout, dx, dy, bounds)
      : resizePanelLayout(layout, edge, dx, dy, bounds))
  }
  const end = () => {
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', end)
    window.removeEventListener('pointercancel', end)
    persistPanelLayout(activityState.panelLayout)
    updatePanelShift()
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', end, { once: true })
  window.addEventListener('pointercancel', end, { once: true })
}

function ago(ms) {
  if (typeof ms !== 'number' || ms === 0) return ''
  const delta = Date.now() - ms
  if (delta < 60_000) return `${Math.max(1, Math.round(delta / 1000))}s`
  if (delta < 3_600_000) return `${Math.round(delta / 60_000)}m`
  return `${Math.round(delta / 3_600_000)}h`
}

function startActivityPoller(ctx) {
  // The web shell, and nothing else: the probe and webless hosts have no
  // fetch/interval, and the floater is only meaningful in a browser anyway.
  if (typeof window === 'undefined'
    || typeof window.fetch !== 'function'
    || typeof window.setInterval !== 'function') {
    return
  }
  const store = snapshotStore()
  // Restore the persisted panel layout, then inject the rules that make the
  // conversation column yield width while the panel is docked-open (the dodge).
  try {
    if (activityState.panelLayout === null) {
      const raw = typeof localStorage !== 'undefined' ? localStorage.getItem(PANEL_LAYOUT_STORAGE_KEY) : null
      activityState.panelLayout = parsePanelLayout(raw)
    }
  } catch {
    activityState.panelLayout = DEFAULT_PANEL_LAYOUT
  }
  if (typeof document !== 'undefined' && typeof document.head !== 'undefined') {
    const shiftCss = document.createElement('style')
    shiftCss.setAttribute('data-rq-panel-shift', '')
    shiftCss.textContent = `html[${PANEL_OPEN_ATTRIBUTE}] [data-phase='active']{padding-right:var(${PANEL_SHIFT_PROPERTY});}`
    document.head.appendChild(shiftCss)
    ctx.effect(() => {
      const parent = shiftCss.parentNode
      if (parent !== null && parent !== undefined && typeof parent.removeChild === 'function') parent.removeChild(shiftCss)
    }, 'rq-activity: dodge css')
  }
  updatePanelShift()
  const tick = async () => {
    measureAnchorRight()
    // Re-check the optional sessions service: it may activate after this
    // bundle materialized (see the binding note above).
    bindSessionList()
    if (document.hidden) return
    try {
      const response = await window.fetch(ACTIVITY_URL, { cache: 'no-store' })
      if (!response.ok) return
      const next = await response.json()
      const labs = Array.isArray(next?.labs) ? next.labs : []
      if (labs.length > 0 && !activityAutoExpanded) {
        activityAutoExpanded = true
        activityCollapsed = false
      }
      activityState.status = 'ready'
      activityState.labs = labs
      publishActivity()
    } catch {
      // Transient: the host route may be absent in a webless profile.
    }
  }
  void tick()
  measureAnchorRight()
  const id = window.setInterval(() => { void tick() }, POLL_MS)
  // The floater follows the CURRENT session (same as dsh-agent-teams): only
  // the lab owned by the session open in the conversation view is shown, and
  // only while that session is a RigorQuant one (labs exist only for those).
  // `sessions` is read OPTIONALLY and bound lazily: this bundle materializes
  // immediately (`dsh.client.immediately`), which on DSH 0.1.2's batched boot
  // can precede the session controller's activation — sampling
  // ctx.get('sessions') once at startup then left the pill permanently
  // unscoped (currentSessionId null → labs filtered to none → no pill). Bind
  // on every tick until the service exists, and re-bind if its instance is
  // replaced.
  let sessionList = null
  let unsubscribeSessionList = null
  const syncCurrentSession = () => {
    try {
      const next = typeof sessionList?.getSnapshot === 'function'
        ? sessionList.getSnapshot().current
        : null
      if (next !== activityState.currentSessionId) {
        activityState.currentSessionId = next ?? null
        publishActivity()
      }
    } catch {
      // The sessions feed is a best-effort scope, not a hard dependency.
    }
  }
  const bindSessionList = () => {
    const list = ctx.get('sessions')?.list
    if (list === sessionList) return
    if (typeof unsubscribeSessionList === 'function') unsubscribeSessionList()
    sessionList = typeof list?.subscribe === 'function' ? list : null
    unsubscribeSessionList = null
    if (sessionList !== null) {
      syncCurrentSession()
      unsubscribeSessionList = sessionList.subscribe(syncCurrentSession)
    }
  }
  bindSessionList()
  ctx.effect(() => () => {
    if (typeof unsubscribeSessionList === 'function') unsubscribeSessionList()
  }, 'rq-activity: current-session listener')
  if (typeof window.addEventListener === 'function') {
    window.addEventListener('resize', measureAnchorRight)
    ctx.effect(() => () => window.removeEventListener('resize', measureAnchorRight),
      'rq-activity: anchor resize listener')
  }
  // Follow the conversation column the instant it resizes (a right dock
  // opening, the details column, window reflow) instead of waiting a poll.
  const observer = typeof window.ResizeObserver === 'function'
    ? new window.ResizeObserver(() => measureAnchorRight())
    : null
  if (observer !== null && typeof document !== 'undefined' && typeof document.querySelector === 'function') {
    const overlay = document.querySelector('[data-shell-overlay]')
    const conversation = document.querySelector("[data-phase='active']")
    if (overlay !== null) observer.observe(overlay)
    if (conversation !== null) observer.observe(conversation)
  }
  ctx.effect(() => () => {
    if (observer !== null) observer.disconnect()
    window.clearInterval(id)
  }, 'rq-activity: poller')
}

function ActivityRow(props) {
  const R = React()
  const { def, caption } = props
  const size = def?.avatarWidth ?? 28
  const img = def?.avatar !== null && def?.avatar !== undefined
    ? R.createElement('img', {
      src: `/plugins/dsh-rigorquant/avatar/${def.avatar}`,
      alt: '',
      style: {
        width: size, height: Math.round(size * 0.75),
        objectFit: 'cover', objectPosition: 'top center',
        borderRadius: 6, flex: 'none',
        background: 'var(--dsw-alias-bg-module-platform)',
      },
    })
    : null
  const right = typeof props.lastAt === 'number' && props.lastAt !== 0
    ? R.createElement('span', {
      style: {
        marginLeft: 'auto', flex: 'none', fontSize: 10,
        color: 'var(--dsw-alias-label-tertiary)',
      },
    }, ago(props.lastAt))
    : null
  return R.createElement('div', {
    style: {
      display: 'flex', alignItems: 'center', gap: 8, minWidth: 0,
      padding: '3px 0',
    },
  },
    img,
    R.createElement('span', {
      style: {
        width: 6, height: 6, borderRadius: 99, flex: 'none',
        background: props.status === 'running'
          ? 'var(--dsw-alias-label-primary)'
          : 'var(--dsw-alias-label-tertiary)',
      },
    }),
    R.createElement('span', { style: { minWidth: 0, flex: 1 } },
      R.createElement('span', {
        style: {
          display: 'block', fontSize: 11.5, fontWeight: 600, lineHeight: 1.35,
          color: 'var(--dsw-alias-label-primary)', whiteSpace: 'nowrap',
          overflow: 'hidden', textOverflow: 'ellipsis',
        },
      }, caption),
      props.lastText
        ? R.createElement('span', {
          style: {
            display: 'block', fontSize: 10.5, lineHeight: 1.4,
            color: 'var(--dsw-alias-label-tertiary)', whiteSpace: 'nowrap',
            overflow: 'hidden', textOverflow: 'ellipsis',
          },
        }, props.lastText)
        : null),
    right)
}

// ---- role pipeline graph -------------------------------------------------
// The RigorQuant preset has no durable task DAG (unlike dsh-agent-teams'
// scheduler), but its eight roles form a fixed handoff pipeline. Render it as
// the same compact dependency graph: columns are stages, nodes are roles
// colored by live status, edges are the role handoffs.

const RQ_NODE_WIDTH = 96
const RQ_NODE_HEIGHT = 28
const RQ_H_GAP = 10
const RQ_LVL_GAP = 44

// Vertical topology: stages stack top-to-bottom (more room vertically than
// horizontally in the panel), each stage spreads its simultaneous roles
// across the width. Nodes are roles; edges are the handoff flow downward.
const RQ_LEVELS = [
  ['root'],
  ['explorer', 'novel', 'lit-line'],
  ['oracle', 'lit-adversary'],
  ['adversary'],
  ['doc-adversary'],
]

const RQ_PIPELINE_EDGES = [
  ['root', 'explorer'], ['root', 'novel'], ['root', 'lit-line'],
  ['explorer', 'oracle'], ['novel', 'oracle'],
  ['oracle', 'adversary'],
  ['lit-line', 'lit-adversary'],
  ['adversary', 'doc-adversary'],
]

// ---- panel geometry ------------------------------------------------------
// Ported from dsh-agent-teams panel-geometry.ts: a docked/floating panel that
// ignores its own size and is resized by dragging its edges, persisted between
// browser sessions. Purely functions of a layout + shell bounds.
const PANEL_DEFAULT_WIDTH = 340
const PANEL_DEFAULT_HEIGHT = 640
const PANEL_MIN_WIDTH = 320
const PANEL_MAX_WIDTH = 640
const PANEL_MIN_HEIGHT = 360
const PANEL_DOCK_TOP = 64
const PANEL_DOCK_BOTTOM = 40
const PANEL_FLOAT_MARGIN = 12
const PANEL_COMPACT_BREAKPOINT = 960
const PANEL_CONVERSATION_GAP = 14
const PANEL_LAYOUT_STORAGE_KEY = 'dsh-rigorquant:panel:v1'
const PANEL_OPEN_ATTRIBUTE = 'data-rq-panel-open'
const PANEL_SHIFT_PROPERTY = '--rq-panel-shift'

const DEFAULT_PANEL_LAYOUT = Object.freeze({
  mode: 'docked', x: 0, y: PANEL_DOCK_TOP,
  width: PANEL_DEFAULT_WIDTH, height: PANEL_DEFAULT_HEIGHT, heightMode: 'auto',
})

const clampValue = (value, minimum, maximum) => Math.min(Math.max(value, minimum), maximum)
const isFiniteNumber = (value) => typeof value === 'number' && Number.isFinite(value)

function parsePanelLayout(value) {
  if (value === null || value === undefined) return DEFAULT_PANEL_LAYOUT
  try {
    const parsed = JSON.parse(value)
    if (typeof parsed !== 'object' || parsed === null) return DEFAULT_PANEL_LAYOUT
    if ((parsed.mode !== 'docked' && parsed.mode !== 'floating')
      || !isFiniteNumber(parsed.x) || !isFiniteNumber(parsed.y)
      || !isFiniteNumber(parsed.width) || !isFiniteNumber(parsed.height)) {
      return DEFAULT_PANEL_LAYOUT
    }
    return {
      mode: parsed.mode, x: parsed.x, y: parsed.y, width: parsed.width, height: parsed.height,
      heightMode: parsed.mode === 'floating' && parsed.heightMode === 'manual' ? 'manual' : 'auto',
    }
  } catch {
    return DEFAULT_PANEL_LAYOUT
  }
}

const compactPanelForBounds = (bounds) => bounds.width <= PANEL_COMPACT_BREAKPOINT
const panelUsesAutoHeight = (layout, bounds) => compactPanelForBounds(bounds) || layout.mode === 'docked' || layout.heightMode === 'auto'

function resolvePanelGeometry(layout, bounds) {
  const boundsWidth = Math.max(1, bounds.width)
  const boundsHeight = Math.max(1, bounds.height)
  if (compactPanelForBounds(bounds)) {
    return {
      ...layout, x: PANEL_FLOAT_MARGIN, y: PANEL_FLOAT_MARGIN,
      width: Math.max(1, boundsWidth - PANEL_FLOAT_MARGIN * 2),
      height: Math.max(1, boundsHeight - PANEL_FLOAT_MARGIN * 2),
    }
  }
  const maximumWidth = Math.max(1, Math.min(PANEL_MAX_WIDTH, boundsWidth - PANEL_FLOAT_MARGIN * 2))
  const minimumWidth = Math.min(PANEL_MIN_WIDTH, maximumWidth)
  const width = clampValue(layout.width, minimumWidth, maximumWidth)
  const maximumHeight = Math.max(1, boundsHeight - PANEL_FLOAT_MARGIN * 2)
  const minimumHeight = Math.min(PANEL_MIN_HEIGHT, maximumHeight)
  if (layout.mode === 'docked') {
    const y = clampValue(PANEL_DOCK_TOP, PANEL_FLOAT_MARGIN, Math.max(PANEL_FLOAT_MARGIN, boundsHeight - minimumHeight - PANEL_FLOAT_MARGIN))
    const availableHeight = Math.max(1, boundsHeight - y - PANEL_DOCK_BOTTOM)
    const height = clampValue(availableHeight, Math.min(minimumHeight, availableHeight), maximumHeight)
    const anchorRight = clampValue(bounds.anchorRight, 0, boundsWidth)
    const maximumX = Math.max(PANEL_FLOAT_MARGIN, boundsWidth - width - PANEL_FLOAT_MARGIN)
    const x = clampValue(anchorRight - PANEL_DOCK_RIGHT - width, PANEL_FLOAT_MARGIN, maximumX)
    return { mode: 'docked', x, y, width, height, heightMode: layout.heightMode }
  }
  const height = clampValue(layout.height, minimumHeight, maximumHeight)
  return {
    mode: 'floating', x: clampValue(layout.x, PANEL_FLOAT_MARGIN, Math.max(PANEL_FLOAT_MARGIN, boundsWidth - width - PANEL_FLOAT_MARGIN)),
    y: clampValue(layout.y, PANEL_FLOAT_MARGIN, Math.max(PANEL_FLOAT_MARGIN, boundsHeight - height - PANEL_FLOAT_MARGIN)),
    width, height, heightMode: layout.heightMode,
  }
}

const floatPanelLayout = (geometry, bounds) => resolvePanelGeometry({ ...geometry, mode: 'floating' }, bounds)
const dockPanelLayout = (layout, bounds) => resolvePanelGeometry({ ...layout, mode: 'docked', heightMode: 'auto' }, bounds)

function movePanelLayout(start, dx, dy, bounds) {
  return resolvePanelGeometry({ ...start, mode: 'floating', x: start.x + dx, y: start.y + dy }, bounds)
}

function resizePanelLayout(start, edge, dx, dy, bounds) {
  if (start.mode === 'docked') {
    if (edge !== 'left') return resolvePanelGeometry(start, bounds)
    return resolvePanelGeometry({ ...start, width: start.width - dx }, bounds)
  }
  const resolved = resolvePanelGeometry(start, bounds)
  const minimumWidth = Math.min(PANEL_MIN_WIDTH, resolved.x + resolved.width - PANEL_FLOAT_MARGIN)
  const minimumHeight = Math.min(PANEL_MIN_HEIGHT, bounds.height - resolved.y - PANEL_FLOAT_MARGIN)
  if (edge === 'left') {
    const right = resolved.x + resolved.width
    const maximumWidth = Math.max(1, Math.min(PANEL_MAX_WIDTH, right - PANEL_FLOAT_MARGIN))
    const width = clampValue(resolved.width - dx, Math.min(minimumWidth, maximumWidth), maximumWidth)
    return { ...resolved, x: right - width, width }
  }
  const maximumHeight = Math.max(1, bounds.height - resolved.y - PANEL_FLOAT_MARGIN)
  const height = clampValue(resolved.height + dy, Math.min(minimumHeight, maximumHeight), maximumHeight)
  if (edge === 'bottom') return { ...resolved, height, heightMode: 'manual' }
  const maximumWidth = Math.max(1, Math.min(PANEL_MAX_WIDTH, bounds.width - resolved.x - PANEL_FLOAT_MARGIN))
  const width = clampValue(resolved.width + dx, Math.min(minimumWidth, maximumWidth), maximumWidth)
  return { ...resolved, width, height, heightMode: 'manual' }
}

/** role → live status: running, idle (present), or pending (not yet spawned). */
function roleStatusOf(lab, role) {
  if (role === 'root') return lab.captain?.status === 'running' ? 'running' : 'idle'
  const members = (lab.members ?? []).filter((member) => member.role === role)
  if (members.length === 0) return 'pending'
  return members.some((member) => member.status === 'running') ? 'running' : 'idle'
}

function RoleGraph(props) {
  const R = React()
  const { lab, t } = props
  const maxLevelNodes = Math.max(...RQ_LEVELS.map((level) => level.length))
  const graphWidth = maxLevelNodes * RQ_NODE_WIDTH + (maxLevelNodes - 1) * RQ_H_GAP
  const graphHeight = (RQ_LEVELS.length - 1) * (RQ_NODE_HEIGHT + RQ_LVL_GAP) + RQ_NODE_HEIGHT
  const positions = new Map()
  for (let levelIndex = 0; levelIndex < RQ_LEVELS.length; levelIndex += 1) {
    const roles = RQ_LEVELS[levelIndex]
    const groupWidth = roles.length * RQ_NODE_WIDTH + (roles.length - 1) * RQ_H_GAP
    const startX = (graphWidth - groupWidth) / 2
    const y = levelIndex * (RQ_NODE_HEIGHT + RQ_LVL_GAP)
    for (let i = 0; i < roles.length; i += 1) {
      positions.set(roles[i], { x: startX + i * (RQ_NODE_WIDTH + RQ_H_GAP), y })
    }
  }
  const edges = RQ_PIPELINE_EDGES.map(([from, to]) => {
    const source = positions.get(from)
    const target = positions.get(to)
    if (source === undefined || target === undefined) return null
    const x1 = source.x + RQ_NODE_WIDTH / 2
    const y1 = source.y + RQ_NODE_HEIGHT
    const x2 = target.x + RQ_NODE_WIDTH / 2
    const y2 = target.y
    const bend = Math.max(10, (y2 - y1) / 2)
    return R.createElement('path', {
      key: `${from}:${to}`,
      d: `M${x1} ${y1}C${x1} ${y1 + bend},${x2} ${y2 - bend},${x2} ${y2}`,
      fill: 'none', stroke: 'var(--dsw-alias-border-l2)', strokeWidth: 1.5,
    })
  }).filter(Boolean)

  const nodes = RQ_LEVELS.flat().map((role) => {
    const status = roleStatusOf(lab, role)
    const def = ROLE_DEF_CLIENT[role]
    const pos = positions.get(role)
    const tone = status === 'running'
      ? 'var(--dsw-alias-state-business-primary)'
      : status === 'idle'
        ? 'var(--dsw-alias-label-secondary)'
        : 'var(--dsw-alias-label-tertiary)'
    return R.createElement('div', {
      key: role,
      'data-role': role,
      'data-status': status,
      title: `${def?.label ?? role} · ${status === 'running' ? t('working') : status === 'idle' ? t('idle') : t('pending')}`,
      style: {
        position: 'absolute', left: pos.x, top: pos.y,
        width: RQ_NODE_WIDTH, height: RQ_NODE_HEIGHT,
        boxSizing: 'border-box', borderRadius: 7, padding: '0 7px',
        display: 'flex', alignItems: 'center', gap: 5,
        fontSize: 10, fontWeight: 600,
        border: `1px solid ${status === 'pending' ? 'var(--dsw-alias-border-l2)' : tone}`,
        background: status === 'pending' ? 'transparent' : 'var(--dsw-alias-bg-layer-2)',
        color: tone,
        whiteSpace: 'nowrap', overflow: 'hidden',
      },
    },
      // The role's docs/figs portrait, so working roles are recognizable.
      R.createElement('img', {
        src: `/plugins/dsh-rigorquant/avatar/${def?.avatar}`,
        alt: '',
        style: {
          flex: 'none', width: 16, height: 16, borderRadius: 4,
          objectFit: 'cover', objectPosition: 'top center',
          background: 'var(--dsw-alias-bg-module-platform)',
          opacity: status === 'pending' ? 0.45 : 1,
        },
      }),
      R.createElement('span', {
        style: { flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' },
      }, def?.label ?? role))
  })

  return R.createElement('div', {
    style: {
      position: 'relative', width: graphWidth, height: graphHeight,
      margin: '6px auto 2px',
    },
  },
    R.createElement('svg', {
      width: graphWidth, height: graphHeight, style: { position: 'absolute', left: 0, top: 0, overflow: 'visible' },
      'aria-hidden': true,
    }, ...edges),
    ...nodes)
}

function ActivityPanel(props) {
  const R = React()
  const t = props.t
  const snapshot = props.useRqActivity((value) => value)
  const currentSessionId = snapshot?.currentSessionId ?? null
  const allLabs = snapshot?.labs ?? []
  // Only the lab relevant to the current session (its own captain session, or
  // one of its subagent transcripts) is shown — never other sessions' labs,
  // and only while the current session is a RigorQuant one (labs exist only
  // for those). Mirrors dsh-agent-teams' captain-session scoping.
  const labs = (() => {
    if (currentSessionId === null || currentSessionId === undefined) return []
    const labBySession = new Map()
    for (const lab of allLabs) {
      labBySession.set(lab.id, lab.id)
      for (const member of lab.members ?? []) labBySession.set(member.sessionId, lab.id)
    }
    const relevant = labBySession.get(currentSessionId)
    return relevant === undefined ? [] : allLabs.filter((lab) => lab.id === relevant)
  })()
  if (labs.length === 0) return null
  if (activityCollapsed) {
    const working = labs.reduce((total, lab) => total + (lab.summary?.working ?? 0), 0)
    return R.createElement('button', {
      type: 'button', 'aria-label': t('expand'),
      onClick: () => setActivityCollapsed(false),
      style: {
        // Vertically centered on the active conversation's right edge (measured
        // against the shell overlay + [data-phase='active']), so right-docked
        // panels and the left workspace rail both stay clear. Absolute — the
        // entry renders inside the shell's own overlay layer.
        position: 'absolute',
        right: typeof snapshot.anchorRight === 'number' ? snapshot.anchorRight : 18,
        top: '50%',
        transform: 'translateY(-50%)',
        zIndex: 9999,
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '7px 12px', borderRadius: 999, cursor: 'pointer',
        border: '1px solid var(--dsw-alias-border-l2)',
        background: 'var(--dsw-alias-bg-layer-2)',
        color: 'var(--dsw-alias-label-primary)',
        fontSize: 12, fontWeight: 600,
        boxShadow: '0 4px 16px rgba(0,0,0,.25)',
      },
    },
      R.createElement('span', {
        style: {
          width: 8, height: 8, borderRadius: 99,
          background: 'var(--dsw-alias-label-primary)',
          animation: 'rq-pulse 1.6s ease-in-out infinite',
        },
      }),
      t('title'),
      R.createElement('span', {
        style: {
          borderRadius: 99, padding: '0 7px', fontSize: 10.5, lineHeight: '16px',
          background: 'var(--dsw-alias-bg-module-platform)',
          color: 'var(--dsw-alias-label-secondary)',
        },
      }, `${working} ${t('working')}`))
  }

  const bodies = labs.map((lab) => {
    const captain = lab.captain
    const rows = [R.createElement(ActivityRow, {
      key: `${lab.id}:captain`,
      def: { avatar: captain?.avatar, avatarWidth: 34 },
      caption: `CAPTAIN · ${captain?.label ?? 'Orchestrator'}`,
      lastText: captain?.lastText ?? '',
      lastAt: captain?.lastAt ?? 0,
      status: captain?.status ?? 'idle',
    })]
    for (const member of lab.members ?? []) {
      // Roster rows show only live agents; the graph (below) paints the full
      // role pipeline from the same roster including just-completed ones.
      if (member.disposed) continue
      rows.push(R.createElement(ActivityRow, {
        key: `${lab.id}:${member.sessionId}`,
        def: { avatar: member.avatar, avatarWidth: 28 },
        caption: `${member.label ?? ''} · ${member.tool ?? ''}`,
        lastText: member.lastText ?? '',
        lastAt: member.lastAt ?? 0,
        status: member.status,
      }))
    }
    const feedItems = lab.feed ?? []
    const feedOpen = activityFeedOpen.has(lab.id)
    const visibleFeed = feedOpen ? feedItems : feedItems.slice(0, 1)
    const feed = visibleFeed.map((item) => R.createElement('div', {
      key: `${lab.id}:${item.t}:${item.sessionId}:${item.kind}`,
      style: {
        display: 'flex', gap: 6, alignItems: 'baseline',
        fontSize: 10.5, lineHeight: 1.4, color: 'var(--dsw-alias-label-secondary)',
      },
    },
      R.createElement('span', {
        style: { flex: 'none', color: 'var(--dsw-alias-label-tertiary)', fontSize: 9.5 },
      }, ago(item.t)),
      R.createElement('span', {
        style: { flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' },
      },
        item.kind === 'tool'
          ? R.createElement('span', {
            style: { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 10 },
          }, item.text)
          : item.text)))
    return R.createElement('div', {
      key: lab.id,
      style: { padding: '8px 0', borderTop: '1px solid var(--dsw-alias-border-l2)' },
    },
      R.createElement('div', {
        style: { display: 'flex', alignItems: 'baseline', gap: 8 },
      },
        R.createElement('span', {
          style: {
            fontSize: 12, fontWeight: 600, color: 'var(--dsw-alias-label-primary)',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          },
        }, lab.title ?? `session ${String(lab.id).slice(0, 8)}`),
        R.createElement('span', {
          style: {
            flex: 'none', borderRadius: 99, padding: '0 7px', fontSize: 10,
            lineHeight: '15px', background: 'var(--dsw-alias-bg-module-platform)',
            color: 'var(--dsw-alias-label-secondary)',
          },
        }, lab.stage),
        R.createElement('span', {
          style: {
            marginLeft: 'auto', flex: 'none', fontSize: 10,
            color: 'var(--dsw-alias-label-tertiary)',
          },
        }, `${lab.summary?.working ?? 0} ${t('working')} · ${lab.summary?.idle ?? 0} ${t('idle')}`)),
      R.createElement(RoleGraph, {
        key: `${lab.id}:pipeline`,
        lab,
        t,
      }),
      rows,
      R.createElement('div', {
        style: {
          display: 'grid', gap: 3, marginTop: 4, paddingTop: 6,
          borderTop: '1px dashed var(--dsw-alias-border-l2)',
        },
      },
        feedItems.length > 1
          ? R.createElement('button', {
            type: 'button',
            onClick: () => {
              if (activityFeedOpen.has(lab.id)) activityFeedOpen.delete(lab.id)
              else activityFeedOpen.add(lab.id)
              publishActivity()
            },
            style: {
              display: 'inline-flex', alignItems: 'center', gap: 4, justifySelf: 'start',
              appearance: 'none', border: 'none', background: 'none', cursor: 'pointer',
              font: 'inherit', fontSize: 10, padding: 0,
              color: 'var(--dsw-alias-label-tertiary)',
            },
          },
            R.createElement('span', {
              style: { transition: 'transform .15s ease', transform: feedOpen ? 'rotate(90deg)' : 'none' },
            }, '▸'),
            feedOpen
              ? t('hideHistory')
              : `${feedItems.length - 1} ${t('history')}`)
          : null,
        ...feed))
  })

  const layout = snapshot?.panelLayout ?? DEFAULT_PANEL_LAYOUT
  const bounds = snapshot?.panelBounds ?? null
  const resolved = bounds !== null
    ? resolvePanelGeometry(layout, bounds)
    : { ...layout, mode: layout.mode }
  const floating = resolved.mode === 'floating'
  const autoHeight = bounds !== null ? panelUsesAutoHeight(layout, bounds) : true
  const onHeaderDown = (event) => {
    // No move when the pointer lands on the collapse button.
    if (typeof event?.target?.closest === 'function' && event.target.closest('button') !== null) return
    const gestureBounds = bounds ?? { width: window.innerWidth, height: window.innerHeight, anchorRight: window.innerWidth }
    beginPanelGesture('move', undefined, event, resolved, gestureBounds)
  }

  return R.createElement('div', {
    style: {
      position: 'absolute', left: resolved.x, top: resolved.y,
      width: resolved.width,
      height: autoHeight ? undefined : resolved.height,
      maxHeight: resolved.height,
      zIndex: 9999,
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden', borderRadius: 12,
      border: '1px solid var(--dsw-alias-border-l2)',
      background: 'var(--dsw-alias-bg-layer-3)',
      boxShadow: '0 8px 32px rgba(0,0,0,.35)',
    },
    'data-rq-panel': '',
    'data-mode': resolved.mode,
  },
    // Drag handle / header.
    R.createElement('div', {
      onPointerDown: onHeaderDown,
      style: {
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '9px 12px', borderBottom: '1px solid var(--dsw-alias-border-l2)',
        cursor: floating ? 'grab' : 'grab',
      },
    },
      R.createElement('span', {
        style: {
          width: 8, height: 8, borderRadius: 99, flex: 'none',
          background: 'var(--dsw-alias-label-primary)',
          animation: 'rq-pulse 1.6s ease-in-out infinite',
        },
      }),
      R.createElement('span', {
        style: {
          flex: 1, minWidth: 0, fontSize: 12.5, fontWeight: 600,
          color: 'var(--dsw-alias-label-primary)',
        },
      }, t('title')),
      R.createElement('button', {
        type: 'button',
        onPointerDown: (event) => { if (typeof event.stopPropagation === 'function') event.stopPropagation() },
        onClick: () => {
          if (floating) {
            if (bounds !== null) applyPanelLayout(dockPanelLayout(resolved, bounds))
          } else {
            applyPanelLayout(floatPanelLayout(resolved, bounds ?? { width: window.innerWidth, height: window.innerHeight, anchorRight: window.innerWidth }))
          }
        },
        style: {
          appearance: 'none', border: '1px solid var(--dsw-alias-border-l2)',
          borderRadius: 8, cursor: 'pointer', font: 'inherit', fontSize: 10.5,
          padding: '2px 8px', background: 'none',
          color: 'var(--dsw-alias-label-secondary)',
        },
      }, floating ? t('dock') : t('float')),
      R.createElement('button', {
        type: 'button',
        onPointerDown: (event) => { if (typeof event.stopPropagation === 'function') event.stopPropagation() },
        onClick: () => setActivityCollapsed(true),
        style: {
          appearance: 'none', border: '1px solid var(--dsw-alias-border-l2)',
          borderRadius: 8, cursor: 'pointer', font: 'inherit', fontSize: 10.5,
          padding: '2px 8px', background: 'none',
          color: 'var(--dsw-alias-label-secondary)',
        },
      }, t('collapse'))),
    R.createElement('div', { style: { padding: '2px 12px 8px', overflowY: 'auto' } }, ...bodies),
    R.createElement('div', {
      style: {
        padding: '6px 12px', borderTop: '1px solid var(--dsw-alias-border-l2)',
        fontSize: 9.5, color: 'var(--dsw-alias-label-tertiary)',
      },
    }, `${t('credit')} · ${t('live')} · ${POLL_MS / 1000}s`),
    // Resize handles for edge dragging.
    R.createElement('div', {
      'data-resize-edge': 'left',
      onPointerDown: (event) => {
        const gestureBounds = bounds ?? { width: window.innerWidth, height: window.innerHeight, anchorRight: window.innerWidth }
        beginPanelGesture('resize', 'left', event, resolved, gestureBounds)
      },
      style: {
        position: 'absolute', left: 0, top: 0, bottom: 0, width: 6,
        cursor: 'ew-resize', touchAction: 'none', opacity: 0,
      },
    }),
    R.createElement('div', {
      'data-resize-edge': 'bottom',
      onPointerDown: (event) => {
        const gestureBounds = bounds ?? { width: window.innerWidth, height: window.innerHeight, anchorRight: window.innerWidth }
        beginPanelGesture('resize', 'bottom', event, resolved, gestureBounds)
      },
      style: {
        position: 'absolute', left: 0, right: 0, bottom: 0, height: 6,
        cursor: 'ns-resize', touchAction: 'none', opacity: 0,
      },
    }),
    R.createElement('div', {
      'data-resize-edge': 'corner',
      onPointerDown: (event) => {
        const gestureBounds = bounds ?? { width: window.innerWidth, height: window.innerHeight, anchorRight: window.innerWidth }
        beginPanelGesture('resize', 'corner', event, resolved, gestureBounds)
      },
      style: {
        position: 'absolute', right: 0, bottom: 0, width: 14, height: 14,
        cursor: 'nwse-resize', touchAction: 'none', opacity: 0,
      },
    }))
}

function applyActivityOverlay(ctx) {
  ctx.effect(() => ctx.locale.register(ACTIVITY_NS, activityCopy), 'rq-activity: panel dictionaries')
  startActivityPoller(ctx)
  ctx.slots.inject('shell.overlay', () => ctx.slots.register(
    {
      name: 'shell.overlay',
      id: 'rigorquant-activity',
      order: 80,
      label: 'RigorQuant activity',
      locale: ACTIVITY_NS,
      inject: () => ({ hooks: { rqActivity: snapshotStore() } }),
    },
    (props) => ActivityPanel({ ...props, t: ctx.locale.bind(ACTIVITY_NS) }),
  ))
}

return { apply, inject }
} })
