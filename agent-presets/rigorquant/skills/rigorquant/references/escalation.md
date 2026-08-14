# Escalation: when a claim must be settled before implementing

Trigger: the method's correctness HINGES on an unproven claim. Examples:
- "This feasible set is convex" (the optimizer's certificate depends on it).
- "This iterative scheme converges to the true solution" (not just: it
  descended for 100 iterations).
- "This MCMC kernel has the target as its invariant distribution."
- "This decomposition/attribution is unique" or "is exactly linear".

Non-triggers (falsification lane suffices): parameter sensitivity, finite-
sample quality, tuning. Do not escalate everything — the default gate is the
check battery; escalation is for load-bearing unproven claims.

## Lane 1 — jacobian MCP (exact computation + independent verification)

Enable the `mcp-jacobian` row in agent.cordis.yml after `npx jacobian setup`.
Tools: `mcp__jacobian__math_find` (discover typed operations) and
`mcp__jacobian__math_run` (execute one). Use for: exact symbolic results,
SAT/SMT with proof artifacts, convexity/feasibility certificates, and its
verifier lanes (producer ≠ checker). Caveats: v0.11.0 is pre-stable; its
catalog decides what it can check — read `operation://catalog` before
claiming coverage. See mcp/jacobian.md in the repo root for wiring.

## Lane 2 — isolated proof subagent (full Jin protocol)

When jacobian lacks the operation: launch ONE `subagent` with the Jin prompt
(protocol.md), isolated (no web/context), told to assume an affirmative
result exists and to return a complete derivation of the claim or its exact
gap. The claim is settled only when the derivation survives the adversary
(concrete outputs, no "routine").

## Lane 3 — Lean (only for proof-critical claims)

Jin's own gate: Lean 4 + pinned Mathlib, `lake build` + axiom audit, trust
boundary `propext`/`Classical.choice`/`Quot.sound` only, no `sorry`/`admit`.
Use only when a fully machine-checked proof is genuinely required (e.g. a
novel analytical result you will publish or build a product on). Cost is
high; do not default to it. Jacobian's `lean.check` lane, when available in
its catalog, is the lower-friction entry point.
