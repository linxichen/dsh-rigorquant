---
status: accepted
date: 2026-09-21
---

# RigorQuant runs on Agent Teams

DSH 0.1.6 ships Agent Teams as an experimental optional bundle: a named,
durable roster under the session's root agent, a durable mailbox, a shared
task board, and a native team view. From 0.5.0 RigorQuant's multi-agent
mechanism **is** Agent Teams — team-only, no classic per-role delegation
tools left in the preset — and the per-role composition Teams does not carry
(persona, tool budget, model tier, hub-and-spoke topology) is re-established
by a RigorQuant host plugin on every teammate's `agent/created`, keyed by
the teammate's **name**. The upgrade study it came from is retired (Decision 25) and stays readable at tag `v0.5.0`. Recorded as
Decision 24 in `docs/architecture.md`.

## Why

- `spawn_teammate` accepts only `name`, `description`, `prompt`, `context`;
  the service forwards none of the composition that `startContinuable`
  would accept. Waiting for upstream would have blocked the upgrade on a
  domain upstream itself calls unstable; applying composition plugin-side on
  `agent/created` is the same mechanism DSH's own child composition and the
  Team tools use, so it is the supported path, and an upstream pass-through
  can later only *delete* code from the plugin.
- The teammate name is the one identity that is durable in the orchestrator's
  log, in every roster row and in the UI. It replaces the `[[rq:role=…]]`
  persona-tag scan. Role by name: `<role>-<n>`.
- Teams' scoped tools cannot be masked by `tools.restrict`; `tools.guard` can
  deny them per call. Hub-and-spoke therefore moves from a procedural rule
  to an enforced one (a teammate may message only the orchestrator), and the
  bash network verbs for web-denied roles move from "audited" to "denied at
  the call". Context isolation is still the only wall.

## Considered and rejected

- **Dual-mode (classic + Teams).** Two personas, two protocol texts, two test
  tables, and a weaker topology in one of them. 0.4.2 stays the last classic
  release instead.
- **Mount the Team packages inside the preset or bundle patch.** The service
  is a host-plane Remote with a global projection; a second instance
  collides and the Web UI expects the host one. RigorQuant consumes the
  shipped optional bundle, never imports the experimental packages, and
  reaches the service duck-typed (`agentTeams`), failing loudly when absent.
- **Fresh teammate for everything.** `maxMembers` is a lifetime cap that
  counts failed members. Explorers, OffGridThinkers and DoubleCheckers are
  fresh per brief (blank context is the point); adversaries and literature
  lines are reused across rounds by message, since their accumulated
  knowledge is the job.
- **Porting the custom activity floater onto the team view.** The native
  roster already shows status, model, diagnostics and the board; only the
  round's *move* is missing, and a header pill supplies it.
- **Per-teammate scratch directories.** `write_scopes` is advisory and stays
  on the role directories Decision 12 fixed.

## Consequences

- Hard-lesson L3 (`docs/hard-lessons-from-the-var-expected-return-run.md`,
  carried by the skill's `references/protocol.md`) is rewritten: the
  freeze-and-hash half stands; "never
  message a settled agent" becomes "a reused teammate only ever receives a
  new hash-bound brief, never a follow-up about an artifact under audit, and
  only while idle or inactive".
- Every teammate is roster-blind (`list_agents`, `team_task_list` denied; a
  teammate reads and updates only its own task); `interrupt_agent` and
  `spawn_teammate` are orchestrator-only, and the orchestrator is denied
  non-role names and `context: fork`.
- Role personas live as Markdown files the plugin reads (`dsh/personas/`),
  not in the preset composition; a repo test pins name↔file identity.
- `install.sh` enables the two Team bundles and writes a `maxMembers`
  override (64) into the profile user patch under a marker; `--uninstall`
  reverses only what it wrote. Hitting the lifetime cap is a BUDGET-class
  outcome: checkpoint and report, one human turn re-arms.
- The model-routing plugin now carries the shipped tier matrix itself (no
  native `agentOptions` rows remain) and resolves the role from the
  membership name.
- The board is coordination, never evidence: `rq_check` reads the study
  record only (Decision 13 unchanged).
- The dependency on an experimental bundle and an alpha harness is accepted
  and stated in the README; the floor is `0.1.6-alpha.2`.
