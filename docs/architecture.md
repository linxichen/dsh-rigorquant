# RigorQuant architecture — the grilled decision record

## Sources studied

- **Shanmu Jin's Crouzeix run** (2026-07-30): full prompt at
  https://github.com/jinshanmu/CrouzeixConjecture/blob/main/crouzeix_conjecture_prompt.txt
  — epistemic isolation, diverse multiagent portfolio with an approach-family
  registry, adversarial counterexample-only audit, concrete-output discipline,
  persistence, terminal honesty. Verification gate: Lean 4 + pinned Mathlib,
  axiom audit (trust boundary `propext`/`Classical.choice`/`Quot.sound`, no
  `sorry`/`admit`), manuscript pinned by SHA-256 and mapped line-by-line to
  Lean declarations.
- **Terence Tao**: Blueprint + Lean formalization (PFR); the Equational
  Theories project (SAT solvers + Vampire/EProver grinding edges, humans/AI on
  the interesting nodes); frontier models as proposal generators on Erdős
  problems, humans verifying.

## Decisions (grilled with the user)

1. **Deliverable** — a framework (preset + skill + compute lanes) enabling any
   model to run long, difficult mathematical tasks unattended; problems are
   empirical/computational (econ/finance/portfolio/simulation), not abstract
   proof.
2. **Rigor gate** — hybrid: falsification by default; escalation to exact/
   formal verification when correctness hinges on an unproven claim.
3. **Check battery** — (A) closed-form equality, (B) exact invariants,
   (C) analytic bounds, (D) staged statistical hardening; on simplified/special
   cases BEFORE numerical implementation.
4. **Trust** — two walled tracks (method open / ground-truth re-derived twice
   by different means) + adversarial audit; counterexample-only elimination;
   "a producer cannot certify its own output".
5. **Compute substrate** — pinned uv Python lane (sympy/mpmath/cvxpy/hypothesis/
   jax) as default; **jacobian MCP as the independent escalation verifier** —
   dual verification, jacobian kept as escalation only.
6. **Stochastic convention** — fixed seed + LLN: sampling error against the
   analytic mean must shrink (≈ C/√N) as N grows; bit-identical seeded replay.
7. **Isolation** — track-split: method track open (existing results allowed),
   ground-truth track re-derives; orchestrator-detected novelty toggle flips
   the method track to full Jin isolation.
8. **Multi-agent mechanism** — DSH-native: `subagent` (blank context; never
   `subagent_fork` for track work) + `workflow` fan-out with JSON schemas +
   goal-round driver; registry/journal files are the cross-round memory.
9. **Model routing** — one model everywhere (user's choice); reasoning-effort
   knob available per role; independence comes from context separation.
10. **Lifecycle** — PASS → auto-implement + proceed; BLOCKED → same exact gap
    3 consecutive rounds → deliver strongest derivation + exact gap; BUDGET →
    5 orchestrator rounds → checkpoint + report (no cost ceiling yet).
11. **Publishing** — repo distributes a bundle (package.json
    `dsh.bundle.patch` + cordis.patch.yml registering the skill), an agent
    preset + bundled skill (install.sh), MIT, `dsh-plugin` GitHub topic —
    compliant with the awesome-list `dsh plugin add` convention.

## Repo map

```
agent-presets/rigorquant/   the preset: composition + persona + rigorquant skill
env/                        pinned uv compute lane (pyproject + lockfile)
mcp/jacobian.md             escalation lane wiring
docs/architecture.md        this record
install.sh                  installs the preset (or --skill-only) into $DSH_HOME
```
