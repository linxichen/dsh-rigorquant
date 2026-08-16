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
   denied, `subagent_adversary`; each `maxDepth: 1`, which permits exactly one
   level of delegation — a child is always at depth ≥ 1, so `maxDepth: 0` would
   block delegation entirely) + `workflow` fan-out with
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
the wording above; the checker CLI and JSON Schemas they require ship inside the
skill, at `skills/rigorquant/scripts/` and `skills/rigorquant/schemas/`.

## Decision 13 — the checker is the honesty boundary

A later review demonstrated that a study with an empty `derivations/`, empty
stage `outputs`, a one-line adversary report and a paper reading "This paper
says nothing" was certified `PASS -- complete evidence`. Three rules follow, and
they bind every future change to the checker:

1. **A study may not vouch for itself.** Every evidence check reads
   `audits/`, `derivations/`, `artifacts/` — never `study.json`. A declaration
   states what was promised; only the record states what was done.
2. **Parse, never grep.** Registry state is read as JSON and traversed;
   `"passed"` appearing somewhere in the file is not a passed route.
3. **One validator, one schema, both tested.** A second copy of either is how
   the two silently diverged into different programs. `tests/` enforces this,
   and the schemas are what the validator actually loads.

## Decision 14 — literature lane

A new literature-research lane answers "what is settled / impossible / open /
current" before compute is spent, and a membrane exports ONLY verified negatives
(proven impossibilities) to the novel lane so it stays un-anchored. The lane is
a grad-student-style citation-graph traversal (backward references + forward
citations + related work + surveys), walled per line, with an independent
literature adversary that re-retrieves each load-bearing claim and certifies
validity + freshness (version/venue/retraction/supersession). Tooling is two
vendored skills (arxiv, MIT; academic-paper-search, user-pinned SKILL.md — MIT,
author-confirmed, see docs/literature-lane.md §14) plus a tiered
retriever (author page → open repos/Unpaywall → preprint → OpenAlex/CORE →
user-supplied mirrors, disabled by default). Thoroughness outranks speed (10+ hr
runs welcome); the completeness gate — not the budget ceiling — is the finish
line. Full spec, schemas, role matrix, and acceptance criteria:
[docs/literature-lane.md](literature-lane.md).

What is **enforced**, and where: the blind deny lists live in the composition
(`tests/test_blind_deny_list.py`); the known-mark, routed-away-impossible +
math-lane escalation, negative-export subset, completeness-checklist,
refs-seed and fabricated-citation gates live in `rq_check.py`
(`tests/test_literature_gate.py`, `tests/test_integration.py`). What stays
**procedural and audited**: `bash`-level network calls from a blind role and
cross-lane filesystem reads — no per-role network or fs scope exists in the
spawn provider, so those are named holes (literature-lane.md §13), not a wall.
The lane's own boundary to the outside world (arXiv, Semantic Scholar,
Crossref) is a live network dependency; `tests/test_retrieval_boundary.py`
marks it unverified rather than reporting "not run" as "passed".

## Decision 15 — the retrieval skills install globally

`arxiv` (MIT, vendored verbatim from NousResearch/hermes-agent) and
`academic-paper-search` (user-authored SKILL.md, MIT, author-confirmed
2026-08-16) are useful to any preset, not just this one, and
the literature roles load them by name. `install.sh` therefore copies both to
`$DSH_HOME/skills/` in both install modes and removes them on `--uninstall`,
while the preset keeps its own copies under
`agent-presets/rigorquant/skills/` so a checkout is self-contained. The blind
roles deny `skill` outright, so a global install never widens what the novel
lane can reach.

## Repo map

```
agent-presets/rigorquant/   the preset: composition + persona + rigorquant skill
  skills/rigorquant/        SKILL.md, references/, scripts/rq_check.py, schemas/
env/                        pinned uv compute lane (pyproject + lockfile)
mcp/jacobian.md             escalation lane wiring
docs/architecture.md        this record
docs/literature-lane.md     literature-lane spec (Decisions 14-15)
tests/                      the validator's suite; a forged study must FAIL
install.sh                  installs the preset (or --skill-only) into $DSH_HOME
```

A study folder (`studies/<slug>/` in Mode B, the repo root in Mode A) lives in
the *research* repo, not here: `interim/` inside each is gitignored, everything
else commits.
