# Upgrade study: DSH 0.1.5-alpha.2 (from 0.1.2-alpha.1)

Companion to [`docs/upgrade-0.1.2.md`](upgrade-0.1.2.md). That study pinned this
repository to **DSH ≥ 0.1.2-alpha.1**; this one covers everything upstream has
done since.

**Baselines and targets**

| Fact | Value | Evidence |
|---|---|---|
| Version this repo was last verified against | `0.1.2-alpha.1` (dev env `0.1.1-rc.2`) | `docs/upgrade-0.1.2.md:5-6` |
| Version this repo pins and enforces | `0.1.2-alpha.1` | `install.sh:18`, `README.md:167,197`, `README.zh-CN.md:151,162` |
| Version **running** in this deployment at study time | `0.1.5-alpha.2` | `dsh --version`; `/opt/homebrew/lib/node_modules/@deepseek-ai/dsh/package.json` |
| Newest published release | `0.1.5-rc.1` (2026-09-10) | npm `versions`, GitHub release `dsh-v0.1.5-rc.1` |
| Version **on disk** now | `0.1.5-rc.1` | the install was upgraded after this study; §4.14 records that the alpha.2 → rc.1 delta is version strings for every package touched here, so every verdict below is unchanged |

> **On the "0.1.12" in the request:** no such DSH version exists (npm publishes
> `0.1.1-rc.2`, `0.1.2-rc.1`, `0.1.3-alpha.*`, `0.1.5-alpha.*`, `0.1.5-rc.1`).
> The release notes for `0.1.5-rc.1` state they summarize everything *since
> `v0.1.2-rc.1`*, so this study covers the whole `0.1.2 → 0.1.5` range, which
> subsumes either reading of the number.

> **Status: implemented.** Every item in §4 is applied on this branch — the
> persona split, the delivery contract, the persona-section constant, the
> patch-file skill root, the two missing rows, the activity-monitor seams, the
> client fallback and the version floor. `tests/preset_harness_probe.cjs`
> (validating each row against the installed harness) and the new assertions in
> `tests/router_probe.cjs`, `tests/activity_probe.cjs` and
> `tests/test_harness_compat.py` pin them. The study below is kept as the
> source-verified record of WHY each fix is what it is.

**Method.** Shallow-cloned `dsh-v0.1.5-alpha.2` (the installed release) and
`dsh-v0.1.5-rc.1` into `/tmp`, then

1. diffed the two tags for every package this repo touches — for
   `core/`, `host/webserver`, `session/`, `subagent/`, `preset/`, `jobs/`, `web/`
   the only differences are `package.json` version strings, so every verdict
   below holds for both;
2. loaded each row of `agent-presets/rigorquant/agent.cordis.yml` through the
   **real `Config` schema of the package that is actually installed**
   (`node_modules/@deepseek-ai/dsh-*/lib/index.js`), not the release notes
   (the probe in §6);
3. read every Host service, Host event, Client slot, Client service, and DOM
   anchor `dsh/index.js`, `dsh/activity.js`, and `dsh/client.js` call, against
   the 0.1.5-alpha.2 source.

---

## 1. What changed since 0.1.2

Release-level (from the `0.1.2-rc.1` / `0.1.3-alpha.1` / `0.1.3-alpha.2` /
`0.1.5-alpha.1` / `0.1.5-alpha.2` / `0.1.5-rc.1` notes), then marked with what
the source audit actually found.

### 1.1 Breaking changes that touch this repository

| Upstream change | Release | Where it lands here | Verdict |
|---|---|---|---|
| Custom persona config split into **prefix + suffix**; old keys/constants must be updated | 0.1.3-alpha.2 | `dsh-persona` row `config.text`; `PERSONA_SECTION = 'deployment:persona'` | **BREAKS** the preset mount and the role-tag probe — §4.1 |
| `report` tool replaced by bidirectional `send_message` for continuable children | 0.1.2-rc.1 | every child persona instructs `report`; every child `toolFilter.deny` blocks `send_message` | **BREAKS** child→orchestrator delivery — §4.3 |
| `Session.events` replaced by `seq` / `eventAt()` / `snapshotEvents()` | 0.1.2-rc.1 | `dsh/activity.js:175,181,192` | **BREAKS** the activity monitor, silently — §4.2 |
| Web plugin panel API: global panels via `sidebar.panellist` + `main`; `conversation` slot moved under `main` | 0.1.5-alpha.2 | `dsh/client.js` uses `settings.plugin.item` + `shell.overlay` only | No break; adoption opportunity — §3.4 |
| Remove `ctx.agent`; callers must pass the Agent explicitly | 0.1.5-alpha.1 | not used | No impact |
| `Inbox` becomes type-only; `agent.inbox` replaces `hasPending`/`claim` | 0.1.5-alpha.1 | not used | No impact |
| Session format **V3**; system prompt recorded in message history; no downgrade reads | 0.1.5-alpha.1/rc.1 | only `snapshotEvents()` reads the log | No impact (no custom log reader) |
| Session persistence API owned by lifecycle `SessionHandle`; `agentLoop.create()` async | 0.1.3-alpha.1 | not used | No impact |
| Remote gateway unified; legacy `APIProxy` removed | 0.1.2-rc.1 | `remote.session` / `remote.settings` already adopted | No impact |
| Default tool sets changed for SDK/Headless/ACP and Web `minimal` | 0.1.3-alpha.2 / 0.1.5-alpha.2 | RigorQuant is a custom preset that lists its own rows | No impact |
| Ordinary subprocess handles lose `pid` | 0.1.3-alpha.2 | not used | No impact |
| Public WebFetch on by default (SSRF-guarded, no per-request approval) | 0.1.2-rc.1 | builtin `dsh-tool-web`, already used | Behaviour change only |
| Generic `workflow` tool no longer exposed by default in Web PTC mode | 0.1.2-rc.1 | `tool-workflow`/`tool-ralph`/`workflow-worker-thread` are already `disabled: true` | No impact |

### 1.2 New capabilities worth having (details in §3)

Right Sidebar with tabs/split/fullscreen and document previews (0.1.5-alpha.1/2);
model-delivered files + deliverables UI (0.1.5-alpha.2); dynamic system-prompt
updates that preserve KV cache (0.1.5-alpha.1); arbitrary file uploads
(0.1.5-alpha.1); continuable-subagent message queue / edit / delete / steer /
stop (0.1.5-alpha.2); `HTTP_PROXY`-aware egress (0.1.5-alpha.1); custom preset
`roots` in configuration; the `present` tool; session projections and the
subagent catalog; native subagent model selection.

---

## 2. Q1 — has DSH changed since 0.1.2? Yes, and three of the changes break this repo

Six releases and three version series separate the pinned baseline from the
running deployment (`0.1.2-rc.1`, `0.1.3-alpha.1/2`, `0.1.5-alpha.1/2`,
`0.1.5-rc.1`). The repository is **not** compatible with the version it is
running on:

1. **The preset cannot mount at all** — the persona row's `text:` key was
   replaced by `prefix:` (0.1.3-alpha.2) — §4.1.
2. **The role-model router stops recognising one-shot children** — same change,
   via the `PERSONA_SECTION` constant, which also fails silently — §4.1.
3. **The team-activity monitor returns an empty panel** — `Session.events` was
   removed (0.1.2-rc.1) and a `?? []` hides it — §4.2.

Everything else the repo reaches for survives: 12 of 13 Host seams audited in
`dsh/activity.js` are unchanged, and every Client seam used by `dsh/client.js`
(`settings.plugin.item`, `shell.overlay`, `settingsSchema.rehydrate/validate`,
`remote.session.modelCatalog`, `remote.settings.describe`, `settingsScope`,
`locale`, `sessions`, the slot registration options `id`/`order`/`label`/
`locale`/`inject`, `[data-shell-overlay]`, `[data-phase='active']`) is still
present in 0.1.5-alpha.2.

---

## 3. Q2 — new features to adopt instead of reinventing

### 3.1 ★ Native subagent catalog replaces the hand-rolled roster

`ctx.subagents.listChildren(parentSessionId)` and
`listDescendants(rootSessionId)` return a durable catalog with per-child
`activity: 'running' | 'inactive'`, `mode`, `label`, `hasChildren`, `parentId`
and `depth`
(`packages/subagent/subagent/src/index.ts:349,368`;
`packages/subagent/subagent/src/control-types.ts:33-84`). `activity` is computed
from exactly the expression `dsh/activity.js:364-369` hand-rolls
(`agents.get(id)?.status === 'running'`, `packages/subagent/subagent/src/control.ts:65-69`),
but it also works for children that **exist only in persistence** — which the
monitor's in-memory map cannot see at all. There is even a browser Remote
(`subagent.list`, `subagent/src/index.ts:385`) that returns the catalog plus a
`parentAvailable` hint, so the browser half need not fetch a custom JSON route
to learn the roster.

*Payoff:* deletes the role-detection-by-label heuristic, fixes the
after-restart under-count, and makes the panel correct for cold sessions.

`ctx.sessionQuery` is the complementary read service for history rather than
live state: `traceSession(rootId)` returns the ancestor chain plus the whole
recursive descendant tree in one call, `readSurface(sessionId)` the rendered
view, `listEvents`/`filterEvents` exact log reads
(`packages/session-query/session-query/src/index.ts:325,308,267`). Note the
shipped base mounts its SQLite provider with `openAt: never`, so exact reads
work but ranked full-text search answers `SESSION_QUERY_SEARCH_DISABLED` unless
a later patch layer opts in
(`packages/bundle/base/cordis.patch.yml:129-133`).

### 3.2 ★ Session projections replace the dead log scans

`ctx.sessionProjections.stateOf(session, key)` (`packages/session/session-projection/src/index.ts:319`)
serves the derived state the monitor currently reconstructs by scanning
`session.events` (which no longer exists):

| Projection key | Replaces |
|---|---|
| `agentPreset` | the `agent-preset/selected` log scan (`activity.js:181-184`) — `packages/preset/agent-presets/src/session.ts:36`, whose own doc says *"Reconstruction reads the `agentPreset` Session projection, never the header"* |
| `subagent` (`{ identity: { mode, label, seq } }`) | the `subagent/descriptor` scan (`activity.js:192-199`) — `packages/subagent/subagent/src/projection.ts:169` |
| `subagentTiming` | `startedAt`/`lastAt` bookkeeping — `projection.ts:63` |
| `sessionStats` | the hand-rolled `toolCount`/`messageCount` counters (`activity.js:376-377`) — turns, steps, llm/tool ms, TTFT, decode tokens (`packages/session/session-stats/src/types.ts:22-45`) |
| `turnBoundary` | `present`'s open-turn check, if the preset ever calls it |

> The `subagent` identity projection carries **no persona**
> (`packages/subagent/subagent/src/projection-types.ts:37-60`), so it replaces
> the *descriptor scan* but not the `[[rq:role=…]]` tag read. The tag still
> comes from the descriptor event (live, via `session/event`) or from the
> rendered prompt.

### 3.3 The role-tag scan can shrink to one path

The router currently keeps two role-resolution paths — a `snapshotEvents()`
scan and a `systemPrompt.assemble()` probe (`dsh/index.js:288-328`). With the
`agentPreset` projection (§3.2) and `session.ownEvents()`, the scan becomes
both correct and cheap:

- **continuable children:** the `subagent/descriptor` event carries `persona`
  (`packages/subagent/subagent/src/descriptor.ts:83`), and the live
  `session/event` listener already captures it (`dsh/index.js:254-257`). For
  cold-resumed children, scan `ownEvents()` (see §4.10) — one call, own log
  only.
- **the root:** `sessionProjections.stateOf(session, 'agentPreset')`, never the
  header (§4.9).
- **the prompt probe** then only has to cover children that are one-shot *and*
  cold, if that case exists at all; `assembleContextFor(agent)` is the public
  canonical helper for it (`packages/core/agent/src/dispatch.ts:174`,
  re-exported at `packages/core/agent/src/index.ts:23`).

### 3.4 ★ Right Sidebar: the activity pill's details belong in a tab

0.1.5 adds a first-class right column
(`packages/client/ui-sidebar-right/`, `ui-sidebar-documentpreview/`,
`ui-deliverables/`). A third-party plugin gets three seats:

- **A tab type of its own.** Register a definition with
  `ctx.sidebarRightTabs.register({ id, kind, title, patterns?, priority?, canOpen?, guide? })`
  (`packages/client/ui-sidebar-right/src/client/index.ts:103-108`;
  `tab-registry.ts:80-131,235`), then supply the body and the chip by
  registering into the keyed slots `sidebar.right.pane.tab` and
  `sidebar.right.pane.tab.title` using the definition's `id` as the key
  (`contract/slots.ts:50,64`; the shipped guide does exactly this at
  `index.ts:184-196`).
- **Programmatic opening.** `ctx.sidebarRight.openTab(kind, { params })` and
  `openTabIn(sessionId, kind, …)` (`service.ts:151-160`). This is what the pill
  would call — "open the RigorQuant activity view" — instead of expanding a
  floating panel.
- **A global main panel.** Two registrations sharing one id: an icon into the
  root list slot `sidebar.panellist`
  (`packages/client/ui-sidebar/src/client/contract/slots.ts:32`; options
  `{ id, order?, label? }`, occupant props `{ size, active }`) and a **keyed**
  entry into `main` under the same key
  (`packages/client/ui-layout/src/client/index.ts:66`; the reserved
  `conversation` key is the conversation stream, `AppFrame.tsx:39-43`).
  Selection is `ctx.layout.selectPanel(id)`
  (`ui-layout/src/client/service.ts:21-40`), which throws for a key with no live
  registration. This is the 0.1.5-alpha.2 "global panels" mechanism and the
  natural docked home for a full activity view: a real column, no geometry
  measurement, zero cost while empty.

`shell.overlay` still exists (`ui-layout/src/client/index.ts:155`, rendered at
`AppFrame.tsx:200,230`), so the current floater keeps working. But the sidebar
is where the platform is investing, and the pill's *detail* view is a natural
tab: full height, no geometry hacks, no `[data-phase='active']` padding dance
(`dsh/client.js:1062`), and it survives the conversation stream re-rendering.

*Recommended shape:* keep the compact pill in `shell.overlay` for at-a-glance
counts, and register a `rigorquant-activity` tab type in the right sidebar for
the roster, per-role feed, and profiles. The pill's click opens the tab.

### 3.5 Model-delivered deliverables (`present`) — and the row is missing

`@deepseek-ai/dsh-tool-present` registers the `present` tool
(`packages/fs/tool-present/src/index.ts:39-79`) and the Web side renders
presented files with right-Sidebar preview, "open in default app", and "reveal
in file manager". The shipped `standard` preset mounts it
(`packages/preset/agent-presets/presets/standard/agent.cordis.yml:254-255`), and
it is **not** host-mounted. `agent-presets/rigorquant/agent.cordis.yml` has no
such row, so RigorQuant agents cannot declare a deliverable at all — the whole
0.1.5 deliverables flow is dead for this preset even though deliverables are
its entire output story.

### 3.6 Preset roots are configurable — the boot-copy hack can shrink

`dsh-agent-presets` now takes `roots: [{ path, trust }]` alongside
`includeShippedRoot` / `includeUserRoot`
(`packages/preset/agent-presets/src/index.ts:104-113, 179-181`). A bundle patch
can therefore point the roster straight at the installed package's
`agent-presets/` directory. `dsh/sync.js` currently copies the preset into
`$DSH_HOME/.agent-presets/rigorquant` on every boot for the stated reason that
*"the harness's own profile overlay pins the `agent-presets` row's roots to the
shipped preset root"* (`dsh/sync.js:4-6`) — that reason is now obsolete.

Caveats before doing it: a patch **replaces the targeted row's whole `config`**
(`packages/bundle/web-app/cordis.patch.yml:5-6`), so a `- id: agent-presets`
row must restate `default: standard`; and the root path may **not** be computed
from `baseUrl`, which in a patch file is the profile directory, not the package
root (see §4.7) — resolve the package with `createRequire` or anchor on
`dshHomePath`.

**One reason not to do it, found while implementing §4.7.** Configured roots
rank *above* the user root (`packages/preset/agent-presets/src/index.ts:178-182`),
so a root pointing into `node_modules` would **shadow**
`$DSH_HOME/.agent-presets/rigorquant` — and the preset is meant to be edited in
place there (the escalation lane flips a row in the installed composition,
`dsh/sync.js`). Serving the preset from the package would silently ignore those
edits until the two copies happened to agree. `env/`, `mcp/` and `docs/` also
still need the file-lane (the uv venv must stay out of `node_modules`), so
`dsh/sync.js` shrinks rather than disappears — and only once the edit-in-place
contract is reworked. The comment in `dsh/sync.js` now states this instead of
the (false) "the harness pins the roots" premise.

### 3.7 Smaller adoptions

- **`modelSelectionSettings: true` + the `list-models` tool**
  (`tool-subagent/src/index.ts:107`; `list-models.ts`) let a caller pick a route
  from the Host's `subagent-model-selection` allow-list, and the choice is
  recorded per Session and **inherited by its children**, so a later settings
  edit cannot mutate a run in flight. That is the native equivalent of part of
  the custom router; it cannot express RigorQuant's fixed-tier matrix (point 2
  of `docs/upgrade-0.1.2.md:111-115` still holds), but it is the right mechanism
  for the *open* roles.
- **`agentOptions.maxTokens`** remains available and still deliberately unset.
- **`dsh-session-stats`** gives per-session token/time counters for the panel.
- **`ctx.goals` + `dsh-goal-round-driver`** — the round driver is a
  no-configuration function plugin
  (`packages/goal/goal-round-driver/src/index.ts:25-26`): mount it and an armed
  goal keeps running unattended while the agent is idle. The preset already
  mounts `tool-goal`; the driver is what makes the unattended contract real.
- **Workflow cost ceilings.** `workflow-worker-thread` defaults
  `maxConcurrentAgents` to `min(16, max(1, cpus-2))`, `maxTotalAgents: 1000`,
  `maxItemsPerCall: 4096` (`workflow/workflow-worker-thread/src/index.ts:115-122`),
  and a run can only *lower* them. RigorQuant disables workflow on purpose
  (`agent.cordis.yml:560-577`), so this matters only if that decision is
  revisited — but the ceilings mean a fan-out lane no longer needs a bespoke
  guard.
- **`dsh-tool-call-timeout-policy`** turns a hung tool into an `isError` result
  with `error.info.code = 'TOOL_TIMEOUT'` by reading `ToolDefinition.timeoutMs`
  (`packages/guard/timeout-policy/src/index.ts:57-79`). It is already
  host-mounted in the base bundle (`packages/bundle/base/cordis.patch.yml:377-378`),
  so RigorQuant gets it for free; the budgets themselves are declared by each
  tool package (`tool-web` and `tool-fs-search` declare them, `tool-fs`,
  `tool-bash` and the persistent shell do not), so long `uv run` calls are a
  watch item rather than something this repository configures.
- **Skill roots verified.** `providerName` / `includeDefaultRoots` /
  `customSkillDirs` are unchanged
  (`packages/skill/skill-filesystem/src/index.ts:51-81`), and the ranking rule
  confirms `cordis.patch.yml`'s claim: custom dirs rank 300, `$DSH_HOME/skills`
  ranks 400, lower wins within a layer
  (`skill-filesystem/src/index.ts:36-40,243-258`). The `--skill-only` duplicate
  is indeed shadowed, not consulted. Preset-local `skill-filesystem`
  (the shipped `cordis` pattern) is cleaner still: preset skills land in the
  preset's own registry layer and shadow globals regardless of rank.
- **Skill picker fuzzy search** (0.1.3-alpha.1) is a *browser* ranker over the
  `/` menu (`packages/client/ui-primitives/src/rank-by-name.ts`), not a
  `skill`-tool feature — the tool still takes exactly one `name`
  (`packages/skill/tool-skill/src/index.ts:81-86`). Nothing to build.
- **`/feedback` detail submissions** (0.1.5-alpha.2) — nothing to build.
- **`dsh-experimental-agent-team`** (npm-installable since 0.1.5-alpha.2) has a
  durable roster, an offline message queue, a shared task board with
  dependency readiness, a `waitForChange` primitive and a browser team UI —
  i.e. much of what the hand-rolled monitor approximates. But it is
  **not installed** in this deployment (the package name is
  `@deepseek-ai/dsh-experimental-agent-team`), and it disables
  `tool-subagent-control` when composed, which would fight the preset's
  `send_message`/`interrupt_agent` surface. Do not depend on it; revisit when
  it stops being experimental.

---

## 4. Q4 — what must be fixed before this runs on 0.1.5

Ranked. §4.1 and §4.2 are hard blockers; §4.3 is a functional regression;
§4.4–§4.11 are correctness/robustness fixes worth landing in the same pass.

### 4.1 ★ BLOCKER — the preset cannot mount (persona split)

0.1.3-alpha.2 replaced the single persona with a prefix/suffix pair. The
current schema is

```ts
// packages/preset/persona/src/index.ts:26-50  (installed 0.1.5-alpha.2)
export const Config = z.object({
  prefix: z.string().required(),          // was: text
  suffix: z.string().default(''),
  complete: z.boolean().default(false),
  includeRuntimeContext: z.boolean().default(true),
})
```

and the section name moved:

```ts
// packages/core/system-prompt/src/index.ts:174-177
export const PERSONA_PREFIX_SECTION = 'deployment:persona-prefix'
export const PERSONA_SUFFIX_SECTION = 'deployment:persona-suffix'
```

RigorQuant still writes `config.text` (`agent-presets/rigorquant/agent.cordis.yml:15-16`),
which the installed schema rejects. Reproduced directly against the installed
build:

```
$ node -e "require('@deepseek-ai/dsh-persona').Config({text:'…'})"
REJECTED: ValidationError $.prefix missing required value
$ node -e "require('@deepseek-ai/dsh-persona').Config({prefix:'…'})"
prefix-only ACCEPTED {"prefix":"…","suffix":"","complete":false,"includeRuntimeContext":true}
```

A row whose plugin throws rejects the **whole** mount
(`packages/preset/agent-presets/src/mount.ts:298-299`, surfaced at `:425-431`
as `agent-preset/invalid`), so the preset is currently unusable and would be
listed as `broken` (`preset.ts:35-40`).

**Fix**

```yaml
- id: persona
  name: '@deepseek-ai/dsh-persona'
  config:
    prefix: >-      # was: text:
      You are RigorQuant, the root orchestrator …
    suffix: Your working directory is {{cwd}}.
```

and in `dsh/index.js`:

```js
const PERSONA_SECTION = 'deployment:persona-prefix'   // was 'deployment:persona'
```

The second edit is not cosmetic: `probePersonaRole` (`dsh/index.js:288-298`)
finds the persona by that exact section name, and the per-child persona the
subagent provider installs registers under exactly
`deployment:persona-prefix` (`packages/subagent/subagent/src/child-agent.ts:210-214`).
With the old name, every child that has no descriptor tag
(`agent.cordis.yml` sets one on every *continuable* row, but the descriptor is
written asynchronously and `tool-subagent`'s per-child `persona` is the live
source) resolves `role = null`, the router skips it, and the
DoubleChecker/adversary tier matrix silently stops applying. No test pins the
section name (see §4.12), which is why this would not have been caught.

### 4.2 ★ BLOCKER (silent) — the activity monitor sees nothing

`Session.events` was removed in 0.1.2-rc.1; 0.1.5-alpha.2 exposes
`eventAt(seq)`, `snapshotEvents(from?, to?)`, `ownEvents()` and `get seq()`
(`packages/core/session/src/index.ts:621,633,648,662`). `dsh/activity.js` reads
it in three places:

```
activity.js:175   const events = agent.session?.events ?? []
activity.js:181   for (… events.length …) selectedPreset = event.data?.agentPreset
activity.js:192   for (… events.length …) descriptor scan
```

The `?? []` turns a removed API into an empty array, so nothing throws and
nothing is logged. Consequences:

- a session created as `standard` and switched to `rigorquant` (the normal
  picker flow) is no longer detected as a lab when `agentPresets` is not
  mounted, and the route answers `200 {"labs":[]}` with no diagnostic;
- children whose descriptor was written **before** the plugin mounted are
  seeded with `role: null` (`activity.js:203-211`) and then dropped by the
  roster filter (`activity.js:392`) and the live-team count (`:395,404`) — an
  under-counted team after every restart.

**Fix:** replace the scans with the projections in §3.2 —
`sessionProjections.stateOf(session, 'agentPreset')` and
`stateOf(session, 'subagent')` — and remove the `?? []` so a missing accessor
fails loudly instead of silently. Better still, move the roster entirely to
`ctx.subagents.listChildren()`/`listDescendants()` (§3.1).

### 4.3 HIGH — children can no longer report to the orchestrator

The one-way `report` tool was replaced in 0.1.2-rc.1 by `send_message`, which
is **bidirectional**: a parent may message a direct continuable child, and *a
resident continuable child may message its direct parent*
(`packages/subagent/tool-subagent-control/src/index.ts:29-40`). The child's
normal result is its final assistant message, delivered to the parent as the
tool result / settlement notice
(`tool-subagent/src/index.ts:596-603`).

RigorQuant still documents the old contract:

- personas: `agent.cordis.yml:210-212, 286-288, 356-358, 391-394, 428-429, 459-460, 497-501`
  ("Deliver your findings with the `report` tool …") — seven occurrences, one
  per child role;
- all seven child `toolFilter.deny` lists include `send_message`
  (`agent.cordis.yml:231, 301, 369, 408, 438, 466, 513`), so a child cannot
  push anything upward even though the capability now exists.

Two skill files repeat the contract and need the same edit:
`skills/rigorquant/references/protocol.md:86-87` and
`skills/rigorquant/SKILL.md:221`.

**Fix (minimum):** replace the `report` instruction with "end your turn with
the concrete result as your final assistant message — the runtime delivers it
to the agent that started you", and drop `report` from the prose in
`docs/architecture.md` (Decision 20) and the affected tests.

**Fix (better):** also remove `send_message` from the child deny lists. A
depth-1 child may then message its direct parent (the orchestrator) when it has
an interim finding or a blocking question — which converts the orchestrator's
poll loop into an event-driven one (§5.2). Keep `interrupt_agent` and
`list_agents` denied for children; only the orchestrator should interrupt.

### 4.4 MEDIUM — two rows the shipped presets carry are missing

```yaml
- id: command-goal
  name: '@deepseek-ai/dsh-command-goal'

- id: present
  name: '@deepseek-ai/dsh-tool-present'
```

The two rows are missing for **different** reasons:

- `command-goal` **is** disabled at the host plane by the web-app bundle
  (`packages/bundle/web-app/cordis.patch.yml:411-412` disables it; `:414-415`
  disables `tool-goal`), so every preset must re-mount it. The shipped
  `standard` preset does (`presets/standard/agent.cordis.yml:95-96`).
  Without it there is no `/goal` slash command in a RigorQuant session, even
  though the goal tools and the round driver are the framework's unattended
  loop.
- `present` is **not disabled anywhere** — because **no bundle mounts it at
  all**. Only presets do: `presets/standard/agent.cordis.yml:255`,
  `presets/ptc/agent.cordis.yml:275`, `presets/cordis/agent.cordis.yml:266`.
  Neither `dsh-base` nor `dsh-web-app` names `dsh-tool-present` in its patch —
  `dsh-base` lists it as a dependency only
  (`packages/bundle/base/package.json:98`). So deliverables land on disk but
  are never declared, and the 0.1.5 right-Sidebar deliverables UI shows nothing
  for a RigorQuant session.

Adding `present` also means one sentence in the deliverables skill: call
`present` after writing the deliverable and before the final response.

### 4.5 MEDIUM — route-registration flag can wedge the monitor

`activity.js:439` sets `routesRegistered = true` **before** the two
`ctx.effect(webServer.register(...))` calls. `webServer.register` throws on a
duplicate `(kind, path)` (`packages/host/webserver/src/index.ts:165-169`), and
Cordis `emit` contains nothing
(`cordis/src/events.ts:194-196`), so a throw on the `internal/service` path
(`activity.js:492-494`) escapes with the flag already set and no retry can ever
happen. Set the flag after both registrations succeed, and reset it in a
`catch`.

### 4.6 MEDIUM — the root test misclassifies forked sessions

`agent.session.header.parentSession === undefined` (`activity.js:189, :329`)
is used as "this is the lab root". `parentSession` is *fork lineage*, so a
forked top-level session also carries it and is demoted out of lab detection.
The durable discriminator is `header.origin !== 'subagent'`
(`packages/core/session/src/types.ts:116`, set at
`packages/subagent/subagent/src/child-agent.ts:152`); `delegationDepth`
(`:122`) is its companion.

### 4.7 HIGH — the plugin's global skill root resolves to a directory that does not exist

`cordis.patch.yml:26-28` configures the profile-wide skill provider:

```yaml
config:
  providerName: rigorquant
  includeDefaultRoots: false
  customSkillDirs:
    - !!js "…fileURLToPath(new URL('agent-presets/rigorquant/skills/', baseUrl))"
```

The comment above it — and `cordis.patch.yml:9-10` — states that `baseUrl`
anchors at the patch file's package root. **It does not.** Every patch layer
(each bundle's `dsh.bundle.patch`, the profile's own `cordis.patch.yml`,
`$DSH_HOME/cordis.patch.yml`, and `--patch` overlays) is loaded by
`loadOverlayPatches` → `parsePatchList` (a plain YAML parse, no per-file base)
and concatenated into one list applied to the root include
(`apps/cli/src/profile-boot.ts:206-212,232,336`;
`packages/boot/app-boot/src/profile.ts:795`), and the root context's base URL is
the **profile directory**:

```ts
// packages/boot/app-boot/src/index.ts:799
ctx.baseUrl = pathToFileURL(dirname(absoluteConfigPath)).href + '/'
```

Per-file `baseUrl` is an `Include`-only behaviour — which is exactly why the
preset's own `skill-filesystem` row (`agent.cordis.yml:96-100`) is correct
while this one is not.

Reproduced against the installed 0.1.5-alpha.2 with a scratch `DSH_HOME` and a
throwing probe in that profile's patch file (probe profile deleted afterwards):

```
$ DSH_HOME=/tmp/rqprobe dsh --profile probe --port 3099 --no-open
Error: dsh: plugin tree failed to load: … failed to apply loader entry
  rq-baseurl-probe (@deepseek-ai/dsh-tool-ask-user):
  BASEPROBE=file:///tmp/rqprobe/profiles/probe/
```

So `customSkillDirs` resolves to `<profile>/agent-presets/rigorquant/skills/`,
which does not exist — and with `includeDefaultRoots: false` the provider
contributes **zero** roots. Consequences: the `rigorquant`, `arxiv` and
`academic-paper-search` skills still load *inside a `rigorquant` session* (the
preset's own row is correct), but the plugin's advertised purpose — "makes the
`rigorquant` skill … available to every session of that profile"
(`cordis.patch.yml:4-6`) — is not delivered, and only an `install.sh
--skill-only` copy under `$DSH_HOME/skills` covers other presets. The
shadowing argument in `cordis.patch.yml:12-21` describes a layer that is empty.

**Fix:** never use `baseUrl` in a patch file. Resolve the package instead, e.g.

```yaml
customSkillDirs:
  - !!js "process.getBuiltinModule('node:path').dirname(
      process.getBuiltinModule('node:module')
        .createRequire(baseUrl + 'package.json')
        .resolve('dsh-rigorquant/package.json')) + '/agent-presets/rigorquant/skills/'"
```

or anchor on `dshHomePath(...)`, which the root context provides before the tree
mounts (`packages/boot/app-boot/src/index.ts:800`), if the skills are landed
under `$DSH_HOME` by `dsh/sync.js` instead.

Attribution: whether this ever worked is not verifiable here (the 0.1.2 tag is
not in the local clone), so treat it as a pre-existing bug rather than a 0.1.5
regression — but it is broken on the version you are running, and no shipped
bundle uses `baseUrl` in a patch file (`grep` over `packages/bundle/*/cordis.patch.yml`
finds only `dshHomePath`, `process.env` and `process.cwd()`).

### 4.8 MEDIUM — the browser half still calls a deleted legacy module

`dsh/client.js:296` keeps a dual-version fallback:

```js
return require('@deepseek-ai/dsh-client-schema-form')
```

That package was deleted from the harness when its helpers folded into the
`settingsSchema` service, and it is **not** in the browser's frozen module table
(`packages/client/web/src/seed.ts:24-38`), so the `require` would throw
`client-modules: require("…") missed the module table`
(`packages/client/modules/src/client/system.ts:208-211`). Today the arm is
unreachable — the plugin hard-injects `settingsScope`, which `ui-settings`
provides *after* `settingsSchema` (`packages/client/ui-settings/src/client/index.ts:51,67`),
so `ctx.get('settingsSchema')` is never `undefined` — but the failure mode if it
ever were reached is severe and unisolated: the throw happens inside
`new RqModelsCardController(ctx)` (`dsh/client.js:795`), i.e. inside `apply`, so
the whole bundle entry fails instead of one card going dead.

**Fix:** delete the fallback arm and the now-false comment above it
(`dsh/client.js:274-283`). While there, `package.json` `dsh.client.inject` lists
`@deepseek-ai/dsh-client-runtime`, which no longer ships; the field is
informational (`packages/util/package-manifest/src/types.ts:52-53`) and unknown
names are skipped, but the list should name packages that exist.

**As implemented:** the bogus entry was replaced with
`@deepseek-ai/dsh-client-ui-renderer` — the package that actually provides the
`slots` service this card injects (`packages/client/ui-renderer/src/client/registry.ts:134`,
`super(ctx, 'slots')`). The other five entries (`api-remotes`,
`api-session-controller`, `client-locale`, `ui-settings`,
`ui-settings-plugins`) already named real packages and were left alone, so the
list is now entirely resolvable. `tests/test_client_bundle.py`'s
`SERVICE_PROVIDERS['slots']` was corrected to match, which is what makes the
edge list a checked claim rather than a comment.

### 4.9 MEDIUM — the root role is read from a field upstream now calls stale

`dsh/index.js:324` resolves the root role as

```js
const preset = header.agentPreset ?? ctx.get('agentPresets')?.composedPreset(agent.ctx)
```

The header field is documented as the preset the session **started** with
(`packages/core/session/src/types.ts:129`), and the projection module says so
outright: *"The creation header names the preset a session STARTED with …
Reconstruction reads the `agentPreset` Session projection, never the header
alone"* (`packages/preset/agent-presets/src/session.ts:2-11`). Because the
`??` only falls back when the field is **undefined**, a session created as
`standard` and switched to `rigorquant` keeps matching whichever value the
header holds. `dsh/activity.js:185-188` has the same shape, with
`composedPreset` first — which is the right order.

**Fix:** prefer `ctx.get('agentPresets')?.composedPreset(agent.ctx)`, or read
`ctx.sessionProjections.stateOf(session, 'agentPreset')`
(`packages/session/session-projection/src/index.ts:319`). Note this is the same
root-cause as §4.2 and is fixed by the same change.

### 4.10 LOW — the descriptor scan can read a fork-inherited ancestor descriptor

`agent.session.snapshotEvents()` with no arguments returns the **whole log
including the fork-inherited prefix** (defaults `fromSeq = 0`, `toSeq = seq`;
`packages/core/session/src/index.ts:633-636`). The router's scan
(`dsh/index.js:306-317`) breaks at the first `subagent/descriptor` it sees and
locks in that role, so under lineage seeds it can adopt an ancestor's tag.

**Fix:** scan `agent.session.ownEvents()` (`:648`) or gate on
`session.isOwnSeq(event.seq)` (`:657`) — the documented guard
(`packages/core/session/README.md:66`).

### 4.11 LOW — `sessionTitle.get()` re-folds the whole log per poll

`activity.js:431` calls `sessionTitle.get(session)` for every lab on **every**
HTTP poll, and each call folds `session.snapshotEvents()`
(`packages/session/session-title/src/index.ts:385-386`). Use the title
projection, or cache by `session.seq`.

### 4.12 LOW — raise the version floor and the docs

Once §4.1 lands, the preset requires **≥ 0.1.5-alpha.2**:
`install.sh:18` `MIN_DSH_VERSION`, `README.md:167,197,246`,
`README.zh-CN.md:151,162,202,216`, and the `agent.cordis.yml:9` header comment.
`version_at_least()` in `install.sh:59-95` handles `0.1.5-alpha.2` correctly,
so only the constant changes. Also update `docs/architecture.md` (Decision 20's
`report` channel, the persona section name) and the tests that pin the old
seams:

- `tests/activity_probe.cjs` stubs sessions as `{ events: [...] }`
  (`:65,75,89,101,142`) — it exercises the dead accessor and would keep passing
  while the real monitor is broken. Re-point it at `snapshotEvents()` (or the
  projections) so it fails against 0.1.5.
- `tests/test_role_tool_budgets.py` (`:25,40`) asserts the `report` delivery
  contract; rewrite for final-message/`send_message`.
- Nothing in the suite pins `deployment:persona`. `tests/router_probe.cjs:135`
  already had to be fixed once for the `snapshotEvents()` rename (CHANGELOG
  "Unreleased"), and its `makeAgent` stub passes `ctx.get: () => undefined`,
  so the persona probe is untested — which is why the section rename in §4.1
  would have gone unnoticed. Add the assertion.

### 4.13 Note — what is *not* broken

For the record, so nobody "fixes" these: the waterfall payloads
(`agent/request` / `agent/request-error`) still carry an injected `agent` and
still resolve identically (`packages/core/agent/src/runtime-types.ts:347,363`;
the fused dispatcher injects the subject at
`packages/core/agent/src/dispatch.ts:107-121`), the accepted return shapes are
unchanged (`LlmCallConfig`, and `RequestErrorAction = { kind: 'retry' } |
undefined`); a root-registered listener still receives every agent's waterfall
because `scopeTarget`'s filter passes a context with no scope tag
(`packages/core/scope/src/index.ts:175-176`); `settings.register/describe/
document-updated`, `llm.resolveModelInfo`, `llm/adapters-updated`,
`agentPresets.composedPreset`, `agents.list/get`, `agent/status`,
`session/event` and all seven event types the monitor handles, `sessions.get`,
`sessionTitle.get`, `webServer.register`, `internal/service`, and every Client
seam listed in §2 survive unchanged. `enableRunInBackground`, `maxDepth`,
`persona`, `toolFilter`, `agentOptions` and `backgroundMode` are all still valid
`tool-subagent` keys, and every name in the current deny lists is still a
mounted tool, so `tools.restrict` will not throw
(`packages/core/tools/src/index.ts:1078-1081`).

One ordering note, not a break: `installModelSelection` also installs an
`agent/request` waterfall, but on `agent.ctx`
(`packages/core/agent/src/model-selection.ts:91-107`, called from
`packages/api/session-controller/src/agent.ts:316`). Cordis runs waterfalls
first-registered-outermost, and the plugin registers at boot — earlier — so the
router's return value wins and the chatbox picker still applies underneath it,
which is the intended policy.

**The browser half needs no port at all.** Every seam `dsh/client.js` actually
touches is intact on 0.1.5-alpha.2: the
`window.__ModuleLoader__.load({ id, factory })` contract and its module table
(`packages/client/modules/src/client/manifest.ts:258-269`;
`packages/client/web/src/seed.ts:24-38`), all seven injected names including the
two gated `remote.*` sub-namespaces (the `cannot get property … without inject`
guard still throws, `vendor/cordis/src/reflect.ts:136-171`),
`slots.inject`/`slots.register`, both registered slots
(`settings.plugin.item` — keyed/root, `ui-settings-plugins/slot-contract.ts:17`;
`shell.overlay` — list/root, `ui-layout/src/client/index.ts:82-91`), the `hooks`
reservation (`ui-slots/src/index.ts:378-384,446-450`),
`remote.session.modelCatalog` and `remote.settings.describe`,
`settingsSchema.rehydrate/validate` plus the four path helpers,
`settingsScope`, `locale.register/bind`, and `ctx.get('sessions')?.list`. The
two DOM anchors still resolve (`AppFrame.tsx:230`, `ConversationRoot.tsx:373`),
and the right-Sidebar restructure did not disturb them.

The only caveat is that those two anchors are *unversioned shell markup*: they
are absent from the `SlotMap`, the owner-prop interfaces and the slot catalog,
so nothing upstream promises them. They survived the 0.1.5 layout rework by
implementation luck, and the plugin's own comments already cite line numbers
that moved (`dsh/client.js:813-814, 912, 1503-1504` cite `AppFrame.tsx:210-211`;
the layer is now at `:230`). The viewport fallback the panel already has
(`dsh/client.js:934-942, 1505`) is the right mitigation — keep it, and add a
regression probe asserting both attributes rather than trusting them silently.
The genuinely unprotected seam is the state *behind* the panel, not the DOM:
that is §4.2.

### 4.14 Should you move to 0.1.5-rc.1 instead?

Optional. For the packages this repo touches, `0.1.5-alpha.2 → 0.1.5-rc.1`
changes **zero** source files under `core/`, `settings/`, `preset/` and
`subagent/`; the deltas are sidebar text preview, `llm-deepseek` dynamic
configuration, and the base patch's default model
(`deepseek-v4-flash` → `deepseek-flash`, with both catalog entries retained).
Every verdict above is identical on rc.1. The one thing rc.1 adds that is
interesting here is *in-history system prompt updates without invalidating the
KV cache* — a reasonable target once the code is ported, but port to the
version you run and verify before chasing it.

---

## 5. Q3 — deeper optimization: tool calling and agent communication

### 5.1 Make the child→parent channel event-driven

Today the orchestrator fans out with `subagent_*` tools and then waits for each
child's final message. With `send_message` allowed upward (§4.3) the
orchestrator can instead be *woken* by a child the moment it has a load-bearing
finding, and `list_agents` gives it a durable view of what is still in flight
(`packages/subagent/tool-subagent-control/src/list-agents.ts:93-106`, which
documents the exact `send_message` routing rules: steer a running child at its
nearest step boundary, start a turn for an idle/ready one). Combined with
`interrupt_agent` (`index.ts:77-109`, ancestor-authorized) this gives the
adversary lane a real enforcement action: a role agent that drifts or loops is
stopped, not merely ignored.

Concretely, for the RigorQuant loop:

| Instead of | Use |
|---|---|
| child writes `audits/<role>.md` and the orchestrator polls the file | child's final message + `send_message` for interim findings |
| orchestrator waits out a runaway derivation | `interrupt_agent` on the child id |
| orchestrator tracking in-flight children in the transcript | `list_agents` (durable mode/label/depth) |
| a mid-run question dying in a final report | child `send_message` to its direct parent |

### 5.2 Use the native catalog instead of accumulating events

Covered in §3.1/§3.2. The concrete win is correctness for cold sessions
(children whose descriptor predates the plugin mount) and the deletion of the
label heuristic (`activity.js:68-81`) and the role FIFO
(`activity.js:130-131, 256-262`).

### 5.3 Adopt `present` for the deliverables contract

The deliverables skill currently ends with "write the report"; on 0.1.5 the
correct flow is "write, then `present`" — which also gives a human running
unattended jobs a one-click path from the conversation to the artifact. The
tool is one row (§4.4) plus one sentence in
`agent-presets/rigorquant/skills/rigorquant/references/deliverables.md`.

### 5.4 Restrict tool catalogs against the *visible* set

0.1.5-alpha.2 fixed "filtered subagents still receive filesystem and Web
guidance for tools they cannot see". RigorQuant's deny lists are already
correct, but the fix means the per-role prompt no longer needs to restate the
denials in prose — worth trimming the personas where they duplicate the filter.

### 5.5 Keep the router, narrow its surface

The router's remaining unique value is: one live override per role, one
fallback per role, terminal-failure degradation with a TTL, and root-role
handling. Two 0.1.5 changes let it shrink:

- read `agentPreset` from the projection and the descriptor from
  `ownEvents()` instead of scanning the full log, which removes the stale
  header read and the fork-lineage hazard (§3.2/§3.3); the prompt probe
  survives only for a one-shot-and-cold child, and shrinks to a single
  `assembleContextFor(agent)` call;
- expose `modelSelectionSettings` + `list-models` for the *open* roles
  (explorer, literature) while leaving the fixed tiers on `agentOptions`.

There are now **four** supported routing layers below the waterfall: the
deployment default (`ctx.agentDefaultModel`, mounted in base at
`packages/bundle/base/cordis.patch.yml:75-79`), the per-Session pick
(`selectModel`, the chatbox), the per-child `agentOptions` /
`modelSelectionSettings` on each `tool-subagent` row, and a per-call
`agent(prompt, { provider, model })` in workflows. The router should only own
what none of them can express: the override/fallback/degrade policy.

One thing that does **not** exist: an agent-type or per-child-preset selector.
A child always joins its parent's composition
(`packages/subagent/subagent/src/child-agent.ts:204`), `tool-subagent` has no
preset key (`tool-subagent/src/index.ts:48-102`), and `agentType` is explicitly
rejected as a workflow option
(`workflow/workflow-worker-thread/src/runtime.ts:42`). Role differentiation
inside one preset therefore stays exactly what RigorQuant already does — several
differently configured `tool-subagent` rows — which is why the `[[rq:role=…]]`
tag remains the right identity channel for the router.

### 5.6 Context economy

Unchanged from the previous study and still correct: compaction at
`thresholdRatio: 0.6`, the tool-result pruner at 4 KiB, blind lanes without web
or skills. `dsh-session-stats` now exposes turns/steps/llm+tool ms/TTFT/decode
tokens per session (`packages/session/session-stats/src/types.ts:22-45`), which
the activity panel can surface natively rather than keeping its own counters.

---

## 6. Reproducing the verification

The preset check is a real, rerunnable validation — it loads each row through
the installed package's own `Config`, so it catches exactly what the loader
catches. `tests/preset_harness_probe.cjs` (added with this study) is that check:

```sh
node tests/preset_harness_probe.cjs
# → CONFIG-FAIL @deepseek-ai/dsh-persona  (row 1)
#                 $.prefix missing required value
#   … 36 rows; 1 hard failure(s); 6 without an exported Config   (exit 1)
```

It resolves `js-yaml` from the harness install and the `@deepseek-ai` directory
from the `dsh` on `PATH`, so it adds no dependency and needs no arguments; pass
a preset path or a harness modules directory to point it elsewhere. Exit code 0
means every enabled row validates.

Everything else in the preset — including all eight per-role
`dsh-tool-subagent` instances and the disabled MCP/escalation rows — validates
today. That single failure is the whole preset-mount blocker, and the probe is
the smoke test that would have caught it. Wiring it into `.githooks/pre-commit`
(or the pytest suite, which already drives the other `.cjs` probes) is the
natural next step, but it should run against the *installed* harness, so it
belongs behind the same "DSH present" guard `install.sh` already uses.

Harness sources used for the audit:

```sh
git clone --depth 1 --branch dsh-v0.1.5-rc.1 https://github.com/deepseek-ai/deepseek-harness.git /tmp/dh-src
cd /tmp/dh-src && git worktree add --detach /tmp/dh-a2 dsh-v0.1.5-alpha.2
```

---

## 7. Summary — what to do, in order

1. **Port the persona row and the section constant** (§4.1). Nothing else
   matters until the preset mounts.
2. **Fix the activity monitor** (§4.2): projections, or the native subagent
   catalog; delete the `?? []`.
3. **Replace the `report` contract** with final-message + optional
   `send_message`, and un-deny `send_message` for children (§4.3).
4. **Add the two missing rows** (`command-goal`, `present`, §4.4) and the
   deliverables sentence.
5. **Fix the patch-file skill root** (§4.7) — it resolves to a nonexistent
   directory, so the plugin contributes no skills outside the preset.
6. Small robustness fixes: route-registration flag (§4.5), fork/root
   classification (§4.6), the client legacy module (§4.8), stale
   `header.agentPreset` (§4.9), `ownEvents()` for the descriptor scan (§4.10),
   title caching (§4.11).
7. **Raise the floor** to ≥ 0.1.5-alpha.2 in `install.sh`, both READMEs and the
   preset header, and update the tests and `docs/architecture.md` (§4.12).
8. Then adopt: the right-Sidebar activity tab (§3.4), the native catalog and
   projections (§3.1/§3.2), and the preset-`roots` simplification (§3.6).

---

## 8. Independent audit

The finished port was reviewed by **Claude Code 2.1.267** — a different agent
runtime from the one that wrote it — read-only against commit `66a2ac5`, with
instructions to *falsify* the "Status: implemented" claim rather than confirm
it. It found four discrepancies and one staleness issue; all are resolved here.

| Finding | Class | Disposition |
|---|---|---|
| §4.8 told the reader to make `dsh.client.inject` name packages that exist but never said what should replace the bogus `dsh-client-runtime`; the port substituted `@deepseek-ai/dsh-client-ui-renderer` (the package that actually provides `slots`), which the study did not record | doc gap | §4.8 now records the substitution with the harness citation (`ui-renderer/src/client/registry.ts:134`) and notes the matching test fix |
| §4.2 promised "remove the `?? []` so a missing accessor fails loudly", but `dsh/activity.js`'s `ownEventsOf` still ended in `return []` — the silent-empty failure mode survived one layer down | code deviation | `ownEventsOf` now throws when a session exposes neither accessor. The router half (`dsh/index.js`) already failed loudly |
| §4.4 asserted *"Both are disabled at the host plane by the web-app bundle"*; only `command-goal` is. `present` appears in **no** bundle patch at all, which the same paragraph also says — an internal contradiction | doc error | §4.4 rewritten: the two rows are missing for *different* reasons, with corrected citations for both |
| The commit message grouped `docs/architecture.md` with the floor locations, but that file carried no floor string and Decision 20 still described the running harness as `0.1.0-rc.7` | overstated | Decision 20 now states the `≥ 0.1.5-alpha.2` floor and frames the `0.1.0-rc.7` line historically |
| The baseline table named `0.1.5-alpha.2` as the running version; the install has since moved to `0.1.5-rc.1` | staleness | The table now separates "at study time" from "on disk now", citing §4.14 for why no verdict changes |

Verified clean by the same audit: §4.1, 4.3, 4.5, 4.6, 4.7, 4.9, 4.10, 4.11 and
four of §4.12's five floor locations; the seven-deny-list count (`send_message`
in none, `interrupt_agent`/`list_agents` in all seven); both skill-file edits;
the existence of the `command-goal` and `present` rows; the claim that no bundle
mounts `dsh-tool-present`; and that `tests/router_probe.cjs` genuinely fails if
`PERSONA_SECTION` is reverted to `deployment:persona` (verified by reading the
assertion and its stub).

> Line numbers quoted *inside* §4 refer to the pre-port tree the study was
> written against; the fixes themselves are cited by content, and the audit
> re-cited them against the post-port tree.
