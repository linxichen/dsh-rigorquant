---
name: rigorquant
description: >
  Operating procedure for long-running empirical/computational mathematics
  research on DeepSeek Harness: context-isolated multi-agent exploration in the
  style of Jin's Crouzeix run and Tao's collaborative projects, dual-track
  ground-truth derivation, adversarial counterexample-only audit, a four-part
  pre-implementation check battery (closed-form equality, exact invariants,
  analytic bounds, statistical hardening), fixed-seed LLN conventions, a
  jacobian/Lean escalation lane, the PASS/BLOCKED/BUDGET lifecycle, and the
  reference-case → generalization → domain-scale stage order enforced by the
  rq_check meta-validator. Load
  when the user asks for rigorous quantitative research, method validation
  before implementation, long unattended numerical work, or says "rigorquant".
---

# RigorQuant operating procedure

You are running an **empirical and computational** technical research
framework: economics, finance, portfolio construction/optimization, simulation,
computational econ/finance. The goal is a method whose **mathematical validity
is established on simplified/special cases before numerical implementation** —
not a theorem for its own sake. Special cases are the scaffold, not the
destination: the study is complete only when the broad original question is
answered. When correctness hinges on an unproven claim, escalate to
proof-grade verification first (see escalation.md).

**Core philosophy — reproducibility is the record; junk is derived state.**
The committed study record is self-contained: a fresh clone of the repo plus
the pinned uv lane regenerates every piece of study evidence, and nothing
disposable sits on the committed surface. Concretely: every command a
deliverable prints, and every path the record cites, resolves to a tracked
file — never to `interim/` scratch; virtualenvs and uv caches are derived
state, rebuilt by `uv sync --frozen` from the pinned lane's lockfile, never
committed; and cleanup and reproducibility are the same close-out pass,
enforced by `rq_check.py` at PASS time (see
[references/reproducibility.md](references/reproducibility.md)).

**Unattended, precisely:** the framework runs unattended within one live
session. Crossing a session boundary disarms the goal; one human turn
("continue") re-arms it. Checkpoint state to `study.json` / `registry.json` /
`journal.md` every round so a resumed session can reconstruct the study.

If this is the first message of a rigorquant task, run Steps 0–2 in order, then
enter the round loop.

## Step 0 — Intake

1. Restate the problem; split it into sub-problems, each with a crisp "valid
   method" success criterion. Mark each sub-problem `known` (an analytical
   result likely exists) or `novel` (no known closed form) — a hint only; the
   orchestrator may override by detection (see protocol.md).
2. **Coverage check (mandatory).** The union of sub-problems must cover the
   ORIGINAL statement, not just the simplified cases. If the question is
   general (e.g. "any convex body", "any distribution class"), at least one
   sub-problem — the **generalization sub-problem** (stage `generalization`) —
   must carry the broad claim as its success criterion, and at least one
   (stage `domain-scale`) must certify the method on a genuinely non-special
   instance. Record the broad claim verbatim in `study.json`
   `broad_criterion`. `rq_check.py` rejects a study at intake without both.
3. Choose simplified/special cases per sub-problem: the smallest
   hand-computable settings that still exercise the method (2 assets, 2–3
   dimensions, low N). These are scaffolding for the broad claim — never the
   definition of success.
4. Record the **seed** for every stochastic run in `study.json`.
5. **Pin the tooling (hard-lessons L7).** Record `intake_pins` in `study.json`:
   `schema_sha256` and `validator_sha256` — the digests of the
   `<skill-dir>/schemas/study.schema.json` and `<skill-dir>/scripts/rq_check.py`
   in effect at intake (hash them with `shasum -a 256`). A mid-run reissue
   that rejects the study is a re-intake event, never an on-the-fly repair.
6. **Declare deliverables (mandatory).** Record in `study.json`
   `deliverables`: `paper` (always `"required"`), `slides`
   (`"required"` unless a reason for `"not-required"` is recorded at intake),
   `web` (`"optional"` or `"required"` — required when the study will produce
   interactive/visual artifacts: widgets, movies, dashboards). The paper and
   slides are produced ONLY at PASS, assembled from validated records (see
   stage 4 and references/deliverables.md). `rq_check.py` enforces the
   declaration at intake and the artifacts at PASS.

For a new task, resolve the study workspace (Step 1) and create `study.json`
before entering the round loop.

## Step 1 — Study workspace

A **study** is one self-contained rigorquant task — a single directory with the
identical internal structure in every repo. All paths in this skill are
relative to the **study root** unless prefixed otherwise.

### Resolve the study root (detect first, ask once, never re-ask)

1. Walk up from the working directory looking for `study.json`, but never past
   the git repository root (`git rev-parse --show-toplevel`). Found → that
   directory is the study root: continue the study, ask nothing. If the study
   root (or any ancestor in the walk) is a **symlink**, reject it and treat the
   walk as not-found — a study root must be a real directory.
2. The repo root contains `studies/*/study.json` → a multi-study repo. Read
   the roster (each study's `slug` from its `study.json`); if the user named
   a study, continue it; otherwise ask ONE question: continue which study, or
   create a new one (new slug).
3. Neither → a new study. Ask ONE `ask_user_question` (recommended default
   first), then never again:
   - **Mode A — one study per repo:** study root = repo root. Recommended
     when the repo is dedicated to this research.
   - **Mode B — multiple studies per repo:** study root = `studies/<slug>/`.
     Recommended when the repo also holds other code or several research
     topics.
4. Create the study: `study.json` (schema in lifecycle.md), the folders
   below, and a `.gitignore` containing `interim/` and `.lock` — in Mode B
   inside the study folder; in Mode A append `/interim/` (anchored, so it
   matches only the repo-root scratch directory) to the repo-root `.gitignore`.
   Persist mode, slug, and `repo_root` in `study.json` (`env_lane` is resolved
   and added by Step 2); resumes never re-ask.

   **Mint the slug as `YYYYMMDD_<kebab-topic>[_v<N>]`** — the 8-digit intake
   date (same day as the `created` field), a kebab-case topic, and `_v<N>`
   only when that date+topic already exists or this is a deliberate later run
   of the same topic. The schema pattern enforces this form. The date is fixed
   at intake and the slug never changes on resume; renaming is an explicit
   migration (directory, `slug`, `task_id`, and any in-study references), never
   a resume-side edit. In LaTeX deliverables, write the slug with escaped
   underscores (`20260814\_convex-sampling`); rq_check.py unescapes before the
   paper's slug/task_id reference check.

### Study layout (identical in both modes)

```
<study-root>/
├── study.json          # identity: slug, title, mode, statement, subproblems,
│                       #   seeds, budget, status, repo_root, env_lane
├── STUDY.md            # human-facing summary, refreshed at checkpoints
├── registry.json       # approach-family registry (see lifecycle.md schema)
├── journal.md          # append-only round log (append every round)
├── derivations/        # ground-truth derivations, two independent per claim
├── audits/             # adversary reports + check-battery results
├── artifacts/          # PASS: final validated method + audit trail
│   ├── paper/          #   mandatory white paper (main.tex)
│   ├── slides/         #   Beamer deck (main.tex) when required
│   └── web/            #   interactive HTML (index.html) when required
├── interim/            # ALL scratch work — never committed:
│   ├── explorer-reports/
│   ├── gt-scripts/
│   └── tmp/
├── .lock               # transient study lock naming the live run (see below)
└── .gitignore          # contains: interim/  (and .lock)
```

Everything except `interim/` and the transient `.lock` is meant to be committed
to git. Internal references recorded in registry.json / journal.md / audits are
study-root-relative. Study-generating scripts additionally live in a tracked
`code/` directory with a `code/README.md`; the validator refuses PASS while
derived state sits on the committed surface or a deliverable cites `interim/`
(see [references/reproducibility.md](references/reproducibility.md)).

**Run identity and lock (once per launched check run):** resolve the study root
to an **absolute path** and mint a run id (`<date>-<short-hash>`); record both
in the header of every output you write this round. Create a `.lock` file in
the study root naming the live run before you start writing; remove it when the
round finishes. If a second orchestrator, or an external repository
reorganization, moves the study root while a run is in flight, the recorded
root no longer matches the resolved root — fail loudly instead of writing.

Create the goal tool objective **once, for the whole task** (`create_goal`),
not per sub-problem. Sub-problems live in `study.json` / `registry.json` state.
Every round the orchestrator returns; the goal-round driver relaunches it.

## Step 2 — Locate the compute lane

The pinned uv lane is installed at a stable anchor, independent of the
checkout: `$DSH_HOME/share/rigorquant/env` (`$DSH_HOME` defaults to `~/.dsh`;
`install.sh` places it there). Resolve `env_lane` in this order:

1. `study.json`'s `env_lane`, if it is an absolute path whose directory
   contains `pyproject.toml`.
2. `$DSH_HOME/share/rigorquant/env`, if it contains `pyproject.toml`.

Record the resolved **absolute** path in `study.json` (`env_lane`). Run
subagent code with `uv run --frozen --project <env_lane> python ...`. If
neither resolves, ask the user where the lane is; never `uv sync` a stray lane
inside the user's project. Never let subagents `pip install` into the ambient
interpreter: reproducibility is a gate (D).

## Step 2b — Literature lane (known/novel intake)

The intake sweep is **mandatory** for every study, and skippable only on an
explicit user assertion at intake — recorded as `literature.phase: "skipped"`
plus a verbatim `skip_reason`, which the validator requires. Otherwise run the
lane before trusting a sub-problem's known/novel mark: walled citation-graph traversal
per line (backward references + forward citations + related work + surveys),
then an independent literature adversary for validity + freshness. Only
mathematically proven impossibilities (verified negatives) cross to the novel
lane, provenance-stripped — never hints, never semi-positives, never 'open' or
'settled'. Verified state lives in literature/known-results.json; the validator
refuses a known mark, a negative export, or a citation without a verified
record. Procedure and schemas: [references/literature.md](references/literature.md);
owning decision: docs/architecture.md Decision 14.

## Step 3 — The round loop (orchestrator)

Each orchestrator round = fan-out → ground truth → adversary → synthesize.

1. **Fan-out (explorers, method track, OPEN):** launch 1–2 `subagent_explorer`
   calls in one message (the explorer role; blank context). Diversify the portfolio
   (formulations, invariants, reductions, algebraic viewpoints, structural
   inductions, decompositions, embeddings, extremal arguments, computational
   sanity checks). Do not tell most of them the favored approach. Require
   concrete outputs: lemmas, equations, constructions, candidate methods with
   exact statements — reject status reports and "routine".
2. **Ground-truth track (semi-isolated):** launch `subagent_double_checker`
   calls that receive ONLY the problem statement and the simplified case, each
   assigned a different means (one symbolic derivation, one independent
   brute-force/special-case computation). Two independent calls are mandatory
   only when the claim is load-bearing (the whole study rests on it);
   otherwise one suffices — never one agent performing both "independent"
   derivations. They must not see each other's output or the explorers'
   drafts. Store the derivations in `derivations/`.
3. **Adversary:** one `subagent_adversary` reads BOTH tracks' outputs. It runs
   the check battery (below) and hunts counterexamples. A route is eliminated
   ONLY by a concrete failing case. It writes the audit report — and the
   report is the deliverable: brief it as ending in `VERDICT: PASS` or
   `VERDICT: NEEDS-EDITS`, and children deliver that verdict through the
   harness `report` tool before finishing (continuable children get it; the
   report wakes the orchestrator). If a child settles without the verdict
   line — reported or written — read its results JSON once, record the
   verdict, and do NOT re-dispatch for prose (hard-lessons L2). Freeze the
   audited artifact until the verdict lands (hash-bound verdicts); never edit
   a document under audit and never message an in-flight or settled agent
   (L3).
4. **Synthesize:** update `registry.json` (group by mathematical idea), mark
   BLOCKED routes with their exact gap, redirect over-crowded families, and
   either advance a stage or relaunch with redirection. On the SECOND
   consecutive NEEDS-EDITS for the same claim or section, the next round
   narrows the claim's declared scope or declares BLOCKED — never a third
   re-patch of the same mechanism (L1). Write `status` from verdicts, never
   before them (L4); orchestrator-produced numbers (generators, tables,
   verification scripts) get a second instrument like any agent output (L5).

**Stage order (each sub-problem passes only by its own success criterion):**

1. **Reference-case gate** — the check battery on the simplified cases.
   Passing it certifies the *implementation*, never the general claim.
2. **Generalization** — lift the validated method to the general case in the
   statement: state the general validity claim with ALL of its hypotheses, tag
   it with an evidence level, and analyze EVERY access/data model the statement
   assumes, concretely — what one query costs, what the method is allowed to
   assume about its inputs, and how each assumed quantity is actually obtained
   in the general case rather than read off the simplified one.
   *(Worked example, from a convex-sampling study: for a sublevel set
   {x : f(x) < a}, membership = one evaluation of f, separation = one
   subgradient, plus the exact per-step cost and how the well-rounded promise's
   r and R are obtained for general f. Your study's access models will differ —
   a portfolio study's are its data panel, rebalancing frequency, and cost
   model.)*
3. **Domain-scale certification** — run the full battery on at least one
   genuinely non-special instance whose ground truth was derived independently
   for this purpose. The instance must not be another member of the family the
   simplified cases already came from — a study whose reference cases are
   box/ball/simplex/ellipsoid must not PASS on box/ball/simplex/ellipsoid
   evidence alone, and one whose reference cases are diagonal covariances must
   not PASS on diagonal-covariance evidence alone.
4. **Audience consultation (research-complete gate)** — when stages 1–3 are
   done, the study enters the explicit `research-complete` state (visible in
   `study.json.status`). Research never down-shifts for an audience. A
   consulting subagent reads the study record + artifacts and drafts, per
   declared deliverable (paper / slides / web), an **audience spec**; the user
   accepts or edits it once. Fail closed on no answer (the checkpointed
   questionnaire waits, `deliverables.consultation_pending: true`). Full
   mechanics, dial-back (claim-driven invalidation only), and the two-tier
   enforcement: [references/deliverables.md](references/deliverables.md).
5. **Deliverables** — produce the declared artifacts (white paper
   `artifacts/paper/main.tex`, Beamer slides `artifacts/slides/main.tex`, and
   `artifacts/web/index.html` when required) by ASSEMBLING the validated
   records (registry, derivations, audits, battery results) and writing them
   against the confirmed audience specs — never by writing new claims. Then
   dispatch `subagent_document_adversary` (one call per deliverable) to audit
   each artifact for SELF-COMPLETENESS — every jargon term, symbol, and
   abbreviation it uses is defined — and commit its verdict as
   `audits/document-adversary-<name>.md` (name in `paper`, `slides`, `web`); a
   NEEDS-EDITS verdict is a blocking gap, capped at two passes per deliverable.
   Structure, the no-overclaim rule, bibliography, and the document-adversary
   gate: [references/deliverables.md](references/deliverables.md).
   `rq_check.py` verifies existence, structure, compilation, references,
   definition of used symbols, and that the paper does not overclaim the
   recorded evidence levels.

A study declares PASS only when the broad criterion is satisfied by stages
1–3 together, the audience consultation is answered, and the declared
stage-4 deliverables exist and satisfy their audience specs. A battery-only
PASS on special cases is BLOCKED, not PASS — record the exact missing stage
as the blockedReason.

**Proof and refutation tracks (parallel).** Do not assume an affirmative result
exists. For every load-bearing claim, run the refutation track alongside the
proof track: hunt a counterexample while someone proves the claim. A correct
outcome may be impossibility, non-identifiability, divergence, or a
counterexample. Record an explicit `unknown` outcome rather than forcing PASS.
Assign evidence levels (see lifecycle.md): falsification-surviving;
independently re-derived; certificate-checked; formally verified.

## The check battery (pre-implementation gate)

Run on the simplified cases before ANY numerical implementation. Details and
tolerances: [references/check-battery.md](references/check-battery.md). The
battery is a **reference-case sanity gate** — passing it does not establish
general validity; the staged validity case in check-battery.md does. Before
declaring PASS, run the meta-validator:

```sh
python3 <skill-dir>/scripts/rq_check.py --study <study-root> --out <study-root>/audits/rq-check.json
```

**`<skill-dir>` is the directory holding this SKILL.md** — resolve it once and
record it; it is NOT relative to the study, and `scripts/rq_check.py` on its own
resolves nowhere. The validator loads the JSON Schemas from `<skill-dir>/schemas/`,
so the schema and the checker cannot disagree.

It validates `study.json` / `registry.json` against those schemas, enforces the
coverage gate (a `generalization` sub-problem + a `domain-scale` sub-problem),
and refuses a PASS without the stage-3 general claim and stage-5 domain-scale
evidence (lifecycle.md "Validity stages"). A battery-only PASS on special cases
is refused.

**What it can and cannot do.** It checks that the evidence *exists, is
referenced, and is internally consistent* — non-empty stage outputs that resolve
on disk, a parsed passed route with an audit reference, a non-empty
`derivations/`, seeds and an N-grid and declared failure conditions **in the
audit record rather than in `study.json`**, tolerances in the audits that match
the study's, and deliverables that actually compile. It cannot judge whether the
mathematics is right; that remains the job of the battery, the ground-truth
track, and the adversary. Treat a green validator as "nothing is missing", never
as "the result is correct".

| Gate | Question | Instrument |
|---|---|---|
| A. Closed-form equality | Does the method reproduce the exactly derived answer? | symbolic + high-precision numeric (sympy, mpmath) |
| B. Exact invariants | Do the structural identities hold exactly? | symbolic arithmetic |
| C. Analytic bounds | Are derived bounds ever violated? | bound derivation + falsification search |
| D. Statistical hardening | Seeded reproducibility, distributional agreement, LLN | hypothesis, fixed seeds, N-grid |

Stochastic methods: **fixed seed + LLN** — for a grid of N, sampling error
against the analytic mean must shrink in standard-error units (≈ C/√N), not
monotonically. Seeded replay is required (D), not optional; exact bit-identity
across platforms is not portable (see check-battery.md).

For econ/finance/portfolio studies, the empirical gates in check-battery.md
(temporal train/test splits, leakage, survivorship, multiple-hypothesis,
costs/turnover, regime sensitivity) are mandatory, not optional.

## Off-grid toggle (OffGridThinker)

If the open method track produces no closed form / invariant / bound that
survives its own re-derivation after a bounded number of attempts, flip the
method track to **full Jin isolation**: no web, no prior context, no local
files, no one else's results — raw model intelligence plus compute tools only.
Do not assume an affirmative result exists — prove it or find a counterexample.

The toggle is a **different agent, not a different instruction**: call
`subagent_offgrid` — the OffGridThinker — instead of `subagent_explorer`. That
row (like `subagent_double_checker`) denies `web_search`, `web_fetch`, `skill`
and every delegation tool, so the isolation is enforced by the composition
rather than by asking an open role to pretend. The boundary is results, not
tools: OffGridThinker keeps the pinned compute lane (sympy/numpy/mpmath, Lean
checkers when provisioned) and loses the literature. Never re-use
`subagent_explorer` with "please ignore the web".

The only thing you may pass a blind role beyond the problem statement and its
simplified cases is the **verified-negatives list** from the literature lane,
provenance-stripped — never a source, never "this is open", never a settled
result. Full protocol: [references/protocol.md](references/protocol.md);
membrane: [references/literature.md](references/literature.md).

## Escalation

When a method's correctness hinges on an unproven claim (convexity of a set,
convergence of a scheme, correctness of a sampler, uniqueness of a
decomposition), settle it BEFORE implementing. The jacobian MCP lane
(`mcp__rigorquant-jacobian__math_find` / `math_run`) is **disabled by default**:
enable the `mcp-jacobian` row first. Provisioning is **approval-gated**, never
automatic:

- Lane tools absent → ask the user, then run
  `npx -y jacobian@0.12.0 upgrade`, verify with
  `npx -y jacobian@0.12.0 doctor --json`, retry.
- A lean call reports `TOOLCHAIN_RESOLUTION` or `MATHLIB_MANIFEST` → ask the
  user, then run `RQ_ALLOW_PROVISION=1 bash <this skill's
  dir>/scripts/provision-lean.sh` (idempotent; installs elan + pinned Lean
  toolchain + jacobian's Mathlib runtime; first run takes minutes — use a
  background job with a long timeout), then retry the call.
- While any install runs, fall back to an isolated proof subagent; record what
  was installed in the audit.

Triggers and the full approval-gated flow:
[references/escalation.md](references/escalation.md).

## Lifecycle

PASS → auto-implement + proceed. BLOCKED (same exact gap, 3 consecutive
rounds) → deliver strongest derivation + exact gap. BUDGET (3 orchestrator
rounds) → checkpoint + report. Schema and rules:
[references/lifecycle.md](references/lifecycle.md).

## Anti-patterns (never do)

- `subagent_fork` for track work (it shares the parent conversation).
- The ground-truth track reading the explorers' drafts (self-certification).
- One ground-truth agent performing both "independent" derivations.
- Eliminating a route on style/vibes instead of a counterexample.
- Accepting "matches at fixed parameters" as validity.
- Passing the reference-case sanity gate as general validity (hard gate:
  BLOCKED/UNKNOWN, never PASS — the battery certifies the implementation;
  stages 2–3 of the stage order certify the broad claim).
- Writing the paper or slides DURING the search (they are stage-4 PASS
  artifacts assembled from validated records; prose written mid-search anchors
  the method track and burns budget rounds).
- Partial-progress exits ("best effort" summaries are not a PASS).
- Unseeded stochastic claims.
- Handwaving an unproven load-bearing claim instead of escalating.
- Auto-installing remote toolchains without user approval.
- A third re-patch of the same claim's mechanism instead of narrowing its
  scope (hard-lessons L1: after two NEEDS-EDITS, narrow or BLOCKED).
- Re-dispatching a settled agent for prose when its structured verdict
  already landed (L2); waiting on a report instead of reading the verdict JSON
  once.
- Editing a document under adversarial audit, or messaging an in-flight or
  settled agent mid-audit (L3) — freeze on audit, hash-bound verdicts.
- Certifying your own repair in `status` before an independent verdict lands
  (L4); status prose that no verdict file or frozen hash backs.
- Trusting orchestrator-produced tables/scripts/status without a second
  instrument (L5) — orchestrator arithmetic is audited like agent output.
- Editing load-bearing text (claims, audience sentences) without recording the
  new digest and reopening certification (L6).
