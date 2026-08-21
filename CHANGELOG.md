# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This file starts at 0.2.0; earlier releases (0.1.0, 0.1.1) predate it.

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
