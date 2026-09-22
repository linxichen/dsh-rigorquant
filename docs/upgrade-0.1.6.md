# Upgrade study: DSH 0.1.6-alpha.2 (from 0.1.5-alpha.2) — native-first, Agent Teams

Companion to [`docs/upgrade-0.1.5.md`](upgrade-0.1.5.md) and
[`docs/upgrade-0.1.2.md`](upgrade-0.1.2.md). Those studies pinned this
repository to **DSH ≥ 0.1.5-alpha.2**; this one covers everything upstream has
done since, and it is written with one bias the user asked for: **replace
hand-rolled machinery with native harness features wherever a native feature
now exists — above all, the Agent Teams domain.**

**Status: Phase 0 done (2026-09-21), no product code changed.** The
machine runs 0.1.6-alpha.2, the probes ran against the built install, and a
manual run confirmed B1/B2 and found one regression the break list lacked
(a stale shared preset copy that 0.1.6 refuses to load) — evidence in
§3.7, environment in §6.
§7 is the execution order; §8 lists the decisions the user owns.

**Baselines and targets**

| Fact | Value | Evidence |
|---|---|---|
| Version this repo pins and enforces | `0.1.5-alpha.2` | `install.sh:18`, `README.md` Install, preset header |
| Version **running** on this machine | `0.1.6-alpha.2` (global install, dist-tag `alpha`; was `0.1.5-rc.2` when the study was written) | `dsh --version` after Phase 0 (§6) |
| Version studied | `0.1.6-alpha.2` (tag `dsh-v0.1.6-alpha.2`, 2026-09-17) | `~/gits/deepseek-harness` at `ddefc45fbc`; npm dist-tag `alpha` |
| Newest `latest`/`next` on npm | `0.1.5-rc.2` | `npm view @deepseek-ai/dsh dist-tags` |
| Commits in range | 1,708 (`dsh-v0.1.5-alpha.2..dsh-v0.1.6-alpha.2`) | `git log --oneline` |
| Study method | source + design notes (`.agents/notes/implemented/2026-09-*`) + release notes, then Phase 0 evidence against the built install | the clone's `lib/` builds are **stale (Sep 3)**; `src/` is authoritative. §§1–5 were written from source; §3.7 records what the built 0.1.6 actually did |

> **On "0.1.6-alpha2":** the tag is `dsh-v0.1.6-alpha.2`. Two pre-releases
> exist since 0.1.5-rc.2: `0.1.6-alpha.1` (the big one: Messages protocol
> default, `agent/created`, session-read deprecations, Team `spawn_teammate`,
> experimental browser/computer use, hooks) and `0.1.6-alpha.2` (Plugins page,
> subagent limits, client session multi-instance, V4 Flash removal, runtime
> plugin resolution). Both are covered.

---

## 1. Summary — what the scan found

Three groups, in order of urgency.

**Breaks (silent or loud) that must be fixed before this runs on 0.1.6** (§3):

| # | Severity | What | Where it bites |
|---|---|---|---|
| B1 | **silent** | `SessionListState.current` was removed from the browser sessions service | the activity floater never learns the current session → blank panel forever (`dsh/client.js:1079-1081`) |
| B2 | **silent** | the `settings.plugin.item` slot is retired; plugin configuration moved to the Plugins page (`plugins.bundle.config`) | the model-routing card renders nowhere (`dsh/client.js:800-802`) |
| B3 | loud, later | `deepseek-v4-flash` dropped from the default DeepSeek catalog | the shipped **fallback** route for DoubleChecker/adversary names an unlisted model (`dsh/index.js:85`, README table, client defaults) |
| B4 | deprecation | `Session.ownEvents()/snapshotEvents()/eventAt()` are deprecated — "new calls are prohibited", storage direction is to stop holding history in memory | router role scan (`dsh/index.js:154,330`) and monitor (`dsh/activity.js:114-115,221,236`) |
| B5 | hygiene | `@deepseek-ai/dsh-workflow-worker-thread` no longer exists (replaced by `workflow-ptc`) | a `disabled: true` row in the preset; inert at mount (disabled rows are never imported) but the harness probe reports UNRESOLVED |
| B6 | new limit | continuable children are pooled: `maxActiveSubagents` default **8** live children per root; creation beyond it rejects with `ACTIVATION_LIMIT_REACHED` | a literature sweep (4 lines) running beside a math fan-out can hit it |
| B7 | floor | version floor, docs, sync stamp | `install.sh`, both READMEs, preset header, `dsh/sync.js` |

**The centrepiece — Agent Teams is now a shipped optional bundle, and it
maps onto RigorQuant's design better than the per-role `subagent_*` rows do**
(§4). Adopting it replaces: the seven hand-composed delegation rows, the
persona-regex role identity, the custom activity monitor (host + browser,
~2,300 lines), the move heuristic that greps tool names, and the procedural
"no follow-up messages" rule. It costs: one new host half (~200 lines) that
applies role persona/tool budget/guards to teammates by **name**, a rewrite of
the orchestrator persona and SKILL round loop around `spawn_teammate` /
`wait_agent` / the shared task board, and a required `maxMembers` override.

**Smaller native adoptions** (§5): the goal round driver is already
host-mounted (the "unattended" contract is native, nothing to add), `present`
+ Office preview + bundled Office skills for deliverables, `workspace/changes`
turn cards, hooks bridge `Stop` gate for the validator, headless `--json` for
batch studies, `spill` and the new plan/subagent sidebar views — all free or
one-line.

---

## 2. What changed upstream (the parts that touch this repository)

Release notes: `gh release view dsh-v0.1.6-alpha.1`, `dsh-v0.1.6-alpha.2`.
Design notes: `~/gits/deepseek-harness/.agents/notes/implemented/**/2026-09-*.md`.

### 2.1 Delegation and teams

- **Agent Teams ships as an optional bundle.** `OPTIONAL_BUNDLES` lists
  `@deepseek-ai/dsh-experimental-agent-team-profile` and
  `…-agent-team-web-profile` (`packages/boot/app-boot/src/profile.ts:167-170`);
  `@deepseek-ai/dsh@0.1.6-alpha.2` declares both as runtime dependencies
  (`npm view … dependencies`). They are switched on from **Settings → Plugins
  → Official (Beta)** or with `dsh plugin --profile web add …`; no npm install
  (`…/process/2026-09-15-shipped-optional-bundles.md`).
- **The Team profile patch** disables `tool-subagent-control`,
  `tool-subagent-list-agents`, `tool-subagent`, `tool-subagent-fork` and
  inserts `agent-team` (`maxMembers: 8`, `maxTasks: 256`, …) and
  `tool-agent-team` (`freshProvider: spawn`, `forkProvider: fork`)
  (`packages/experimental/agent-team-profile/cordis.patch.yml`). In the **web**
  profile those four host rows are already disabled — presets own delegation
  tools (`packages/bundle/web-app/cordis.patch.yml:472-481`) — so on web the
  Team layer is exactly the two inserted rows.
- **Nine scoped tools per member** (`packages/experimental/tool-agent-team/src/index.ts`):
  `spawn_teammate` (Lead-only; `name`, `description`, `prompt`, `context:
  fresh|fork` — *no persona, tool filter, or model*, lines 171-199),
  `send_message` (any member → any member, Steer semantics, 202),
  `list_agents`, `wait_agent` (10 s–1 h, `noProgress` shortcut, 229),
  `interrupt_agent` (Lead-only), `team_task_create/list/get/update`
  (CAS by `expected_revision`, `blocked_by` DAG, advisory `write_scopes`).
  A fixed `team:policy` prompt section says *"create teammates only when the
  user explicitly asks"* and *"The Lead must wait for required teammates
  before giving the final answer"* (lines 31-37).
- **The service drops start-time composition.** `SpawnTeammateRequest` is
  `{name, description, prompt, context, provider, signal}`
  (`packages/experimental/agent-team/src/types.ts:144-151`), and the roster
  calls `ctx.subagents.startContinuable({ …, request: { prompt, parent } })`
  (`roster.ts:282-288`) — even though `ContinuableStartSpec.request` accepts
  `persona`, `toolFilter`, `agentOptions`, `maxDepth`
  (`packages/subagent/subagent/src/types.ts:32-50`). Teammates therefore run
  the **parent's composition with the deployment persona and the full
  catalog** unless something else scopes them (§4.3).
- **Membership is derived, not declared.** Every ordinary root is the implicit
  Lead; a direct child is a teammate iff the Lead's log holds a `team/member`
  record for it in phase `provisioning|active` (`roster.ts:92-119`). Names are
  immutable and never reused; `maxMembers` counts **every teammate ever
  created, failed ones included** (README "Known limitations"; `roster.ts:271-276`).
- **Durable mailbox and task board** are log-only events on the Lead session
  (`team/member`, `team/task`, `team/message/queued|delivered`, all in
  DSH `persistence-catalog.md:63-66`); replayed on read; survive restart.
- **Web UI** (`client-ui-agent-team`): a header action opening the roster
  (status, model, diagnostics), the task board (create/edit/assign/complete),
  and teammate navigation into the ordinary addressed-subagent conversation
  (`src/client/mount.ts:34-70`). 0.1.6-alpha.2 also opens **any** subagent
  conversation in the right sidebar.
- **Continuable-child capacity.** `maxActiveSubagents` (host `dsh-subagent`,
  default 8) bounds *live* continuable children per root pool; natural
  settlement (idle, empty inbox, no owned children) disposes a child and
  returns its slot (`continuation-activation.ts:724-785`); the GUI edits it in
  **Plugins → Subagent** together with `maxDepth` (default 1)
  (`packages/subagent/subagent/README.md:45-55`).
- **`agent/created` replaces `agent/session-start`**: serial, awaited before
  the first model request, fires on fresh/resume/clear/compaction
  (DSH `subsystems/core.md:933-951`). `tool-agent-team` itself installs its
  scoped tools from this hook (`tool-agent-team/src/index.ts:402`).
- **Per-agent tool policy is public.** `agent.ctx.tools.restrict({allow,deny})`
  works on any scoped context at any time (global names only)
  (`packages/core/tools/src/index.ts:1077-1105`); `agent.ctx.tools.guard(fn)`
  is a monotonic per-call denial that sees `name`, `arguments`, `agent`
  (`:713`, `:309-335`). This is what `applyChildComposition` uses for the
  classic per-child persona and filter (`subagent/src/child-agent.ts:200-219`).

### 2.2 Sessions, models, plugins, browser

- **Deprecated synchronous history reads** — `eventAt`, `snapshotEvents`,
  `ownEvents` (`packages/core/session/src/index.ts:625-666`;
  `…/architecture/2026-09-09-deprecate-synchronous-session-event-reads.md`).
  Existing calls may stay for now; new calls are prohibited; the stated
  direction is to stop retaining full history in memory. The `subagent`
  projection still carries **no persona** (`projection-types.ts`), so the
  `[[rq:role=…]]` descriptor scan has no projection replacement.
- **Default DeepSeek catalog** is now `deepseek-flash` (DeepSeek-V41-Flash,
  text+image, `in-history` system-prompt updates) and `deepseek-v4-pro`
  (`packages/llm/llm-deepseek/src/common/models.ts:6-20`). `deepseek-v4-flash`
  and the vision-exp model are gone (PR #4313). Unlisted ids still pass
  through to the wire as text-only routes, so nothing fails at load — the
  provider decides. **Messages is the default protocol**; efforts are
  `off|low|high|max`.
- **Session events are reported to DeepSeek with requests by default**
  (`session-log-deepseek.enabled: true`, base row
  `packages/bundle/base/cordis.patch.yml:43-44`;
  `…/2026-09-14-session-log-upload-default.md`). A research deployment may
  want `enabled: false` in the profile's user patch.
- **Plugins page.** Configuration moved out of Settings: `plugins.item`
  (official plugins), `plugins.bundle.config` (keyed by the bundle's package
  name), `plugins.row.config` (keyed `<pkg>#<row id>`); each entry renders two
  views, `summary` and `page`; "only a save writes" — no discard control
  (`packages/client/ui-plugin-manager/src/client/slot-contract.ts`;
  `…/2026-09-16-plugin-configuration-on-the-plugins-page.md`). **The
  `settings.plugin.item` slot is retired.**
- **Client sessions are references.** `ctx.sessions.list` no longer carries
  `current`; views obtain their Session from an explicit Provider
  (`scope: 'session'` slots receive `sessionId`), and a plugin can ask
  `sessions.retainInfo(id).retainedBy.mainView` whether a session is in the
  main view (`packages/api/session-controller/src/client/sessions/service.ts:53-68`;
  `…/2026-09-15-client-session-references.md`; removal commit `6830e1460d`).
- **Runtime plugin resolution.** Bare plugin names resolve through an
  immutable per-boot generation installed into Node's ESM/CJS resolvers
  (installation first, then bundles in profile order); the Plugin Manager can
  mount and unload rows live; HMR is non-transactional (a failed activation
  can leave partial state) (`…/2026-09-09-profile-resolution-generations.md`,
  `…/2026-09-09-nontransactional-loader.md`).
- **Patches targeting a missing row id warn and continue**, and a later layer
  may configure a row an earlier layer inserted (`vendor/include/src/index.ts:75-117`).
  Enabling an optional bundle **appends** it to the profile's layer list
  (`packages/boot/plugin-manager/src/operations.ts:91`).
- **Standard preset drift** (`packages/preset/agent-presets/presets/standard/agent.cordis.yml`):
  `tool-subagent` now sets `modelSelectionSettings: true`;
  `workflow-worker-thread` → `workflow-ptc`; external-agent rows use
  `backgroundMode: one-shot` instead of `enableRunInBackground: false` (both
  keys still exist in `tool-subagent`'s `Config`); a disabled
  `tool-plugin-manager` row was added.
- **Base bundle already mounts** `goal` + `goal-round-driver`
  (`base/cordis.patch.yml:300-303`), `spill-local`/`spill-policy` (`:390-394`),
  `mcp-resources` (`:478-479`), `session-log-deepseek` (`:43`). Web mounts
  `workspace-changes` (turn changed-files card) and `ui-schedule`.
- **Hooks bridge** (`@deepseek-ai/dsh-hooks-claude-code`, one `configPath`
  per process, hooks run in the agent's session cwd): `SessionStart`,
  `UserPromptSubmit`, `PreToolUse` (deny/ask), `PostToolUse` (block with
  feedback), `Stop` (force another step), `SubagentStart/Stop` (observe)
  (`packages/hooks/hooks-claude-code/README.md:58-64`). No consecutive-block
  cap on `Stop`.
- **Headless**: `--json` (NDJSON run events), `--session-id`, task on stdin
  (`…/2026-09-09-headless-machine-readable-run-surface.md`).
- **Deliverables**: `present` declares workspace source files (no copy);
  Office files preview in the sidebar; three bundled Office skills
  (python-docx / python-pptx / openpyxl) at the bundled rank; plan cards and
  changed-files cards join the turn tail
  (`…/2026-09-08-present-workspace-source-files.md`,
  `…/2026-09-15-bundled-office-skills.md`, `…/2026-09-17-persistent-plan-cards.md`).
- **Sandbox** still governs file effects only — "network and process policy are
  outside its vocabulary" (`packages/sandbox/sandbox-policy/README.md:148`).
  The Decision 14 residual holes (bash-curl, cross-lane reads) remain
  procedural, but `tools.guard` can now bound `bash` arguments per agent.

---

## 3. Breaks — what must change before this runs on 0.1.6

### 3.1 ★ B1 — the activity floater goes blank (silent)

`dsh/client.js:1079-1081` reads `ctx.get('sessions').list.getSnapshot().current`.
That field was removed when Client Sessions became reference-owned
(`6830e1460d`, 2026-09-17); `SessionListState` is now `{ids, byId, phase,
subagentsByParent, jobsBySession}`. `currentSessionId` stays `null`, the
snapshot is never fetched for a lab, and the pill renders nothing — the same
class of failure as the 0.1.5 "monitor sees nothing" blocker.

**Fix (minimal):** find the main-view session by scanning
`list.getSnapshot().ids` for `sessions.retainInfo(id).getSnapshot().retainedBy.mainView > 0`
(the Team UI uses that exact check, `client-ui-agent-team/src/client/mount.ts:58`).
**Fix (native):** render the pill from a `scope: 'session'` slot
(`conversation.session.header.actions|utilities`,
`ui-conversation/src/client/contract/slots.ts:143-153`) so the Session comes
from the Provider, and drop the global overlay geometry code. §4.6 argues the
whole panel should go native; this item is only the blocker.

### 3.2 ★ B2 — the model-routing card renders nowhere (silent)

`dsh/client.js:800-802` registers into `settings.plugin.item`, which 0.1.6
retired. The card must register into **`plugins.bundle.config`** keyed by the
package name `dsh-rigorquant`, and render two owner-requested views:
`view: 'summary'` (one line under the title) and `view: 'page'` (the form with
its own Save). The page owns title/icon/crumb; discard and the unsaved marker
go (leaving the page drops staged edits). The `settingsSchema` draft model,
`remote.settings.describe` and `remote.session.modelCatalog` seams are
unchanged. `tests/client_bundle_probe.cjs` must switch its slot expectation.

### 3.3 B3 — the shipped fallback names a removed model

`DEFAULT_FALLBACK = deepseek-v4-flash@low` (`dsh/index.js:85`), the README
tables ("`deepseek-v4-flash` @ low"), the client card defaults, and the router
probe all name a model the default catalog no longer lists. Retarget to
**`deepseek-flash`** (DeepSeek-V41-Flash; efforts `off|low|high|max`). Keep
`deepseek-v4-pro@high` as the primary. Note for the persona: V41 Flash
accepts images, so `read_image` becomes usable for roles reading figures.

### 3.4 B4 — deprecated synchronous history reads

Both host halves scan `ownEvents()` for the first `subagent/descriptor`
(`dsh/index.js:330`, `dsh/activity.js:221,236`). Policy: existing calls may
stay; no new ones. Under §4 the scan disappears anyway — role identity becomes
the **teammate name** from `ctx.agentTeams.tryMembership(agent)` (durable in
the Lead log, no regex, no history read) — and the one-shot/cold fallback
keeps the `systemPrompt.assemble` probe, which works on resume because the
child's persona section is re-registered from its descriptor. If Phase 1 ships
before Phase 2, leave the calls in place and add the line-scoped comment that
upstream uses for deferred migration.

### 3.5 B5/B7 — hygiene and the floor

- Replace the disabled `workflow-worker-thread` row with a disabled
  `workflow-ptc` row (`provider: spawn`); disabled rows are never imported
  (`vendor/loader/src/config/entry.ts:131-134`) and preset discovery skips
  them too (`agent-presets/src/discovery.ts:182`), so this is honesty, not a
  mount fix. The same row **enabled** is fatal: discovery marks the preset
  *Failed to load* and the picker hides it (§3.7 finding 1). Align the disabled external-agent rows on `backgroundMode:
  one-shot`. Keep `modelSelectionSettings` **off** (Decision 16).
- Floor → `0.1.6-alpha.2` in `install.sh:18`, both READMEs, the preset header
  comment, and `.rq-sync.json` docs. `install.sh` should also detect whether
  the Agent Teams optional bundle is enabled (`dsh.profile.bundles` in
  `$DSH_HOME/profiles/<p>/package.json`) and print the toggle instruction.

### 3.6 B6 — the live-children pool

Default 8 concurrent continuable children per root. RigorQuant children are
depth-1 and settle naturally when idle, so the pool bounds *concurrency*, not
lifetime. Two consequences: the literature lane's default of 4 parallel lines
plus a 1–2 explorer fan-out plus the second DoubleChecker is ≤ 8 only if the
orchestrator sequences the lanes; and the SKILL should say "fan-out is bounded
by the host's `maxActiveSubagents` (Plugins → Subagent); `ACTIVATION_LIMIT_REACHED`
means wait for a child to settle, never retry in a loop". Optionally the
README suggests raising it to 12 for literature-heavy studies.

### 3.7 Verify, do not assume (Phase 0 results, 2026-09-21, built 0.1.6)

The three items the source read left open, each with what the built install
did (Phase 0, issue #4; environment in §6):

- `cordis.patch.yml`'s `createRequire(baseUrl + 'package.json').resolve('dsh-rigorquant/package.json')`
  under **runtime resolution mode**: `baseUrl` is still the profile directory,
  and profile-local `node_modules` are checked before the virtual fallback.
  **Confirmed.** On the `rq16` profile the Plugins page lists the bundle's
  four components — `skill-filesystem-rigorquant`, `rq-model-router`,
  `rq-activity`, `rq-preset-sync` — all *Running*; the skill-root row is the
  one that evaluates that expression, so it resolved.
- Plugin Manager live unload: both host halves register through `ctx.effect`/
  `ctx.on` and the activity routes through `internal/service`; confirm that
  toggling the `rq-*` rows off and on in the Plugins page leaves no dangling
  route or listener. **Not exercised in Phase 0** — it is the Phase 1 release
  check (spec: "verified on a real 0.1.6 profile before release").
- `tests/preset_harness_probe.cjs` against a built 0.1.6. **Green**: 38 rows,
  0 hard failures, 6 without an exported Config, exactly one `UNRESOLVED`
  (`@deepseek-ai/dsh-workflow-worker-thread`, disabled — B5 as predicted).

**Probe results against the install** (`dsh --version` = `0.1.6-alpha.2`,
packages under the global install's `node_modules/@deepseek-ai`):

| Probe | Runs against | Result |
|---|---|---|
| `preset_harness_probe.cjs` | the installed packages' `Config` schemas | green (the bullet above) |
| `router_probe.cjs` | a stub host context (never the install) | green — `ok: true`, both degrade paths and both effort demotions logged |
| `client_bundle_probe.cjs` | a stub slot registry (never the install) | green — registers, `inject` intact, `modelCatalogCalls: 1` |

The two stub-bound probes are green **because** they stub the surfaces that
changed: neither can see B1 or B2. B1–B3 were therefore confirmed by reading
the installed packages directly:

- **B2**: no installed `lib/*.js` mentions `settings.plugin.item`;
  `dsh-client-ui-settings-plugins@0.1.6-alpha.2` declares `settings.plugins`,
  `settings.plugins.tab` and `settings.section` only; `plugins.bundle.config`
  is declared by `dsh-client-ui-plugin-manager` (`kind: 'keyed', scope:
  'root'`). The 0.4.1 card's ring does not exist → B2 stands, and the
  client-bundle probe must grow a real slot-name assertion (spec seam 2).
- **B1**: the installed `SessionListState` (`dsh-api-session-controller/lib/
  types/client/sessions/service.d.ts:42`) is `{ids, byId, phase,
  subagentsByParent, jobsBySession}` — no `current`. `retainInfo(` and
  `retainedBy.mainView` exist in the installed session controller and the Team
  UI reads them, so the §3.1 fix has its API.
- **B3**: the installed `dsh-llm-deepseek` catalog is `deepseek-flash`
  (DeepSeek-V41-Flash, `inputModalities: ['text', 'image']`) and
  `deepseek-v4-pro`. `deepseek-v4-flash` survives only as a locale key in
  `dsh-client-ui-model-selection` and as `dsh-web-search-deepseek`'s own
  default — not as a routable model.

**Manual run** (0.4.1 preset = master `fbdd80e`, profile `rq16` with both
Team bundles on, ~5 minutes, workspace `rigorquant_studies`; a smoke prompt,
no study started). Issue #4 expected B1 and B2 to be the only visible
regressions; **that did not hold** — finding 1 is a third one, and findings
5–6 are visible changes the break list did not name. Likewise the criterion
expected the client-bundle probe to surface the retired slot; it cannot (it
stubs the registry), so B2 was confirmed from the installed files above.
Findings, most important first:

1. **The shared preset copy was stale and the preset showed "Failed to load".**
   `$DSH_HOME/.agent-presets/rigorquant/` was the Sep 6 tree (single-key
   `text:` persona, an *enabled* `workflow-worker-thread` row) stamped
   `.rq-sync.json` = `0.4.1`. The 0.1.5 port landed on master after the
   0.4.1 release without a version bump, so `rq-preset-sync`'s local-edit
   rule ("a target stamped with the current version is left alone") kept the
   old tree on every boot. On 0.1.6 the preset settings card reads *Failed
   to load — row "workflow-worker-thread" names a plugin that cannot be
   resolved* and the session picker hides the preset. Discovery does skip
   `disabled: true` rows (`agent-presets/src/discovery.ts:182`), so a
   **disabled** unresolvable row is the hygiene item B5 says it is; an
   **enabled** one makes the preset unselectable. Re-running `install.sh`
   (`DSH_PROFILE=rq16`) replaced the tree and the preset loaded. The `web`
   profile shares that directory and would have shown the same. Consequence
   for Phase 1: the 0.4.2 version bump is what makes the sync replace the
   preset; until then every profile on this machine is one `install.sh`
   behind master.
2. **B1 confirmed live.** With a child running, `[data-shell-overlay]` holds
   the floater's mount with empty content; no fixed-position element exists
   on the page. The native "N subagents" breadcrumb is the only sign of the
   child.
3. **B2 confirmed live.** The bundle page shows version, description and the
   four components and nothing else; Settings → Built-in plugins is an
   inventory (Session / Global) with no per-plugin cards.
4. **Teams enabled, roster header action present.** A fresh RigorQuant
   session's header shows *Agent Team*; the panel lists `lead` (Idle) and an
   empty shared task board with *New task*. Classic `subagent_*` children are
   not members and do not appear — as expected.
5. **The classic orchestrator sees both mechanisms.** Its request carried
   36 tools: the seven `subagent_<role>` rows **plus** `spawn_teammate`,
   `list_agents`, `send_message`, `interrupt_agent`, `wait_agent` and
   `team_task_create/get/list/update`. The Team layer is a profile (host
   plane) patch and the preset is agent plane, so a Teams-enabled profile
   hands the 0.4.2 orchestrator Team tools its persona never mentions. A
   one-shot child (depth 1, `agentPreset: rigorquant`) saw the same nine Team
   tools. Phase 1 must decide whether 0.4.2 says anything about them; a
   tool restriction cannot name them (they are not mounted on every
   deployment), so it is persona wording or nothing.
6. **Delegation and delivery work on a live route.** `subagent_adversary`
   (routed by the stored override to `zai/glm-5.3@high`) returned its final
   message verbatim (`2+2=4`): one-shot `spawn`, descriptor `{version: 3,
   mode: 'one-shot', provider: 'spawn'}`, final-message delivery intact.
   `subagent_explorer` died with *subagent run failed* because the operator's
   stored explorer route names a distributor model the provider no longer
   serves (`503 model_not_found`, retried 5× by `llm-retry`, turn ended in
   error). That is the operator's route, not the harness; but the same
   settings hold several fallbacks on `deepseek-official/deepseek-v4-flash`
   and `…-vision-exp`, so **B3 also bites stored routes**, not only the
   shipped default. The router correctly stayed out of it: a 5xx is not
   `routeFatal` (4xx / `NO_ADAPTER` / usage-limit only, Decision 16).
7. **The roster's Model column does not show the routed model.** The panel
   showed `lead · Model: deepseek-v4.1-flash-…` (the session's
   `agent-default-model`) while the orchestrator's requests were rewritten to
   `zai/glm-5.3`. The roster reports `options.model` from the agent
   (`agent-team/src/roster.ts:137,447`), not what left the wire. The spec's
   "the roster's per-member model column shows the routed model natively"
   holds only if the team plugin sets the created teammate's `model` option
   rather than rewriting at `agent/request` — a Phase 2 design input.
8. **`agentPreset` in the session header is the default.** The orchestrator's record's
   first line says `agentPreset: standard`; the truth is the
   `agent-preset/selected` event (seq 4). Children carry `rigorquant` in the
   header. Nothing in this repository reads the header field.

Commands and paths: `node tests/preset_harness_probe.cjs`;
`node tests/router_probe.cjs dsh/index.js`;
`node tests/client_bundle_probe.cjs dsh/client.js dsh-rigorquant`;
`dsh rq16 --dump-config` (Team rows follow the base/web layers, the
RigorQuant patch follows them); session records under
`$DSH_HOME/sessions/--Users-linxi-gits-rigorquant_studies--/`.

### 3.8 Phase 1 release verification (2026-09-22, 0.4.2)

The release checks the spec names, run against the release tree itself
(issue #8). The scratch profile this time is **`rq6`** — recreated for this
run (worktree `file:` install of the 0.4.2 tree via pnpm hardlinks, both
Team bundles on, `dsh --profile rq6 --no-open --port 38116`) — because the
release must be verified on the code it ships, not the master clone `rq16`
installs.

- **Harness probe green.** `node tests/preset_harness_probe.cjs` against the
  installed `0.1.6-alpha.2`: **38 rows, 0 hard failures, 0 UNRESOLVED**,
  7 rows without an exported Config — one more than §3.7's six because the
  renamed `workflow-ptc` row resolves but exports no Config, where the
  retired worker-thread name was the UNRESOLVED. No row is expected to be
  unresolved, and none is.
- **The version bump replaced the shared preset.** §3.7 finding 1's
  mechanism held in the release direction: `install.sh` (run from the
  worktree with `dsh` off PATH, so the plugin step skips by design) replaced
  `$DSH_HOME/.agent-presets/rigorquant`, and `rq-preset-sync` stamped
  `.rq-sync.json` = **0.4.2** at first boot.
- **Package-relative patch resolution under runtime mode, on the release
  tree.** The bundle page on `rq6` shows **v0.4.2** (the pnpm hardlink serves
  the worktree's `package.json`) with **4 total · 4 running**:
  `skill-filesystem-rigorquant`, `rq-model-router`, `rq-activity`,
  `rq-preset-sync`. The skill-root row is the one evaluating
  `createRequire(baseUrl + 'package.json').resolve('dsh-rigorquant/package.json')`,
  so it resolved against the worktree install under the same boot-root
  `baseUrl` §3.7 confirmed. The bundle page also renders the
  **RigorQuant model routing** card between the description and the rows —
  the `plugins.bundle.config` registration of B2's fix, live.
- **Plugin Manager live unload leaves nothing dangling.** The check §3.7
  deferred to Phase 1. With all four rows Running, both HTTP routes answer
  200 (`/plugins/dsh-rigorquant/activity` JSON snapshot,
  `/plugins/dsh-rigorquant/avatar/avatar-explorer.png`). All four RigorQuant
  rows toggled **off** in the Plugins page: both routes **404**, the page
  reads "4 total · 4 off". Toggled back **on**: "4 total · 4 running", both
  routes 200 again with a valid snapshot. `rq-activity` alone was cycled off
  and on twice more (three unload/reload transitions of the route-owning
  component in total): every off state 404s, every on state 200s — no
  duplicate-route throw, no wedged `routesRegistered` flag, and the host log
  stayed silent throughout (a leaked `ctx.on` listener or a stranded
  disposer would surface as one of those). The browser console holds only
  the expected resource errors (the pre-auth 401 loads and the 404s of the
  probes themselves while the rows were off); no JS exception.
- **§8 decision 7 disposed: nothing.** 0.4.2 ships no persona wording about
  the nine Team tools a Teams-enabled profile hands the classic orchestrator
  (§3.7 finding 5). This is the line for profiles that cannot enable Teams,
  so most of its sessions never see them; the persona speaks when Decision
  24 replaces the mechanism wholesale.
- **Suite and gate.** `RQ_COVERAGE=1` full suite green with the coverage
  gate ≥ 95% (CI parity), including the new consistency test pinning the
  two version stamps together.

### 3.9 Phase 2 tracer bullet: `rq-team` composition (2026-09-22, issue #9)

`dsh/team.js` applies each teammate's persona and tool-tier budget purely
from its NAME, resolved through the installed `0.1.6-alpha.2` harness's
real `agentTeams` service — verified by reading the shipped `.d.ts` files
directly (not the pre-written design in §4.3 alone): `TeamService` really
registers as `agentTeams`; `tryMembership(agent)` is the exact non-throwing
call the shipped `@deepseek-ai/dsh-experimental-tool-agent-team` package
itself uses to scope its own tools; `agent/created` really fires on all four
of `startup`/`resume`/`clear`/`compact`, confirming composition must be
reapplied on every one, not just twice as §4.3's prose loosely implied.

One correction to §4.3's own sketch, found by reading the harness's
`dsh-system-prompt` types in full: the "RigorQuant team guard: armed" line
is a `systemPrompt.context()` registration (`PromptContext`/`CONTEXT_ORDERS`
— "dynamic model context materialized as a durable user-role snapshot", the
same family as the harness's own `SANDBOX_POLICY`/`APPROVAL_POLICY`/
`SUBAGENT_DELEGATION` context entries), not a second `systemPrompt.section()`
call — the issue's own wording ("a runtime context line") names the correct
API precisely. The persona itself stays a `.section()` at
`deployment:persona-prefix`/order 0, matching `dsh/index.js`'s existing
`PERSONA_SECTION` read.

- `tests/team_probe.cjs` + `tests/test_team_plugin.py` (13 tests): plugin
  mounts clean; DoubleChecker (blind) loses web/skill/goal/todo/ask-user/
  plan-mode; Explorer (open) keeps web/skill; Adversary (web-denied) keeps
  skill; an unparseable teammate name and a non-RigorQuant team are both
  silently untouched; the orchestrator gets the armed *context* (not a
  section); a `resume`-sourced re-creation disposes the first registration
  and installs a fresh one (proves reapplication, not a skipped no-op);
  `agentTeams` absent logs one warning and no armed context appears
  anywhere; the module declares no hard `agentTeams` dependency and
  imports no experimental package.
- `tests/test_repo_consistency.py` (+2): the router's `ROLES`,
  `dsh/team.js`'s `TEAMMATE_ROLES`, and the `dsh/personas/*.md` file set
  must name exactly the same seven roles, each file stating its own role
  name up front; the persona-section-name literal is pinned equal on both
  `dsh/index.js` and `dsh/team.js`.
- Full suite: 331 passed, 1 skipped; coverage 96.3% ≥ 95%.
- **Confirmed composing on the installed `0.1.6-alpha.2`** (`rq6` profile,
  Team bundles on, `dsh --profile rq6 --dump-config`): the `rq-team` row
  appears in the composed profile tree, enabled, after `rq-preset-sync`.
  `dsh/team.js` imports cleanly from the profile's linked copy (`name`,
  `inject`, `TEAMMATE_ROLES`, `apply` all resolve). The server boots with a
  clean log — no mount error, and no `agentTeams absent` warning, consistent
  with the Team bundles being enabled. The Plugins page shows the bundle at
  v0.4.2 with **5 total, 5 running** components, `rq-team` among them,
  and the "RigorQuant model routing" card renders (Root orchestrator's
  stored override: `zai/GLM-5.3` @ high — explains why every turn routes
  there regardless of the chatbox picker; Decision 16, unrelated to #9).
- **The interactive demo, run for real** on `rq6`: asked the live
  orchestrator to (1) quote any context line naming "RigorQuant team
  guard" and (2) `spawn_teammate` a `doublechecker-1` and relay its own
  persona's first sentence and tool catalog. Both checks came back exactly
  as designed, from the model itself with no knowledge of the
  implementation:
  - *Check 1*: `"RigorQuant team guard: armed"` — the orchestrator located
    it in "the runtime-context block injected into the conversation
    (`Current runtime context.` snapshot), not in my system prompt
    proper — my system prompt contains no occurrence of that string." An
    independent, live confirmation of Decision 1's `.context()` (not
    `.section()`) correction — the model itself distinguishes the two
    slots without being told the mechanism.
  - *Check 2*: `doublechecker-1` reported `PERSONA_FIRST_SENTENCE: You are
    a RigorQuant DoubleChecker working in epistemic isolation.` — verbatim
    against `dsh/personas/doublechecker.md` — and a `TOOL_CATALOG` missing
    exactly the nine denied tools (`web_search`, `web_fetch`, `skill`,
    `create_goal`, `update_goal`, `get_goal`, `todo_write`,
    `ask_user_question`, `exit_plan_mode`) while keeping everything else
    (including the still-mounted classic delegation tools and the Team
    tools per-call guards don't yet restrict — both correctly out of #9's
    scope).
  The resume half of the demo (restart, reconfirm) was not repeated live
  after this — `tests/test_team_plugin.py`'s `resume`-sourced scenario
  already proves reapplication deterministically, and the account's
  5-hour usage quota (exhausted mid-session, `code: 1308`, identical
  across `zai`, `linxicloud`, and `deepseek-official` routes — confirming
  it is account-wide, not model- or provider-scoped) made further live
  turns impractical.

### 3.10 Phase 2, topology by guard: per-call enforcement (2026-09-22, issue #10)

`dsh/team.js` gained the second half of Decision 24's "enforcement by
scope": a `tools.guard` per composed member, alongside the `tools.restrict`
#9 shipped. Restriction masks only the GLOBAL tool catalog and cannot reach
the scoped Team tools `tool-agent-team` registers directly in each member's
own scope (`send_message`, `list_agents`, `team_task_list`, `team_task_get`,
`team_task_update`, `spawn_teammate`), so hub-and-spoke and roster/board
blindness were still procedural, not enforced, until this issue.

- Every teammate's guard: `send_message` denied unless the target is the
  literal string `'lead'` (the Team tool's own prompt teaches this name for
  the Lead); `list_agents`/`team_task_list` denied outright, unconditionally
  — reading the ADR's "Consequences" section against §4.3's own earlier
  draft wording ("for blind roles") settled this in favor of the ADR: every
  teammate is roster-blind, not just the blind tier; `team_task_get`/
  `team_task_update` denied when the named task's live `ownerName` (read
  through `agentTeams.getTask`, never cached) belongs to someone else —
  an unowned task stays reachable, or `team_task_update(action: 'claim')`
  could never succeed on a fresh task; for web-denied roles (blind roles
  plus Adversary/Document adversary) a `bash` command matching
  `\b(curl|wget|pip\s+install|uv\s+(sync|add|pip))\b` is refused.
- The orchestrator's guard: `spawn_teammate` denied when `name` does not
  parse to `<role>-<n>`, or when `context` is `'fork'`.
- `tests/team_probe.cjs` now drives a fake call through every rule (not just
  records restriction/section calls): sibling `send_message` denied / Lead
  allowed, roster/board tools denied, a foreign task denied and an unowned
  or own task allowed, a bash network verb denied for a web-denied role and
  allowed for an open role, and the orchestrator's bad-name/fork refusals —
  15 checks, one guard function per composed member, invoked directly
  (`tests/test_team_plugin.py`, +7 tests over #9's 12).
- `tests/test_repo_consistency.py` gained
  `test_team_guard_enforces_the_same_hub_and_spoke_the_pillbox_map_draws`,
  next to the pillbox-map pin it names: the guard's one legal `send_message`
  target must be the named `LEAD_TARGET` constant equal to `'lead'`, and
  `list_agents`/`team_task_list` must be denied unconditionally (no tier
  narrows that set).
- Full suite: 338 passed; coverage unchanged at 96.3% (the guard is
  JS-side, covered by the Node probe, not the Python coverage gate).
- **Not yet done live**: the issue's demo line ("a teammate's sibling
  message and a DoubleChecker's `curl` show as refused in its
  conversation") needs an interactive session against the installed
  `0.1.6-alpha.2` profile, the way #9's demo (§3.9) ran. The installed
  `rq6`/`rq16` profiles' `dsh-rigorquant` plugin is a copy taken from the
  master checkout at spawn time (`dsh plugin add file:...`), not a link to
  this worktree, so re-syncing it first is required; deferred rather than
  spending another live session's quota on it without being asked.

---

## 4. The centrepiece — RigorQuant on Agent Teams

### 4.1 Why Teams fits this framework

| RigorQuant need | Today (0.4.x) | With Agent Teams |
|---|---|---|
| Role identity | `[[rq:role=…]]` regex over persona text, scanned from history (`dsh/index.js:135-138,330`) | the teammate **name** (`explorer-1`, `doublechecker-2`…): durable in the Lead log, in every roster row, in the Web UI |
| Fan-out / wait | spawn N children, then rely on settlement notices waking the orchestrator | `spawn_teammate` ×N, then `wait_agent` — a native blocking primitive; the settlement notice still lands in the Lead's turn stream (`subagent/README.md:109`) |
| Round state / who-does-what | `registry.json` + `journal.md` (evidence) plus a move heuristic that greps tool names (`dsh/activity.js:132-141`) | the **shared task board**: sub-problems as tasks, the four moves as a `blocked_by` DAG, ownership by claim, CAS revisions; the move is "first task not completed" — no heuristic |
| Per-role scratch dirs ("keep your work in your own scratch directory") | prose | advisory `write_scopes` (`interim/<teammate>/`) with **overlap warnings rendered natively** |
| Interim findings / blocking questions | `send_message` to a parent id the brief had to carry | `send_message` to `lead`, durable, cold-resumes an inactive orchestrator |
| "Never message an in-flight agent" (Decision 19 L3) | a procedural rule born from lost/duplicated deliveries | mailbox is durable, ordered, de-duplicated; the *freeze-until-verdict + hash* half of L3 stays |
| Live team view | 2,360 lines of monitor + floater, served over a custom route | roster + task board + per-teammate model + navigation, shipped |
| Human intervention | one human turn re-arms the goal | plus: the human can open any teammate's conversation and steer it directly |

What Teams does **not** give, and the plan re-establishes (§4.3): per-teammate
persona, tool budget, model tier, and the hub-and-spoke topology (any member
may message any member by default).

### 4.2 Mounting decision — consume the shipped optional bundle

Do **not** mount `agent-team`/`tool-agent-team` inside the preset or in
`cordis.patch.yml`:

- `TeamService` is a `TypertRemoteService` (browser Remote `agentTeams/*`)
  and registers a global session projection (`agent-team/src/index.ts:59-120`);
  a second instance collides (`provide()` throws on duplicate realm/name), and
  the Web UI expects the host-plane one.
- "Released products must not depend on experimental packages" is upstream's
  rule for itself, but it signals churn: RigorQuant should **not import** the
  experimental packages at all. Use `ctx.get('agentTeams')` duck-typed, and
  fail loudly when absent.
- The Team profile's disables are no-ops on web (§2.1), so enabling it changes
  nothing else in a RigorQuant session.

So: `README` Install gains one step — *enable Agent Teams (Beta) in Settings →
Plugins* (or `dsh plugin --profile web add @deepseek-ai/dsh-experimental-agent-team-profile
@deepseek-ai/dsh-experimental-agent-team-web-profile`) — and `install.sh`
checks for it.

**`maxMembers` is a lifetime cap (8 in the shipped profile) and RigorQuant
needs more.** Nine role slots exceed 8 before a second round starts. Two
levers, use both:

1. A user-layer override (`$DSH_HOME/profiles/<p>/cordis.patch.yml`, applied
   after every bundle, so order-proof): `- id: agent-team` with the whole
   config restated (`maxMembers: 64`, others at their defaults — a patch
   replaces the row's `config` wholesale). `install.sh` appends it
   idempotently under a `# dsh-rigorquant` marker and prints what it wrote;
   `--uninstall` removes it. Also ship the same override in RigorQuant's own
   `cordis.patch.yml` — it applies when the Team layer precedes ours and only
   warns otherwise.
2. A roster policy in the skill (§4.4) that reuses teammates where the science
   allows, so the lifetime count grows slowly.

### 4.3 The new host half: `rq-team` (roles by name, enforcement by scope)

One plugin row (`dsh-rigorquant/team`, `inject: []`, optional
`agentTeams`), replacing the role-tag machinery in the router and the whole
monitor. On every `agent/created` (fresh **and** resume — the persona must be
re-applied on cold resume because nothing persists it in the child's
descriptor):

1. `preset = ctx.get('agentPresets')?.composedPreset(agent.ctx)`; skip unless
   `rigorquant` (a teammate joins its parent's composition in the creation
   window, before `agent/created`).
2. `m = ctx.get('agentTeams')?.tryMembership(agent)`; `role = m.role === 'lead'
   ? 'root' : roleFromName(m.name)` with the convention
   `^(explorer|offgrid|doublechecker|adversary|lit-line|lit-adversary|doc-adversary)(-[a-z0-9]+)?$`.
3. For a teammate with a role, on `agent.ctx` (exactly what
   `applyChildComposition` does for classic children, `child-agent.ts:200-219`):
   - `systemPrompt.section({ name: 'deployment:persona-prefix', order:
     getSectionOrder('DEPLOYMENT_PERSONA_PREFIX'), text: ROLE_PERSONA[role] })`
     — the role persona shadows the orchestrator persona for this teammate.
   - `tools.restrict({ deny: ROLE_DENY[role] })` for **global** tools:
     blind roles deny `web_search, web_fetch, skill`; every role denies
     `create_goal, update_goal, get_goal, todo_write, ask_user_question,
     exit_plan_mode`. (`tools.restrict` throws on unknown names — the lists
     may only name tools every deployment mounts, as today.)
   - `tools.guard(exec => …)` for the **scoped Team tools**, which
     `restrict` cannot mask: deny `send_message` unless
     `arguments.target === 'lead'` (hub-and-spoke, now *enforced*); deny
     `list_agents` and `team_task_list` for blind roles; deny
     `team_task_get/update` on a task the caller does not own (read the board
     through `agentTeams.getTask`); for blind roles, deny `bash` whose
     command matches `\b(curl|wget|pip\s+install|uv\s+(sync|add|pip))\b` — the
     bash-curl residual hole shrinks from "audited" to "denied at the call".
4. For the orchestrator, guards on `spawn_teammate`: deny a `name` that does not
   parse to a role (an unnamed teammate would run the *orchestrator* persona
   with the full catalog — the exact failure Decision 8 forbids), and deny
   `context: 'fork'` (Decision 8: fork inherits the parent conversation).
5. Register a runtime context line on the Lead — `RigorQuant team guard:
   armed` — so the persona can say: *if that line is absent, do not spawn;
   report the missing plugin.* This is the only defence when the preset is
   synced but the plugin is not mounted.

The router (`dsh/index.js`) keeps its `agent/request` overlay and fallback
lane, but resolves the role through `rq-team` (name), and now carries the
**shipped tier matrix itself** (`ROLE_PRIMARY`: doublechecker/adversary →
`deepseek-v4-pro@high`; fallback `deepseek-flash@low`) because there is no
native `agentOptions` row to defer to any more. The card's "reset" therefore
returns to the shipped default rather than to a native route; the `NATIVE_PRIMARY`
distinction and the raw user-section dance can go. The roster's per-member
`model` column reports the agent's `options.model`, not what the router put
on the wire (§3.7 finding 7): for the column to show the route, `rq-team`
must set the teammate's model option at creation rather than rewrite each
request — the spec's "shows the routed model natively" holds only then.

Upstream, in parallel: a small PR adding optional `persona`, `toolFilter`,
`agentOptions` to `SpawnTeammateRequest` and passing them to
`startContinuable` (they are already accepted there, `subagent/src/types.ts:47`)
would make step 3 durable in the descriptor and delete most of `rq-team`.
Until then the plugin-side application is the supported path (it is the
pattern `tool-agent-team` uses for its own tools).

### 4.4 Preset and skill rewrite

**Composition (`agent.cordis.yml`).** Remove the seven `tool-subagent-*` role
rows, `tool-subagent-control`, `tool-subagent-list-agents`, and the disabled
fork row (the Team's scoped tools replace them for the whole team). Keep
external-agent rows disabled. Keep `maxDepth` semantics by construction:
`spawn_teammate` is Lead-only in the service, and no other delegation tool is
mounted. The persona's ISOLATION paragraph changes from "per-role delegation
tools" to "the `rq-team` guard: role by name, tool budget by scope, topology by
guard; still not a network wall".

**Naming and roster policy (SKILL.md Step 3, protocol.md).**
`<role>-<n>` names; descriptions are role labels only (never a brief — every
member can read `list_agents`). Fresh teammate per brief for `explorer`,
`offgrid`, `doublechecker` (blank context is the point); **reuse** `adversary`,
`lit-adversary`, `doc-adversary`, and each `lit-line` across rounds via
`send_message` (their accumulated knowledge is the job, and reuse keeps the
lifetime count down). Fan-out bounded by the pool (§3.6).

**Round loop as a task DAG.** At Promise, the orchestrator creates the round's
tasks with `blocked_by`: `explore-<sub>` ×k → `ground-truth-<claim>` ×2 →
`attack-<sub>` → `certify-<round>`. Each teammate's brief names its task id;
the teammate claims it (CAS), works under `write_scopes: [interim/<name>/]`,
completes it, and ends its turn with the verdict/derivation as its final
message (unchanged delivery contract). The orchestrator's wait is
`wait_agent` (re-list on wake; `noProgress` means wake someone first), never
polling. `registry.json`/`journal.md` remain the *evidence* record and the
validator never reads the board — coordination is not proof (Decision 13).

**Team policy text.** The fixed section says teammates are created only on an
explicit request; the orchestrator persona states that a RigorQuant study **is**
that request. `send_message` guidance ("do not resend a queued message") is
native now; protocol.md L3 keeps only the freeze-and-hash half.

**Blind roles cannot load skills** (unchanged): their personas stay complete
in `rq-team`'s `ROLE_PERSONA` table (moved out of the composition into the
plugin, with a repo test that the two never drift and that each persona keeps
its role name).

### 4.5 Tests that move

- `tests/test_role_tool_budgets.py`, `test_blind_deny_list.py`,
  `conftest.py::BLIND_TOOLS/DELEGATION`: budgets become `ROLE_DENY` + guard
  tables exported by `rq-team`; add a guard probe (`tests/team_probe.cjs`)
  that fakes `agentTeams.tryMembership` and asserts: sibling `send_message`
  denied, `lead` allowed; blind `bash curl` denied; `spawn_teammate` with a
  non-role name or `fork` denied; persona section registered with the right
  name and order; re-applied on `source: 'resume'`.
- `router_probe.cjs`: role from membership name; shipped matrix applied when
  no override; fallback on `deepseek-flash`.
- `test_repo_consistency.py`: tag↔row identity → name↔persona identity; the
  hub-and-spoke pin now asserts the guard table (no non-lead targets).

### 4.6 The browser half — go native, keep a thin pill

Retire `dsh/activity.js` (host), `tests/activity_probe.cjs`,
`tests/test_activity.py`, and the floater/panel/geometry code in
`dsh/client.js` (≈1,400 lines). The Team UI already shows the roster, status,
model, diagnostics, and the task board, and opens teammates in the sidebar.

Keep one small **move pill** in `conversation.session.header.utilities`
(`scope: 'session'` → the Session is provided; B1 disappears) that calls
`ctx.remote.agentTeams.view(leadSessionId)` and derives the move
from the task board (first incomplete of `promise/fan-out/ground-truth/attack/certify`)
with the role portraits for running teammates. The `remote.agentTeams` namespace
is mounted by the Team web bundle; inject it optionally and render nothing
when absent. The README's hub-and-spoke SVG stays as the static picture of the
topology the guards enforce.

Move the model-routing card to `plugins.bundle.config` (B2) with
`summary`/`page` views; drop Discard.

---

## 5. Other native adoptions (cheap, mostly free)

| # | Feature | Verdict | What to do |
|---|---|---|---|
| N1 | `goal-round-driver` host-mounted (`base:302`) | already native | fix the docs: the 0.1.5 study said "mount it"; it is mounted. Persona wording stays ("one human turn re-arms across a restart"). |
| N2 | `present` + sidebar Office preview + bundled Office skills | adopt | deliverables.md: `present` every deliverable (already), and allow the slides deliverable to be `.pptx` through the bundled `pptx` skill when the study asks; the document adversary audits the rendered text either way |
| N3 | `workspace/changes` per-turn card | adopt (docs) | Decision 19's "frozen until the verdict lands": the card is the human-visible witness of an edit after certification; `rq_check` keeps reading the study record, not the session |
| N4 | Hooks bridge, `Stop` event | optional, guarded | a preset row mounting `@deepseek-ai/dsh-hooks-claude-code` with a `hooks.json` whose `Stop` hook runs `rq_check.py --stop-gate`: block the stop when `study.json` asserts a certification outcome the record does not back. Must self-limit (no upstream consecutive-block cap) — at most two blocks per round, tracked in `interim/`. |
| N5 | Headless `--json`/`--session-id`/stdin | adopt (docs) | a "batch study" recipe: `dsh --profile headless --json --session-id study-<slug> - < brief.md`, events piped to a log; the goal re-arm rule is unchanged |
| N6 | `spill` in base | note | oversized tool results become bounded previews with locators; keep the pruner at 4 KiB; add one line to the persona: read a spilled result back with the locator instead of re-running |
| N7 | `mcp-resources` in base | note | when `mcp-jacobian` is enabled, resource tools appear for every teammate; same residual-hole rule as the checker lane (persona) |
| N8 | Subagent conversations / plan cards in the sidebar | free | README "The team, live" |
| N9 | `session-log-deepseek` default on | deployment note | README: how to disable in the user patch |
| N10 | Auto review, browser/computer use, schedule | skip | orthogonal; children already run with `approvalPolicy: never` |
| N11 | `modelSelectionSettings` | keep off | Decision 16 stands: the fixed tier matrix must not be caller-selectable |

---

## 6. Environment before any code moves (done 2026-09-21)

What the plan said, and what was actually run, in order:

1. Install the alpha: `npm i -g @deepseek-ai/dsh@alpha` — the **global**
   install, no isolated prefix (decided during grilling; the previous
   `0.1.5-rc.2` is one `npm i -g @deepseek-ai/dsh@0.1.5-rc.2` away).
   `dsh --version` → `0.1.6-alpha.2`. The install ships the five
   `dsh-experimental-agent-team*` packages beside the 255 others.
2. Scratch profile: `dsh rq16 --from-default-profile web --dump-config`
   creates `$DSH_HOME/profiles/rq16` from the web template and exits. Both
   Team bundles were switched on by appending
   `@deepseek-ai/dsh-experimental-agent-team-profile` and
   `…-agent-team-web-profile` to `dsh.profile.bundles` in the profile's
   `package.json` — the same manifest write the Plugins page makes for an
   optional bundle (`plugin-manager` `setBundleEnabled`); nothing is installed
   into the profile, the packages resolve from the installation. Then
   `dsh plugin --profile rq16 add file:$HOME/gits/dsh-rigorquant` (the master
   checkout, `fbdd80e`) for the plugin half only. `dsh rq16 --dump-config`
   shows the two Team rows after the base/web layers and the RigorQuant rows
   after them.
3. Probes and installed-file inspections: §3.7.
4. Manual run: `dsh rq16 --no-open --port 3416`, then the Plugins page, the
   Settings → Agent presets card (where the preset read *Failed to load* —
   §3.7 finding 1, against the shared preset tree as it stood), then
   `DSH_PROFILE=rq16 ./install.sh` from the master checkout to refresh
   `$DSH_HOME/.agent-presets/rigorquant` and `$DSH_HOME/share/rigorquant`
   (and re-add the plugin, a no-op), a reload, and a RigorQuant session in
   the `rigorquant_studies` workspace with a smoke prompt (tool list, persona
   line, one `subagent_explorer`, one `subagent_adversary`); §3.7.

To reproduce finding 1, run step 4 before any `install.sh` — the installer
replaces the shared tree unconditionally and hides it. The `web` profile is
untouched except that it shares those two directories, which now hold
master `fbdd80e`.

---

## 7. Execution order

**Phase 0 — Environment and evidence** (§6). No code. **Done 2026-09-21**
(issue #4); results in §3.7.

**Phase 1 — Compatibility (0.4.x still classic; releasable as 0.4.2)**
B1 (minimal `retainedBy.mainView` fix), B2 (card → `plugins.bundle.config`),
B3 (`deepseek-flash`), B5/B7 (rows, floor, docs), B6 (SKILL wording),
§3.7 verifications, probes updated. This is the safety net if Phase 2 slips.
**Done 2026-09-22** (issues #5–#7, released as 0.4.2 by #8); results in
§3.8.

**Phase 2 — Agent Teams (0.5.0)**
`dsh/team.js` (`rq-team`) + `ROLE_PERSONA`/`ROLE_DENY`/guards; router keyed
by membership; preset rows removed; persona + SKILL.md + protocol.md +
lifecycle.md + literature.md rewritten around `spawn_teammate`/`wait_agent`/
task DAG; `install.sh` Teams check + `maxMembers` user-patch override;
`cordis.patch.yml` row + override; tests in §4.5; CHANGELOG; architecture.md
**Decision 24** (Teams: identity by name, enforcement by scope, topology by
guard) amending 8, 14, 16, 19, 20, 23. The composition half (`dsh/team.js`,
the seven `dsh/personas/<role>.md` files, the `cordis.patch.yml` row) is
**done 2026-09-22** (issue #9 — the first tracer bullet: persona +
global tool-tier budget applied per teammate by name, and the
orchestrator's "guard armed" runtime context); results in §3.9. Router
role-resolution by membership (#11), classic preset-row removal (#14), and
`install.sh`'s
Teams-enabling (#12) land separately — the classic `[[rq:role=...]]`
mechanism and the seven classic delegation rows coexist with `rq-team`
until #14.

**Phase 3 — Browser goes native (0.5.0)**
retire `activity.js` + probes + tests; thin move pill on
`remote.agentTeams.view`; README "The team, live" rewritten around the native
roster/task board; `docs/figs/agent-team-activity.*` kept as the static
picture (or regenerated from a task-board snapshot).

**Phase 4 — Optional native gates (0.5.x)**
N4 hooks `Stop` gate; N5 headless recipe; N2 pptx deliverable path; upstream
PR for `SpawnTeammateRequest` composition pass-through.

---

## 8. Decisions the user owns

> **Settled 2026-09-21** (grilled; recorded as Decision 24 /
> `docs/adr/0001-rigorquant-on-agent-teams.md`): 1 team-only from 0.5.0,
> 0.4.2 published as the last classic release; 2 yes, `install.sh` also
> enables the two Team bundles; 3 reuse adversaries and literature lines,
> fresh explorers/OffGridThinkers/DoubleCheckers, L3 rewritten; 4 retire the
> panel, keep a move pill; 5 no hooks gate (follow-up idea); 6 upstream PR
> after 0.5.0 ships. Further settled: every teammate is roster-blind; the
> bash network guard covers all web-denied roles; role personas live in
> `dsh/personas/<role>.md`; `write_scopes` stay on the Decision 12 role
> dirs; the live-children pool stays at 8; a lifetime-cap failure is a
> BUDGET-class outcome; the alpha replaces the global `dsh` install;
> Phase 4 items are follow-up tickets outside the spec. Vocabulary in
> `CONTEXT.md` (study / task / move / stage / orchestrator / teammate).

1. **Team-only or dual-mode?** Recommendation: **team-only from 0.5.0**, with
   0.4.2 (Phase 1) as the classic branch for deployments that cannot enable
   an experimental bundle. Dual-mode doubles the persona/test surface and the
   classic mode's topology is weaker than the guarded one.
2. **`maxMembers` override written by `install.sh` into the profile's user
   patch** (recommended: yes, marker-delimited, removable) versus README-only.
3. **Roster policy**: fresh explorers/offgrid/doublecheckers per brief, reused
   adversaries and literature lines (recommended) — versus fresh everything
   (needs `maxMembers ≈ 64+`) or reuse everything (breaks blank context).
4. **Activity view**: retire the custom panel for the native roster + a thin
   move pill (recommended) versus porting the whole floater onto
   `agentTeams/view`.
5. **Hooks `Stop` gate** (N4): ship disabled with a documented enable, or not
   at all.
6. **Upstream PR** for `spawn_teammate` composition pass-through: file it
   (recommended — it removes most of `rq-team` later) or wait for the domain
   to stabilise.
7. **0.4.2 on a Teams-enabled profile** (raised by §3.7 finding 5, Phase 1):
   the classic orchestrator and its children see the nine Team tools beside
   the `subagent_*` rows. A tool restriction cannot name them (not mounted on
   every deployment). Options: one persona sentence telling the orchestrator
   to leave them alone, or nothing (0.4.2 is the line for profiles that
   cannot enable Teams, so most 0.4.2 sessions never see them).

---

## 9. Not broken (checked, no action)

Every event and service the host halves use still exists in the 0.1.6
catalog: `session/event`, `session/disposed`, `agent/disposed`,
`agent/status`, `agent-preset/selected`, `agent/request`,
`agent/request-error` (payload shape unchanged: `agent`, `provider`,
`failure`), `settings/document-updated`, `llm/adapters-updated`,
`internal/service`; `settings.register/describe` with `applies: 'live'`,
`systemPrompt.assemble`, `agentPresets.composedPreset/composeFrom`,
`sessionProjections.stateOf`, `sessionTitle.get`, `webServer`. The persona
`prefix`/`suffix` split, `present`, the skill-root ranking, JSONL persistence,
`$DSH_HOME/.agent-presets` discovery (`agent-presets/src/index.ts:182-184`),
and the `tool-subagent` `Config` keys used by the disabled rows are unchanged.
`agent/session-start` is not used anywhere in this repository.
