# Lifecycle, registry, and termination

## Terminal states

- **PASS** — the check battery passes on the simplified cases. Auto-implement
  the method (write it into the target artifact/codebase with its audit trail
  reference), mark the sub-problem PASS in task.json, and proceed to the next
  stage/sub-problem. No user confirmation required by default.
- **BLOCKED** — the SAME exact gap persisted for 3 consecutive orchestrator
  rounds. Stop the sub-problem: deliver the strongest rigorously proved
  derivation and the exact remaining gap (Jin's terminal report). Do not pad
  it with partial results or "why it is hard".
- **BUDGET** — 5 orchestrator rounds reached without PASS or a stable block.
  Checkpoint registry.json + journal.md, deliver a status report, halt.
  (No API-cost ceiling is configured yet; the round cap is the budget.)

## registry.json schema

```json
{
  "task": "<problem id>",
  "subproblem": "<id>",
  "rounds": 0,
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
          "outputs": ["paths to concrete derivations/artifacts"]
        }
      ]
    }
  ]
}
```

Rules: group by mathematical idea, never by wording; a route with a
theorem-strength missing lemma is `blocked`, not `active`; `dead` requires a
counterexample reference; `passed` requires an audit reference.

## Round accounting

Each orchestrator round = one full fan-out → ground-truth → adversary →
synthesize cycle (Step 3 of SKILL.md). Increment `rounds` on synthesis.
BLOCKED counting: consecutive rounds where the same `blockedReason` string
appears for the sub-problem; any materially new mechanism resets the count.

## Goal wiring

`create_goal` with the sub-problem objective; `max_goal_rounds` = remaining
budget; `update_goal complete` on PASS; `update_goal blocked` (with the
concrete gap as blocked_reason) on BLOCKED after the 3-round rule.
