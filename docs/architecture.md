# RigorQuant architecture — the grilled decision record

## Sources studied

- **Shanmu Jin's Crouzeix run** (2026-07-30): full prompt at
  https://github.com/jinshanmu/CrouzeixConjecture/blob/main/crouzeix_conjecture_prompt.txt
  — epistemic isolation, diverse multiagent portfolio with an approach-family
  registry, adversarial counterexample-only audit, concrete-output discipline,
  persistence, terminal honesty. Verification gate: Lean 4 + pinned Mathlib,
  axiom audit (trust boundary `propext`/`Classical.choice`/`Quot.sound`, no
  `sorry`/`admit`), manuscript pinned by SHA-256 and mapped line-by-line to
  Lean declarations.
- **Terence Tao**: Blueprint + Lean formalization (PFR); the Equational
  Theories project (SAT solvers + Vampire/EProver grinding edges, humans/AI on
  the interesting nodes); frontier models as proposal generators on Erdős
  problems, humans verifying.

## Decisions (grilled with the user)

1. **Deliverable** — a framework (preset + skill + compute lanes) enabling any
   model to run long, difficult mathematical tasks **unattended within a single
   live session**; problems are empirical/computational
   (econ/finance/portfolio/simulation), not abstract proof. Crossing a session
   boundary disarms the goal and needs one human turn to re-arm (decision 10).
2. **Rigor gate** — hybrid: falsification by default; escalation to exact/
   formal verification when correctness hinges on an unproven claim.
3. **Check battery** — (A) closed-form equality, (B) exact invariants,
   (C) analytic bounds, (D) staged statistical hardening; on simplified/special
   cases BEFORE numerical implementation. The battery is a **reference-case
   sanity gate**, not a general-validity proof; general validity is established
   in explicit stages (see the skill's references/lifecycle.md).
4. **Trust** — two tracks (method open / ground-truth re-derived twice by
   different means) + adversarial audit; counterexample-only elimination; "a
   producer cannot certify its own output". Context isolation between the root
   and its subagents is harness-enforced; web access, filesystem scope, and
   recursion are **procedural** (per-role delegation tools), not a "wall".
5. **Compute substrate** — pinned uv Python lane (sympy/mpmath/cvxpy/hypothesis/
   jax) as default; **jacobian MCP as the independent escalation verifier** —
   dual verification, jacobian kept as escalation only. The `mcp-jacobian` row
   ships **disabled** and the command **pinned** (`jacobian@0.12.0`) so nothing
   runs at mount time; provisioning is approval-gated.
6. **Stochastic convention** — fixed seed + LLN: sampling error against the
   analytic mean must shrink (≈ C/√N) as N grows. Seeded, environment-pinned
   replay — not portable bit-identity.
7. **Isolation** — track-split: method track open (existing results allowed),
   ground-truth track re-derives; the orchestrator-detected off-grid toggle
   hands the route to the OffGridThinker, a separate agent whose only boundary
   is other people's results (no web, no prior context, no local files; the
   compute lane stays). These are procedural separations; only context
   isolation is harness-enforced.
8. **Multi-agent mechanism** — DSH-native: per-role delegation tools
   (`subagent_explorer` explorer, `subagent_offgrid` OffGridThinker and
   `subagent_double_checker` DoubleChecker, both web-denied,
   `subagent_adversary`; each `maxDepth: 1`, which permits exactly one
   level of delegation — a child is always at depth ≥ 1, so `maxDepth: 0` would
   block delegation entirely) + `workflow` fan-out with
   JSON schemas + goal-round driver; registry/journal files are the cross-round
   memory. `subagent_fork` is not used for track work. *(Amended on
   `feature/subagent-context`: the `subagent_fork`, `workflow`, and `ralph`
   rows are disabled outright in this preset — their children carry no role
   tag, and workflow `agent()` calls express neither a per-child persona nor a
   per-child toolFilter, so the preset declares them out of scope rather than
   minting unscoped, root-persona'd agents. Fan-out remains the goal-round
   driver plus the per-role delegation tools.)*
9. **Model routing** — one model everywhere (user's choice); reasoning-effort
   knob available per role; independence comes from context separation.
10. **Lifecycle** — PASS → auto-implement under branch/worktree + frozen write
    scope + rollback, then proceed; BLOCKED → same exact gap 3 consecutive
    rounds → deliver strongest derivation + exact gap; UNKNOWN → recorded when
    neither proof nor counterexample lands; BUDGET → 5 orchestrator rounds →
    checkpoint + report. One task-level goal (no per-sub-problem goals); budget
    fields (`max_cost_usd`, `max_wall_minutes`) may be set. Resuming across a
    session needs one human turn.
11. **Publishing** — repo distributes a bundle (package.json
    `dsh.bundle.patch` + cordis.patch.yml registering the skill), an agent
    preset + bundled skill (install.sh), MIT, `dsh-plugin` GitHub topic —
    compliant with the awesome-list `dsh plugin add` convention. The npm bundle
    ships `env/` and `mcp/`; `install.sh` anchors the compute lane at
    `$DSH_HOME/share/rigorquant`.
12. **Workspace** — a **study** is the self-contained work unit: one
    rigorquant task in one directory with an identical internal structure
    everywhere. Two modes, implied by location, no config flag: **Mode A —
    one study per repo** (`study.json` at repo root) and **Mode B — multiple
    studies per repo** (`studies/<slug>/study.json`, roster derived from
    `studies/*/study.json`). Durable deliverables (study.json, STUDY.md,
    registry.json, journal, derivations/, audits/, artifacts/) are committed;
    ALL scratch lives in `interim/` (explorer-reports, gt-scripts, tmp),
    gitignored via a study-local `.gitignore`. Intake resolves the study root
    by detection first (bounded at the git root, rejecting symlinks) and asks
    the user at most ONE question (mode + slug) when creating a study — resumed
    studies ask nothing, keeping runs unattended within the session. Supersedes
    the legacy hidden `.rigorquant/` layout, which conflated deliverables with
    scratch and could not hold multiple studies.

## Review amendments

The four-pass repository review ([docs/repository-review.md](repository-review.md))
recorded accepted verdicts that amend decisions 1 (unattended scope), 3/6
(sanity gate + statistical criteria), 4/7/8 (isolation language + per-role
tools), 5 (opt-in, pinned jacobian), 10 (one goal, auto-implement safety), and
11/12 (bundle contents + workspace). Those verdicts are the source of truth for
the wording above; the checker CLI and JSON Schemas they require ship inside the
skill, at `skills/rigorquant/scripts/` and `skills/rigorquant/schemas/`.

## Decision 13 — the checker is the honesty boundary

A later review demonstrated that a study with an empty `derivations/`, empty
stage `outputs`, a one-line adversary report and a paper reading "This paper
says nothing" was certified `PASS -- complete evidence`. Three rules follow, and
they bind every future change to the checker:

1. **A study may not vouch for itself.** Every evidence check reads
   `audits/`, `derivations/`, `artifacts/` — never `study.json`. A declaration
   states what was promised; only the record states what was done.
2. **Parse, never grep.** Registry state is read as JSON and traversed;
   `"passed"` appearing somewhere in the file is not a passed route.
3. **One validator, one schema, both tested.** A second copy of either is how
   the two silently diverged into different programs. `tests/` enforces this,
   and the schemas are what the validator actually loads.

## Decision 14 — literature lane

A new literature-research lane answers "what is settled / impossible / open /
current" before compute is spent, and a membrane exports ONLY verified negatives
(proven impossibilities) to the off-grid lane so it stays un-anchored. The lane is
a grad-student-style citation-graph traversal (backward references + forward
citations + related work + surveys), walled per line, with an independent
literature adversary that re-retrieves each load-bearing claim and certifies
validity + freshness (version/venue/retraction/supersession). Tooling is two
vendored skills (arxiv and academic-paper-search — both MIT; each skill's own
vendoring record carries its provenance) plus a tiered retriever (author page →
open repos/Unpaywall → preprint → OpenAlex/CORE → user-supplied mirrors,
disabled by default). Thoroughness outranks speed (10+ hr runs welcome); the
completeness gate — not the budget ceiling — is the finish line. The field
procedure lives in the `literature` skill; this record owns the decisions.

**Locked constraints.** These are the user decisions the implementation is
bound by, and they outlive any particular gate:

| # | Constraint |
|---|---|
| C1 | The blind lane keeps `bash`. Blindness is **tool-enforced** for web_search/web_fetch and delegation, **procedural + audited** for no-curl and no-cross-lane-read. Never described as a "wall"; the residual holes are named below. |
| C2 | The blind lane gets **delegation denied outright**, not merely capped by depth. Blind = the DoubleChecker (always) + the OffGridThinker (the off-grid toggle). A per-role network sandbox in DSH core is the future upgrade path. |
| C3 | A **verified negative** is a *mathematically proven* impossibility, falsehood, or known-intractability. Expert opinion, "big names think it unlikely", and the absence of a known result are NOT negatives. |
| C4 | The literature lane briefs the orchestrator; the orchestrator passes the off-grid lane **negatives only — never hints, never semi-positives**. |
| C5 | A fully-settled sub-problem gets no off-grid lane (the answer is a citation). A fully-impossible one gets no off-grid lane either (the answer is the impossibility, recorded as `status: "impossible"` with its math-lane escalation). |
| C6 | Paywall bypass is permitted and author-hosted copies are first-class. Retrieval is tiered; mirrors are **user-supplied and disabled by default**, with the legal basis recorded by the user. |
| C7 | Thoroughness beats speed; 10+ hours per run is acceptable. The budget is a resume-able safety ceiling, never a finish target. |

**The membrane, as edges.** This is the complete set of crossings; anything not
listed does not cross:

```
orchestrator ──line hypotheses──▶ lit line-agent (walled)
lit line-agent ──dossier──▶ orchestrator (interim/, never read by the off-grid lane)
orchestrator ──claims list──▶ lit adversary (NOT the dossier prose)
lit adversary ──verdict──▶ orchestrator
orchestrator ──verified negatives (provenance-stripped)──▶ off-grid lane
```

Open status never crosses (transmitting "this is open" is a hint), settled
results for other sub-problems never cross, and no source, survey, or
related-work framing crosses. The lane certifies "the literature says X, and X
is current" — never "X is true"; that stays with the math lane, and a negative
the study's *conclusion* rests on escalates there before the study may rely on
it.

What is **enforced**, and where: the blind deny lists live in the composition
(`tests/test_blind_deny_list.py`); the known-mark, routed-away-impossible +
math-lane escalation, negative-export subset, completeness-checklist,
refs-seed and fabricated-citation gates live in `rq_check.py`
(`tests/test_literature_gate.py`, `tests/test_integration.py`). The lane's
boundary to the outside world (arXiv, Semantic Scholar, Crossref) is a live
network dependency; `tests/test_retrieval_boundary.py` marks it unverified
rather than reporting "not run" as "passed".

**Residual holes, named.** What stays procedural and audited, because no
per-role network or filesystem scope exists in the spawn provider:

- **Bash-curl.** The blind lane keeps `bash`; nothing prevents it from curling
  `export.arxiv.org`. The math adversary audits for it — a blind output that
  cites or recalls an external result it could not have derived is flagged.
- **Cross-lane filesystem read.** A blind child could read `literature/` or a
  sibling's `interim/lit/`. Same class as the ground-truth hole the repository
  review named; per-line directories and a root-only merge are conventions,
  not enforcement.
- **Paywalled full text.** Where no tier yields full text, the lit adversary
  records `unverifiable` (abstract-only): a lower confidence tier, never
  `verified-current`, never load-bearing.
- **Mirror rot.** Mirrors rotate domains and break unattended runs; the
  user-supplied, empty-by-default tier keeps those URLs out of this repository
  and makes the legal basis a user-owned fact.
- **Hallucinated dossiers.** The lit adversary's independent re-retrieval plus
  the provenance gate is the defense; a dossier may never vouch for itself.
- **Rate limits and resume drift.** Semantic Scholar and Crossref throttle;
  retrieval must back off and record partial sweeps honestly rather than
  fabricate coverage, and a resumed walk re-anchors on the checkpointed
  frontier, with the completeness checklist carrying what was already swept.
- **Cost.** Thoroughness-first runs burn tokens; `max_cost_usd` /
  `max_wall_minutes` remain available as ceilings.

Deferred on purpose: OCR of PDFs (revisit only if abstract-only verification
proves insufficient in practice), and any mirror URL hardcoded in-repo.

## Decision 15 — the retrieval skills install globally

`arxiv` (MIT, vendored verbatim from NousResearch/hermes-agent) and
`academic-paper-search` (user-authored SKILL.md, MIT, author-confirmed
2026-08-16) are useful to any preset, not just this one, and
the literature roles load them by name. `install.sh` therefore copies both to
`$DSH_HOME/skills/` in both install modes and removes them on `--uninstall`,
while the preset keeps its own copies under
`agent-presets/rigorquant/skills/` so a checkout is self-contained. The blind
roles deny `skill` outright, so a global install never widens what the
off-grid lane can reach.

## Decision 16 — role-routed models (the rq-model-router plugin)

The preset used to run every agent on one model: children inherit the parent's
route, so the session default (flash@high) powered the DoubleChecker and the
adversary too. The economics point both ways — most of the agent volume is
divergent exploration and retrieval where flash@high is the right price, while
the two proof-critical roles are exactly where a weak model burns the most
rounds (a wrong derivation or a missed counterexample triggers the whole
BLOCKED loop). Decision: keep **dynamic per-role policy** in a plugin, while
fixed child defaults may use the native tool-row configuration in the
composition.

- **Mechanism.** The `dsh-rigorquant` package ships a host half that listens
  on the `agent/request` waterfall. It mounts at profile boot, so its listener
  can overlay an explicit user choice or an active fallback after the native
  child route has resolved. The per-role choice — provider, model, AND
  reasoning effort — wins over both the chatbox picker (root) and parent
  inheritance (children) only when the user configured an override; otherwise
  the fixed-tier tool row's native `agentOptions` remains authoritative.
  DSH 0.1.2 now carries `reasoningEffort` in that native channel, so it is no
  longer necessary to rewrite the shipped DoubleChecker/adversary primary on every
  request.
- **Role identity.** Every role persona carries a machine-readable tag
  `[[rq:role=<role>]]`. Continuable children persist the persona in their
  first `subagent/descriptor` event; one-shot (foreground) children carry it
  only in the live prompt, so the router probes the child's assembled persona
  section once. Children without a tag — fork, workflow workers, ralph
  rounds — and sessions on other presets are never touched. The `root` role
  applies only to sessions without a `parentSession` (a workflow worker also
  runs under this preset, but it is not the root).
- **Root follows the chatbox.** The root role has no primary by default: the
  picker stays the master switch for the root and for every role left on
  "inherit". Pinning root is a one-select action in the card.
- **One fallback per role.** On a terminal primary failure (no adapter, or an
  HTTP 4xx the route cannot recover from) the router degrades that
  session+role to the role's own fallback and forces exactly one retry. A
  successful assistant step on the fallback — or the TTL (10 min) — restores
  the primary; a failing fallback is never retried again by the router.
- **Persistence and UI.** Choices live in the `rigorquant-models` settings
  namespace (user layer of `settings.yaml`); the browser half renders the
  card in the Plugins settings tab, keyed by that namespace, with model and
  effort dropdowns from the live provider catalog.
- **Shipped defaults.** DoubleChecker and adversary: `deepseek-v4-pro`@high with a
  `deepseek-v4-flash`@low fallback (a fallback is a degrade lane, not a second
  full-price route). Every other role: inherit. Defaults
  assume the `deepseek-official` catalog; a deployment without it overrides
  the row config or the card, and a default that cannot route degrades
  through the same fallback lane (or fails loudly if the fallback cannot
  either).
- **0.1.2 native defaults.** `tool-subagent-double-checker` and
  `tool-subagent-adversary` now declare those fixed primary choices through
  the builtin `agentOptions` channel, including `reasoningEffort`. The router
  reads the raw user layer so a reset returns to that native route instead of
  running a redundant rewrite. `maxTokens` remains omitted deliberately: the
  provider's own output ceiling is safer than imposing an arbitrary cap on
  proof-heavy reports. The new `modelSelectionSettings` allow-list is not
  enabled for these role tools because caller-selected routes would undermine
  the forced tier matrix; the Settings card remains the explicit override
  surface.

Guarded by tests: every role persona must keep its tag, the router's ROLES list
must equal the tagged roles plus `root`, and the fixed-tier rows must retain
matching native `agentOptions` defaults. A persona that loses its tag silently
falls back to the session model, which is exactly the failure class this closes;
`tests/router_probe.cjs` separately pins native pass-through and fallback
recovery.

## Decision 17 — budgets are finish targets, with explicit escalation

Measured on real runs, the previous framing — "the budget is a resume-able
safety ceiling, never a finish target; 10+ hour runs are expected"
(literature lane), `max_orchestrator_rounds: 5`, fan-out 2–4, and an
unconditional dual ground-truth track — let a single study bill into the
hundreds of millions of metered tokens, dominated by per-step re-sends of a
~9k-token header plus open-ended traversal. Decision: **bounded by default,
escalation is an explicit recorded act.**

- `max_orchestrator_rounds` default 5 → **3**; BUDGET fires at 3 rounds.
- Fan-out default 2–4 explorers → **1–2**; the second ground-truth track is
  mandatory only for **load-bearing** claims (the whole study rests on them),
  never one agent doing both "independent" derivations.
- Literature budget default 8/4/80/8 → **4/3/20/4**. A line concludes at the
  budget with the strongest completed dossier and remaining checklist items
  recorded open. Exceeding the budget requires an explicit user escalation
  recorded in `study.json` `literature.budget` (raising numbers or setting
  `max_cost_usd`); a silent overrun is a defect. `max_wall_minutes` stays
  unset by default (the field remains nullable).
- Compaction fires at **60%** of the routed context window (was 80%) and the
  tool-result pruner retains **4 KiB** per result (was 8 KiB): an earlier,
  smaller compaction shrinks the cached prefix re-sent on every step. The
  model-facing tool catalog itself is host-plane — the heavy tools
  (`workflow`, `ralph`, `ask_user_question`, …) are registered by the profile
  composition, not this preset, so they cannot be trimmed from this
  repository; a session's catalog is the union of host tools + preset rows.
- Journal stays append-only (a rolling journal was considered and rejected:
  the append-only record is the study's audit trail).

## Decision 18 — j-space is unbundled

The j-space cognition suite shipped inside this preset (skill directory,
install.sh wiring, and an inline j-space protocol paragraph in every persona).
It is the user's separate distribution and adds a hard external dependency to
every rigorquant session — including the blind roles (`offgrid`, `doublechecker`),
which deny the `skill` tool and can never load it, so the inline block was
pure prompt tax on every one of their requests. Decision: **j-space lives in
its own branch, not here.** The skill directory, its install/uninstall lines,
and all inline persona references are removed; rigorquant no longer mandates
it. Guarded by a consistency test asserting the absence.

## Decision 19 — claim-keyed blocking (narrow before patch)

The 20260820 var-expected-return-term run burned rounds 2–6 of an 8-round
budget re-certifying one stage-3 claim: every round found a genuine new
defect (interval-independence → input-truth hypothesis → funding → factor-map
hypothesis → log-vs-simple funding rate), so the "same gap 3 rounds →
BLOCKED" rule never fired and patching never had to stop. Repeated
independent failures on one claim are evidence that the claim's scope exceeds
what is provable. Decision: **BLOCKED is keyed on the claim, not the gap** —
after two consecutive NEEDS-EDITS on the same claim or section, the next
round must either narrow the declared scope to what is certified or declare
BLOCKED with the exact gap; a re-patch that changes only the mechanism, not
the scope, is a defect. Guarded by procedure (lifecycle.md, SKILL.md Step 3).

## Decision 20 — verdict data is the deliverable; status waits for it

The same run's other loops were all process failures: six delegated agents
produced complete verdict JSON (36/36 cells) without ever writing the report
files; queued follow-up messages to settled agents produced re-audits of dead
documents; concurrent edits invalidated audit hashes; `status` certified the
orchestrator's own repair before the ruling landed; and the orchestrator's
own generator emitted a wrong table cell that went unaudited. Decision:

- A delegated verdict is the **report with the `VERDICT:` line**; the JSON is
  a side effect. A run that settles without the verdict line is a failed run:
  read the results JSON once, record the verdict, never re-dispatch for
  prose. The orchestrator may transcribe an independent agent's structured
  verdict; transcription is not certification.
- An artifact under adversarial audit is **frozen until the verdict lands**,
  and the verdict records the audited snapshot's SHA-256. No follow-up
  messages to in-flight or settled agents.
- **Status is written from verdicts.** `rq_check.py` refuses a status that
  asserts a certification outcome without referencing an existing verdict
  file or frozen hash (`status.verdict-reference`).
- The stage-3 claim's digest (`claim_sha256`) is recorded at certification;
  `rq_check.py` flags an edit after certification as needs-re-certification
  (`stage3.claim-digest`).
- Schema and validator digests are pinned at intake (`intake_pins`);
  `rq_check.py` flags a reissue mismatch as a re-intake event
  (`intake.schema-pin` / `intake.validator-pin`).
- Orchestrator-produced numbers are audited like agent output (second
  instrument); document-adversary passes are capped at two per deliverable.

Guarded by `tests/test_procedural_gates.py`.

## Decision 21 — adopt the 0.1.1-rc.2 builtins; dual-version the browser half

Studied deepseek-harness 0.1.1-rc.2 (the newest release; the running harness
is 0.1.0-rc.7). The host half and preset are byte-compatible; the browser half
hit the one breaking change: `@deepseek-ai/dsh-client-schema-form` was deleted
in rc.2 and its helpers folded into the `settingsSchema` service
(`rehydrate`/`validate`; path helpers unchanged). Decision:

- **Dual-version the client.** `dsh/client.js` resolves the draft model from
  `ctx.settingsSchema` when present (rc.2+) and falls back to the legacy
  module on older harnesses, so one bundle runs on both. The bundle probe
  gains an `rc2` mode that removes the legacy module from the table and serves
  the service — a residual require would throw and fail the mount
  (`tests/client_bundle_probe.cjs`, `test_card_mounts_on_rc2_settings_schema_service`).
- **Adopt the child `report` channel.** Continuable in-process children carry
  a child-scoped `report` tool (host-mounted, present since rc.7; rc.2 renamed
  the delivery mode `wakeup`→`next-step`). RigorQuant's L2 report-first
  delegation now instructs every role to deliver its verdict through `report`
  — the verdict is pushed to the orchestrator and wakes it, replacing
  wait-for-report-file loops. Works on the current harness, no upgrade needed.
- **Parallel `web_search`.** rc.8 added a `queries` array (default 4, merged);
  the literature lane batches independent queries.
- **Named external-agent bundles.** Claude Code / Codex are installable as
  profile bundles (named instances, per-role permission modes: plan/never
  default, bypass reserved for the approval-gated escalation lane). The
  preset documents the modes on the disabled rows; bundles install at the
  profile, not in this preset.
- **Multimodal.** rc.8/rc.1/rc.2 add native DeepSeek image requests, the
  `deepseek-v4-flash-vision-exp` model, Files API upload+reuse, and a
  model-facing `read_image` tool. The router card renders the live catalog, so
  the vision model appears on rc.2 without config; roles that read figures may
  use `read_image` when the route supports image input.
- **Watch (not wired):** the experimental `agent-team` domain (shared task
  DAG, `spawn_teammate`/`wait_agent`) is the closest native match to the
  round-loop fan-out; adopt only when it stabilizes.

Storage note: rc.8 changed the SQLite backend format (no migration), but it is
opt-in; rigorquant sessions persist as JSONL, which is byte-compatible across
the upgrade.

## Decision 22 — reproducibility is the record; junk is derived state

Core philosophy of the plugin, hard-won from the 20260820
var-expected-return-term run: the study tree ended at ~729 MB of venvs and
caches, its deliverables promised "reproduction" through gitignored scratch
paths, and a fresh clone had zero working reproduction commands. Two
obligations:

- **Perfect reproducibility.** The committed study record is self-contained:
  a fresh clone plus the pinned uv lane regenerates every piece of evidence.
  Every command a deliverable prints, and every path the record cites,
  resolves to a tracked file — never to `interim/` scratch. Study-generating
  scripts live in a tracked `code/` directory; record-cited data files live
  in `audits/` / `literature/`; the pinned lane's `pyproject.toml` + `uv.lock`
  make the environment reproducible by declaration, not by presence.
- **Minimal junk.** Derived state (venvs, uv caches, bytecode, OS metadata)
  is never committed and is deleted at close-out; `interim/` is the one
  designated scratch home, gitignored at intake. Cleanup and reproducibility
  are the same close-out pass.

Enforcement is in `rq_check.py` at PASS time: `evidence.junk` (derived state
on the committed surface), `deliverables.scratch-refs` (a deliverable citing
`interim/`), `deliverables.repro-paths` (a deliverable citing a missing
`code/|derivations/|audits/|literature/` file), plus the pre-existing
registry-outputs-exist check. Full statement, operational rules R1-R7, junk
taxonomy and the close-out sweep protocol:
`agent-presets/rigorquant/skills/rigorquant/references/reproducibility.md`.

## Decision 23 — the bundle self-installs the preset and the lane

The distribution previously had two doors: `./install.sh` (everything) and
`dsh plugin add` (a router with nothing to route, because only install.sh
could land the preset and the lane). The asymmetry was mechanical, not
stylistic:

- **Presets are outside the patch plane.** Discovery is a filesystem scan of
  `$DSH_HOME/.agent-presets` (plus configured and shipped roots), and the
  harness's own profile overlay pins the `agent-presets` row's `roots` to the
  shipped root after every bundle layer composes — no `cordis.patch.yml` row
  can point the roster at node_modules.
- **node_modules cannot host the compute lane.** A venv is derived state with
  absolute paths; pnpm's virtual store is version-pathed (an upgrade churns
  every recorded absolute `env_lane` in existing studies' `study.json`) and
  volatile (`pnpm remove/update` deletes a provisioned environment mid-study).

Decision: ship a second host half, `rq-preset-sync` (`dsh/sync.js`, exported
as `./sync`, mounted by a bundle row). Once per profile boot it lands files —
the same work `install.sh` does, executed inside the host process:

```
agent-presets/rigorquant → $DSH_HOME/.agent-presets/rigorquant
env/ mcp/ docs/          → $DSH_HOME/share/rigorquant/<same>
```

Contract, each property pinned by tests:

- **Idempotent byte-compare** — identical trees are left untouched; no mtime
  churn on files a watcher may be serving.
- **Replace on install/upgrade** — changed or missing files are copied and
  target-only entries pruned, EXCEPT derived state (`.venv`, `__pycache__`,
  `*.pyc`, `.DS_Store`), which is never copied out of a source and never
  pruned from a target. A lazily provisioned venv at the lane anchor survives
  every boot and every package update.
- **Local-edit preservation** — a target stamped with the CURRENT version
  whose shipped files all still exist is kept (`kept-local`). The preset is
  meant to be edited in place (the escalation lane enables `mcp-jacobian` by
  flipping a row in the INSTALLED composition); boot-sync must not revert
  that. An upgrade moves the stamp and legitimately replaces shipped files —
  the same contract as re-running `install.sh`.
- **Soft failure** — a sync error logs a warning; it never blocks the profile
  or the router sharing this package.

Lifecycle honesty: DSH's plugin CLI has **no uninstall hook** — `dsh plugin
remove` is pnpm delete plus a manifest reconcile, and code that no longer
exists cannot run — so "remove the preset when the plugin is removed" is not
implementable from inside this package. Each install/boot instead REPLACES the
managed trees wholesale, every managed root carries an ownership marker
(`.rq-sync.json`: manager + version + syncedAt) so ownership stays
discoverable after removal, removal stays explicit (`./install.sh
--uninstall`), and orphaning is benign: the synced preset is self-contained
(skills travel inside its directory) and merely routes nothing without the
router.

Tests: `tests/test_preset_sync.py` executes the engine over real directories
via `tests/preset_sync_probe.cjs` (first sync, quiet rerun, replace-on-bump,
venv-survival, no venv leakage, kept-local edits, damage restore);
`test_repo_consistency.py` pins the wiring (row mounted, export resolves,
exclusions named).

## Repo map

```
agent-presets/rigorquant/   the preset: composition + persona + rigorquant skill
  skills/rigorquant/        SKILL.md, references/, scripts/rq_check.py, schemas/
dsh/                        host halves: rq-model-router + rq-preset-sync, card
cordis.patch.yml            bundle patch: skill layer + router + boot-sync rows
env/                        pinned uv compute lane (pyproject + lockfile)
mcp/jacobian.md             escalation lane wiring
docs/architecture.md        this record
tests/                      the validator's suite; a forged study must FAIL
install.sh                  installs the preset (or --skill-only) into $DSH_HOME
```

A study folder (`studies/<slug>/` in Mode B, the repo root in Mode A) lives in
the *research* repo, not here: `interim/` inside each is gitignored, everything
else commits.
