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
  "broad_criterion": "the ORIGINAL broad claim a PASS must deliver, verbatim — never re-scoped to the simplified cases",
  "success_criterion": "summary of the broad criterion plus the stage evidence required",
  "subproblems": [
    { "id": "SPn", "name": "...", "status": "known|novel",
      "stage": "reference-case|generalization|domain-scale",
      "success_criterion": "...", "evidence_level": "..." }
  ],
  "validity_stages": {
    "stage3_general_claim": { "claim": "...", "evidence_level": "...", "outputs": ["..."] },
    "stage5_domain_scale": { "instance": "...", "outputs": ["..."] }
  },
  "deliverables": {
    "paper": "required",
    "slides": "required | not-required:<reason recorded at intake>",
    "web": "optional | required",
    "consultation_pending": false,
    "consultation_record": { "date": "...", "agent": "...", "artifacts_read": ["..."] },
    "last_accepted": { "paper": {...}, "slides": {...}, "web": {...} },
    "audience": {
      "paper": { "role": "...", "level": "...", "sentence": "...",
                 "assume_known": ["..."], "must_define": ["B(", "poly", "O*"],
                 "avoid": ["..."], "depth": "...", "format": "..." },
      "slides": { "...": "..." },
      "web": { "...": "..." }
    }
  },
  "simplified_cases": ["..."],
  "seeds": { "task_seed": 0, "convention": "per-run seed = task_seed + run_index" },
  "tolerances": {
    "deterministic": { "abs": "...", "rel": "..." },
    "stochastic": { "se_units": 3, "confidence": 0.95, "lln_grid": [1000, 10000, 100000] }
  },
  "budget": { "max_orchestrator_rounds": 5, "max_cost_usd": null, "max_wall_minutes": null },
  "status": "per-sub-problem status + current round; a PASS is claimed ONLY when this string begins with the token PASS"
}
```

The machine-readable version of this schema is
`<skill-dir>/schemas/study.schema.json`, and it is the file `rq_check.py`
actually loads — the JSON above is its human-facing mirror. If the two ever
disagree, the schema file wins and `tests/` fails.

Notes on the schema:

- **PASS claim detection.** `status` is free text with one rule: it claims a
  PASS only if it *begins* with `PASS`. `"round 2: SP3 active, no PASS yet"` is
  not a claim and does not trip the PASS gates. A status that begins with PASS
  but is also marked reopened (e.g. "PASS reopened") is likewise not a claim:
  the study re-entered active work, so the PASS gates do not fire.
- `mode` is the clean enum `"repo-root" | "multi-study"` (never a literal path
  or a `<...>` placeholder).
- `env_lane` is an **absolute** path or the documented anchor
  `$DSH_HOME/share/rigorquant/env`. It is **not** persisted at intake — Step 2
  resolves and adds it.
- `tolerances` splits deterministic and stochastic acceptance (see
  check-battery.md): deterministic methods use condition-aware absolute and
  relative tolerances; stochastic methods agree in standard-error /
  confidence-interval units, never a universal `1e-12`.
- **Deliverables rule:** `paper` is always `"required"`; `slides` is
  `"required"` unless the intake records a reason for `"not-required"`;
  `web` is `"optional"` unless the study will produce interactive/visual
  artifacts (widgets, movies, dashboards), in which case it is `"required"`.
  The artifacts are produced at PASS only, assembled from validated records
  (see references/deliverables.md); `rq_check.py` enforces the declaration at
  intake and existence + structure + no-overclaim at PASS.
- **Coverage rule:** the union of sub-problem stages must cover the original
  statement. Every general question requires at least one `generalization`
  sub-problem (the broad claim is its criterion) and at least one
  `domain-scale` sub-problem (certification on a genuinely non-special
  instance). A study whose simplified cases are box/ball/simplex/ellipsoid (or
  a portfolio study's diagonal covariance) must not PASS on evidence from those
  same special bodies alone; rq_check.py refuses an instance that names only
  such a body (box/ball/simplex/ellipsoid/diagonal) or restates a simplified
  case.
  `<skill-dir>/scripts/rq_check.py --study <study-root>` enforces this at intake
  and at PASS, and refuses a PASS unless `validity_stages` stage-3 and stage-5
  each record non-empty `outputs` that resolve to files that exist and stay inside the study root (absolute or
  ".."-escaping paths, and the validator's own report, are refused).

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

Stages 3 and 5 are **mandatory for a broad claim**, not optional polish:
stage 3 = the general validity claim with all hypotheses and an evidence
level; stage 5 = the full battery on a genuinely non-special instance. Record
them in `study.json` `validity_stages`. A PASS recorded without stage-3 and
stage-5 evidence is invalid, and the meta-validator
(`python3 <skill-dir>/scripts/rq_check.py --study <study-root>`) refuses it.

## Terminal states

- **research-complete** — an intermediate, explicit state reached when every
  subproblem route is `passed`, `validity_stages` stage-3 + stage-5 evidence
  are recorded, and `rq_check.py` accepts the study with deliverable gates
  suppressed. It is visible in `study.json.status`. At this point the
  **one-time audience consultation** (references/deliverables.md) must fire
  before any deliverable is crafted; until it is answered,
  `deliverables.consultation_pending` is `true` and a PASS is refused. The
  user may dial the study back to `active` from this (or any later) state;
  dial-back sets `consultation_pending: true`, retains the audience spec as
  `deliverables.last_accepted`, and does **not** mark verified artifacts
  stale — invalidation is claim-driven only (an artifact loses validity when
  new research changes a load-bearing claim it asserts, via the "superseded"
  mechanism), never merely because a dial-back happened.
- **PASS** — the staged validity case (above) passes for the sub-problem. A
  study-level PASS additionally requires the `validity_stages` stage-3 and
  stage-5 evidence recorded, the declared `deliverables` produced
  (`artifacts/paper/main.tex`; `artifacts/slides/main.tex` when required;
  `artifacts/web/index.html` when required — assembled from validated records
  per references/deliverables.md), the **audience consultation completed**
  (`consultation_pending` false; `deliverables.audience.<name>` present for
  every declared deliverable), AND the meta-validator to accept it (run
  `python3 <skill-dir>/scripts/rq_check.py --study <study-root>` before declaring). A
  battery-only PASS on special cases is not a study PASS.
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

Run the meta-validator before declaring any PASS, writing its report into the
audit trail:

```sh
python3 <skill-dir>/scripts/rq_check.py --study <study-root> --out <study-root>/audits/rq-check.json
```

`<skill-dir>` is the directory containing SKILL.md (see SKILL.md "the check
battery"). It validates `study.json` / `registry.json` against the schemas in
`<skill-dir>/schemas/`, checks evidence completeness and falsifiability against
the **audit record** (never against `study.json` itself), rejects a missing
N-grid, verifies every declared SHA-256, and refuses a PASS without mandatory
evidence. With `--out` it writes a report carrying the result, every problem
found, the state-file hashes, and an environment manifest; ship that report
alongside the audit.

## Goal wiring

Create the goal tool objective **once, for the whole task** (`create_goal`);
`max_goal_rounds` = remaining budget. There is no per-sub-problem goal — the
goal service supports one current same-session goal, and creating another
before the first is `complete` raises. Represent sub-problems in `registry.json`
/ `study.json` state only. `update_goal complete` on PASS; `update_goal blocked`
(with the concrete gap as blocked_reason) on BLOCKED after the 3-round rule.
