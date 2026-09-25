# Escalation: when a claim must be settled before implementing

Trigger: the method's correctness HINGES on an unproven claim. Examples:
- "This feasible set is convex" (the optimizer's certificate depends on it).
- "This iterative scheme converges to the true solution" (not just: it
  descended for 100 iterations).
- "This MCMC kernel has the target as its invariant distribution."
- "This decomposition/attribution is unique" or "is exactly linear".

Non-triggers (the check battery suffices): parameter sensitivity, finite-
sample quality, tuning. Do not escalate everything — the default gate is the
check battery; escalation is for load-bearing unproven claims.

## Lane 1 — jacobian MCP (exact computation + independent verification)

The lane is not in the preset. You mount it at runtime with the `rq_escalate`
tool, which starts a **pinned** launcher (`npx -y jacobian@0.12.0 mcp`) in the
target agent's scope. On that agent's next request it sees the
`mcp__rigorquant-jacobian__*` tools: `math_find` (discover typed operations)
and `math_run` (execute one). The lane stays mounted until the session ends;
calling `rq_escalate` again for the same agent is a no-op.

Escalation flow when a trigger fires:

1. Call `rq_escalate({})` **without asking the user** whenever a claim meets
   the trigger. To give the lane to a running teammate instead (a
   DoubleChecker settling the claim, say), call
   `rq_escalate({ teammate: "<name>" })` before it needs the tools. Teammates
   cannot call `rq_escalate` themselves.
2. Record the escalation in `journal.md` as it opens and as it closes, one
   line each: `escalation open: <claim>` and
   `escalation closed: <claim> — <verdict>`.
3. Mounted → use the tools directly (exact symbolic results, SAT/SMT with
   proof artifacts, convexity/feasibility certificates, verifier lanes —
   producer ≠ checker).
4. `rq_escalate` returns an error (jacobian cannot start: first escalation on
   this machine) → **ASK the user**, then install: run
   `npx -y jacobian@0.12.0 upgrade`, verify with
   `npx -y jacobian@0.12.0 doctor --json` (expect handshake ok and the
   math.find / math.run tools), then call `rq_escalate` again. (`jacobian
   setup` is NOT the right command for DSH: it refuses without one of
   jacobian's native client targets — claude/cursor/opencode/codex/gemini —
   and `rq_escalate` already plays that role.)
5. Lean lane error → **ASK the user**, then provision: if a lean capability
   call (`lean.statement.propose/compare`, `lean.proof_state.inspect`,
   `lean.check`) returns `TOOLCHAIN_RESOLUTION` or `MATHLIB_MANIFEST`, run
   `RQ_ALLOW_PROVISION=1 bash <this skill's dir>/scripts/provision-lean.sh`
   (idempotent; installs elan, the pinned toolchain v4.31.0, and builds
   jacobian's pinned Mathlib runtime; it does not mutate shell rc files unless
   `RQ_MODIFY_SHELL_RC=1`; first run takes minutes — launch it as a background
   job with a long timeout and keep working). Then retry the lean call. The
   lane already appends ~/.elan/bin to its child PATH, so the toolchain
   resolves at call time with no dsh restart.
6. After a restart (a resumed session, or a compaction that dropped the
   tools), read `journal.md`: if an escalation is open (an `escalation open`
   line with no matching `escalation closed`), call `rq_escalate` again for
   every agent that still needs the lane.
7. Never block the method work on the lane: while any install runs, fall back
   to Lane 2 (isolated proof teammate) and record in the audit what was
   installed and that it succeeded.

A blind role (OffGridThinker, DoubleChecker) may receive the lane, but only
to CHECK a derivation it has already made — never to find or search for a
known result. Its persona states the same rule.

Caveats: jacobian is pre-stable; its catalog decides what it can check — read
the catalog (math.find / `operation://catalog`) before claiming coverage. The
installed Lean lane exposes `lean.statement.propose`,
`lean.statement.compare`, and `lean.proof_state.inspect` (core Lean, no
Mathlib); the full machine-check lane is `lean.check`, which additionally needs
the pinned Mathlib runtime (elan toolchain + lake build — provisioned by
scripts/provision-lean.sh). See mcp/jacobian.md for details.

## Lane 2 — isolated proof teammate (full Jin protocol)

When jacobian lacks the operation: create ONE fresh `doublechecker-<n>` with the
Jin prompt (protocol.md), isolated (no web/context). Do **not** assume an
affirmative result exists — ask it to return either a complete derivation of
the claim or a concrete counterexample / its exact gap. The claim is settled
only when the result survives the adversary (concrete outputs, no "routine").

## Lane 3 — Lean (manual external lane; only for proof-critical claims)

Jin's own gate: Lean 4 + pinned Mathlib, `lake build` + axiom audit, trust
boundary `propext`/`Classical.choice`/`Quot.sound` only, no `sorry`/`admit`.
Use only when a fully machine-checked proof is genuinely required (e.g. a novel
analytical result you will publish or build a product on). Cost is high; do not
default to it.

Two honesty notes. First, the framework ships **no in-repo Lean source or
lakefile**, so this lane is a manual external procedure, not a bundled,
automated capability. Second, the **axiom audit is a prose review procedure**:
no script in this framework checks `#print axioms` or rejects `sorry`/`admit`
for you — treat any Lean result as evidence only if the axiom audit was
performed and recorded. Jacobian's `lean.check` lane is the lower-friction
entry point; the provisioning script (scripts/provision-lean.sh) supplies the
pinned Mathlib runtime after approval (see Lane 1 step 5).
