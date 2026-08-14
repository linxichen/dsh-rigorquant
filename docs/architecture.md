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
   model to run long, difficult mathematical tasks **unattended within a single
   live session**; problems are empirical/computational
   (econ/finance/portfolio/simulation), not abstract proof. Crossing a session
   boundary disarms the goal and needs one human turn to re-arm (decision 10).
2. **Rigor gate** — hybrid: falsification by default; escalation to exact/
   formal verification when correctness hinges on an unproven claim.
3. **Check battery** — (A) closed-form equality, (B) exact invariants,
   (C) analytic bounds, (D) staged statistical hardening; on simplified/special
   cases BEFORE numerical implementation. The battery is a **reference-case
   sanity gate**, not a general-validity proof; general validity is established
   in explicit stages (see the skill's references/lifecycle.md).
4. **Trust** — two tracks (method open / ground-truth re-derived twice by
   different means) + adversarial audit; counterexample-only elimination; "a
   producer cannot certify its own output". Context isolation between the root
   and its subagents is harness-enforced; web access, filesystem scope, and
   recursion are **procedural** (per-role delegation tools), not a "wall".
5. **Compute substrate** — pinned uv Python lane (sympy/mpmath/cvxpy/hypothesis/
   jax) as default; **jacobian MCP as the independent escalation verifier** —
   dual verification, jacobian kept as escalation only. The `mcp-jacobian` row
   ships **disabled** and the command **pinned** (`jacobian@0.12.0`) so nothing
   runs at mount time; provisioning is approval-gated.
6. **Stochastic convention** — fixed seed + LLN: sampling error against the
   analytic mean must shrink (≈ C/√N) as N grows. Seeded, environment-pinned
   replay — not portable bit-identity.
7. **Isolation** — track-split: method track open (existing results allowed),
   ground-truth track re-derives; orchestrator-detected novelty toggle flips
   the method track to full Jin isolation (no web, no prior context, no local
   files). These are procedural separations; only context isolation is
   harness-enforced.
8. **Multi-agent mechanism** — DSH-native: per-role delegation tools
   (`subagent` explorer, `subagent_ground_truth` oracle with `web_search`
   denied, `subagent_adversary`; each `maxDepth: 0`) + `workflow` fan-out with
   JSON schemas + goal-round driver; registry/journal files are the cross-round
   memory. `subagent_fork` is not used for track work.
9. **Model routing** — one model everywhere (user's choice); reasoning-effort
   knob available per role; independence comes from context separation.
10. **Lifecycle** — PASS → auto-implement under branch/worktree + frozen write
    scope + rollback, then proceed; BLOCKED → same exact gap 3 consecutive
    rounds → deliver strongest derivation + exact gap; UNKNOWN → recorded when
    neither proof nor counterexample lands; BUDGET → 5 orchestrator rounds →
    checkpoint + report. One task-level goal (no per-sub-problem goals); budget
    fields (`max_cost_usd`, `max_wall_minutes`) may be set. Resuming across a
    session needs one human turn.
11. **Publishing** — repo distributes a bundle (package.json
    `dsh.bundle.patch` + cordis.patch.yml registering the skill), an agent
    preset + bundled skill (install.sh), MIT, `dsh-plugin` GitHub topic —
    compliant with the awesome-list `dsh plugin add` convention. The npm bundle
    ships `env/` and `mcp/`; `install.sh` anchors the compute lane at
    `$DSH_HOME/share/rigorquant`.
12. **Workspace** — a **study** is the self-contained work unit: one
    rigorquant task in one directory with an identical internal structure
    everywhere. Two modes, implied by location, no config flag: **Mode A —
    one study per repo** (`study.json` at repo root) and **Mode B — multiple
    studies per repo** (`studies/<slug>/study.json`, roster derived from
    `studies/*/study.json`). Durable deliverables (study.json, STUDY.md,
    registry.json, journal, derivations/, audits/, artifacts/) are committed;
    ALL scratch lives in `interim/` (explorer-reports, gt-scripts, tmp),
    gitignored via a study-local `.gitignore`. Intake resolves the study root
    by detection first (bounded at the git root, rejecting symlinks) and asks
    the user at most ONE question (mode + slug) when creating a study — resumed
    studies ask nothing, keeping runs unattended within the session. Supersedes
    the legacy hidden `.rigorquant/` layout, which conflated deliverables with
    scratch and could not hold multiple studies.

## Review amendments

The four-pass repository review ([docs/repository-review.md](repository-review.md))
recorded accepted verdicts that amend decisions 1 (unattended scope), 3/6
(sanity gate + statistical criteria), 4/7/8 (isolation language + per-role
tools), 5 (opt-in, pinned jacobian), 10 (one goal, auto-implement safety), and
11/12 (bundle contents + workspace). Those verdicts are the source of truth for
the wording above; the checker CLI and JSON Schemas they require live under
`schemas/` and `scripts/` (see the skill's lifecycle.md).

## Repo map

```
agent-presets/rigorquant/   the preset: composition + persona + rigorquant skill
env/                        pinned uv compute lane (pyproject + lockfile)
mcp/jacobian.md             escalation lane wiring
docs/architecture.md        this record
studies/                    one study folder per task (Mode B layout; interim/
                            inside each is gitignored, everything else commits)
install.sh                  installs the preset (or --skill-only) into $DSH_HOME
```
