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

The lane is ON by default and self-provisions: the preset's `mcp-jacobian` row
spawns `npx -y jacobian mcp` (the package runs no lifecycle scripts; npx
caches it on first spawn). The model sees `mcp__jacobian__math_find`
(discover typed operations) and `mcp__jacobian__math_run` (execute one).

Automatic escalation flow when a trigger fires:

1. Check whether the `mcp__jacobian__*` tools are in the tool catalog.
2. Present → use them directly (exact symbolic results, SAT/SMT with proof
   artifacts, convexity/feasibility certificates, verifier lanes —
   producer ≠ checker).
3. Absent (first escalation on this machine) → OFFER the user the one-time
   persistent install: "May I run `npx jacobian setup`? It installs the
   launcher and its pinned Python runtime (~160 MB) once." On approval run it,
   then verify with `jacobian doctor`. The preset's own config already wires
   the lane — nothing to hand-edit. HMR picks the lane up after a composition
   reload; if the tools are still absent, note that a session restart brings
   them in.
4. Never block the method work on the lane: while unavailable, fall back to
   Lane 2 (isolated proof subagent) and record that in the audit.

Caveats: jacobian is pre-stable; its catalog decides what it can check — read
`operation://catalog` before claiming coverage. See mcp/jacobian.md in the
repo root for details.

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
