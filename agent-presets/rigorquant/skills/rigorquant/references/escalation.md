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
3. Absent (first escalation on this machine) → AUTO-INSTALL, no prompt:
   run `npx -y jacobian upgrade`, verify with `npx -y jacobian doctor --json`
   (expect handshake ok and the math.find / math.run tools), then retry.
   (`jacobian setup` is NOT the right command for DSH: it refuses without one
   of jacobian's native client targets — claude/cursor/opencode/codex/gemini —
   and the preset's mcp-jacobian row already plays that role.)
4. Lean lane error → AUTO-PROVISION, no prompt: if a lean capability call
   (`lean.statement.propose/compare`, `lean.proof_state.inspect`,
   `lean.check`) returns `TOOLCHAIN_RESOLUTION` or `MATHLIB_MANIFEST`, run
   `bash <this skill's dir>/scripts/provision-lean.sh` (idempotent; installs
   elan, the pinned toolchain v4.31.0, persists ~/.elan/bin on PATH, and
   builds jacobian's pinned Mathlib runtime; first run takes minutes — launch
   it as a background job with a long timeout and keep working). Then retry
   the lean call. The preset row already appends ~/.elan/bin to the lane's
   child PATH, so the toolchain resolves at call time with no dsh restart.
5. Never block the method work on the lane: while any install runs, fall back
   to Lane 2 (isolated proof subagent) and record in the audit what was
   installed and that it succeeded.

Caveats: jacobian is pre-stable; its catalog decides what it can check — read
the catalog (math.find / `operation://catalog`) before claiming coverage.
The installed Lean lane exposes `lean.statement.propose`,
`lean.statement.compare`, and `lean.proof_state.inspect` (core Lean, no
Mathlib); the full machine-check lane is `lean.check`, which additionally
needs the pinned Mathlib runtime (elan toolchain + lake build — provisioned by
mcp/jacobian.md). See mcp/jacobian.md in the repo root for details.

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
high; do not default to it. Jacobian's `lean.check` lane is the lower-friction entry point; the
provisioning script (scripts/provision-lean.sh) supplies the pinned Mathlib
runtime automatically (see Lane 1 step 4).
