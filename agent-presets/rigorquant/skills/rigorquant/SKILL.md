---
name: rigorquant
description: >
  Operating procedure for unattended, long-running empirical/computational
  mathematics research on DeepSeek Harness: walled multi-agent exploration in
  the style of Jin's Crouzeix run and Tao's collaborative projects, dual-track
  ground-truth derivation, adversarial counterexample-only audit, a four-part
  pre-implementation check battery (closed-form equality, exact invariants,
  analytic bounds, statistical hardening), fixed-seed LLN conventions, a
  jacobian/Lean escalation lane, and the PASS/BLOCKED/BUDGET lifecycle. Load
  when the user asks for rigorous quantitative research, method validation
  before implementation, long unattended numerical work, or says "rigorquant".
---

# RigorQuant operating procedure

You are running an unattended research framework for **empirical and
computational** mathematics: economics, finance, portfolio
construction/optimization, simulation, computational econ/finance. The goal is
a method whose **mathematical validity is established on simplified/special
cases before numerical implementation** — not a theorem for its own sake. When
correctness hinges on an unproven claim, escalate to proof-grade verification
first (see escalation.md).

If this is the first message of a rigorquant task, run Step 0–2 in order, then
enter the round loop.

## Step 0 — Intake

1. Restate the problem; split it into sub-problems, each with a crisp "valid
   method" success criterion. Mark each sub-problem `known` (an analytical
   result likely exists) or `novel` (no known closed form) — a hint only; the
   orchestrator may override by detection (see protocol.md).
2. Choose simplified/special cases per sub-problem: the smallest
   hand-computable settings that still exercise the method (2 assets, 2–3
   dimensions, low N).
3. Record the **seed** for every stochastic run in `task.json`.

## Step 1 — Workspace setup

```
.rigorquant/
├── task.json            # problem statement, sub-problems, seeds, env path
├── registry.json        # approach-family registry (see lifecycle.md schema)
├── derivations/         # ground-truth derivations, two independent per claim
├── audits/              # adversary reports + check-battery results
├── artifacts/           # PASS: final validated method + audit trail
└── journal.md           # round log (append every round)
```

Create the goal tool objective for the whole task (`create_goal`). Every
round the orchestrator returns; the goal-round driver relaunches it.

## Step 2 — Locate the compute lane

The pinned uv lane lives in the dsh-rigorquant checkout (`env/pyproject.toml`,
see env/README.md in the repo). Run subagent code with
`uv run --project <lane> python ...`. If the lane is not found, `uv sync` it
once and record the path in `task.json`. Never let subagents `pip install`
into the ambient interpreter: reproducibility is a gate (D).

## Step 3 — The round loop (orchestrator)

Each orchestrator round = fan-out → ground truth → adversary → synthesize.

1. **Fan-out (explorers, method track, OPEN):** launch 2–4 `subagent` calls in
   one message (blank context; NOT `subagent_fork`). Diversify the portfolio
   (formulations, invariants, reductions, algebraic viewpoints, structural
   inductions, decompositions, embeddings, extremal arguments, computational
   sanity checks). Do not tell most of them the favored approach. Require
   concrete outputs: lemmas, equations, constructions, candidate methods with
   exact statements — reject status reports and "routine".
2. **Ground-truth track (semi-isolated):** one `subagent` receives ONLY the
   problem statement and the simplified case. It re-derives the closed form,
   invariants, and bounds **twice, by different means** (symbolic derivation
   plus independent brute-force/special-case computation). It may know standard
   results but must re-derive, not cite-and-trust. Store both derivations in
   `derivations/`.
3. **Adversary:** one `subagent` reads BOTH tracks' outputs. It runs the check
   battery (below) and hunts counterexamples. A route is eliminated ONLY by a
   concrete failing case. It writes the audit report.
4. **Synthesize:** update `registry.json` (group by mathematical idea), mark
   BLOCKED routes with their exact gap, redirect over-crowded families, and
   either PASS (implement + next stage) or relaunch with redirection.

## The check battery (pre-implementation gate)

Run on the simplified cases before ANY numerical implementation. Details and
tolerances: [references/check-battery.md](references/check-battery.md).

| Gate | Question | Instrument |
|---|---|---|
| A. Closed-form equality | Does the method reproduce the exactly derived answer? | symbolic + high-precision numeric (sympy, mpmath) |
| B. Exact invariants | Do the structural identities hold exactly? | symbolic arithmetic |
| C. Analytic bounds | Are derived bounds ever violated? | bound derivation + falsification search |
| D. Statistical hardening | Seeded reproducibility, distributional agreement, LLN | hypothesis, fixed seeds, N-grid |

Stochastic methods: **fixed seed + LLN** — for a grid of N, sampling error
against the analytic mean must shrink (≈ C/√N). Bit-identical replay for a
given seed is required (D), not optional.

## Novelty toggle (isolation)

If the open method track produces no closed form / invariant / bound that
survives its own re-derivation after a bounded number of attempts, flip the
method track to **full Jin isolation**: no web, no prior context, no local
files; "assume a complete affirmative result exists"; work from axioms and
computation until one is found. Full protocol:
[references/protocol.md](references/protocol.md).

## Escalation

When a method's correctness hinges on an unproven claim (convexity of a set,
convergence of a scheme, correctness of a sampler, uniqueness of a
decomposition), settle it BEFORE implementing. The jacobian MCP lane
(`mcp__jacobian__math_find` / `math_run`) is ON by default and
self-provisions. Missing pieces are AUTO-INSTALLED, never prompted:

- Lane tools absent → run `npx -y jacobian upgrade` yourself, verify with
  `npx -y jacobian doctor --json`, retry.
- A lean call reports `TOOLCHAIN_RESOLUTION` or `MATHLIB_MANIFEST` → run
  `bash <this skill's dir>/scripts/provision-lean.sh` (idempotent; installs
  elan + pinned Lean toolchain + jacobian's Mathlib runtime; first run takes
  minutes — use a background job with a long timeout), then retry the call.
- While any install runs, fall back to an isolated proof subagent; record
  what was installed in the audit.

Triggers and the full automatic flow:
[references/escalation.md](references/escalation.md).

## Lifecycle

PASS → auto-implement + proceed. BLOCKED (same exact gap, 3 consecutive
rounds) → deliver strongest derivation + exact gap. BUDGET (5 orchestrator
rounds) → checkpoint + report. Schema and rules:
[references/lifecycle.md](references/lifecycle.md).

## Anti-patterns (never do)

- `subagent_fork` for track work (breaks the wall).
- The ground-truth track reading the explorers' drafts (self-certification).
- Eliminating a route on style/vibes instead of a counterexample.
- Accepting "matches at fixed parameters" as validity (that is Jin's
  "computational verification through fixed parameters is insufficient").
- Partial-progress exits ("best effort" summaries are not a PASS).
- Unseeded stochastic claims.
- Handwaving an unproven load-bearing claim instead of escalating.
