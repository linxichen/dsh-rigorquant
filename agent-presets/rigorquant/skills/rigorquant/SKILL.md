---
name: rigorquant
description: >
  Operating procedure for long-running empirical/computational mathematics
  research on DeepSeek Harness: context-isolated multi-agent exploration in the
  style of Jin's Crouzeix run and Tao's collaborative projects, dual-track
  ground-truth derivation, adversarial counterexample-only audit, a four-part
  pre-implementation check battery (closed-form equality, exact invariants,
  analytic bounds, statistical hardening), fixed-seed LLN conventions, a
  jacobian/Lean escalation lane, and the PASS/BLOCKED/BUDGET lifecycle. Load
  when the user asks for rigorous quantitative research, method validation
  before implementation, long unattended numerical work, or says "rigorquant".
---

# RigorQuant operating procedure

You are running an **empirical and computational** mathematics research
framework: economics, finance, portfolio construction/optimization, simulation,
computational econ/finance. The goal is a method whose **mathematical validity
is established on simplified/special cases before numerical implementation** —
not a theorem for its own sake. When correctness hinges on an unproven claim,
escalate to proof-grade verification first (see escalation.md).

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
2. Choose simplified/special cases per sub-problem: the smallest
   hand-computable settings that still exercise the method (2 assets, 2–3
   dimensions, low N).
3. Record the **seed** for every stochastic run in `study.json`.

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
├── interim/            # ALL scratch work — never committed:
│   ├── explorer-reports/
│   ├── gt-scripts/
│   └── tmp/
├── .lock               # transient study lock naming the live run (see below)
└── .gitignore          # contains: interim/  (and .lock)
```

Everything except `interim/` and the transient `.lock` is meant to be committed
to git. Internal references recorded in registry.json / journal.md / audits are
study-root-relative.

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

## Step 3 — The round loop (orchestrator)

Each orchestrator round = fan-out → ground truth → adversary → synthesize.

1. **Fan-out (explorers, method track, OPEN):** launch 2–4 `subagent` calls in
   one message (the explorer role; blank context). Diversify the portfolio
   (formulations, invariants, reductions, algebraic viewpoints, structural
   inductions, decompositions, embeddings, extremal arguments, computational
   sanity checks). Do not tell most of them the favored approach. Require
   concrete outputs: lemmas, equations, constructions, candidate methods with
   exact statements — reject status reports and "routine".
2. **Ground-truth track (semi-isolated):** launch **two separate**
   `subagent_ground_truth` calls, each receiving ONLY the problem statement and
   the simplified case, and each assigned a different means (one symbolic
   derivation, one independent brute-force/special-case computation). They must
   not see each other's output or the explorers' drafts. Store both derivations
   in `derivations/`.
3. **Adversary:** one `subagent_adversary` reads BOTH tracks' outputs. It runs
   the check battery (below) and hunts counterexamples. A route is eliminated
   ONLY by a concrete failing case. It writes the audit report.
4. **Synthesize:** update `registry.json` (group by mathematical idea), mark
   BLOCKED routes with their exact gap, redirect over-crowded families, and
   either PASS (implement + next stage) or relaunch with redirection.

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
declaring PASS, run the meta-validator
(`python3 scripts/rq_check.py --study <study-root>`): it validates the state
files, checks evidence completeness and falsifiability, and refuses a PASS
without mandatory evidence.

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

## Novelty toggle (isolation)

If the open method track produces no closed form / invariant / bound that
survives its own re-derivation after a bounded number of attempts, flip the
method track to **full Jin isolation**: no web, no prior context, no local
files; work from axioms and computation. Do not assume an affirmative result
exists — prove it or find a counterexample. Full protocol:
[references/protocol.md](references/protocol.md).

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
rounds) → deliver strongest derivation + exact gap. BUDGET (5 orchestrator
rounds) → checkpoint + report. Schema and rules:
[references/lifecycle.md](references/lifecycle.md).

## Anti-patterns (never do)

- `subagent_fork` for track work (it shares the parent conversation).
- The ground-truth track reading the explorers' drafts (self-certification).
- One ground-truth agent performing both "independent" derivations.
- Eliminating a route on style/vibes instead of a counterexample.
- Accepting "matches at fixed parameters" as validity.
- Passing the reference-case sanity gate as general validity.
- Partial-progress exits ("best effort" summaries are not a PASS).
- Unseeded stochastic claims.
- Handwaving an unproven load-bearing claim instead of escalating.
- Auto-installing remote toolchains without user approval.
