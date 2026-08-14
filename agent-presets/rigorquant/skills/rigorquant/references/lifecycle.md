# Lifecycle, registry, and termination

## study.json schema

Created at intake (SKILL.md Step 1); internal references recorded anywhere in
a study (registry.json, journal.md, audits) are study-root-relative.

```json
{
  "slug": "kebab-case study id",
  "title": "one-line title",
  "mode": "repo-root | multi-study",
  "repo_root": "<absolute path resolved at intake>",
  "env_lane": "<absolute path to the pinned uv lane — added by Step 2>",
  "task_id": "<problem id>",
  "created": "YYYY-MM-DD",
  "statement": "the problem statement",
  "success_criterion": "what a validated method must deliver",
  "subproblems": [
    { "id": "SPn", "name": "...", "status": "known|novel",
      "success_criterion": "...", "evidence_level": "..." }
  ],
  "simplified_cases": ["..."],
  "seeds": { "task_seed": 0, "convention": "per-run seed = task_seed + run_index" },
  "tolerances": {
    "deterministic": { "abs": "...", "rel": "..." },
    "stochastic": { "se_units": 3, "confidence": 0.95, "lln_grid": [1000, 10000, 100000] }
  },
  "budget": { "max_orchestrator_rounds": 5, "max_cost_usd": null, "max_wall_minutes": null },
  "status": "per-sub-problem status + current round"
}
```

Notes on the schema:

- `mode` is the clean enum `"repo-root" | "multi-study"` (never a literal path
  or a `<...>` placeholder).
- `env_lane` is an **absolute** path or the documented anchor
  `$DSH_HOME/share/rigorquant/env`. It is **not** persisted at intake — Step 2
  resolves and adds it.
- `tolerances` splits deterministic and stochastic acceptance (see
  check-battery.md): deterministic methods use condition-aware absolute and
  relative tolerances; stochastic methods agree in standard-error /
  confidence-interval units, never a universal `1e-12`.

## registry.json schema (subproblems map)

```json
{
  "task": "<problem id>",
  "rounds": 0,
  "subproblems": {
    "SP1": {
      "status": "active | blocked | passed | dead | unknown",
      "blockedReason": "exact remaining gap (only when blocked)",
      "blockedRounds": 0,
      "evidence_level": "falsification-surviving | independently re-derived | certificate-checked | formally verified",
      "families": [
        {
          "familyId": "kebab-case idea name",
          "idea": "one sentence: the mathematical mechanism",
          "routes": [
            {
              "routeId": "kebab-case",
              "status": "active | blocked | dead | passed",
              "blockedReason": "exact remaining gap (only when blocked)",
              "mechanism": "what changed when reopened",
              "outputs": ["study-root-relative paths to concrete derivations/artifacts"]
            }
          ]
        }
      ]
    }
  }
}
```

Rules: key the map by sub-problem id (`SPn`) so each sub-problem keeps its own
`blockedReason` and `blockedRounds` counter — a synthesis that alternates
sub-problems must not overwrite another's state. Group families by mathematical
idea, never by wording; a route with a theorem-strength missing lemma is
`blocked`, not `active`; `dead` requires a counterexample reference; `passed`
requires an audit reference.

## Evidence levels

Tag every load-bearing claim with one of:

- **falsification-surviving** — the claim survived the adversary and the check
  battery.
- **independently re-derived** — two independent ground-truth derivations
  agree.
- **certificate-checked** — a machine-checked certificate (SAT/SMT/prover
  artifact, jacobian `verify`) establishes the claim.
- **formally verified** — a Lean proof with a recorded axiom audit establishes
  it.

Only certificate-checked or formally-verified claims conclusively settle
load-bearing claims; the first two are strong evidence, not settlement.

## Validity stages

PASS is defined against the check battery, which is a **reference-case sanity
gate** — passing it does not establish general validity. Establish validity in
stages:

1. Specification, assumptions, and applicability domain.
2. Independent reference-case oracle (the battery's A/B targets).
3. General proof, certificate, or precisely bounded validity claim.
4. Numerical stability, conditioning, residual, and complexity analysis.
5. Domain-scale stress testing.
6. Empirical or out-of-sample validation where applicable.

Call the battery a sanity gate unless stages 3–6 are also satisfied.

## Terminal states

- **PASS** — the staged validity case (above) passes for the sub-problem.
  Auto-implementation is allowed only under a safety protocol: create a branch
  or worktree, declare a **frozen write scope** (only the target artifact
  files), run the target's tests, and keep a rollback path (the pre-change
  commit). Never write into an arbitrary target repository without user
  confirmation; unattended writes are allowed only into the study's own
  `artifacts/`. Then mark the sub-problem PASS and proceed.
- **BLOCKED** — the SAME exact gap persisted for 3 consecutive orchestrator
  rounds (tracked per sub-problem in `registry.json` `blockedRounds`). Stop the
  sub-problem: deliver the strongest rigorously proved derivation and the exact
  remaining gap (Jin's terminal report). Do not pad it with partial results or
  "why it is hard".
- **UNKNOWN** — the refutation track found no counterexample and the proof
  track found no proof (or the correct answer is impossibility /
  non-identifiability / divergence). Record it as `unknown`; do not relabel it
  PASS or BLOCKED.
- **BUDGET** — 5 orchestrator rounds reached without PASS or a stable block.
  Checkpoint registry.json + journal.md, deliver a status report, halt. Budget
  fields (`max_cost_usd`, `max_wall_minutes`) may be set to impose limits;
  unset means unbounded.

## Round accounting

Each orchestrator round = one full fan-out → ground-truth → adversary →
synthesize cycle (Step 3 of SKILL.md). Increment `rounds` on synthesis.
BLOCKED counting is per sub-problem: consecutive rounds where the same
`blockedReason` appears for that `SPn`; any materially new mechanism resets its
`blockedRounds`.

## Provenance and reports

Every report, script, and summary must be hashable and auditable:

- Store the generating script path and its SHA-256 in every report.
- Hash inputs, code, outputs, and an environment manifest (Python version,
  OS/architecture, BLAS/device backend, JAX precision flags, solver status,
  every random stream including Hypothesis).
- Make reports immutable after the round completes.
- Generate the journal summary mechanically from the audit records; reject a
  summary that does not match its referenced artifacts.

Run `python3 scripts/rq_check.py --study <study-root>` before declaring any
PASS. It validates `study.json` / `registry.json`, checks evidence completeness
and falsifiability, rejects a missing N-grid, hashes the inputs, and refuses a
PASS without mandatory evidence. Ship the report alongside the audit.

## Goal wiring

Create the goal tool objective **once, for the whole task** (`create_goal`);
`max_goal_rounds` = remaining budget. There is no per-sub-problem goal — the
goal service supports one current same-session goal, and creating another
before the first is `complete` raises. Represent sub-problems in `registry.json`
/ `study.json` state only. `update_goal complete` on PASS; `update_goal blocked`
(with the concrete gap as blocked_reason) on BLOCKED after the 3-round rule.
