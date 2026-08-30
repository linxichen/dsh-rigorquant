# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This file starts at 0.2.0; earlier releases (0.1.0, 0.1.1) predate it.

## [Unreleased]

### Fixed
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
- **Self-installing bundle (Decision 23):** a second host half, `rq-preset-sync`
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
- **0.1.1-rc.2 readiness (Decision 21):** the browser half is dual-version —
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
- **j-space is unbundled** (Decision 18): the bundled skill directory,
  install.sh wiring, and every inline j-space persona paragraph are removed —
  rigorquant no longer depends on j-space (including the blind roles, which
  cannot load skills anyway); it ships from its own distribution.
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
