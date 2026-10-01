---
status: accepted
date: 2026-09-29
---

# RigorQuant moves to DSH 0.2.0-rc.2 and takes up four native surfaces

DSH 0.2.0-rc.2's compatibility gate reads a bundle's `peerDependencies`
before it loads it and **skips a bundle whose range the running core does not
satisfy**. RigorQuant 0.6.1 declared `>=0.1.7-rc.2 <0.1.8`, so on 0.2.0 it
would have mounted nowhere — no preset, no router, no team guard, and no error
a user could see. From 0.7.0 RigorQuant requires `>=0.2.0-rc.2 <0.2.1`:
`peerDependencies` is the enforced range (the loader and `dsh plugin add` read
it), `install.sh` refuses a core at EITHER end before copying anything, and
`engines.dsh` plus `dsh.manifestVersion: 1` state the same contract in the
manifest's own fields — which this core reads for nothing yet, so they are
documentation, not a fifth mechanism. 0.6.1 is the last release for the
0.1.7-rc.2 line. Alongside the range, the release takes up four mechanisms the
core serves natively: the timed `ask_user_question`, manifest display
metadata, field descriptions for the harness's generated settings page, and
the declarative manifest dialect. Recorded as Decision 26 in
`docs/architecture.md`.

## Why

- **The old range goes dark, not degraded.** The loader logs a skipped bundle
  and boots the rest of the profile, so a user sees a missing RigorQuant, not
  a failure. There is no version of "keep 0.1.7 support in the same manifest"
  that avoids this: one `peerDependencies` range is evaluated against one
  running core.
- **The architecture did not move with the version.** Diffing the two cores
  package by package: the declared-preset loader, persona, tools, system
  prompt, config forms, Agent Teams service, MCP client and home-path helpers
  are identical. 0.2.0-rc.2 adds telemetry, desktop analytics, a session-log
  settings page and an opt-in schedule bundle, none of which RigorQuant
  consumes. So this is a range cutover, not a rewrite — and the tests that
  already validate every preset row against the installed core's own schemas
  were run, green, against 0.2.0-rc.2 before the range changed.
- **The timed ask is the unattended contract's missing piece.** A study runs
  unattended inside one live session, and its intake question ("one study per
  repo, or `studies/<slug>/`?") and its approval-gated escalation asks
  (`jacobian` install, Lean provisioning) previously either blocked the round
  or were forbidden. `dsh-tool-ask-user`'s new `mode: timed` returns a
  `pending` result when the user has not answered within the wait, keeps the
  questions answerable, and steers the reply in later as a user message. The
  preset selects it with an explicit wait; the persona and skill state that
  pending is neither an answer nor permission, and reserve `timeout: -1` for a
  step no further work can route around.
- **Metadata the browser reads without running the plugin.** `locale/en.json`,
  `locale/zh.json` and `icon.svg` are resolved from the manifest by the
  Plugins page, bundle details and the Settings plugin inventory. RigorQuant
  ships both languages already, so the fallback (npm name, npm description,
  default artwork) was the only part missing.
- **Field descriptions for the harness's generated page, on the right fields.**
  `SettingsForms` renders one generated settings page per row, and only from
  `meta.volatile` subtrees (`volatileForm`); everything else on the row — the
  preset id, the degrade TTL — is dropped before the form exists. So the
  descriptions live on the sixteen route fields, one each, naming the role and
  the slot ("DoubleChecker — primary route: … Unset takes the shipped tier.").
  The first attempt described the dropped fields instead and shared one generic
  line between the routes: text that renders nowhere, and text that names
  nothing. `description()` clones the schema, so the routing contract is
  untouched — `tests/router_schema_probe.cjs` evaluates the real builder and
  shows every route field still `meta.volatile` and still a live cell.

## Considered and rejected

- **Supporting 0.1.7 and 0.2.0 from one release.** Two harness generations for
  a dependency that is itself experimental, with no interval in which both are
  tested; the previous cutover (Decision 25) set the same precedent.
- **Deleting the routing card for the harness's generated settings page.**
  `SettingsForms` does auto-generate a page from the router row's `Config`,
  but that page cannot pick from the live model catalog, cannot express
  "inherit the session route", and cannot clear one role's override. The card
  keeps its job; the native page remains available beside it.
- **Scheduling rounds with the opt-in experimental schedule bundle.** It could
  restart work without a human turn, which is exactly the boundary
  RigorQuant's unattended contract draws: rounds do not continue across
  restarts, and one human "continue" rearms the goal.
- **A native per-agent MCP mount helper, or a plugin-registered settings
  namespace.** Neither exists on this core; `rq_escalate` mounting
  `dsh-mcp-client` in one agent scope, and routes as `.volatile()` profile
  config, stay the native mechanisms available.

## Consequences

- `install.sh` refuses a core below 0.2.0-rc.2 before copying anything, and
  both READMEs carry the operator sequence for the cutover. An operator on any
  0.5.x or 0.6.x release upgrades straight to this one: the installer keeps the
  migrations those releases needed (the retired web bundle, the
  `settings.yaml` route port, the pre-0.6.0 directory preset), so no
  intermediate release has to be installed first.
- The harness probe (`tests/preset_harness_probe.cjs`) validates every row
  against the 0.2.0-rc.2 packages, and it judges the core with the harness's
  own `evaluatePluginCompatibility` rather than a second range matcher; the new
  `tool-ask-user` row config, the locale documents, the icon and the router's
  route descriptions are pinned by `tests/test_repo_consistency.py` and
  `tests/router_schema_probe.cjs`.
- A `pending` ask is recorded as provisional at intake and stays open at the
  escalation gate, so a study never treats silence as consent.
- Anything this migration makes dead is deleted in the same release, and so
  are the tests that pin it.
