# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This file starts at 0.2.0; earlier releases (0.1.0, 0.1.1) predate it.

## [Unreleased]

### Changed
- **The study runs on Agent Teams only** (Decision 24,
  `docs/adr/0001-rigorquant-on-agent-teams.md`). SKILL.md Step 3 runs a round
  as five moves (Promise → Fan out → Ground-truth → Attack → Certify) on
  `spawn_teammate` / `wait_agent` / `send_message`. At Promise the orchestrator
  lays the round out as a task DAG with one `blocked_by` layer per move
  (explore per sub-problem → ground-truth per claim, two for a load-bearing
  one → attack per sub-problem → certify per round), which is the layering
  the move pill reads. Teammates are named `<role>-<n>` with a per-role
  counter taken from the roster on resume, and each description is only the
  role label. Fan out is batched to at most eight live teammates, and
  hitting the lifetime teammate cap is a BUDGET outcome. Explorer,
  OffGridThinker and DoubleChecker are fresh per brief. Adversary,
  Literature adversary, Document adversary and each `lit-line-<n>` are
  reused by message, only while idle or inactive.
- **Hard-lesson L3 is rewritten.** Freeze-and-hash stays verbatim. "Never
  message a settled agent" becomes the new-brief rule: a reused teammate only
  receives a new hash-bound brief, only while idle or inactive. The native
  "a queued message is already stored; never resend it" rule replaces the old
  discard rule. protocol.md adds the brief contract: task id, snapshot hash,
  and a description that is only the role label.
- **Orchestrator persona.** The ISOLATION paragraph now says role by name,
  tool budget by scope and topology by guard, and still not a network wall.
  The persona states that a RigorQuant study is the explicit request the Team
  policy asks for, and it must not spawn while the "RigorQuant team guard:
  armed" line is absent. It reads a spilled tool result back by its locator
  instead of re-running the tool. Each teammate persona now claims and
  completes the task its brief names.

### Removed
- **The classic delegation rows.** The preset drops the seven per-role
  delegation rows, `tool-subagent-control`, `tool-subagent-list-agents`, and
  the disabled fork row. The Team tools register the control tools under the
  same names, so the classic rows would have duplicated them. The
  external-agent rows and the checker lane stay disabled, and `present` stays.
  The router's `ROLE_TOOLS` map goes with the rows. Repo-consistency pins
  forbid the rows, pin the new L3, and pin the skill's vocabulary.

### Fixed
- **The move pill rendered nothing on every real session** (issue #13's client
  half). It read the Lead's board off a client session projection
  (`useSessions(state => state.projectionsBySession[…].values.agentTeam)`) that
  does not exist on the pinned floor: `projectionsBySession` occurs nowhere in
  the installed `0.1.6-alpha.2` harness, so the read was silently `undefined`
  and the pill never rendered — while its own probe stayed green, because the
  probe stubbed the same invented API. It now reads the Lead's live view through
  the Team namespace's own request, `remote.agentTeams.view(leadSessionId)`,
  injected rather than read off the root context, so a profile whose Team bundle
  is absent never registers the pill at all instead of rendering a branch that
  also swallowed every real failure. Verified live on the installed
  `0.1.6-alpha.2`: a web profile with a running team now shows the round's move
  in the session header (the portrait badges were not exercised live — every
  `spawn_teammate` in that environment failed before a teammate reached
  `status: 'running'`, so they rest on the probe).
  `tests/client_bundle_probe.cjs` models the real seams and
  `tests/test_client_bundle.py` pins the read, the gate, and zero fictional
  projection reads. See `docs/upgrade-0.1.6.md` §3.14.
- **`install.sh` could produce a profile that cannot boot, and installed the
  published package from a git worktree** (issue #21, both found verifying
  #13's client half live). The Team bundles were added by bare name, so pnpm
  resolved the `latest` dist-tag — two prereleases behind a `0.1.6-alpha.2` core
  — and the profile then failed to apply its plugin tree (`typert-loader: …
  parameter codec has no create() factory`). They are now added as
  `<bundle>@<core version>`, and a profile that already lists the pair at
  another version is re-pinned by the next run (a bundle the operator enabled
  with no recorded version is still left alone). The install-spec choice tested
  `[ -d "$HERE/.git" ]`, which is false in a linked worktree (`.git` is a file),
  so a worktree profile got `dsh-rigorquant@0.4.2` from npm — the release that
  still ships the deleted `dsh/activity.js` — and the pre-commit hook wiring was
  skipped there too; both now share one `is_git_checkout` helper. Verified live
  against the installed CLI; see `docs/upgrade-0.1.6.md` §3.13.

## [0.4.2] - 2026-09-22

The last classic release (Decision 24, `docs/adr/0001-rigorquant-on-agent-teams.md`):
the existing mechanism — delegation rows, custom router, activity monitor —
runs on DSH **0.1.6-alpha.2**, its two silent browser breaks fixed and its
fallback retargeted, holding the line for operators who cannot enable a Beta
bundle while 0.5.0 moves the same study loop onto Agent Teams. It also
carries the 0.1.5 port, which never shipped on its own: 0.4.1 predates it.

### Added
- **DSH 0.1.5 support, and the version floor that goes with it.** The full
  install requires **DSH ≥ 0.1.6-alpha.2** (`install.sh`, both READMEs) —
  the floor the 0.1.6 amendments below raise from the port's own
  `0.1.5-alpha.2`, for the reason the Changed section states. The floor is
  mount-time, not cosmetic: 0.1.3-alpha.2 split the persona into a
  required `prefix` plus an optional `suffix` and deleted the single `text`
  key, and a row whose config fails validation rejects the **whole** preset
  mount while the preset picker still lists it as healthy.
- **`tests/preset_harness_probe.cjs`** — validates every row of the composition
  against the **installed** harness package's own `Config` schema, so a renamed
  config key becomes a one-line diff instead of an unmountable preset.
  `tests/test_harness_compat.py` runs it and skips when no `dsh` is installed.
- **`present` and `command-goal` rows** in the preset. No bundle mounts
  `@deepseek-ai/dsh-tool-present` — only presets do — so RigorQuant sessions
  had no `present` tool at all; `command-goal` restores `/goal`. The
  deliverables skill now ends its assembly workflow with a `present` call.
- Regression coverage for the seams this port depends on: a forked top-level
  session stays a lab (`origin`, not `parentSession`), a lab is discovered
  through the `agentPreset` projection, the router resolves a one-shot child
  through the **live** persona section, and the child catalog keeps
  `send_message`.
- **The installer detects Agent Teams; it does not enable it.** A full
  install reads `dsh.profile.bundles` in the target profile's `package.json`
  and reports whether both optional Team bundles are on, printing where to
  toggle them when they are not. Detection only: enabling a bundle appends a
  layer to the profile's stack, which changes what every session in that
  profile composes, so it stays the operator's decision until Decision 24
  (0.5.0) enables them under a marker it can find again. An unreadable
  manifest is reported as unknown, never as "off".

### Changed
- **The shipped fallback route is `deepseek-flash` @ low.** The 0.1.6 default
  DeepSeek catalog lists `deepseek-flash` (DeepSeek-V41-Flash, efforts
  `off|low|high|max`) and `deepseek-v4-pro`; the V4 flash id the
  DoubleChecker/adversary fallback lane named is no longer listed, and an
  unlisted id fails only once the lane is entered, so the miss was silent until
  a primary failed. The router's `DEFAULT_FALLBACK`, the routing card's
  defaults (served from the router's schema), both README tables and Decision
  16 now name `deepseek-flash`; the primary stays `deepseek-v4-pro` @ high.
  The router exports `DEFAULT_PRIMARY`/`DEFAULT_FALLBACK`; the router probe
  seeds its settings base from them and pins the literals, so a retarget
  cannot pass the probe by editing the probe's own fixture. Two
  repo-consistency pins: both README tier rows equal the router constants,
  and no tracked file outside the upgrade studies names the retired id.
- **Child results travel as the final assistant message.** The one-way `report`
  tool was removed in 0.1.2-rc.1; a continuable child's final assistant message
  is now what the runtime hands to the agent that started it. Every role persona
  (and the protocol/SKILL documents) says exactly that, and the seven child
  `toolFilter` deny lists no longer name `send_message`, so a depth-1 child can
  push an interim finding or a blocking question to its direct parent.
  `interrupt_agent` and `list_agents` stay orchestrator-only.
- **Persona section constant follows the 0.1.3-alpha.2 rename.** The router
  reads `deployment:persona-prefix` (was `deployment:persona`) when it probes a
  one-shot child's live prompt; the old name silently returned `null` and the
  child lost its tier routing.
- **The activity monitor reads live seams.** `agent.session.events` was removed
  in 0.1.2-rc.1 and a `?.events ?? []` turned that into a permanently empty
  panel; the monitor now reads `ownEvents()` (with `snapshotEvents()` as the
  fallback), prefers the `agentPreset` Session projection over the stale
  creation header, and treats `origin: 'subagent'` — not `parentSession` — as
  the child discriminator.
- **The browser half uses only `settingsSchema`.** The
  `@deepseek-ai/dsh-client-schema-form` fallback was removed: that package is
  gone from the harness and from the browser's frozen module table, so the
  `require` could only throw inside the controller's construction and take the
  whole bundle entry down. The bundle probe now refuses to answer the deleted
  name. `dsh.client.inject` names `@deepseek-ai/dsh-client-ui-renderer` (the
  package that actually provides `slots`) instead of the removed
  `@deepseek-ai/dsh-client-runtime`.
- **The floor is DSH ≥ 0.1.6-alpha.2.** Both READMEs, `install.sh`, the
  preset header and `dsh/sync.js` state it (sync states and cannot enforce:
  the bundle install path of Decision 22 runs after the profile has
  composed, so there is nothing left to refuse), and the READMEs say
  outright that the floor is an alpha harness. The floor sits above every
  row's own requirement because the seams that broke are browser-side — on
  0.1.5 the preset still mounts while the routing card and the activity
  floater render nothing at all.
- **The deprecated synchronous history reads stay, with the deferral note.**
  0.1.6 deprecated `ownEvents()`/`snapshotEvents()` under the policy
  "existing logic may remain unmigrated for now, but new calls are
  prohibited". The router and the activity half each keep one helper
  carrying that note, and the consistency suite pins both the accessor
  count and the call sites, so the deferral cannot quietly grow a third
  caller. Both disappear under Decision 24, where a role comes from the
  teammate's name.
- **Fan-out wording follows the host's live-children pool.** The skill and
  the protocol state the pool — eight live children per root
  (`maxActiveSubagents`, default 8) — and that a spawn over the bound fails
  with `ACTIVATION_LIMIT_REACHED`, which reads like a transient error and is
  not one: wait for a teammate to settle, never retry in a loop, because
  nothing releases a slot but a teammate finishing. Raising the setting is
  the operator's change, in Plugins, not the orchestrator's.

### Fixed
- **The model-routing card renders again on DSH 0.1.6 — on the Plugins page.**
  0.1.6 retired the Settings-tab `settings.plugin.item` slot the card
  registered into, and a registration into a slot nothing renders is silent:
  the card simply never appeared. The browser half now registers the bundle's
  configuration entry on `plugins.bundle.config`, keyed by the package name,
  so the form renders on the **dsh-rigorquant** page under Plugins between the
  bundle's description and its rows. It renders the two views the slot
  contract names (`summary`: the one-liner; `page`: the form with its own
  Save — the bundle page asks for `page` today), and follows the page's form
  contract: only a save writes, so the Discard control and the unsaved marker
  are gone and leaving the page drops staged edits. A profile whose router row
  is off used to render nothing; on the bundle's page the section is drawn
  once the entry is registered, so the page view now says the namespace is not
  served instead of leaving an empty section. The settings-schema draft model,
  the `settings.describe` seam and the model-catalog seam are unchanged. The
  client-bundle probe asserts the new slot with both views, the absence of the
  retired slot, and the `plugins.bundle.config` key equals the loader id.
- **The activity floater finds the main-view session again on DSH 0.1.6.**
  Client sessions became references and the sessions list lost its `current`
  field; the floater read it, got `undefined` forever, and rendered nothing —
  silently, since a missing field is not an error. It now scans the client
  session list (`ids`, then the live rows in `byId`) for the id whose retain
  info counts a `mainView` reference — the same
  `sessions.retainInfo(id).retainedBy.mainView` check the harness's own team
  UI makes — and re-scans on every list publish, which a main-view retain or
  release triggers. The probe now runs the poller against a 0.1.6-shaped
  sessions stub (no `current`; `retainInfo`) and asserts the resolved session,
  the rendered panel, that moving the main view moves the panel, and that no
  `.current` read remains in the bundle. Found while verifying by eye: the
  docked panel's "dodge" stylesheet was registered as an effect *body* rather
  than as its disposer, so it was removed the instant it was added and the
  conversation column never yielded width to a docked-open panel; the effect
  now returns the removal, and the column yields.
- **The plugin's global skill root resolved to a directory that does not
  exist.** A patch file's `!!js` is evaluated against the boot root context,
  whose `baseUrl` is the **profile** directory — not the patch file's package
  root (that per-file anchor is an `Include` behaviour only composition files
  get). `cordis.patch.yml` therefore pointed `customSkillDirs` at
  `<profile>/agent-presets/rigorquant/skills/`, which never exists, and with
  `includeDefaultRoots: false` the provider contributed **zero** roots: the
  `rigorquant`, `arxiv` and `academic-paper-search` skills were unavailable to
  every other preset in the profile. The path is now resolved through
  `createRequire` against the installed package.
- **The web surface can no longer wedge itself.** `rq-activity` set its
  `routesRegistered` flag before registering the two HTTP routes; a duplicate
  route throws, Cordis `emit` contains the throw, and the flag stayed set, so
  the monitor was permanently dead with only a host-log stack. Both routes now
  share one effect that sets the flag only after both succeed, disposes a
  partial pair on failure, and logs instead of escaping.
- **`sessionTitle.get()` folded the whole log on every poll.** The folded title
  is now cached against the session cursor it was taken at, and pruned with the
  entry it belongs to.
- **The monitor refuses to report an empty panel.** `ownEventsOf` threw away
  the silent-empty failure mode one layer down: a session exposing neither
  `ownEvents()` nor `snapshotEvents()` now raises instead of yielding `[]`. The
  whole bug being fixed was a removed API degrading into an empty panel with no
  diagnostic, so keeping a `return []` would have preserved it.
- **The disabled rows still name packages that exist.** The workflow engine
  row follows 0.1.6's rename to `workflow-ptc`
  (`@deepseek-ai/dsh-workflow-worker-thread` no longer exists) and the
  disabled external-agent rows move from `enableRunInBackground: false` to
  `backgroundMode: one-shot`, matching the shipped `standard` preset. All
  three stay **disabled** for the reasons that disabled them (untagged,
  unscopeable children), and `modelSelectionSettings` stays off — a
  caller-chosen model would override the role's routed tier (Decision 16).
  Nothing mounts either way — a disabled row is never imported — but a row
  that cannot resolve reads as a typo rather than a decision, and the
  harness probe against the installed 0.1.6 now reports **38 rows, 0 hard
  failures and no UNRESOLVED row** (see Verified).
- **`install.sh --help` no longer runs `--skill-only`.** Backticks in an
  unquoted heredoc in the usage text executed it as a command, so `--help`
  wrote "command not found" to stderr and printed the floor line with a gap
  in it.

### Verified
- **Released against the installed 0.1.6-alpha.2** (`docs/upgrade-0.1.6.md`
  §3.8, on a scratch profile installing the release tree by `file:`): the
  preset harness probe reports **38 rows, 0 hard failures and no UNRESOLVED
  row**; the bundle page shows v0.4.2 with **all four components Running** —
  the skill-root row is the one that evaluates the patch's package-relative
  `createRequire` resolution, so runtime resolution mode is confirmed on a
  real profile — and `rq-preset-sync` stamped 0.4.2 at first boot, the
  version bump being what replaces the shared preset tree (the stale-copy
  failure mode the 0.1.5 port's unreleased bump would have hit). Toggling
  the four RigorQuant rows off and on in the Plugins page (three
  unload/reload transitions of the route-owning component) left **no
  dangling route or listener**: both `/plugins/dsh-rigorquant/` routes 404
  while off and 200 with a live snapshot after every re-enable, with the
  host log silent throughout. The full suite ran green under the coverage
  gate, including a new consistency test pinning the package and lane
  version stamps together.
- An independent read-only audit (Claude Code 2.1.267, a different agent
  runtime) was asked to FALSIFY the port's "implemented" claim against commit
  `66a2ac5`. It confirmed §4.1, 4.3, 4.5–4.7, 4.9–4.11, the seven-deny-list
  count, both skill-file edits, the two new rows, and that
  `tests/router_probe.cjs` really fails if `PERSONA_SECTION` is reverted; it
  found three doc/claim deviations and one stale version note, all fixed in
  `docs/upgrade-0.1.5.md` §8 (which records the findings and their
  dispositions).
- **A reasoning effort the exact route refuses no longer kills the turn.**
  The settings card's effort dropdown fell back to a generic
  `[off, high, max]` vocabulary whenever the catalog reported no effort
  surface, so a model with no reasoning metadata (e.g. `zai/glm-5.3-flash`)
  could be saved with `high` — and every turn routed to it then died in
  `UNSUPPORTED_REASONING_EFFORT` before any provider I/O. The dropdown now
  offers only the chosen model's real effort surfaces ("Default" only when it
  has none; a stored unsupported level renders disabled), switching models
  keeps an effort only when the new surface lists it, and the host router
  drops a refused effort at routing time — the model's default level governs,
  logged once per route. The router probe also runs again (its agent stub
  predated DSH 0.1.2's `session.snapshotEvents()` rename).

### Documentation
- `docs/upgrade-0.1.5.md` — the source-verified upgrade study: what changed
  between 0.1.2 and 0.1.5, what the preset must adopt, the deeper agent/tool
  optimizations, and the ranked fix list this release implements.
- `docs/upgrade-0.1.6.md` — the 0.1.6 source study: what changed upstream, the
  break list (the two silent browser breaks, the removed fallback model, the
  deprecated history reads), the Phase 0 probe evidence against the installed
  alpha, and the Phase 1 release verification recorded in its §3.8.
- `docs/architecture.md` Decision 20 records the two contract changes (the
  final-message delivery channel and the `settingsSchema`-only draft model) and
  the persona split; its 0.1.6 amendment is the compat surface this release
  ships. Decision 24 (`docs/adr/0001-rigorquant-on-agent-teams.md`) is the plan
  0.4.2 is the safety net for: the last classic release, while 0.5.0 moves the
  same study loop onto Agent Teams.

## [0.4.1] - 2026-09-02

### Added
- **95% validator coverage gate** (`.githooks/pre-commit`, `.coveragerc`, CI).
  The checked-in git hook runs the full suite with `RQ_COVERAGE=1`; each
  `rq_check.py` subprocess is measured explicitly with `coverage run
  --parallel`, then the hook combines child files and enforces
  `coverage report --fail-under=95`. `install.sh` wires `.githooks` in git
  checkouts, CI runs the identical gate, and a consistency test pins the hook,
  config, lane dependency, installer wiring, and the safe cleanup glob. The
  validator's refusal surface is now covered at 96.3% (tests/test_gate_surface.py
  adds real gate-level negative cases rather than synthetic line hits).

### Changed
- **Decision-record numbering compacted.** The later detailed decisions now run
  consecutively from 13 through 23; all references in docs, runtime comments,
  installer text, READMEs, and tests move with their decision.

### Fixed
- **Stale claims the decision record contradicts** (README, README.zh-CN,
  docs/architecture.md). The READMEs advertised a capability the composition
  no longer ships; the bullet is removed. Architecture's grilled summary
  carried three pre-amendment statements: item 9's "one model everywhere"
  (superseded by Decision 16's per-role routing), item 10's "BUDGET → 5
  orchestrator rounds" (moved to 3 by Decision 17), and Decision 14's C7
  "budget is a safety ceiling, never a finish target" (inverted by Decision
  17). All three now carry inline amendment notes, the convention item 8
  already used.

### Changed
- **Roles renamed: Oracle → DoubleChecker; the novelty toggle becomes its own
  agent, OffGridThinker; the explorer tool is no longer bare `subagent`.**
  (Design record: docs/architecture.md, Decision 23.)
  (`agent.cordis.yml`, `dsh/index.js`, `dsh/activity.js`, `dsh/client.js`,
  skills, docs, tests.) The ground-truth role is now **DoubleChecker**
  (`subagent_double_checker`, row `tool-subagent-double-checker`, routing tag
  `[[rq:role=doublechecker]]`, settings keys `doublecheckerPrimary`/`Fallback`)
  — the name says what it does: re-derive the claim twice by different means.
  The old `subagent_novel` row is now the **OffGridThinker** (`subagent_offgrid`,
  tag `[[rq:role=offgrid]]`, settings keys `offgridPrimary`/`Fallback`), a role
  in its own right instead of an Explorer variant: its one boundary is other
  people's results — no web, no literature, no other agents' drafts — while the
  pinned compute lane (sympy/numpy/mpmath/cvxpy/hypothesis/jax, Lean checkers
  when provisioned) stays fully available for derivation. The open explorer's
  delegation tool is now `subagent_explorer` (row `tool-subagent-explorer`)
  rather than the generic `subagent`, so every delegation tool carries its role
  name. Deployments with saved per-role overrides in the `rigorquant-models`
  namespace should re-enter them under the new keys (the old `oracle*`/`novel*`
  fields are simply ignored).
- **The activity pillbox role map is a hub-and-spoke, not a stage DAG**
  (`dsh/client.js`, `tests/test_repo_consistency.py`). The orchestrator is the
  only hub — it spawns every role and receives every report, and two child
  roles never hand off to each other — so the map now shows the root at the
  center with the seven child roles as spokes (ordered proposal → retrieval →
  re-derivation → audit → certification), each spoke tinted while its role is
  running. The shoehorned five-stage DAG and its dashed loop-back edge are
  gone.
- **Role portraits** (`docs/figs/`). `avatar-oracle.png` is replaced by
  `avatar-doublechecker.png`, and the OffGridThinker gets its own portrait
  (`avatar-offgrid.png`) instead of sharing the explorer's. Regenerated the
  activity-panel SVG (now eight roles) and updated the hero banner caption.
- **Per-role tool budgets for delegation children** (`agent-presets/rigorquant/agent.cordis.yml`,
  `tests/test_blind_deny_list.py`). Every role now carries an explicit
  `toolFilter` that removes the tool schemas it must never touch from the
  child's request, instead of relying on depth-1 spawn failures. Denied
  everywhere: the full delegation set (C2), the workflow/ralph loops,
  child-control tools, the goal trio and `todo_write` (Decision 10: one
  root-owned task-level goal), `ask_user_question` (children run unattended),
  and plan mode. Per-role policy: the explorer keeps web/skill (open track);
  the adversary is web-blind but skill-capable (the verdict must rest on
  derivation and computation it ran itself — a web citation would enter the
  PASS gate unaudited — while the check battery lives in the skill); blind
  roles stay web/skill-denied; the document adversary keeps web denied.
  Static lists only name tools every deployment mounts (a static deny of a
  plugin-optional tool would throw at child spawn); deployment-optional noise
  (ssh/import/image tools) is left to the barebone assembly filter. All seven
  roles are landed: explorer, lit-line, and lit-adversary at 13 first-class
  tools (open retrieval and proposal roles: web, skills, bash, and background
  sweeps kept per review); adversary and doc-adversary at 11 (web denied; the
  doc-adversary keeps write because rq_check reads its verdict file from the
  record); blind roles at 10.
  A consistency test asserts each role's deny list against the derived
  delegation set plus the orchestrator-owned set and fails if any delegation
  row mounts without a filter; a budget module pins each landed role's exact
  visible catalog and the spawn-safety invariant.
- **Blind personas carry the compute-lane block** (`agent.cordis.yml`,
  `tests/test_blind_deny_list.py`). The oracle and novel personas now include
  the sanctioned invocation (`uv run --frozen --project <env_lane> python ...`,
  lane at `$DSH_HOME/share/rigorquant/env`), the installed-package list, the
  symbolic-first/high-precision rule, and a no-install/no-fetch discipline
  that converts the bash-network residual hole into an auditable instruction.
  A consistency test pins the block in both personas and against SKILL.md's
  documented form.
- **Untagged spawner rows disabled** (`agent.cordis.yml`, `docs/architecture.md`,
  `tests/test_role_tool_budgets.py`). `subagent_fork`, `tool-workflow`,
  `tool-ralph`, and the `workflow-worker-thread` engine are disabled in this
  preset. Their children carry no role tag (the router never routes them), and
  workflow `agent()` calls express neither a per-child persona nor a per-child
  toolFilter — 74 of the 162 children in the 0.4.x study logs were untagged
  workers wearing the root persona with the full ~54-tool catalog (~23k-token
  headers). Disabled rows mount no tools, so their names also leave every
  deny list (tools.restrict throws on unmounted names); the per-role deny
  lists, the conftest delegation/orchestrator sets, and the guaranteed-mounted
  universe all drop them, and a regression test fails if any of the four rows
  is re-enabled without revisiting that. Decision 8 amended in
  docs/architecture.md.

### Fixed
- **Delegation denial lagged the document-adversary row** (`agent-presets/rigorquant/agent.cordis.yml`,
  `tests/test_blind_deny_list.py`). `subagent_document_adversary` was mounted by the
  composition but absent from every delegation deny list and from the test's
  `BLIND_TOOLS` set, so oracle/novel/lit/doc-adversary children still saw that
  spawn tool in their depth-1 catalog — Decision 14's C2 ("delegation denied
  outright") was one row behind the composition. The name now appears in all
  five deny lists and in `BLIND_TOOLS`; a new consistency test derives the
  delegation set from every mounted `provider: spawn` row and fails when a
  future delegation row is added without extending the deny lists.
- **Activity pillbox DAG mislabeled the literature adversary and missed the
  optional loop-back** (`dsh/activity.js`, `dsh/client.js`). The literature
  adversary node read "Literature" (same as the literature lane). It now has a
  distinct label ("Lit adversary" on the narrow DAG node, "Literature adversary"
  on the roster), and a dashed `lit-adversary → adversary` edge marks the
  optional verification handoff back into the main adversarial audit.
- **Effort dropdown was hard-coded to `[off, high, max]`** (`dsh/client.js`). A
  model whose route doesn't support a level (e.g. some reject `high`) was
  still offered it, sending an effort the provider errors on. The card now
  keeps each model's `reasoning.efforts` from the catalog, offers exactly what
  the chosen model supports, and drops a now-invalid effort when switching to a
  model that no longer accepts it.
- **Usage-limit 429 did not trigger the RigorQuant fallback** (`dsh/index.js`).
  The official quota response can arrive as provider code `1308` with
  “Usage limit reached” text but no normalized numeric status. The router now
  classifies that exact terminal failure, records the effective primary route,
  and retries the configured fallback once; the router probe covers it.
- **RigorQuant model card let nobody change models** (`dsh/client.js`). The
  card read `remote.session`/`remote.settings` but never declared those
  sub-namespaces in its `inject`; Cordis gates sub-namespace access and throws
  `cannot get property "remote.session" without inject`, so `loadCatalog` failed
  and the dropdown stayed at `loading` with only the “Inherit” placeholder. The
  card now declares `remote.session` and `remote.settings`, and the probe models
  the gate so a forgotten sub-namespace fails the build.
- **RigorQuant model card still reported “unavailable” after the Remote fix**
  (`dsh/client.js`). The bundle is `immediately`, so its `load()` could run
  before `@deepseek-ai/dsh-api-session-controller` mounted `remote.session` in
  the application batch; the card then threw on the missing namespace and
  reported a connection failure even though the builtin catalog RPC succeeded.
  `loadCatalog` now lazily waits (bounded retry) for `remote.session` to mount
  instead of failing on the boot race.
- **RigorQuant model catalog unavailable on DSH 0.1.2** (`dsh/client.js`,
  `package.json`). The card used the removed private
  `connection.api.llm.models` facade and reported its absence as a connection
  error. It now declares the official `remote` dependency and uses
  `remote.session.modelCatalog()` plus `remote.settings.describe()`, matching
  the builtin model selector.
- **Activity pillbox boot/navigation regressions on DSH 0.1.2**
  (`dsh/client.js`). The immediately-materialized floater sampled `sessions`
  before its binding existed and also started its first poll while that lexical
  binding was still in the TDZ. It now declares `sessions` as a required
  dependency, initializes/re-binds before polling, serializes and aborts
  requests, and scope-owns expansion so a route change cannot leave stale
  docked conversation padding behind.

### Changed
- Added `THIRD_PARTY_NOTICES` preserving the upstream MIT notice for the
  substantial `dsh-agent-teams` activity-panel geometry adaptation.
- **DSH 0.1.2 native subagent-route migration** (`agent-presets/rigorquant/agent.cordis.yml`,
  `dsh/index.js`, `install.sh`). Fixed-tier oracle/adversary primaries now use
  native `tool-subagent` `agentOptions` (including `reasoningEffort`); the custom
  router only applies explicit settings overrides and fallback retries. The
  router regression probe covers native pass-through, reset, and degradation.
  The installer now rejects DSH versions older than `0.1.2-alpha.1`, which is
  the new preset floor.
- Updated the English/Chinese README, architecture record, upgrade study, and
  Settings-card copy to document native defaults and the intentional omission of
  arbitrary `maxTokens` caps.

## [0.4.0] - 2026-08-29

### Added
- **Document-adversary role** (`subagent_document_adversary`). An independent
  agent that audits each finished deliverable for **self-completeness**: every
  jargon term, symbol, and abbreviation used in the artifact must be defined in
  the artifact itself or the audience spec's symbol registry. Returns
  `VERDICT: PASS` / `VERDICT: NEEDS-EDITS`; a `NEEDS-EDITS` is a blocking gap
  the validator refuses a `PASS` without. Wired end-to-end: routable as a model
  role (`dsh/index.js` `ROLES`/`ROLE_TOOLS`), one role row in the
  `rigorquant-models` Settings card (`dsh/client.js`, en/zh copy + its own
  `docs/figs/avatar-document-adversary.png` portrait), a stage + pipeline node
  in the live activity view (`dsh/activity.js`, `dsh/client.js`, its own
  portrait), and a README (en/zh) team entry. Adds
  `docs/figs/avatar-literature-adversary.png` so the literature adversary gets
  its own portrait instead of sharing the literature-line one.
- **Upgrade study for DSH v0.1.2-alpha.1** (`docs/upgrade-0.1.2.md`). Audited
  every Host event / service, Client slot / service, and settings seam this
  repo calls against the `dsh-v0.1.2-alpha.1` tag: no breaking incompatibility
  was found (ApiProxy removal, conversation-UI split, profile-launch
  unification, and the network-launch token do not touch this surface).
  Identified new builtins to adopt instead of reinventing: per-tool
  `@deepseek-ai/dsh-tool-subagent` `agentOptions` as the per-role model default
  (`provider`/`model`/`maxTokens` already exist on 0.1.1-rc.2; `reasoningEffort`
  is the 0.1.2 addition), keeping only the degrade-lane + root handling in the
  custom router; plus builtin public WebFetch (SSRF-guarded, no per-request
  approval) and builtin per-answer token display.
- **Live team-activity view (README "The team, live").** A new host half
  `rq-activity` (`dsh/activity.js`, exported as `./activity`) observes the
  events the core already publishes — agent lifecycle, `agent/status`, session
  events — and serves what the lab is doing as a JSON snapshot plus the six
  `docs/figs/` role portraits over `/plugins/dsh-rigorquant/...` (same HTTP
  surface dsh-agent-teams uses). The browser half registers a `shell.overlay`
  floater: a pill vertically centered on the active conversation's right edge
  (measured against `[data-shell-overlay]` + `[data-phase='active']`, the same
  geometry dsh-agent-teams uses, so it follows the column and stays clear of
  the workspace rail and right-docked panels like dsh-better-sidebar's task
  view), expanded into a live panel showing each
  RigorQuant lab's stage (five-move loop), working/idle roster with role
  avatars, and a newest-first activity feed. One-shot subagents (no persona
  tag — only a `label`) get their role from the parent's `subagent_*` tool
  call via a per-parent FIFO, with a label-prefix fallback for cold reseed.
  The feed is collapsed to the latest action by default, with an arrow to
  expand the recent history. A role-pipeline graph (stages stacked
  VERTICALLY, nodes = the eight roles, edges = handoffs) renders above the
  roster with the
  same dependency-graph aesthetic as dsh-agent-teams, colored by live status
  (running/idle/pending). A role lights up by reading its member's current
  agent status straight from the registry (`ctx.agents.get(id).status` — the
  same memberActivity signal dsh-agent-teams uses), falling back to recent
  session activity, so a one-shot subagent that finishes before a poll still
  flashes its role. Each pipeline node carries its role's `docs/figs/`
  portrait, so working roles are recognizable at a glance. Subagents that
  finish stay in the
  roster as idle for
  a while (the graph keeps their role rather than going empty), while the
  live-team summary counts only still-present agents. The panel is a
  docked/floating surface (ported from dsh-agent-teams panel-geometry): drag
  the header to float it, drag its left/bottom/corner edge to resize, and it
  persists its layout between sessions. While docked-open the active
  conversation column yields width (`data-rq-panel-open` + `--rq-panel-shift`
  padding), so the panel never covers the text.
  The floater is scoped to the current session: it
  shows only the lab owned by the conversation open in the view (its captain
  session or one of its subagent transcripts), never other sessions' labs, and
  only while that session is a RigorQuant one. Purely observational — no tool,
  route, or model change; webless profiles stay inert (routes register lazily
  on `webServer`).
  All panel colors are `--dsw-alias` tokens, so it follows the shell's own
  light/dark theme. Design adapted from
  [dsh-agent-teams](https://github.com/NanmiCoder/dsh-agent-teams) (NanmiCoder,
  MIT); reader-safe README picture in `docs/figs/agent-team-activity.svg`
  (generated by `docs/figs/agent-team-activity.js`, freshness-pinned in tests).
- **Host tests for the monitor** (`tests/test_activity.py` +
  `tests/activity_probe.cjs`): mounts the module against a stub ctx, drives the
  life cycle, and exercises both HTTP routes — snapshot content, newest-first
  feed, allowlisted portraits, and no-route webless safety.

## [0.3.2] - 2026-08-22

### Added
- **Self-installing bundle (Decision 22):** a second host half, `rq-preset-sync`
  (`dsh/sync.js`, exported as `./sync`), lands the agent preset into
  `$DSH_HOME/.agent-presets/rigorquant` and env/mcp/docs into
  `$DSH_HOME/share/rigorquant/` once per profile boot — so
  `dsh plugin --profile <p> add dsh-rigorquant` alone now yields a working
  distribution. Idempotent byte-compare; derived state (`.venv`, `__pycache__`)
  never copied or pruned; a same-version target keeps local edits (the
  escalation lane flips rows in the installed composition); an upgrade
  replaces shipped files. There is no uninstall hook in DSH's plugin CLI, so
  removal stays explicit (`./install.sh --uninstall`) and every managed root
  carries an `.rq-sync.json` ownership marker. Engine executed for real in
  `tests/test_preset_sync.py` via `tests/preset_sync_probe.cjs`; wiring pinned
  in `tests/test_repo_consistency.py`.
- **0.1.1-rc.2 readiness (Decision 20):** the browser half is dual-version —
  `dsh/client.js` resolves the settings draft model from the rc.2
  `settingsSchema` service (the standalone `dsh-client-schema-form` package was
  deleted in rc.2) and falls back to the legacy module on older harnesses; the
  bundle probe gains an `rc2` mode proving the mount without the deleted
  package.
- Every role persona now delivers its verdict through the harness child
  `report` tool (report-first delegation, L2): continuable children get it,
  and the delivered report wakes the orchestrator.
- The literature lane batches independent `web_search` queries (`queries`
  array, DSH >= 0.1.1-rc.1).
- Documented named Claude Code / Codex profile bundles (per-role permission
  modes; rows stay disabled — bundles install at the profile) and the rc.2
  multimodal stack (vision model, Files API, `read_image`). The experimental
  `agent-team` domain is flagged as a watch item, not wired.

## [0.3.1] - 2026-08-21

### Changed
- Study slugs now follow `YYYYMMDD_<kebab-topic>[_v<N>]` — the 8-digit intake
  date, a kebab-case topic, and an optional `_v<N>` variant tag — instead of
  `rq-<topic>-<NN>`. The schema pattern enforces the new form, SKILL.md Step 1
  documents minting (date fixed at intake, never changed on resume), and the
  five archived studies in rigorquant_studies were renamed in place
  (`rq-convex-sampling-01` → `20260814_convex-sampling`, etc.) with their
  internal references updated.
- **Bounded budgets with explicit escalation** (Decision 17): default
  `max_orchestrator_rounds` 5→3, fan-out 2–4→1–2 explorers, the second
  ground-truth track mandatory only for load-bearing claims, and literature
  budget 8/4/80/8 → 4/3/20/4. The "10+ hour runs are expected / budget is
  never a finish target" framing is replaced by budget-as-finish-target with a
  recorded user escalation for overruns; `max_wall_minutes` stays unset and
  the journal stays append-only.
- Compaction now fires at 60% of the routed context window (was 80%) and the
  tool-result pruner retains 4 KiB per result (was 8 KiB) — both shrink the
  per-step re-sent surface on long runs (heavy outputs already live in files).
- The model router's shipped fallback effort is `low` (was `high`): a fallback
  is a degrade lane, not a second full-price route.
- **Procedural gates from the 20260820 var-expected-return run** (Decisions
  19–20): claim-keyed BLOCKED (two NEEDS-EDITS on one claim → narrow the scope
  or BLOCKED, never a third re-patch); report-first delegation (the `VERDICT:`
  line is the deliverable, JSON is data, transcription is not certification);
  freeze-on-audit with hash-bound verdicts and no messages to in-flight
  agents; status written from verdicts; record-source-of-truth with
  `claim_sha256`; schema/validator pins at intake; document-adversary passes
  capped at two. `rq_check.py` now refuses a verdictless status claim
  (`status.verdict-reference`), flags an edited stage-3 claim
  (`stage3.claim-digest`), and flags a schema/validator reissue
  (`intake.schema-pin` / `intake.validator-pin`).

## [0.3.0] - 2026-08-18

### Added
- Role-routed models: the `rigorquant-models` settings namespace maps every
  RigorQuant role to a primary and a fallback model, each with its own
  reasoning effort, and the router rewrites `agent/request` per role. Roles are
  identified by a `[[rq:role=...]]` tag in the preset persona, so sessions on
  other presets — and forks, workflow workers, and ralph children — are never
  touched.
- A browser half (`dsh/client.js`) serving that namespace as a card in
  Settings -> Plugins, with a per-role primary/fallback selection and a
  per-choice reasoning effort.
- `tests/test_client_bundle.py` and its Node probe: the browser half is
  executed the way the web shell executes it, covering the four contracts a
  client bundle has to satisfy (loader registration, cordis surface, slot
  registration, and render under framework-composed props). Nothing in this
  repository could catch a browser-half defect before.
- One-line installation. `./install.sh` now installs the plugin as well as the
  preset and compute lane, and the package is executable, so
  `npx dsh-rigorquant` installs everything without a clone. A checkout
  installs `file:` from itself; a fetched copy installs the published version.

### Fixed
- The settings namespace is `rigorquant-models`, not `rigorquant.models`. dsh
  brands namespaces with /^[a-z][a-z0-9-]*$/ only on the wire path, so
  registration and `settings.describe` accepted the dotted name and every
  write was rejected — the card could display a choice but never persist one.

### Changed
- Requires DSH ≥ 0.1.0-rc.7: the bundle patch now inserts a loader entry that
  needs rc.7's keyed `settings.plugin.item` slot and self-registered plugin
  settings.
- `./install.sh` no longer copies skills into $DSH_HOME/skills in its default
  mode; the plugin serves them from a higher-ranked custom root. `--skill-only`
  remains the path for skills without the plugin.

## [0.2.0] - 2026-08-15

### Added
- A single, tested meta-validator (rq_check.py) shipped inside the rigorquant
  skill, loading the JSON Schemas that sit beside it, so the schema and the
  checker cannot drift apart.
- The validator's test suite (tests/, 66 tests) and CI (.github/workflows/ci.yml):
  a forged study that must FAIL, plus repo-consistency assertions that replace
  human re-reading with executable checks.
- Machine enforcement for the honesty gate: evidence is read from
  audits/, derivations/, artifacts/ (never study.json), the registry is parsed
  rather than grepped, and a domain-scale instance that names only a
  special/reference body (box/ball/simplex/ellipsoid/diagonal) or restates a
  simplified case is refused.

### Changed
- Moved rq_check.py and the JSON Schemas into
  agent-presets/rigorquant/skills/rigorquant/ (the single canonical location);
  the old repo-root scripts/ and schemas/ are removed.
- The validator is stricter: a study that previously received a false PASS (empty
  stage outputs, a decorative "passed", a self-vouching report, a non-study-root
  output path) is now refused.
- package.json now ships tests/; the npm package no longer includes generated
  __pycache__/*.pyc.
- Docs re-anchored to <skill-dir>; layout wording corrected ("not shipped in the
  npm bundle" instead of "untracked").

### Fixed
- TeX compile: the discovered engine's directory is now put on PATH so latexmk
  can launch pdflatex on MacTeX installs (previously valid studies were refused
  with a false compile failure).
- The no-overclaim rule now covers all four evidence levels, not only
  "formally verified".
- Documented the reopened-status rule: a status that begins with PASS but is
  marked reopened is no longer a PASS claim (previously an undocumented escape
  hatch).
